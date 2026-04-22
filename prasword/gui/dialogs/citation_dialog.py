"""
prasword.gui.dialogs.citation_dialog
======================================
Browse, search, and insert in-text bibliography citations.

Features
--------
* Search bar filters by author, title, year, journal, and cite-key.
* Left panel: filterable list of all bibliography entries.
* Right panel: full formatted entry + all raw BibTeX fields.
* Citation style selector: APA / MLA / Chicago / IEEE.
* Double-click or "Insert" inserts the formatted in-text citation.
* "Copy key" copies the bare cite-key ([citekey]) to the clipboard.
* If no .bib entries exist a helpful "Import BibTeX" prompt is shown.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QClipboard, QColor
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSplitter,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from prasword.core.document import Document

from prasword.features.academic.bibtex_manager import BibTeXManager
from prasword.utils.logger import get_logger

log = get_logger(__name__)

# Colour for "no entries" prompt text
_MUTED = "#6c7086"


class CitationDialog(QDialog):
    """
    Citation browser and insertion dialog.

    Parameters
    ----------
    document : Document
        The document whose bib_entries will be searched.
    editor : EditorWidget | None
        If provided, the "Insert Citation" button inserts into the editor.
        If None, the dialog can still be used to copy cite-keys.
    parent : QWidget | None
    """

    def __init__(
        self,
        document: "Document",
        editor=None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._document = document
        self._editor   = editor
        self.setWindowTitle("Insert Citation")
        self.setMinimumSize(680, 480)
        self.resize(760, 520)
        self._build_ui()
        self._populate_list()

    # ------------------------------------------------------------------ #
    # UI                                                                   #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── Top toolbar ───────────────────────────────────────────────
        toolbar = QHBoxLayout()

        toolbar.addWidget(QLabel("Search:"))
        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("Author, title, year, cite-key…")
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._on_search)
        toolbar.addWidget(self._search_edit, 1)

        toolbar.addWidget(QLabel("  Style:"))
        self._style_combo = QComboBox()
        self._style_combo.addItems(["APA", "MLA", "Chicago", "IEEE"])
        self._style_combo.setMinimumWidth(100)
        self._style_combo.currentTextChanged.connect(self._on_style_changed)
        toolbar.addWidget(self._style_combo)

        root.addLayout(toolbar)

        # ── Result count ─────────────────────────────────────────────
        self._count_label = QLabel("0 entries")
        self._count_label.setStyleSheet(f"color: {_MUTED}; font-size: 9pt;")
        root.addWidget(self._count_label)

        # ── Main splitter: list | detail ──────────────────────────────
        splitter = QSplitter(Qt.Horizontal)

        self._entry_list = QListWidget()
        self._entry_list.setMinimumWidth(240)
        self._entry_list.currentItemChanged.connect(self._on_selection_changed)
        self._entry_list.itemDoubleClicked.connect(lambda _: self._insert())
        splitter.addWidget(self._entry_list)

        self._detail_browser = QTextBrowser()
        self._detail_browser.setOpenExternalLinks(True)
        self._detail_browser.setMinimumWidth(280)
        splitter.addWidget(self._detail_browser)

        splitter.setSizes([280, 400])
        root.addWidget(splitter, 1)

        # ── Button row ────────────────────────────────────────────────
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        root.addWidget(sep)

        btn_row = QHBoxLayout()
        self._btn_copy_key = QPushButton("Copy Cite-key")
        self._btn_copy_key.setToolTip("Copy [citekey] to clipboard")
        self._btn_copy_key.clicked.connect(self._copy_key)
        btn_row.addWidget(self._btn_copy_key)

        btn_row.addStretch()

        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)

        self._btn_insert = QPushButton("Insert Citation")
        self._btn_insert.setDefault(True)
        self._btn_insert.setEnabled(False)
        self._btn_insert.clicked.connect(self._insert)
        btn_row.addWidget(self._btn_insert)

        root.addLayout(btn_row)

    # ------------------------------------------------------------------ #
    # Populate / filter                                                    #
    # ------------------------------------------------------------------ #

    def _populate_list(self, entries: dict | None = None) -> None:
        self._entry_list.clear()
        source = entries if entries is not None else self._document.bib_entries

        if not source:
            item = QListWidgetItem(
                "No bibliography entries found.\n"
                "Use Tools → Import BibTeX… to load a .bib file."
            )
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable)
            item.setForeground(QColor(_MUTED))
            self._entry_list.addItem(item)
            self._count_label.setText("0 entries")
            self._btn_insert.setEnabled(False)
            return

        self._count_label.setText(f"{len(source)} entr{'y' if len(source)==1 else 'ies'}")

        # Sort by year desc, then author
        def _sort_key(kv):
            fields = kv[1]
            year = fields.get("year", "0000").strip("{}")
            author = fields.get("author", "").strip("{}").split(",")[0]
            return (-int(year) if year.isdigit() else 0, author)

        for citekey, fields in sorted(source.items(), key=_sort_key):
            raw_author = fields.get("author", "Unknown").strip("{}")
            first_author = raw_author.split(" and ")[0].strip()
            last_name = (
                first_author.split(",")[0].strip()
                if "," in first_author
                else (first_author.split()[-1] if first_author.split() else first_author)
            )
            year  = fields.get("year",  "n.d.").strip("{}")
            title = fields.get("title", citekey).strip("{}")
            title_short = title[:52] + "…" if len(title) > 55 else title
            etype = fields.get("ENTRYTYPE", fields.get("entrytype", "")).upper()

            label = f"{last_name} ({year})\n  {title_short}"
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, citekey)
            item.setToolTip(f"[{citekey}]" + (f"  {etype}" if etype else ""))
            self._entry_list.addItem(item)

    # ------------------------------------------------------------------ #
    # Slots                                                                #
    # ------------------------------------------------------------------ #

    @Slot(str)
    def _on_search(self, query: str) -> None:
        if not query.strip():
            self._populate_list()
        else:
            results = BibTeXManager.search(self._document, query)
            self._populate_list(results)

    @Slot(str)
    def _on_style_changed(self, _: str) -> None:
        # Refresh detail panel if something is selected
        item = self._entry_list.currentItem()
        if item:
            self._on_selection_changed(item, None)

    @Slot(QListWidgetItem, QListWidgetItem)
    def _on_selection_changed(self, current: QListWidgetItem, _) -> None:
        if current is None:
            self._detail_browser.clear()
            self._btn_insert.setEnabled(False)
            return
        citekey = current.data(Qt.UserRole)
        if not citekey:
            self._btn_insert.setEnabled(False)
            return

        self._btn_insert.setEnabled(True)
        entry = self._document.bib_entries.get(citekey, {})
        style = self._style_combo.currentText().lower()
        formatted = BibTeXManager.format_entry(entry, style)

        # Build HTML detail view
        etype = entry.get("ENTRYTYPE", entry.get("entrytype", "")).upper()
        raw_fields = {k: v for k, v in entry.items()
                      if k not in ("ENTRYTYPE", "entrytype", "ID")}
        field_rows = "".join(
            f"<tr><td style='color:#a6adc8;padding-right:12px'><b>{k}</b></td>"
            f"<td style='color:#cdd6f4'>{v}</td></tr>"
            for k, v in sorted(raw_fields.items())
        )
        html = (
            f"<p style='color:#89b4fa;font-size:11pt'><b>[{citekey}]</b>"
            + (f" &nbsp;<span style='color:#6c7086;font-size:9pt'>{etype}</span>" if etype else "")
            + "</p>"
            f"<p style='color:#cdd6f4'>{formatted}</p>"
            f"<hr style='border-color:#45475a'/>"
            f"<table style='font-size:9pt'>{field_rows}</table>"
        )
        self._detail_browser.setHtml(html)

    @Slot()
    def _copy_key(self) -> None:
        item = self._entry_list.currentItem()
        if item:
            citekey = item.data(Qt.UserRole)
            if citekey:
                QApplication.clipboard().setText(f"[{citekey}]")
                log.debug("Copied cite-key: %s", citekey)

    @Slot()
    def _insert(self) -> None:
        item = self._entry_list.currentItem()
        if not item:
            return
        citekey = item.data(Qt.UserRole)
        if not citekey:
            return

        if self._editor:
            style = self._style_combo.currentText().lower()
            try:
                from prasword.features.academic.citation_engine import CitationEngine
                CitationEngine.insert_citation(
                    self._editor, self._document, citekey, style
                )
                log.info("Citation inserted: [%s] style=%s", citekey, style)
            except Exception as exc:
                log.warning("Citation insert failed: %s", exc)
        else:
            # No editor — just copy key
            QApplication.clipboard().setText(f"[{citekey}]")

        self.accept()
