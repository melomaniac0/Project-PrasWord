"""
prasword.gui.panels.sidebar_panel
==================================
Left sidebar dock containing three panels in a tab widget:

  📁 Files    — QFileSystemModel tree filtered to supported doc types.
                Double-click opens a file in the editor.
                Root can be changed to any directory; "⌂" jumps to home.
                Live filter bar narrows visible filenames.

  ≡ TOC       — Flat list of heading entries for the active document.
                Click scrolls the editor to that heading (via anchor).
                Refreshed automatically when the active document changes
                or its metadata_changed signal fires.

  📚 Refs     — Search-filtered list of BibTeX bibliography entries.
                Shows author, year, title; tooltip shows the cite-key.
                Refreshed alongside the TOC.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, QDir, QSortFilterProxyModel, Signal, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QTreeView,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from prasword.core.document_manager import DocumentManager
    from prasword.core.document import Document

from prasword.utils.logger import get_logger

log = get_logger(__name__)


# ── FileTreePanel ────────────────────────────────────────────────────────────

class FileTreePanel(QWidget):
    """
    Browsable file-system tree filtered to PrasWord-supported extensions.

    Signals
    -------
    file_activated(str)
        Emitted with the absolute path when the user double-clicks a file.
    """

    file_activated = Signal(str)

    _SUPPORTED = ["*.docx", "*.md", "*.markdown", "*.txt", "*.pdf", "*.bib"]

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._root_path = Path.home()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # ── Header row: current root label + home button ─────────────
        hdr = QHBoxLayout()
        self._root_label = QLabel()
        self._root_label.setStyleSheet("font-size: 8pt; color: #a6adc8;")
        self._root_label.setWordWrap(False)
        hdr.addWidget(self._root_label, 1)

        btn_home = QPushButton("⌂")
        btn_home.setFixedSize(24, 24)
        btn_home.setToolTip("Jump to home directory")
        btn_home.clicked.connect(lambda: self.set_root(Path.home()))
        hdr.addWidget(btn_home)

        btn_cwd = QPushButton(".")
        btn_cwd.setFixedSize(24, 24)
        btn_cwd.setToolTip("Jump to current working directory")
        btn_cwd.clicked.connect(lambda: self.set_root(Path.cwd()))
        hdr.addWidget(btn_cwd)

        layout.addLayout(hdr)

        # ── Filter bar ───────────────────────────────────────────────
        self._filter_edit = QLineEdit()
        self._filter_edit.setPlaceholderText("Filter filenames…")
        self._filter_edit.setClearButtonEnabled(True)
        self._filter_edit.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter_edit)

        # ── File system model ─────────────────────────────────────────
        from PySide6.QtWidgets import QFileSystemModel
        self._fs_model = QFileSystemModel(self)
        self._fs_model.setRootPath(str(self._root_path))
        self._fs_model.setNameFilters(self._SUPPORTED)
        self._fs_model.setNameFilterDisables(False)   # hide non-matching files

        # ── Tree view ─────────────────────────────────────────────────
        self._tree = QTreeView()
        self._tree.setModel(self._fs_model)
        self._tree.setRootIndex(self._fs_model.index(str(self._root_path)))
        self._tree.setHeaderHidden(True)
        self._tree.setAnimated(True)
        self._tree.setIndentation(14)
        self._tree.setSortingEnabled(True)
        self._tree.sortByColumn(0, Qt.AscendingOrder)
        self._tree.setSelectionMode(QAbstractItemView.SingleSelection)
        # Hide size / type / date columns
        for col in range(1, self._fs_model.columnCount()):
            self._tree.hideColumn(col)
        self._tree.doubleClicked.connect(self._on_activated)

        layout.addWidget(self._tree)
        self._update_root_label()

    # ------------------------------------------------------------------

    def set_root(self, path: Path) -> None:
        """Change the tree root to *path*."""
        path = path.resolve()
        self._root_path = path
        self._fs_model.setRootPath(str(path))
        self._tree.setRootIndex(self._fs_model.index(str(path)))
        self._update_root_label()
        log.debug("File tree root → %s", path)

    @Slot(str)
    def _apply_filter(self, text: str) -> None:
        if text.strip():
            self._fs_model.setNameFilters([f"*{text.strip()}*"])
        else:
            self._fs_model.setNameFilters(self._SUPPORTED)

    @Slot()
    def _on_activated(self, index) -> None:
        path = self._fs_model.filePath(index)
        if Path(path).is_file():
            self.file_activated.emit(path)
            log.debug("File activated: %s", path)

    def _update_root_label(self) -> None:
        # Show only the last two path components to keep the label short
        parts = self._root_path.parts
        short = str(Path(*parts[-2:])) if len(parts) >= 2 else str(self._root_path)
        self._root_label.setText(short)
        self._root_label.setToolTip(str(self._root_path))


# ── TocPanel ────────────────────────────────────────────────────────────────

class TocPanel(QWidget):
    """
    Table of Contents panel — lists headings from the active document.

    Clicking a heading item emits heading_clicked(anchor_id) so the main
    window can scroll the editor to the right position.
    """

    heading_clicked = Signal(str)   # anchor id

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        hdr = QLabel("Table of Contents")
        hdr.setStyleSheet("font-weight: 600; font-size: 9pt;")
        layout.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self._list = QListWidget()
        self._list.setSpacing(1)
        self._list.setAlternatingRowColors(True)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        self._empty_label = QLabel("No headings yet.\nUse Format → Heading to add one.")
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #6c7086; font-size: 9pt;")
        layout.addWidget(self._empty_label)

        self._empty_label.setVisible(True)
        self._list.setVisible(False)

    def update_entries(self, entries: list[dict]) -> None:
        """
        Rebuild the list from heading scan results.

        Parameters
        ----------
        entries : list[dict]
            Each dict: {"level": int, "text": str, "anchor": str}
        """
        self._list.clear()
        if not entries:
            self._empty_label.setVisible(True)
            self._list.setVisible(False)
            return

        self._empty_label.setVisible(False)
        self._list.setVisible(True)

        # Level colour map (H1 brightest, H6 most muted)
        colours = {
            1: "#89b4fa", 2: "#89b4fa",
            3: "#cba6f7", 4: "#cba6f7",
            5: "#a6adc8", 6: "#6c7086",
        }
        for entry in entries:
            level = entry["level"]
            indent = "  " * (level - 1)
            prefix = {1: "■", 2: "▪", 3: "▫", 4: "·", 5: "·", 6: "·"}.get(level, "·")
            item = QListWidgetItem(f"{indent}{prefix} {entry['text']}")
            item.setData(Qt.UserRole, entry["anchor"])
            colour = colours.get(level, "#a6adc8")
            item.setForeground(QColor(colour))
            fsize = max(7, 10 - level)
            font = item.font()
            font.setPointSize(fsize)
            if level <= 2:
                font.setBold(True)
            item.setFont(font)
            self._list.addItem(item)

    @Slot(QListWidgetItem)
    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        anchor = item.data(Qt.UserRole)
        if anchor:
            self.heading_clicked.emit(anchor)


# ── ReferencesPanel ─────────────────────────────────────────────────────────

class ReferencesPanel(QWidget):
    """
    Searchable bibliography references panel.

    Shows all BibTeX entries for the active document. Typing in the search
    bar filters by author, title, and year (case-insensitive).
    Clicking an entry selects it (future: copy cite-key to clipboard).
    """

    cite_key_selected = Signal(str)   # emitted on click → citekey

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._all_entries: dict[str, dict] = {}
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        hdr = QLabel("Bibliography")
        hdr.setStyleSheet("font-weight: 600; font-size: 9pt;")
        layout.addWidget(hdr)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search author, title, year…")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(self._on_filter)
        layout.addWidget(self._search)

        self._count_label = QLabel("0 entries")
        self._count_label.setStyleSheet("font-size: 8pt; color: #6c7086;")
        layout.addWidget(self._count_label)

        self._list = QListWidget()
        self._list.setSpacing(1)
        self._list.setAlternatingRowColors(True)
        self._list.itemClicked.connect(self._on_item_clicked)
        layout.addWidget(self._list)

        self._empty_label = QLabel(
            "No bibliography entries.\n"
            "Use Tools → Import BibTeX… to load a .bib file."
        )
        self._empty_label.setAlignment(Qt.AlignCenter)
        self._empty_label.setStyleSheet("color: #6c7086; font-size: 9pt;")
        layout.addWidget(self._empty_label)

    def update_entries(self, entries: dict[str, dict]) -> None:
        """
        Refresh the list from a bib_entries dict.

        Parameters
        ----------
        entries : dict[str, dict]
            Mapping citekey → BibTeX field dict.
        """
        self._all_entries = entries
        self._populate(entries)

    def _populate(self, entries: dict[str, dict]) -> None:
        self._list.clear()
        total = len(entries)
        self._count_label.setText(f"{total} entr{'y' if total == 1 else 'ies'}")

        if not entries:
            self._empty_label.setVisible(True)
            self._list.setVisible(False)
            return

        self._empty_label.setVisible(False)
        self._list.setVisible(True)

        for citekey, fields in sorted(entries.items(), key=lambda kv: kv[1].get("year", "")):
            # Derive a one-line summary
            raw_author = fields.get("author", "Unknown Author")
            # Take first author's last name only
            first_author = raw_author.split(" and ")[0].strip("{}")
            last_name = (
                first_author.split(",")[0].strip()
                if "," in first_author
                else first_author.split()[-1] if first_author.split() else first_author
            )
            year  = fields.get("year", "n.d.").strip("{}")
            title = fields.get("title", citekey).strip("{}")
            etype = fields.get("ENTRYTYPE", fields.get("entrytype", "")).strip().upper()

            # Truncate long titles
            title_short = title if len(title) <= 55 else title[:52] + "…"
            line = f"{last_name} ({year}) — {title_short}"

            item = QListWidgetItem(line)
            item.setData(Qt.UserRole, citekey)
            item.setToolTip(
                f"[{citekey}]"
                + (f"  [{etype}]" if etype else "")
                + f"\n{title}"
            )
            self._list.addItem(item)

    @Slot(str)
    def _on_filter(self, query: str) -> None:
        if not query.strip():
            self._populate(self._all_entries)
            return
        q = query.lower()
        filtered = {
            k: v for k, v in self._all_entries.items()
            if q in " ".join([
                v.get("author", ""),
                v.get("title", ""),
                v.get("year", ""),
                v.get("journal", ""),
                k,
            ]).lower()
        }
        self._populate(filtered)

    @Slot(QListWidgetItem)
    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        citekey = item.data(Qt.UserRole)
        if citekey:
            self.cite_key_selected.emit(citekey)


# ── SidebarPanel (composite) ─────────────────────────────────────────────────

class SidebarPanel(QWidget):
    """
    Composite sidebar panel combining FileTree, TOC, and References tabs.

    Connects to DocumentManager to refresh TOC and refs when the active
    document changes.

    Parameters
    ----------
    doc_manager : DocumentManager
    parent : QWidget | None
    """

    def __init__(self, doc_manager: "DocumentManager", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._doc_manager = doc_manager
        self._current_doc: Optional["Document"] = None
        self._build_ui()
        doc_manager.active_document_changed.connect(self._on_active_doc_changed)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._tabs = QTabWidget()
        self._tabs.setTabPosition(QTabWidget.North)
        self._tabs.setDocumentMode(True)

        self._file_panel = FileTreePanel()
        self._toc_panel  = TocPanel()
        self._refs_panel = ReferencesPanel()

        self._tabs.addTab(self._file_panel, "📁")
        self._tabs.addTab(self._toc_panel,  "≡")
        self._tabs.addTab(self._refs_panel, "📚")

        self._tabs.setTabToolTip(0, "File Browser")
        self._tabs.setTabToolTip(1, "Table of Contents")
        self._tabs.setTabToolTip(2, "Bibliography References")

        layout.addWidget(self._tabs)

    # ------------------------------------------------------------------
    # Document manager signal handlers
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_active_doc_changed(self, doc: Optional["Document"]) -> None:
        # Disconnect old document signals to avoid stale refreshes
        if self._current_doc is not None:
            try:
                self._current_doc.metadata_changed.disconnect(self._on_metadata_changed)
            except RuntimeError:
                pass   # already disconnected

        self._current_doc = doc
        if doc is None:
            self._toc_panel.update_entries([])
            self._refs_panel.update_entries({})
            return

        doc.metadata_changed.connect(self._on_metadata_changed)
        self._refresh()

    @Slot()
    def _on_metadata_changed(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        if self._current_doc is None:
            return
        self._toc_panel.update_entries(self._current_doc.toc_entries)
        self._refs_panel.update_entries(self._current_doc.bib_entries)

    # ------------------------------------------------------------------
    # Public helpers (called by MainWindow)
    # ------------------------------------------------------------------

    def show_file_panel(self) -> None:
        """Switch the active tab to the file browser."""
        self._tabs.setCurrentIndex(0)

    def show_toc_panel(self) -> None:
        """Switch the active tab to the TOC."""
        self._tabs.setCurrentIndex(1)

    def show_refs_panel(self) -> None:
        """Switch the active tab to the bibliography."""
        self._tabs.setCurrentIndex(2)
