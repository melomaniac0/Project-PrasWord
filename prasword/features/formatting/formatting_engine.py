"""
prasword.features.formatting.formatting_engine
===============================================
Central dispatcher for all text and paragraph formatting operations.

Every method accepts an EditorWidget and operates on the current selection
(or, where noted, the cursor paragraph). All operations are wrapped in
beginEditBlock/endEditBlock so they land on Qt's undo stack as single units.

Character formatting
    Bold · Italic · Underline · Strikethrough
    Subscript · Superscript
    Font family · Font size · Text colour · Background highlight
    Clear all character formatting

Paragraph formatting
    Alignment  (Left / Centre / Right / Justify)
    Line spacing (proportional factor)
    Paragraph spacing (before / after, in points)
    Block indent level (integer levels)
    Left / right margin (points)
    First-line indent (points)

Headings
    H1–H6 with size, weight and colour; level 0 resets to body text.

State queries
    is_bold / is_italic / is_underline / is_strikethrough
    current_font_family / current_font_size / current_alignment
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)

if TYPE_CHECKING:
    from prasword.gui.editor_widget import EditorWidget

from prasword.utils.logger import get_logger

log = get_logger(__name__)


# ── Internal helpers ────────────────────────────────────────────────────────

def _char_fmt(editor: "EditorWidget") -> QTextCharFormat:
    """Return the QTextCharFormat at the current cursor / selection."""
    return editor.currentCharFormat()


def _apply_char_fmt(editor: "EditorWidget", fmt: QTextCharFormat) -> None:
    """Merge *fmt* into the selection, wrapped in one undo block."""
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    editor.mergeCurrentCharFormat(fmt)
    cursor.endEditBlock()


def _apply_block_fmt(editor: "EditorWidget", fmt: QTextBlockFormat) -> None:
    """Merge *fmt* into the current paragraph's block format."""
    cursor = editor.textCursor()
    cursor.beginEditBlock()
    cursor.mergeBlockFormat(fmt)
    cursor.endEditBlock()


# ── FormattingEngine ────────────────────────────────────────────────────────

class FormattingEngine:
    """
    Stateless, static formatting dispatcher.

    All public methods follow the same contract:
    - Accept an EditorWidget as the first argument.
    - Operate on the current text cursor / selection.
    - Return a bool for toggle operations (True = feature now ON).
    - Never import GUI widgets at module level (avoids circular imports).
    """

    # ------------------------------------------------------------------ #
    # Bold / Italic / Underline / Strikethrough                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def toggle_bold(editor: "EditorWidget") -> bool:
        """Toggle bold on the selection. Returns True if bold is now active."""
        fmt = _char_fmt(editor)
        now_bold = fmt.fontWeight() == QFont.Bold
        new_fmt = QTextCharFormat()
        new_fmt.setFontWeight(QFont.Normal if now_bold else QFont.Bold)
        _apply_char_fmt(editor, new_fmt)
        log.debug("Bold → %s", not now_bold)
        return not now_bold

    @staticmethod
    def toggle_italic(editor: "EditorWidget") -> bool:
        """Toggle italic on the selection."""
        fmt = _char_fmt(editor)
        new_state = not fmt.fontItalic()
        new_fmt = QTextCharFormat()
        new_fmt.setFontItalic(new_state)
        _apply_char_fmt(editor, new_fmt)
        log.debug("Italic → %s", new_state)
        return new_state

    @staticmethod
    def toggle_underline(editor: "EditorWidget") -> bool:
        """Toggle underline on the selection."""
        fmt = _char_fmt(editor)
        new_state = not fmt.fontUnderline()
        new_fmt = QTextCharFormat()
        new_fmt.setFontUnderline(new_state)
        _apply_char_fmt(editor, new_fmt)
        log.debug("Underline → %s", new_state)
        return new_state

    @staticmethod
    def toggle_strikethrough(editor: "EditorWidget") -> bool:
        """Toggle strikethrough on the selection."""
        fmt = _char_fmt(editor)
        new_state = not fmt.fontStrikeOut()
        new_fmt = QTextCharFormat()
        new_fmt.setFontStrikeOut(new_state)
        _apply_char_fmt(editor, new_fmt)
        log.debug("Strikethrough → %s", new_state)
        return new_state

    # ------------------------------------------------------------------ #
    # Subscript / Superscript                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def toggle_subscript(editor: "EditorWidget") -> bool:
        """Toggle subscript vertical alignment."""
        fmt = _char_fmt(editor)
        currently = fmt.verticalAlignment() == QTextCharFormat.AlignSubScript
        new_fmt = QTextCharFormat()
        new_fmt.setVerticalAlignment(
            QTextCharFormat.AlignNormal if currently
            else QTextCharFormat.AlignSubScript
        )
        _apply_char_fmt(editor, new_fmt)
        return not currently

    @staticmethod
    def toggle_superscript(editor: "EditorWidget") -> bool:
        """Toggle superscript vertical alignment."""
        fmt = _char_fmt(editor)
        currently = fmt.verticalAlignment() == QTextCharFormat.AlignSuperScript
        new_fmt = QTextCharFormat()
        new_fmt.setVerticalAlignment(
            QTextCharFormat.AlignNormal if currently
            else QTextCharFormat.AlignSuperScript
        )
        _apply_char_fmt(editor, new_fmt)
        return not currently

    # ------------------------------------------------------------------ #
    # Font family / size                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def set_font_family(editor: "EditorWidget", family: str) -> None:
        """Set the font family for the current selection."""
        if not family:
            return
        new_fmt = QTextCharFormat()
        new_fmt.setFontFamilies([family])
        _apply_char_fmt(editor, new_fmt)
        log.debug("Font family → %s", family)

    @staticmethod
    def set_font_size(editor: "EditorWidget", size: float) -> None:
        """Set font point size (must be positive) for the current selection."""
        if size <= 0:
            return
        new_fmt = QTextCharFormat()
        new_fmt.setFontPointSize(size)
        _apply_char_fmt(editor, new_fmt)
        log.debug("Font size → %.1f pt", size)

    # ------------------------------------------------------------------ #
    # Colour / highlight                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def set_text_color(editor: "EditorWidget", color: QColor) -> None:
        """Set foreground (text) colour for the current selection."""
        if not color.isValid():
            return
        new_fmt = QTextCharFormat()
        new_fmt.setForeground(color)
        _apply_char_fmt(editor, new_fmt)
        log.debug("Text colour → %s", color.name())

    @staticmethod
    def set_highlight_color(editor: "EditorWidget", color: QColor) -> None:
        """
        Set background highlight colour.
        Pass an invalid QColor to clear the highlight.
        """
        new_fmt = QTextCharFormat()
        if color.isValid() and color.alpha() > 0:
            new_fmt.setBackground(color)
        else:
            new_fmt.clearBackground()
        _apply_char_fmt(editor, new_fmt)
        log.debug("Highlight → %s", color.name() if color.isValid() else "cleared")

    @staticmethod
    def clear_character_formatting(editor: "EditorWidget") -> None:
        """Strip all character-level formatting from the current selection."""
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        cursor.setCharFormat(QTextCharFormat())
        cursor.endEditBlock()
        log.debug("Character formatting cleared.")

    # ------------------------------------------------------------------ #
    # Paragraph — alignment                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def set_alignment(editor: "EditorWidget", alignment: Qt.AlignmentFlag) -> None:
        """
        Set paragraph alignment.

        Parameters
        ----------
        alignment : Qt.AlignmentFlag
            Qt.AlignLeft | Qt.AlignHCenter | Qt.AlignRight | Qt.AlignJustify
        """
        editor.setAlignment(alignment)
        log.debug("Alignment → %s", alignment)

    @staticmethod
    def align_left(editor: "EditorWidget") -> None:
        FormattingEngine.set_alignment(editor, Qt.AlignLeft)

    @staticmethod
    def align_center(editor: "EditorWidget") -> None:
        FormattingEngine.set_alignment(editor, Qt.AlignHCenter)

    @staticmethod
    def align_right(editor: "EditorWidget") -> None:
        FormattingEngine.set_alignment(editor, Qt.AlignRight)

    @staticmethod
    def align_justify(editor: "EditorWidget") -> None:
        FormattingEngine.set_alignment(editor, Qt.AlignJustify)

    # ------------------------------------------------------------------ #
    # Paragraph — line spacing & paragraph spacing                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def set_line_spacing(editor: "EditorWidget", factor: float) -> None:
        """
        Set line spacing as a proportional multiplier.

        Parameters
        ----------
        factor : float
            1.0 = single, 1.5 = one-and-a-half, 2.0 = double, etc.
        """
        fmt = QTextBlockFormat()
        fmt.setLineHeight(
            factor * 100,
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )
        _apply_block_fmt(editor, fmt)
        log.debug("Line spacing → %.2f×", factor)

    @staticmethod
    def set_paragraph_spacing(
        editor: "EditorWidget",
        before_pt: float = 0.0,
        after_pt: float = 6.0,
    ) -> None:
        """
        Set extra space above and below the current paragraph.

        Parameters
        ----------
        before_pt : float   Points of space above the paragraph.
        after_pt  : float   Points of space below the paragraph.
        """
        fmt = QTextBlockFormat()
        fmt.setTopMargin(before_pt)
        fmt.setBottomMargin(after_pt)
        _apply_block_fmt(editor, fmt)
        log.debug("Para spacing → before=%.1f after=%.1f pt", before_pt, after_pt)

    # ------------------------------------------------------------------ #
    # Paragraph — indentation                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def set_indent(editor: "EditorWidget", level: int) -> None:
        """
        Set block indent level (0 = flush left, each +1 adds ~40 px).

        Parameters
        ----------
        level : int   Non-negative integer indent level.
        """
        level = max(0, level)
        fmt = QTextBlockFormat()
        fmt.setIndent(level)
        _apply_block_fmt(editor, fmt)
        log.debug("Indent level → %d", level)

    @staticmethod
    def increase_indent(editor: "EditorWidget") -> None:
        """Increase indent level by 1."""
        current = editor.textCursor().blockFormat().indent()
        FormattingEngine.set_indent(editor, current + 1)

    @staticmethod
    def decrease_indent(editor: "EditorWidget") -> None:
        """Decrease indent level by 1 (minimum 0)."""
        current = editor.textCursor().blockFormat().indent()
        FormattingEngine.set_indent(editor, max(0, current - 1))

    @staticmethod
    def set_left_margin(editor: "EditorWidget", margin_pt: float) -> None:
        """Set left paragraph margin in points."""
        fmt = QTextBlockFormat()
        fmt.setLeftMargin(margin_pt)
        _apply_block_fmt(editor, fmt)

    @staticmethod
    def set_right_margin(editor: "EditorWidget", margin_pt: float) -> None:
        """Set right paragraph margin in points."""
        fmt = QTextBlockFormat()
        fmt.setRightMargin(margin_pt)
        _apply_block_fmt(editor, fmt)

    @staticmethod
    def set_first_line_indent(editor: "EditorWidget", indent_pt: float) -> None:
        """Set the first-line indent in points (positive = indent, negative = hanging)."""
        fmt = QTextBlockFormat()
        fmt.setTextIndent(indent_pt)
        _apply_block_fmt(editor, fmt)

    # ------------------------------------------------------------------ #
    # Headings H1–H6                                                      #
    # ------------------------------------------------------------------ #

    # (size_pt, QFont weight, colour hex — designed for dark theme; auto-adapt in future)
    _HEADING_STYLES: dict[int, tuple[float, int, str]] = {
        1: (26.0, QFont.Bold,     "#89b4fa"),
        2: (22.0, QFont.Bold,     "#89b4fa"),
        3: (18.0, QFont.Bold,     "#cba6f7"),
        4: (15.0, QFont.Bold,     "#cba6f7"),
        5: (13.0, QFont.DemiBold, "#a6e3a1"),
        6: (11.0, QFont.DemiBold, "#a6e3a1"),
    }

    @staticmethod
    def apply_heading(editor: "EditorWidget", level: int) -> None:
        """
        Apply a heading style to the current paragraph.

        Parameters
        ----------
        level : int
            1–6 for H1–H6. Use 0 to reset to normal body text.
        """
        cursor = editor.textCursor()
        cursor.beginEditBlock()

        if level == 0:
            cursor.setCharFormat(QTextCharFormat())
            bfmt = QTextBlockFormat()
            bfmt.setHeadingLevel(0)
            bfmt.setTopMargin(0)
            bfmt.setBottomMargin(0)
            cursor.mergeBlockFormat(bfmt)
        else:
            level = max(1, min(6, level))
            size_pt, weight, colour = FormattingEngine._HEADING_STYLES[level]

            cfmt = QTextCharFormat()
            cfmt.setFontPointSize(size_pt)
            cfmt.setFontWeight(weight)
            cfmt.setForeground(QColor(colour))
            cursor.setCharFormat(cfmt)

            bfmt = QTextBlockFormat()
            bfmt.setHeadingLevel(level)
            bfmt.setTopMargin(size_pt * 0.6)
            bfmt.setBottomMargin(size_pt * 0.3)
            cursor.mergeBlockFormat(bfmt)

        cursor.endEditBlock()
        log.debug("Heading level applied: %d", level)

    # ------------------------------------------------------------------ #
    # State queries — used by toolbar to sync checked/active states       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def is_bold(editor: "EditorWidget") -> bool:
        return _char_fmt(editor).fontWeight() == QFont.Bold

    @staticmethod
    def is_italic(editor: "EditorWidget") -> bool:
        return _char_fmt(editor).fontItalic()

    @staticmethod
    def is_underline(editor: "EditorWidget") -> bool:
        return _char_fmt(editor).fontUnderline()

    @staticmethod
    def is_strikethrough(editor: "EditorWidget") -> bool:
        return _char_fmt(editor).fontStrikeOut()

    @staticmethod
    def is_subscript(editor: "EditorWidget") -> bool:
        return _char_fmt(editor).verticalAlignment() == QTextCharFormat.AlignSubScript

    @staticmethod
    def is_superscript(editor: "EditorWidget") -> bool:
        return _char_fmt(editor).verticalAlignment() == QTextCharFormat.AlignSuperScript

    @staticmethod
    def current_font_family(editor: "EditorWidget") -> str:
        """Return the font family at the cursor, falling back to the widget font."""
        families = _char_fmt(editor).fontFamilies()
        if families:
            return families[0]
        return editor.font().family()

    @staticmethod
    def current_font_size(editor: "EditorWidget") -> float:
        """Return the font point size at the cursor, falling back to the widget font."""
        size = _char_fmt(editor).fontPointSize()
        return size if size > 0 else editor.font().pointSizeF()

    @staticmethod
    def current_alignment(editor: "EditorWidget") -> Qt.AlignmentFlag:
        """Return the alignment of the paragraph at the cursor."""
        return editor.alignment()

    @staticmethod
    def current_heading_level(editor: "EditorWidget") -> int:
        """Return the heading level (0–6) of the paragraph at the cursor."""
        return editor.textCursor().blockFormat().headingLevel()
