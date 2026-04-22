"""
prasword.gui.dialogs.find_replace_dialog
=========================================
Non-modal Find & Replace dialog.

Features
--------
* Plain-text and regular expression search.
* Case-sensitive and whole-word toggles.
* Find Next / Find Previous with wrap-around.
* Replace current match / Replace All.
* Live match-count badge updated on every keystroke.
* All matches highlighted in the document (ExtraSelections).
* Keyboard shortcuts: Enter → Find Next, Shift+Enter → Find Prev.
* Remembers the last search term within the session.
"""

from __future__ import annotations

import re
from typing import Optional

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QColor, QKeySequence, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QShortcut,
    QWidget,
)
from PySide6.QtGui import QTextDocument

from prasword.utils.logger import get_logger

log = get_logger(__name__)

# Highlight colour for all background matches (non-active)
_MATCH_BG   = QColor("#f9e2af")
_MATCH_FG   = QColor("#1e1e2e")
# Active (current) match
_ACTIVE_BG  = QColor("#a6e3a1")
_ACTIVE_FG  = QColor("#1e1e2e")


class FindReplaceDialog(QDialog):
    """
    Non-modal Find & Replace dialog bound to a single EditorWidget.

    Parameters
    ----------
    editor : EditorWidget
        The editor to search in. The dialog keeps a reference but never
        takes ownership.
    parent : QWidget | None
    """

    def __init__(self, editor, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._editor = editor
        # Track all match positions for highlighting
        self._match_positions: list[tuple[int, int]] = []  # (start, end)
        self._current_match_idx: int = -1

        self.setWindowTitle("Find & Replace")
        self.setMinimumWidth(520)
        self.setWindowFlags(
            Qt.Dialog |
            Qt.WindowStaysOnTopHint |
            Qt.WindowCloseButtonHint
        )
        self._build_ui()
        self._connect_shortcuts()

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        grid = QGridLayout(self)
        grid.setSpacing(8)
        grid.setColumnStretch(1, 1)

        # ── Find row ─────────────────────────────────────────────────
        grid.addWidget(QLabel("Find:"), 0, 0, Qt.AlignRight)
        self._find_edit = QLineEdit()
        self._find_edit.setPlaceholderText("Search text or /regex/…")
        self._find_edit.setClearButtonEnabled(True)
        self._find_edit.textChanged.connect(self._on_find_text_changed)
        self._find_edit.returnPressed.connect(self._find_next)
        grid.addWidget(self._find_edit, 0, 1)

        self._count_label = QLabel("")
        self._count_label.setMinimumWidth(90)
        self._count_label.setStyleSheet("color: #a6adc8; font-size: 9pt;")
        grid.addWidget(self._count_label, 0, 2)

        # ── Replace row ───────────────────────────────────────────────
        grid.addWidget(QLabel("Replace:"), 1, 0, Qt.AlignRight)
        self._replace_edit = QLineEdit()
        self._replace_edit.setPlaceholderText("Replacement text…")
        self._replace_edit.setClearButtonEnabled(True)
        grid.addWidget(self._replace_edit, 1, 1)

        # ── Options row ───────────────────────────────────────────────
        opt_row = QHBoxLayout()
        self._chk_case  = QCheckBox("Match case")
        self._chk_word  = QCheckBox("Whole word")
        self._chk_regex = QCheckBox("Regex")
        self._chk_wrap  = QCheckBox("Wrap")
        self._chk_wrap.setChecked(True)
        for chk in (self._chk_case, self._chk_word, self._chk_regex, self._chk_wrap):
            chk.toggled.connect(self._on_options_changed)
            opt_row.addWidget(chk)
        opt_row.addStretch()
        grid.addLayout(opt_row, 2, 0, 1, 3)

        # ── Button row ────────────────────────────────────────────────
        btn_row = QHBoxLayout()

        self._btn_prev = QPushButton("◀ Prev")
        self._btn_prev.setToolTip("Find previous (Shift+Enter)")
        self._btn_prev.clicked.connect(self._find_prev)
        btn_row.addWidget(self._btn_prev)

        self._btn_next = QPushButton("Next ▶")
        self._btn_next.setDefault(True)
        self._btn_next.setToolTip("Find next (Enter)")
        self._btn_next.clicked.connect(self._find_next)
        btn_row.addWidget(self._btn_next)

        btn_row.addStretch()

        self._btn_replace = QPushButton("Replace")
        self._btn_replace.setToolTip("Replace this match and find next")
        self._btn_replace.clicked.connect(self._replace_one)
        btn_row.addWidget(self._btn_replace)

        self._btn_replace_all = QPushButton("Replace All")
        self._btn_replace_all.clicked.connect(self._replace_all)
        btn_row.addWidget(self._btn_replace_all)

        btn_row.addStretch()

        self._btn_close = QPushButton("Close")
        self._btn_close.clicked.connect(self._on_close)
        btn_row.addWidget(self._btn_close)

        grid.addLayout(btn_row, 3, 0, 1, 3)

        # ── Status label ─────────────────────────────────────────────
        self._status_label = QLabel("")
        self._status_label.setStyleSheet("color: #f38ba8; font-size: 8pt;")
        grid.addWidget(self._status_label, 4, 0, 1, 3)

    def _connect_shortcuts(self) -> None:
        prev_sc = QShortcut(QKeySequence("Shift+Return"), self)
        prev_sc.activated.connect(self._find_prev)

    # ------------------------------------------------------------------ #
    # Search helpers                                                       #
    # ------------------------------------------------------------------ #

    def _compile_pattern(self) -> re.Pattern | None:
        """
        Compile the current search text into a re.Pattern.
        Returns None on empty input or regex compile error.
        Sets _status_label with any error message.
        """
        text = self._find_edit.text()
        if not text:
            return None
        flags = re.UNICODE
        if not self._chk_case.isChecked():
            flags |= re.IGNORECASE
        try:
            if self._chk_regex.isChecked():
                pat = re.compile(text, flags)
            else:
                escaped = re.escape(text)
                if self._chk_word.isChecked():
                    escaped = rf"\b{escaped}\b"
                pat = re.compile(escaped, flags)
            self._status_label.setText("")
            return pat
        except re.error as exc:
            self._status_label.setText(f"Regex error: {exc}")
            return None

    def _find_all_positions(self) -> list[tuple[int, int]]:
        """Return list of (start, end) char positions for all matches."""
        pat = self._compile_pattern()
        if pat is None:
            return []
        text = self._editor.document().toPlainText()
        return [(m.start(), m.end()) for m in pat.finditer(text)]

    def _highlight_all_matches(self) -> None:
        """Colour all matches in the document using ExtraSelections."""
        from PySide6.QtWidgets import QTextEdit
        selections = []
        for i, (start, end) in enumerate(self._match_positions):
            sel = QTextEdit.ExtraSelection()
            sel.cursor = QTextCursor(self._editor.document())
            sel.cursor.setPosition(start)
            sel.cursor.setPosition(end, QTextCursor.KeepAnchor)
            if i == self._current_match_idx:
                sel.format.setBackground(_ACTIVE_BG)
                sel.format.setForeground(_ACTIVE_FG)
            else:
                sel.format.setBackground(_MATCH_BG)
                sel.format.setForeground(_MATCH_FG)
            selections.append(sel)
        self._editor.setExtraSelections(selections)

    def _clear_highlights(self) -> None:
        self._editor.setExtraSelections([])

    def _scroll_to_match(self, idx: int) -> None:
        """Move the editor cursor to match at *idx* and scroll to it."""
        if not (0 <= idx < len(self._match_positions)):
            return
        start, end = self._match_positions[idx]
        cursor = QTextCursor(self._editor.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.KeepAnchor)
        self._editor.setTextCursor(cursor)
        self._editor.ensureCursorVisible()
        self._current_match_idx = idx
        self._highlight_all_matches()
        self._update_count_label()

    def _update_count_label(self) -> None:
        n = len(self._match_positions)
        if n == 0:
            text = self._find_edit.text()
            self._count_label.setText("No matches" if text else "")
        elif self._current_match_idx >= 0:
            self._count_label.setText(f"{self._current_match_idx + 1} / {n}")
        else:
            self._count_label.setText(f"{n} match{'es' if n != 1 else ''}")

    # ------------------------------------------------------------------ #
    # Slots                                                                #
    # ------------------------------------------------------------------ #

    @Slot()
    def _on_find_text_changed(self) -> None:
        """Recompute match list and highlight on every keystroke."""
        self._match_positions = self._find_all_positions()
        self._current_match_idx = -1
        if self._match_positions:
            # Highlight all but don't jump yet
            self._highlight_all_matches()
        else:
            self._clear_highlights()
        self._update_count_label()

    @Slot()
    def _on_options_changed(self) -> None:
        self._on_find_text_changed()

    @Slot()
    def _find_next(self) -> None:
        self._match_positions = self._find_all_positions()
        if not self._match_positions:
            return
        # Find next match after cursor position
        cursor_pos = self._editor.textCursor().position()
        for i, (start, _) in enumerate(self._match_positions):
            if start > cursor_pos:
                self._scroll_to_match(i)
                return
        # Wrap around
        if self._chk_wrap.isChecked():
            self._scroll_to_match(0)
        else:
            self._status_label.setText("No more matches below.")

    @Slot()
    def _find_prev(self) -> None:
        self._match_positions = self._find_all_positions()
        if not self._match_positions:
            return
        cursor_pos = self._editor.textCursor().position()
        for i, (_, end) in reversed(list(enumerate(self._match_positions))):
            if end < cursor_pos:
                self._scroll_to_match(i)
                return
        if self._chk_wrap.isChecked():
            self._scroll_to_match(len(self._match_positions) - 1)
        else:
            self._status_label.setText("No more matches above.")

    @Slot()
    def _replace_one(self) -> None:
        """Replace the currently selected match and advance to the next."""
        cursor = self._editor.textCursor()
        if cursor.hasSelection():
            replacement = self._replace_edit.text()
            cursor.beginEditBlock()
            cursor.insertText(replacement)
            cursor.endEditBlock()
        self._find_next()

    @Slot()
    def _replace_all(self) -> None:
        """Replace every match in the document in one undo operation."""
        pat = self._compile_pattern()
        if pat is None:
            return
        replacement = self._replace_edit.text()
        doc_text = self._editor.document().toPlainText()

        # Count before replacement
        matches = list(pat.finditer(doc_text))
        n = len(matches)
        if n == 0:
            QMessageBox.information(self, "Replace All", "No matches found.")
            return

        try:
            new_text = pat.sub(replacement, doc_text)
        except re.error as exc:
            QMessageBox.warning(self, "Replace Error", str(exc))
            return

        cursor = self._editor.textCursor()
        cursor.beginEditBlock()
        cursor.select(QTextCursor.Document)
        cursor.insertText(new_text)
        cursor.endEditBlock()

        self._clear_highlights()
        self._match_positions = []
        self._current_match_idx = -1
        self._update_count_label()

        QMessageBox.information(
            self, "Replace All",
            f"Replaced {n} occurrence{'s' if n != 1 else ''}."
        )
        log.info("Replace All: %d occurrences replaced.", n)

    @Slot()
    def _on_close(self) -> None:
        self._clear_highlights()
        self.close()

    def closeEvent(self, event) -> None:
        self._clear_highlights()
        super().closeEvent(event)
