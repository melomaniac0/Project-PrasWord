"""
prasword.features.datascience.csv_table
========================================
CSV / TSV → styled QTextTable converter.

Features
--------
* Auto-detects delimiter (comma, tab, semicolon, pipe) via csv.Sniffer.
* Header row styled with bold text, accent colour, and shaded background.
* Odd/even row alternation (zebra striping) for readability.
* Percentage-width column constraints so the table fills the page.
* Optional numeric alignment: detects purely numeric cells and right-aligns them.
* ``to_markdown(path_or_text)`` exports the table as a GitHub-flavoured
  Markdown table string (no Qt dependency).
* ``to_html(path_or_text)`` exports as an HTML <table>.
* Safety cap: tables over *max_rows* rows are truncated with a notice.

Supported input
---------------
* File path  → CsvTableConverter.insert_from_file(editor, path, …)
* Raw string → CsvTableConverter.insert_from_string(editor, csv_text, …)
* Parsed rows → CsvTableConverter.insert_from_rows(editor, rows, …)
"""

from __future__ import annotations

import csv
import io
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QTextCharFormat,
    QTextLength,
    QTextTableFormat,
)

if TYPE_CHECKING:
    from prasword.gui.editor_widget import EditorWidget

from prasword.utils.logger import get_logger

log = get_logger(__name__)

# ── Style constants ───────────────────────────────────────────────────────────

_HEADER_FG   = "#89b4fa"
_HEADER_BG   = "#313244"
_ROW_FG      = "#cdd6f4"
_ROW_BG_EVEN = "#181825"
_ROW_BG_ODD  = "#1e1e2e"
_BORDER_COL  = "#45475a"
_TABLE_BG    = "#1e1e2e"


def _sniff_dialect(text: str) -> csv.Dialect | None:
    """Sniff the CSV dialect; return None if sniffing fails."""
    try:
        return csv.Sniffer().sniff(text[:4096], delimiters=",\t;|")
    except csv.Error:
        return None


def _parse_csv(text: str) -> list[list[str]]:
    """Parse a CSV/TSV string and return a list of rows."""
    dialect = _sniff_dialect(text)
    if dialect:
        reader = csv.reader(io.StringIO(text), dialect)
    else:
        reader = csv.reader(io.StringIO(text))
    return [row for row in reader if any(cell.strip() for cell in row)]


def _is_numeric(value: str) -> bool:
    """Return True if *value* looks like a number (int, float, %, currency)."""
    v = value.strip().lstrip("$€£¥").rstrip("%").replace(",", "")
    try:
        float(v)
        return True
    except ValueError:
        return False


class CsvTableConverter:
    """
    Static helpers to convert CSV/TSV data to a styled QTextTable.
    """

    # ------------------------------------------------------------------ #
    # Main insert methods                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def insert_from_file(
        editor: "EditorWidget",
        path: Path,
        has_header: bool = True,
        max_rows: int = 500,
        numeric_align: bool = True,
    ) -> int:
        """
        Read *path* and insert as a QTextTable at the cursor.

        Parameters
        ----------
        editor : EditorWidget
        path : Path
        has_header : bool
        max_rows : int
            Rows beyond this limit are dropped (a notice is appended).
        numeric_align : bool
            Right-align cells that contain only numeric values.

        Returns
        -------
        int
            Number of data rows inserted (excluding header).
        """
        text = path.read_text(encoding="utf-8", errors="replace")
        return CsvTableConverter.insert_from_string(
            editor, text,
            has_header=has_header,
            max_rows=max_rows,
            numeric_align=numeric_align,
        )

    @staticmethod
    def insert_from_string(
        editor: "EditorWidget",
        csv_text: str,
        has_header: bool = True,
        max_rows: int = 500,
        numeric_align: bool = True,
    ) -> int:
        """
        Parse *csv_text* and insert as a QTextTable at the cursor.

        Returns the number of data rows (excluding the header) inserted.
        """
        rows = _parse_csv(csv_text)
        return CsvTableConverter.insert_from_rows(
            editor, rows,
            has_header=has_header,
            max_rows=max_rows,
            numeric_align=numeric_align,
        )

    @staticmethod
    def insert_from_rows(
        editor: "EditorWidget",
        rows: list[list[str]],
        has_header: bool = True,
        max_rows: int = 500,
        numeric_align: bool = True,
    ) -> int:
        """
        Insert a QTextTable from an already-parsed list of row lists.

        Parameters
        ----------
        editor : EditorWidget
        rows : list[list[str]]
        has_header : bool
        max_rows : int
        numeric_align : bool

        Returns
        -------
        int
            Number of data rows inserted.
        """
        if not rows:
            log.warning("CSV table: no rows to insert.")
            return 0

        truncated = False
        cap = max_rows + (1 if has_header else 0)
        if len(rows) > cap:
            rows      = rows[:cap]
            truncated = True

        num_cols = max(len(r) for r in rows)
        num_rows = len(rows)

        # Detect numeric columns for alignment
        num_col_mask: list[bool] = []
        if numeric_align:
            for c in range(num_cols):
                start_r = 1 if has_header else 0
                vals    = [rows[r][c] for r in range(start_r, num_rows) if c < len(rows[r])]
                num_col_mask.append(bool(vals) and all(_is_numeric(v) for v in vals if v.strip()))
        else:
            num_col_mask = [False] * num_cols

        cursor = editor.textCursor()
        cursor.beginEditBlock()

        # ── Table format ──────────────────────────────────────────────
        tfmt = QTextTableFormat()
        tfmt.setCellPadding(6)
        tfmt.setCellSpacing(0)
        tfmt.setBorderStyle(QTextTableFormat.BorderStyle_Solid)
        tfmt.setBorder(1)
        tfmt.setBorderBrush(QColor(_BORDER_COL))
        tfmt.setBackground(QColor(_TABLE_BG))
        tfmt.setAlignment(Qt.AlignLeft)
        col_widths = [
            QTextLength(QTextLength.PercentageLength, 100.0 / num_cols)
        ] * num_cols
        tfmt.setColumnWidthConstraints(col_widths)

        table = cursor.insertTable(num_rows, num_cols, tfmt)

        mono = QFont()
        mono.setFamily("Consolas, Courier New")
        mono.setPointSize(9)
        mono.setStyleHint(QFont.Monospace)

        for r, row in enumerate(rows):
            for c in range(num_cols):
                cell        = table.cellAt(r, c)
                cell_cursor = cell.firstCursorPosition()
                value       = row[c].strip() if c < len(row) else ""

                fmt = QTextCharFormat()

                if r == 0 and has_header:
                    # ── Header cell ───────────────────────────────────
                    fmt.setFontWeight(QFont.Bold)
                    fmt.setForeground(QColor(_HEADER_FG))
                    fmt.setBackground(QColor(_HEADER_BG))
                else:
                    # ── Data cell ─────────────────────────────────────
                    fmt.setForeground(QColor(_ROW_FG))
                    bg = _ROW_BG_EVEN if r % 2 == 0 else _ROW_BG_ODD
                    fmt.setBackground(QColor(bg))
                    if num_col_mask[c]:
                        fmt.setFont(mono)

                cell_cursor.setCharFormat(fmt)

                # Alignment
                blk_fmt = cell_cursor.blockFormat()
                if r == 0 and has_header:
                    blk_fmt.setAlignment(Qt.AlignLeft)
                elif num_col_mask[c]:
                    blk_fmt.setAlignment(Qt.AlignRight)
                else:
                    blk_fmt.setAlignment(Qt.AlignLeft)
                cell_cursor.setBlockFormat(blk_fmt)

                cell_cursor.insertText(value)

        cursor.endEditBlock()

        # Truncation notice
        if truncated:
            from PySide6.QtGui import QTextCursor as _TC
            notice_cursor = editor.textCursor()
            notice_cursor.movePosition(_TC.MoveOperation.End)
            editor.setTextCursor(notice_cursor)
            notice_fmt = QTextCharFormat()
            notice_fmt.setForeground(QColor("#f9e2af"))
            notice_fmt.setFontItalic(True)
            notice_cursor.insertBlock()
            notice_cursor.insertText(
                f"  ⚠ Table truncated to {max_rows} data rows.", notice_fmt
            )

        data_rows = num_rows - (1 if has_header else 0)
        log.info("CSV table inserted: %d rows × %d cols", num_rows, num_cols)
        return data_rows

    # ------------------------------------------------------------------ #
    # Export helpers (no Qt dependency)                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def to_markdown(source: str | Path, has_header: bool = True) -> str:
        """
        Convert CSV/TSV data to a GitHub-Flavoured Markdown table.

        Parameters
        ----------
        source : str | Path
            Raw CSV string or path to a file.
        has_header : bool

        Returns
        -------
        str
            GFM Markdown table string.
        """
        if isinstance(source, Path):
            source = source.read_text(encoding="utf-8", errors="replace")
        rows = _parse_csv(source)
        if not rows:
            return ""

        num_cols = max(len(r) for r in rows)

        def _pad(row: list[str]) -> list[str]:
            return row + [""] * (num_cols - len(row))

        lines: list[str] = []
        if has_header and rows:
            header = _pad(rows[0])
            lines.append("| " + " | ".join(header) + " |")
            lines.append("| " + " | ".join(["---"] * num_cols) + " |")
            data_rows = rows[1:]
        else:
            data_rows = rows

        for row in data_rows:
            lines.append("| " + " | ".join(_pad(row)) + " |")

        return "\n".join(lines)

    @staticmethod
    def to_html(source: str | Path, has_header: bool = True) -> str:
        """
        Convert CSV/TSV data to an HTML table string.

        Parameters
        ----------
        source : str | Path
        has_header : bool

        Returns
        -------
        str
            HTML <table> string.
        """
        if isinstance(source, Path):
            source = source.read_text(encoding="utf-8", errors="replace")
        rows = _parse_csv(source)
        if not rows:
            return ""

        def _escape(s: str) -> str:
            return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

        lines = ["<table border='1' cellpadding='6' cellspacing='0'>"]
        for r, row in enumerate(rows):
            lines.append("  <tr>")
            tag = "th" if r == 0 and has_header else "td"
            for cell in row:
                lines.append(f"    <{tag}>{_escape(cell.strip())}</{tag}>")
            lines.append("  </tr>")
        lines.append("</table>")
        return "\n".join(lines)
