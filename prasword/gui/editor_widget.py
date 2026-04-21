"""
prasword.gui.editor_widget
==========================
The central rich-text editing surface.

``EditorWidget`` wraps a ``QTextEdit`` to provide:

* A fixed A4-ish page canvas with configurable margins.
* Integration with a ``Document`` object (shared ``QTextDocument``).
* Keystroke-level signals for the metrics module.
* A distraction-free mode toggle that hides all decoration.
* Line-number gutter (rendered via a companion ``LineNumberArea`` widget).
* Convenience methods for inserting formatted content (headings, code
  blocks, math, tables) called by the feature toolbar actions.

The widget deliberately contains *no* business logic — it delegates all
formatting decisions to the ``FormattingEngine`` and all content decisions
to the active ``Document``.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, QRect, QSize
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QPaintEvent,
    QResizeEvent,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import QTextEdit, QWidget

from prasword.core.document import Document
from prasword.utils.logger import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Line-number gutter
# ---------------------------------------------------------------------------

class LineNumberArea(QWidget):
    """
    A narrow gutter widget painted on the left side of the editor.

    It delegates its ``paintEvent`` back to the parent ``EditorWidget``
    so the gutter and the editor share one coordinate system.
    """

    def __init__(self, editor: "EditorWidget") -> None:
        super().__init__(editor)
        self._editor = editor

    def sizeHint(self) -> QSize:
        return QSize(self._editor.line_number_area_width(), 0)

    def paintEvent(self, event: QPaintEvent) -> None:  # type: ignore[override]
        self._editor.paint_line_numbers(event)


# ---------------------------------------------------------------------------
# Main editor widget
# ---------------------------------------------------------------------------

class EditorWidget(QTextEdit):
    """
    Rich-text document editing surface.

    Signals
    -------
    content_changed()
        Re-emitted from ``QTextDocument.contentsChanged`` for convenience.
    cursor_position_changed(int line, int col)
        Line and column numbers of the current cursor position.
    selection_changed()
        Forwarded from ``QTextEdit.selectionChanged``.

    Parameters
    ----------
    document : Document | None
        The Document to display.  If ``None``, the editor shows a blank
        QTextDocument (useful for testing / splash screens).
    parent : QWidget | None
    """

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------
    content_changed = Signal()
    cursor_position_changed = Signal(int, int)  # line, col

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------

    def __init__(
        self,
        document: Optional[Document] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._document: Optional[Document] = None
        self._show_line_numbers: bool = True
        self._distraction_free: bool = False
        self._line_number_area = LineNumberArea(self)

        self._setup_appearance()
        self._connect_internal_signals()

        if document is not None:
            self.set_document(document)

    # ------------------------------------------------------------------
    # Document binding
    # ------------------------------------------------------------------

    def set_document(self, doc: Document) -> None:
        """
        Bind the editor to *doc*, sharing its QTextDocument.

        Parameters
        ----------
        doc : Document
            The document to display.
        """
        self._document = doc
        # Share the backing QTextDocument (not a copy).
        super().setDocument(doc.qt_document)
        log.debug("EditorWidget bound to document: %s", doc.id)

    @property
    def current_document(self) -> Optional[Document]:
        """The currently bound Document, or None."""
        return self._document

    # ------------------------------------------------------------------
    # Distraction-free mode
    # ------------------------------------------------------------------

    def set_distraction_free(self, enabled: bool) -> None:
        """
        Toggle distraction-free (zen) mode.

        In distraction-free mode the line-number gutter is hidden and the
        document canvas is centred with generous margins.
        """
        self._distraction_free = enabled
        self._line_number_area.setVisible(
            self._show_line_numbers and not enabled
        )
        if enabled:
            # Wider, centred margins for focus.
            self.setViewportMargins(120, 48, 120, 48)
        else:
            self._update_viewport_margins()
        log.debug("Distraction-free mode: %s", enabled)

    # ------------------------------------------------------------------
    # Line numbers
    # ------------------------------------------------------------------

    def set_show_line_numbers(self, visible: bool) -> None:
        """Show or hide the line-number gutter."""
        self._show_line_numbers = visible
        self._line_number_area.setVisible(
            visible and not self._distraction_free
        )
        self._update_viewport_margins()

    def line_number_area_width(self) -> int:
        """Compute the required pixel width for the line-number gutter."""
        if not self._show_line_numbers or self._distraction_free:
            return 0
        digits = max(3, len(str(max(1, self.document().blockCount()))))
        return 6 + self.fontMetrics().horizontalAdvance("9") * digits

    def paint_line_numbers(self, event: QPaintEvent) -> None:
        """Called by ``LineNumberArea.paintEvent`` to render line numbers."""
        painter = QPainter(self._line_number_area)
        bg_color = QColor("#313244")  # matches dark theme bg_surface
        painter.fillRect(event.rect(), bg_color)

        block = self.document().begin()
        block_number = 0
        top = int(
            self.document().documentLayout().blockBoundingRect(block).translated(
                0, -self.verticalScrollBar().value()
            ).top()
        )
        bottom = top + int(
            self.document().documentLayout().blockBoundingRect(block).height()
        )
        area_height = event.rect().bottom()

        while block.isValid() and top <= area_height:
            if block.isVisible() and bottom >= event.rect().top():
                number = str(block_number + 1)
                painter.setPen(QColor("#585b70"))
                painter.drawText(
                    0, top,
                    self._line_number_area.width() - 4,
                    self.fontMetrics().height(),
                    Qt.AlignRight,
                    number,
                )
            block = block.next()
            top = bottom
            if block.isValid():
                bottom = top + int(
                    self.document()
                    .documentLayout()
                    .blockBoundingRect(block)
                    .height()
                )
            block_number += 1

    # ------------------------------------------------------------------
    # Convenience insertion helpers (called by feature toolbar slots)
    # ------------------------------------------------------------------

    def insert_heading(self, level: int, text: str = "") -> None:
        """
        Insert an Hx heading block at the cursor position.

        Parameters
        ----------
        level : int
            Heading level 1–6.
        text : str
            Optional pre-filled heading text.
        """
        cursor = self.textCursor()
        cursor.beginEditBlock()
        fmt = cursor.blockCharFormat()
        heading_sizes = {1: 24, 2: 20, 3: 16, 4: 14, 5: 12, 6: 11}
        fmt.setFontPointSize(heading_sizes.get(level, 11))
        fmt.setFontWeight(QFont.Bold)
        cursor.setCharFormat(fmt)
        cursor.insertText(text or f"Heading {level}")
        cursor.insertBlock()
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def insert_code_block(self, language: str = "python") -> None:
        """
        Insert a fenced code block placeholder.

        The Data Science feature module will decorate the block with
        syntax highlighting after insertion.

        Parameters
        ----------
        language : str
            Language hint stored in the block's user data.
        """
        cursor = self.textCursor()
        cursor.beginEditBlock()

        char_fmt = QTextCharFormat()
        char_fmt.setFont(QFont("Courier New", 10))
        char_fmt.setBackground(QColor("#11111b"))
        char_fmt.setForeground(QColor("#cdd6f4"))

        cursor.insertText(f"# {language}\n", char_fmt)
        cursor.insertText("# Write your code here\n", char_fmt)
        cursor.endEditBlock()
        self.setTextCursor(cursor)

    def insert_math_block(self, latex: str = r"E = mc^2") -> None:
        """
        Insert a LaTeX math expression placeholder.

        The Data Science module renders the expression to SVG / PNG and
        replaces the placeholder with an image once rendering completes.

        Parameters
        ----------
        latex : str
            LaTeX source without surrounding $$ delimiters.
        """
        cursor = self.textCursor()
        cursor.insertText(f"$$\n{latex}\n$$\n")

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------

    def resizeEvent(self, event: QResizeEvent) -> None:  # type: ignore[override]
        super().resizeEvent(event)
        cr = self.contentsRect()
        w = self.line_number_area_width()
        self._line_number_area.setGeometry(
            QRect(cr.left(), cr.top(), w, cr.height())
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _setup_appearance(self) -> None:
        """Configure default visual properties."""
        self.setAcceptRichText(True)
        self.setLineWrapMode(QTextEdit.WidgetWidth)
        self.setTabStopDistance(40.0)  # 4-space equivalent in pixels
        # Page-like inner margin (top/bottom gutter).
        self._update_viewport_margins()

    def _update_viewport_margins(self) -> None:
        left = self.line_number_area_width()
        self.setViewportMargins(left, 0, 0, 0)

    def _connect_internal_signals(self) -> None:
        """Wire up Qt internal signals to our public API signals."""
        self.cursorPositionChanged.connect(self._on_cursor_moved)

    def _on_cursor_moved(self) -> None:
        cursor = self.textCursor()
        line = cursor.blockNumber() + 1
        col = cursor.positionInBlock() + 1
        self.cursor_position_changed.emit(line, col)
