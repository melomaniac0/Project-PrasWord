"""
prasword.core.document_manager
================================
Central controller for all open documents.

``DocumentManager`` is the single source of truth for the collection of
documents the user currently has open.  It is intentionally GUI-agnostic:
the tabbed interface, file-tree panel, and menu actions all route through
this class rather than manipulating documents directly.

Responsibilities
----------------
* Create new blank documents.
* Load documents from disk (delegates IO to the FileIO utility).
* Save / Save-As (delegates IO to FileIO).
* Track the *active* document (the one currently visible in the editor).
* Emit signals when the set of open documents changes so the GUI can
  rebuild its tab bar etc. without polling.
* Enforce "unsaved changes" prompts via signals — the GUI layer is
  responsible for showing the actual dialog.

Design decisions
----------------
* Documents are keyed by their stable ``document.id`` (UUID string) so
  that renaming / path changes do not break internal references.
* The manager never imports GUI classes — all communication with the GUI
  layer is done through Qt signals.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal

from prasword.core.document import Document, DocumentState
from prasword.utils.logger import get_logger

log = get_logger(__name__)

# Incremented for every "Untitled N" document created in this session.
_untitled_counter: int = 0


def _next_untitled_title() -> str:
    global _untitled_counter
    _untitled_counter += 1
    return f"Untitled {_untitled_counter}" if _untitled_counter > 1 else "Untitled"


# ---------------------------------------------------------------------------
# DocumentManager
# ---------------------------------------------------------------------------

class DocumentManager(QObject):
    """
    Central controller for the set of open documents.

    Signals
    -------
    document_opened(Document)
        Emitted after a document is successfully added to the manager.
    document_closed(str)
        Emitted with the ``document.id`` of a document that has been removed.
    active_document_changed(Document | None)
        Emitted when the user switches tabs / the active document changes.
    document_saved(Document)
        Emitted after a successful save.
    unsaved_changes_detected(Document)
        Emitted when a close/quit is attempted and the document has unsaved
        changes.  The GUI layer should connect a slot that shows a dialog
        and then calls ``force_close`` or cancels the operation.

    Parameters
    ----------
    parent : QObject | None
        Qt parent for memory management.
    """

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------
    document_opened = Signal(object)          # Document
    document_closed = Signal(str)             # document.id
    active_document_changed = Signal(object)  # Document | None
    document_saved = Signal(object)           # Document
    unsaved_changes_detected = Signal(object) # Document

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        # Ordered list preserves tab order.
        self._documents: list[Document] = []
        # Fast lookup: id → Document.
        self._index: dict[str, Document] = {}
        # Currently active document (may be None if no documents are open).
        self._active: Optional[Document] = None

        log.debug("DocumentManager initialised.")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def documents(self) -> list[Document]:
        """Ordered list of all open documents (defensive copy)."""
        return list(self._documents)

    @property
    def active_document(self) -> Optional[Document]:
        """The document currently shown in the editor, or ``None``."""
        return self._active

    @property
    def document_count(self) -> int:
        """Number of currently open documents."""
        return len(self._documents)

    def get_by_id(self, doc_id: str) -> Optional[Document]:
        """Look up a document by its stable UUID string."""
        return self._index.get(doc_id)

    def get_by_path(self, path: Path) -> Optional[Document]:
        """
        Return the first open document whose ``file_path`` matches *path*,
        or ``None`` if not found.  Useful to avoid opening the same file twice.
        """
        resolved = path.resolve()
        for doc in self._documents:
            if doc.file_path and doc.file_path.resolve() == resolved:
                return doc
        return None

    def has_modified_documents(self) -> bool:
        """``True`` if any open document has unsaved changes."""
        return any(d.is_modified or d.is_new for d in self._documents)

    # ------------------------------------------------------------------
    # Document lifecycle
    # ------------------------------------------------------------------

    def new_document(self) -> Document:
        """
        Create a new, blank, unsaved document and make it active.

        Returns
        -------
        Document
            The newly created document.
        """
        doc = Document(file_path=None, parent=self)
        # Override the generic "Untitled" title with a session counter.
        doc._title = _next_untitled_title()  # noqa: SLF001
        self._register(doc)
        self.set_active(doc)
        log.info("New document created: %s", doc.title)
        return doc

    def open_document(self, path: Path) -> Document:
        """
        Open a document from *path*.

        If the file is already open, the existing document is activated and
        returned without opening it a second time.

        Parameters
        ----------
        path : Path
            Absolute (or relative — will be resolved) path to the file.

        Returns
        -------
        Document
            The opened (or already-open) document.

        Raises
        ------
        FileNotFoundError
            If *path* does not exist on disk.
        ValueError
            If the file format is unsupported.
        """
        path = Path(path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        # Guard against double-opening.
        existing = self.get_by_path(path)
        if existing is not None:
            log.info("Document already open, activating: %s", path)
            self.set_active(existing)
            return existing

        doc = Document(file_path=path, parent=self)
        self._load_file(doc, path)
        self._register(doc)
        self.set_active(doc)
        log.info("Opened document: %s", path)
        return doc

    def save_document(self, doc: Document, path: Optional[Path] = None) -> bool:
        """
        Persist *doc* to disk.

        Parameters
        ----------
        doc : Document
            The document to save.
        path : Path | None
            If given, performs a Save-As to *path*.  Otherwise saves to
            ``doc.file_path`` (which must be set).

        Returns
        -------
        bool
            ``True`` on success, ``False`` on failure (error already logged).

        Raises
        ------
        ValueError
            If neither *path* nor ``doc.file_path`` is set.
        """
        target = path or doc.file_path
        if target is None:
            raise ValueError(
                "Cannot save: no file path provided and document has not been "
                "saved before.  Use Save As to choose a location."
            )
        target = Path(target).resolve()

        try:
            self._write_file(doc, target)
            doc.mark_saved(target)
            self.document_saved.emit(doc)
            log.info("Document saved: %s", target)
            return True
        except Exception:
            log.exception("Failed to save document to %s", target)
            return False

    def close_document(self, doc: Document, *, force: bool = False) -> bool:
        """
        Remove *doc* from the manager.

        If the document has unsaved changes and *force* is ``False``, emits
        ``unsaved_changes_detected`` and returns ``False`` without closing.
        The GUI layer is then responsible for showing a save/discard/cancel
        dialog and calling ``close_document(doc, force=True)`` if appropriate.

        Parameters
        ----------
        doc : Document
            The document to close.
        force : bool
            If ``True``, bypass the unsaved-changes guard.

        Returns
        -------
        bool
            ``True`` if the document was closed, ``False`` if aborted.
        """
        if not force and (doc.is_modified or doc.is_new and doc.word_count() > 0):
            log.debug(
                "Document %s has unsaved changes; emitting signal.", doc.id
            )
            self.unsaved_changes_detected.emit(doc)
            return False

        doc_id = doc.id
        self._documents.remove(doc)
        del self._index[doc_id]

        # Pick a new active document.
        if self._active is doc:
            self._active = self._documents[-1] if self._documents else None
            self.active_document_changed.emit(self._active)

        self.document_closed.emit(doc_id)
        doc.setParent(None)  # Release Qt ownership.
        log.info("Document closed: %s", doc_id)
        return True

    def force_close(self, doc: Document) -> bool:
        """Unconditionally close *doc* (used after a save/discard dialog)."""
        return self.close_document(doc, force=True)

    # ------------------------------------------------------------------
    # Active-document management
    # ------------------------------------------------------------------

    def set_active(self, doc: Document) -> None:
        """
        Make *doc* the active document.

        Parameters
        ----------
        doc : Document
            Must already be registered with this manager.
        """
        if doc is self._active:
            return
        if doc.id not in self._index:
            raise ValueError(
                f"Document {doc.id!r} is not managed by this DocumentManager."
            )
        self._active = doc
        self.active_document_changed.emit(doc)
        log.debug("Active document → %s", doc.title)

    # ------------------------------------------------------------------
    # Application-quit helpers
    # ------------------------------------------------------------------

    def request_quit(self) -> bool:
        """
        Check whether all documents can be closed cleanly.

        Emits ``unsaved_changes_detected`` for each document with unsaved
        changes and returns ``False`` so the caller knows it must wait for
        user confirmation before quitting.

        Returns ``True`` only if all documents are clean and quitting is safe.
        """
        dirty = [
            d for d in self._documents
            if d.is_modified or (d.is_new and d.word_count() > 0)
        ]
        if dirty:
            for doc in dirty:
                self.unsaved_changes_detected.emit(doc)
            return False
        return True

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _register(self, doc: Document) -> None:
        """Add *doc* to internal collections and emit ``document_opened``."""
        self._documents.append(doc)
        self._index[doc.id] = doc
        self.document_opened.emit(doc)

    def _load_file(self, doc: Document, path: Path) -> None:
        """
        Delegate file reading to the FileIO utility.

        The FileIO module is imported here (not at module level) to keep
        the core package free of heavy optional dependencies that may not
        be installed in every environment.
        """
        from prasword.features.filemanagement.file_io import FileIO  # lazy import
        FileIO.load(doc, path)

    def _write_file(self, doc: Document, path: Path) -> None:
        """Delegate file writing to the FileIO utility."""
        from prasword.features.filemanagement.file_io import FileIO  # lazy import
        FileIO.save(doc, path)

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"<DocumentManager "
            f"docs={self.document_count} "
            f"active={self._active!r}>"
        )
