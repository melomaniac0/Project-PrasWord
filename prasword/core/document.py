"""
prasword.core.document
======================
Data model for a single open document.

A ``Document`` is the authoritative in-memory representation of one file.
It owns:

* The ``QTextDocument`` that backs the editor widget.
* File-path metadata (``None`` for brand-new, unsaved documents).
* Dirty-state tracking (has the document been modified since last save?).
* Document-level metadata: title, author, word-count cache, bibliography
  entries, cross-references, etc.

The ``Document`` does *not* perform any GUI operations; it is a pure data /
logic object that the GUI layer observes via Qt signals.
"""

from __future__ import annotations

import uuid
from enum import Enum, auto
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QTextDocument

from prasword.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# DocumentState
# ---------------------------------------------------------------------------

class DocumentState(Enum):
    """
    Lifecycle state of a Document.

    NEW
        Created in-memory, never persisted to disk.
    CLEAN
        Loaded from disk (or just saved); no unsaved changes.
    MODIFIED
        Has unsaved changes relative to the last saved version.
    """

    NEW = auto()
    CLEAN = auto()
    MODIFIED = auto()


# ---------------------------------------------------------------------------
# Document
# ---------------------------------------------------------------------------

class Document(QObject):
    """
    In-memory representation of one open document.

    Signals
    -------
    state_changed(DocumentState)
        Emitted whenever the document transitions between NEW / CLEAN /
        MODIFIED states.
    title_changed(str)
        Emitted when the display title changes (e.g. after a Save As).
    metadata_changed()
        Emitted when any metadata field (author, keywords …) changes.

    Parameters
    ----------
    file_path : Path | None
        Absolute path to the file on disk, or ``None`` for a brand-new
        document that has not yet been saved.
    parent : QObject | None
        Qt parent for memory management.
    """

    # ------------------------------------------------------------------
    # Qt signals
    # ------------------------------------------------------------------
    state_changed = Signal(object)   # DocumentState
    title_changed = Signal(str)
    metadata_changed = Signal()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        file_path: Optional[Path] = None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)

        # Stable internal identifier — used as dict key in DocumentManager.
        self._id: str = str(uuid.uuid4())

        # Backing Qt document; the editor widget will share this object.
        self._qt_doc: QTextDocument = QTextDocument(self)
        self._qt_doc.setModified(False)

        # File-system location (may be None).
        self._file_path: Optional[Path] = file_path

        # Lifecycle state.
        self._state: DocumentState = (
            DocumentState.NEW if file_path is None else DocumentState.CLEAN
        )

        # Metadata.
        self._title: str = self._derive_title()
        self._author: str = ""
        self._keywords: list[str] = []

        # Academic / DS extras (populated by feature modules).
        self._bib_entries: dict[str, dict] = {}       # citekey → BibTeX fields
        self._cross_refs: dict[str, str] = {}         # label  → anchor id
        self._toc_entries: list[dict] = []            # [{level, title, anchor}]

        # Connect Qt's own modified signal so we keep our state in sync.
        self._qt_doc.modificationChanged.connect(self._on_qt_modification_changed)

        log.debug("Document created: id=%s path=%s", self._id, file_path)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        """Stable UUID-based identifier for this document."""
        return self._id

    @property
    def qt_document(self) -> QTextDocument:
        """
        The ``QTextDocument`` backing this document.

        The editor widget (``QTextEdit`` / ``QPlainTextEdit``) should call
        ``setDocument(doc.qt_document)`` to share this object.
        """
        return self._qt_doc

    @property
    def file_path(self) -> Optional[Path]:
        """Absolute path to the file on disk, or ``None``."""
        return self._file_path

    @file_path.setter
    def file_path(self, path: Optional[Path]) -> None:
        if path == self._file_path:
            return
        self._file_path = path
        self._title = self._derive_title()
        self.title_changed.emit(self._title)
        log.debug("Document %s: file_path → %s", self._id, path)

    @property
    def title(self) -> str:
        """
        Display title — the file stem if saved, or "Untitled" / "Untitled N".
        """
        return self._title

    @property
    def state(self) -> DocumentState:
        """Current lifecycle state."""
        return self._state

    @property
    def is_modified(self) -> bool:
        """``True`` if the document has unsaved changes."""
        return self._state is DocumentState.MODIFIED

    @property
    def is_new(self) -> bool:
        """``True`` if the document has never been saved to disk."""
        return self._state is DocumentState.NEW

    @property
    def author(self) -> str:
        return self._author

    @author.setter
    def author(self, value: str) -> None:
        self._author = value
        self.metadata_changed.emit()

    @property
    def keywords(self) -> list[str]:
        return list(self._keywords)

    @property
    def bib_entries(self) -> dict[str, dict]:
        """BibTeX entries keyed by cite-key."""
        return self._bib_entries

    @property
    def cross_refs(self) -> dict[str, str]:
        """Cross-reference map: label → anchor ID."""
        return self._cross_refs

    @property
    def toc_entries(self) -> list[dict]:
        """Ordered list of table-of-contents entries."""
        return self._toc_entries

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def mark_saved(self, path: Optional[Path] = None) -> None:
        """
        Transition the document to CLEAN state after a successful save.

        Parameters
        ----------
        path : Path | None
            If provided, updates ``file_path`` (used by Save As).
        """
        if path is not None:
            self.file_path = path
        self._qt_doc.setModified(False)
        self._set_state(DocumentState.CLEAN)
        log.debug("Document %s marked as saved.", self._id)

    def mark_modified(self) -> None:
        """
        Programmatically mark the document as modified.

        Usually triggered automatically by Qt's modificationChanged signal,
        but feature modules (e.g. bibliography import) may call this directly.
        """
        new_state = (
            DocumentState.NEW if self._file_path is None else DocumentState.MODIFIED
        )
        self._qt_doc.setModified(True)
        self._set_state(new_state)

    # ------------------------------------------------------------------
    # Content helpers
    # ------------------------------------------------------------------

    def plain_text(self) -> str:
        """Return the document's plain-text content."""
        return self._qt_doc.toPlainText()

    def html(self) -> str:
        """Return the document's HTML representation."""
        return self._qt_doc.toHtml()

    def word_count(self) -> int:
        """
        Return an approximate word count.

        This is intentionally fast (split on whitespace) because it is called
        on every keystroke via the metrics module. For publication-accurate
        counts the MetricsEngine performs a more thorough analysis.
        """
        text = self._qt_doc.toPlainText().strip()
        return len(text.split()) if text else 0

    def character_count(self, include_spaces: bool = True) -> int:
        """Return the character count, optionally excluding spaces."""
        text = self._qt_doc.toPlainText()
        if not include_spaces:
            text = text.replace(" ", "")
        return len(text)

    # ------------------------------------------------------------------
    # Bibliography / cross-ref helpers (used by academic feature module)
    # ------------------------------------------------------------------

    def add_bib_entry(self, citekey: str, fields: dict) -> None:
        """Register a BibTeX entry."""
        self._bib_entries[citekey] = fields
        self.mark_modified()
        self.metadata_changed.emit()

    def remove_bib_entry(self, citekey: str) -> None:
        """Remove a BibTeX entry by cite-key."""
        self._bib_entries.pop(citekey, None)
        self.mark_modified()
        self.metadata_changed.emit()

    def set_toc_entries(self, entries: list[dict]) -> None:
        """Replace the TOC entry list (called by the layout feature module)."""
        self._toc_entries = entries
        self.metadata_changed.emit()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _derive_title(self) -> str:
        if self._file_path is None:
            return "Untitled"
        return self._file_path.stem

    def _set_state(self, new_state: DocumentState) -> None:
        if new_state == self._state:
            return
        old = self._state
        self._state = new_state
        log.debug(
            "Document %s: state %s → %s",
            self._id, old.name, new_state.name,
        )
        self.state_changed.emit(new_state)

    # ------------------------------------------------------------------
    # Qt signal handler
    # ------------------------------------------------------------------

    def _on_qt_modification_changed(self, modified: bool) -> None:
        """Sync our state whenever Qt's own modified flag changes."""
        if modified:
            self.mark_modified()
        # We do NOT auto-mark as clean here — that happens only after an
        # explicit save via mark_saved().

    # ------------------------------------------------------------------
    # Dunder helpers
    # ------------------------------------------------------------------

    def __repr__(self) -> str:
        return (
            f"<Document id={self._id[:8]} "
            f"title={self._title!r} "
            f"state={self._state.name}>"
        )
