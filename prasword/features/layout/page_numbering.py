"""
prasword.features.layout.page_numbering
========================================
Page numbering support.

Qt's QTextDocument exposes a ``pageCount()`` method and the QPrinter
paint device provides per-page callbacks during printing.  We attach
page numbers two ways:

1. **Print/Export path** — paint page numbers onto each page during the
   QPainter render loop (see ``PageNumberPainter``).
2. **Editor overlay** — a translucent ``QLabel`` painted over the editor
   viewport that tracks the estimated current page number as the user
   scrolls (see ``PageOverlay``).

Numbering styles
----------------
arabic        1, 2, 3  (default)
roman_lower   i, ii, iii
roman_upper   I, II, III
alpha_lower   a, b, c
alpha_upper   A, B, C
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prasword.core.document import Document

from prasword.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Numeral formatters
# ---------------------------------------------------------------------------

def _to_roman(n: int, upper: bool = True) -> str:
    """Convert a positive integer to a Roman numeral string."""
    val = [1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1]
    syms = ["M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"]
    result = ""
    for i, v in enumerate(val):
        while n >= v:
            result += syms[i]
            n -= v
    return result if upper else result.lower()


def _to_alpha(n: int, upper: bool = True) -> str:
    """Convert 1-based integer to alphabetic label (1→a, 27→aa, …)."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(ord("A" if upper else "a") + rem) + result
    return result


_FORMATTERS = {
    "arabic":      lambda n: str(n),
    "roman_lower": lambda n: _to_roman(n, upper=False),
    "roman_upper": lambda n: _to_roman(n, upper=True),
    "alpha_lower": lambda n: _to_alpha(n, upper=False),
    "alpha_upper": lambda n: _to_alpha(n, upper=True),
}


@dataclass
class NumberingConfig:
    """Configuration for page numbering."""
    style: str = "arabic"          # one of the _FORMATTERS keys
    start: int = 1                 # first page number value
    show_total: bool = False       # show "Page N of M" style
    prefix: str = ""               # text before the number
    suffix: str = ""               # text after the number

    def format(self, page: int, total: int) -> str:
        """Return the formatted page number string."""
        formatter = _FORMATTERS.get(self.style, _FORMATTERS["arabic"])
        num_str = formatter(page - 1 + self.start)
        if self.show_total:
            total_str = formatter(total - 1 + self.start)
            return f"{self.prefix}Page {num_str} of {total_str}{self.suffix}"
        return f"{self.prefix}{num_str}{self.suffix}"


class PageNumberPainter:
    """
    Paints page numbers onto a QPainter during PDF / print export.

    Intended to be called from a custom print loop that iterates over
    QTextDocument pages.

    Usage
    -----
    >>> painter = QPainter(printer)
    >>> pnp = PageNumberPainter(config, document)
    >>> for page in range(1, doc.pageCount() + 1):
    ...     pnp.paint_page_number(painter, printer, page)
    """

    def __init__(self, config: NumberingConfig, document: "Document") -> None:
        self._config = config
        self._total = document.qt_document.pageCount()

    def paint_page_number(self, painter, printer, page: int) -> None:
        """
        Paint the page number for *page* at the bottom-centre of the current
        printer page.

        Parameters
        ----------
        painter : QPainter  Active painter on the printer device.
        printer : QPrinter  Printer / PDF device.
        page : int          1-based page number.
        """
        from PySide6.QtCore import QRect, Qt
        from PySide6.QtGui import QFont

        text = self._config.format(page, self._total)
        page_rect = printer.pageRect(printer.Unit.DevicePixel).toRect()

        font = QFont("Segoe UI", 8)
        painter.setFont(font)

        # Bottom centre, 12 px above the page edge.
        margin = 12
        text_rect = QRect(
            page_rect.left(),
            page_rect.bottom() - painter.fontMetrics().height() - margin,
            page_rect.width(),
            painter.fontMetrics().height() + margin,
        )
        painter.drawText(text_rect, Qt.AlignHCenter | Qt.AlignBottom, text)
        log.debug("Page number painted: %s (page %d/%d)", text, page, self._total)


class PageOverlay:
    """
    A translucent page-indicator label overlaid on the editor viewport.

    Shows "Page N / M" in the bottom-right corner of the visible editor area.
    Updates when the vertical scrollbar moves.

    Usage
    -----
    >>> overlay = PageOverlay(editor)
    >>> overlay.install()
    """

    def __init__(self, editor, config: NumberingConfig | None = None) -> None:
        self._editor = editor
        self._config = config or NumberingConfig(show_total=True)
        self._label = None

    def install(self) -> None:
        """Attach the overlay label to *editor*'s viewport."""
        from PySide6.QtWidgets import QLabel
        from PySide6.QtCore import Qt

        vp = self._editor.viewport()
        self._label = QLabel(vp)
        self._label.setAlignment(Qt.AlignRight | Qt.AlignBottom)
        self._label.setStyleSheet(
            "background: rgba(30,30,46,0.75);"
            "color: #a6adc8;"
            "font-size: 8pt;"
            "padding: 2px 8px;"
            "border-radius: 4px;"
        )
        self._label.setAttribute(Qt.WA_TransparentForMouseEvents)
        self._label.show()

        self._editor.verticalScrollBar().valueChanged.connect(self._update)
        self._update()

    def _update(self) -> None:
        if not self._label:
            return
        doc = self._editor.document()
        total = max(1, doc.pageCount())
        # Estimate current page from scroll position.
        sb = self._editor.verticalScrollBar()
        ratio = sb.value() / max(1, sb.maximum()) if sb.maximum() > 0 else 0
        current = max(1, min(total, int(ratio * total) + 1))
        text = self._config.format(current, total)
        self._label.setText(text)
        # Position in bottom-right of viewport.
        vp = self._editor.viewport()
        lw, lh = self._label.sizeHint().width() + 16, 22
        self._label.setGeometry(vp.width() - lw - 8, vp.height() - lh - 8, lw, lh)
