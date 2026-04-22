"""
prasword.gui.dialogs.insert_table_dialog
=========================================
Insert Table dialog with two modes:

  Blank Table
    Choose rows × columns, optional header row, border style, and
    background colour. Inserts a styled QTextTable.

  Import CSV / TSV
    Browse to a .csv or .tsv file. Preview the first few rows.
    Choose whether the first row is a header. Inserts via CsvTableConverter.
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from prasword.utils.logger import get_logger

log = get_logger(__name__)

_BORDER_STYLES = {
    "Solid thin":   (1, "solid"),
    "Solid medium": (2, "solid"),
    "None":         (0, "none"),
}


class InsertTableDialog(QDialog):
    """
    Table insertion dialog.

    Parameters
    ----------
    editor : EditorWidget | None
        The target editor. If None the dialog opens but Insert is disabled.
    parent : QWidget | None
    """

    def __init__(self, editor=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._editor = editor
        self._csv_path: Path | None = None
        self.setWindowTitle("Insert Table")
        self.setMinimumSize(500, 380)
        self.resize(560, 420)
        self._build_ui()

    # ------------------------------------------------------------------ #
    # UI                                                                   #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        self._tabs = QTabWidget()

        self._tabs.addTab(self._build_blank_tab(), "Blank Table")
        self._tabs.addTab(self._build_csv_tab(),   "Import CSV / TSV")

        root.addWidget(self._tabs, 1)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        root.addWidget(sep)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        self._btn_insert = QPushButton("Insert")
        self._btn_insert.setDefault(True)
        self._btn_insert.setEnabled(bool(self._editor))
        self._btn_insert.clicked.connect(self._on_insert)
        btn_row.addWidget(self._btn_insert)
        root.addLayout(btn_row)

    def _build_blank_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setSpacing(10)

        # Rows / columns
        dims = QGroupBox("Dimensions")
        dl = QHBoxLayout(dims)
        dl.addWidget(QLabel("Rows:"))
        self._rows_spin = QSpinBox()
        self._rows_spin.setRange(1, 200)
        self._rows_spin.setValue(3)
        self._rows_spin.setFixedWidth(70)
        dl.addWidget(self._rows_spin)
        dl.addSpacing(20)
        dl.addWidget(QLabel("Columns:"))
        self._cols_spin = QSpinBox()
        self._cols_spin.setRange(1, 26)
        self._cols_spin.setValue(3)
        self._cols_spin.setFixedWidth(70)
        dl.addWidget(self._cols_spin)
        dl.addStretch()
        layout.addWidget(dims)

        # Options
        opts = QGroupBox("Options")
        ol = QVBoxLayout(opts)
        self._chk_header_blank = QCheckBox("First row is a header (bold + shaded)")
        self._chk_header_blank.setChecked(True)
        ol.addWidget(self._chk_header_blank)

        border_row = QHBoxLayout()
        border_row.addWidget(QLabel("Border:"))
        self._border_combo = QComboBox()
        self._border_combo.addItems(list(_BORDER_STYLES.keys()))
        border_row.addWidget(self._border_combo)
        border_row.addStretch()
        ol.addLayout(border_row)
        layout.addWidget(opts)
        layout.addStretch()
        return w

    def _build_csv_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)

        # File picker
        file_row = QHBoxLayout()
        self._csv_path_edit = QLineEdit()
        self._csv_path_edit.setPlaceholderText("Click Browse… to select a CSV or TSV file")
        self._csv_path_edit.setReadOnly(True)
        file_row.addWidget(self._csv_path_edit, 1)
        btn_browse = QPushButton("Browse…")
        btn_browse.clicked.connect(self._browse_csv)
        file_row.addWidget(btn_browse)
        layout.addLayout(file_row)

        # Options row
        opt_row = QHBoxLayout()
        self._chk_header_csv = QCheckBox("First row is a header")
        self._chk_header_csv.setChecked(True)
        opt_row.addWidget(self._chk_header_csv)
        opt_row.addStretch()
        self._rows_label = QLabel("")
        self._rows_label.setStyleSheet("color: #6c7086; font-size: 9pt;")
        opt_row.addWidget(self._rows_label)
        layout.addLayout(opt_row)

        # Preview table
        self._preview_table = QTableWidget(0, 0)
        self._preview_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._preview_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._preview_table, 1)
        return w

    # ------------------------------------------------------------------ #
    # Slots                                                                #
    # ------------------------------------------------------------------ #

    @Slot()
    def _browse_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open CSV / TSV", "",
            "Delimited files (*.csv *.tsv *.txt);;All Files (*)"
        )
        if not path:
            return
        self._csv_path = Path(path)
        self._csv_path_edit.setText(str(self._csv_path))
        self._load_csv_preview()

    def _load_csv_preview(self, max_rows: int = 8) -> None:
        if not self._csv_path or not self._csv_path.exists():
            return
        try:
            text = self._csv_path.read_text(encoding="utf-8", errors="replace")
            # Sniff delimiter
            dialect = csv.Sniffer().sniff(text[:2048], delimiters=",\t;|")
            rows = list(csv.reader(io.StringIO(text), dialect))[:max_rows + 1]
        except Exception:
            rows = list(csv.reader(io.StringIO(text)))[:max_rows + 1]

        if not rows:
            return

        num_cols = max(len(r) for r in rows)
        self._preview_table.setRowCount(len(rows))
        self._preview_table.setColumnCount(num_cols)

        total_rows = len(list(csv.reader(io.StringIO(
            self._csv_path.read_text(encoding="utf-8", errors="replace")
        ))))
        self._rows_label.setText(f"{total_rows} rows total")

        for r, row in enumerate(rows):
            for c in range(num_cols):
                val = row[c].strip() if c < len(row) else ""
                item = QTableWidgetItem(val)
                if r == 0:
                    f = item.font(); f.setBold(True); item.setFont(f)
                self._preview_table.setItem(r, c, item)

        self._preview_table.resizeColumnsToContents()

    @Slot()
    def _on_insert(self) -> None:
        if not self._editor:
            self.reject()
            return

        if self._tabs.currentIndex() == 0:
            self._insert_blank_table()
        else:
            self._insert_csv_table()
        self.accept()

    def _insert_blank_table(self) -> None:
        from PySide6.QtGui import QFont, QTextCharFormat, QTextCursor, QTextLength, QTextTableFormat

        rows = self._rows_spin.value()
        cols = self._cols_spin.value()
        border_key = self._border_combo.currentText()
        border_width, _ = _BORDER_STYLES.get(border_key, (1, "solid"))
        has_header = self._chk_header_blank.isChecked()

        fmt = QTextTableFormat()
        fmt.setCellPadding(6)
        fmt.setCellSpacing(0)
        fmt.setBorder(border_width)
        fmt.setBorderBrush(QColor("#45475a"))
        fmt.setBackground(QColor("#1e1e2e"))
        col_constraint = [
            QTextLength(QTextLength.PercentageLength, 100.0 / cols)
        ] * cols
        fmt.setColumnWidthConstraints(col_constraint)

        cursor = self._editor.textCursor()
        cursor.beginEditBlock()
        table = cursor.insertTable(rows, cols, fmt)

        if has_header:
            for c in range(cols):
                cell_cursor = table.cellAt(0, c).firstCursorPosition()
                hdr_fmt = QTextCharFormat()
                hdr_fmt.setFontWeight(QFont.Bold)
                hdr_fmt.setForeground(QColor("#89b4fa"))
                hdr_fmt.setBackground(QColor("#313244"))
                cell_cursor.setCharFormat(hdr_fmt)
                cell_cursor.insertText(f"Header {c + 1}")

        cursor.endEditBlock()
        log.info("Blank table inserted: %d×%d", rows, cols)

    def _insert_csv_table(self) -> None:
        if not self._csv_path:
            return
        from prasword.features.datascience.csv_table import CsvTableConverter
        CsvTableConverter.insert_from_file(
            self._editor,
            self._csv_path,
            has_header=self._chk_header_csv.isChecked(),
        )
        log.info("CSV table inserted from: %s", self._csv_path)
