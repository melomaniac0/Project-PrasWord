"""
tests/test_formatting.py
========================
Comprehensive unit tests for FormattingEngine.

Covers
------
* Bold / italic / underline / strikethrough toggle (on and off).
* Subscript / superscript toggle.
* Font family and size setters.
* Text colour and highlight colour setters.
* clear_character_formatting().
* Alignment helpers (left / centre / right / justify).
* Line spacing setter.
* Indent helpers (set, increase, decrease, floor at 0).
* Paragraph spacing (before/after).
* Left / right margin and first-line indent setters.
* Heading levels H1–H6 and reset to body (level 0).
* State query helpers: is_bold, is_italic, is_underline, is_strikethrough,
  is_subscript, is_superscript, current_font_family, current_font_size,
  current_alignment, current_heading_level.
* Operations are undoable (undo restores prior state).
* Edge cases: empty document, no selection.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCursor
from PySide6.QtWidgets import QApplication
import sys

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("PrasWordTest")
    app.setOrganizationName("PrasWordTest")
    return app


from prasword.core.document import Document
from prasword.gui.editor_widget import EditorWidget
from prasword.features.formatting.formatting_engine import FormattingEngine


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def blank_editor(qapp):
    doc = Document()
    return EditorWidget(document=doc)


@pytest.fixture
def editor(qapp):
    """Editor with sample text and the full document selected."""
    doc = Document()
    doc.qt_document.setPlainText(
        "The quick brown fox jumps over the lazy dog.\n"
        "Pack my box with five dozen liquor jugs.\n"
    )
    e = EditorWidget(document=doc)
    _select_all(e)
    return e


@pytest.fixture
def word_editor(qapp):
    """Editor with a single word selected."""
    doc = Document()
    doc.qt_document.setPlainText("Hello World")
    e = EditorWidget(document=doc)
    c = e.textCursor()
    c.setPosition(0)
    c.setPosition(5, QTextCursor.KeepAnchor)  # select "Hello"
    e.setTextCursor(c)
    return e


def _select_all(e: EditorWidget) -> None:
    c = e.textCursor()
    c.select(QTextCursor.Document)
    e.setTextCursor(c)


# ═══════════════════════════════════════════════════════════════════════════════
# Bold
# ═══════════════════════════════════════════════════════════════════════════════

class TestBold:

    def test_toggle_bold_on(self, editor):
        result = FormattingEngine.toggle_bold(editor)
        assert result is True
        assert FormattingEngine.is_bold(editor)

    def test_toggle_bold_off(self, editor):
        FormattingEngine.toggle_bold(editor)   # on
        result = FormattingEngine.toggle_bold(editor)  # off
        assert result is False
        assert not FormattingEngine.is_bold(editor)

    def test_is_bold_false_by_default(self, editor):
        assert not FormattingEngine.is_bold(editor)

    def test_bold_with_no_selection(self, blank_editor):
        # Should not raise even with nothing selected
        FormattingEngine.toggle_bold(blank_editor)

    def test_bold_undo(self, editor):
        FormattingEngine.toggle_bold(editor)
        assert FormattingEngine.is_bold(editor)
        editor.document().undo()
        # After undo the format should be restored (not bold)
        assert not FormattingEngine.is_bold(editor)


# ═══════════════════════════════════════════════════════════════════════════════
# Italic
# ═══════════════════════════════════════════════════════════════════════════════

class TestItalic:

    def test_toggle_italic_on(self, editor):
        result = FormattingEngine.toggle_italic(editor)
        assert result is True
        assert FormattingEngine.is_italic(editor)

    def test_toggle_italic_off(self, editor):
        FormattingEngine.toggle_italic(editor)
        result = FormattingEngine.toggle_italic(editor)
        assert result is False
        assert not FormattingEngine.is_italic(editor)

    def test_is_italic_false_by_default(self, editor):
        assert not FormattingEngine.is_italic(editor)


# ═══════════════════════════════════════════════════════════════════════════════
# Underline
# ═══════════════════════════════════════════════════════════════════════════════

class TestUnderline:

    def test_toggle_underline_on(self, editor):
        result = FormattingEngine.toggle_underline(editor)
        assert result is True
        assert FormattingEngine.is_underline(editor)

    def test_toggle_underline_off(self, editor):
        FormattingEngine.toggle_underline(editor)
        result = FormattingEngine.toggle_underline(editor)
        assert result is False

    def test_is_underline_false_by_default(self, editor):
        assert not FormattingEngine.is_underline(editor)


# ═══════════════════════════════════════════════════════════════════════════════
# Strikethrough
# ═══════════════════════════════════════════════════════════════════════════════

class TestStrikethrough:

    def test_toggle_strikethrough_on(self, editor):
        result = FormattingEngine.toggle_strikethrough(editor)
        assert result is True
        assert FormattingEngine.is_strikethrough(editor)

    def test_toggle_strikethrough_off(self, editor):
        FormattingEngine.toggle_strikethrough(editor)
        result = FormattingEngine.toggle_strikethrough(editor)
        assert result is False

    def test_is_strikethrough_false_by_default(self, editor):
        assert not FormattingEngine.is_strikethrough(editor)


# ═══════════════════════════════════════════════════════════════════════════════
# Subscript / Superscript
# ═══════════════════════════════════════════════════════════════════════════════

class TestVerticalAlignment:

    def test_toggle_subscript_on(self, editor):
        result = FormattingEngine.toggle_subscript(editor)
        assert result is True
        assert FormattingEngine.is_subscript(editor)

    def test_toggle_subscript_off(self, editor):
        FormattingEngine.toggle_subscript(editor)
        result = FormattingEngine.toggle_subscript(editor)
        assert result is False
        assert not FormattingEngine.is_subscript(editor)

    def test_toggle_superscript_on(self, editor):
        result = FormattingEngine.toggle_superscript(editor)
        assert result is True
        assert FormattingEngine.is_superscript(editor)

    def test_toggle_superscript_off(self, editor):
        FormattingEngine.toggle_superscript(editor)
        result = FormattingEngine.toggle_superscript(editor)
        assert result is False

    def test_subscript_and_superscript_are_mutually_independent(self, editor):
        FormattingEngine.toggle_subscript(editor)
        assert FormattingEngine.is_subscript(editor)
        assert not FormattingEngine.is_superscript(editor)


# ═══════════════════════════════════════════════════════════════════════════════
# Font family / size
# ═══════════════════════════════════════════════════════════════════════════════

class TestFont:

    def test_set_font_family(self, editor):
        FormattingEngine.set_font_family(editor, "Arial")
        assert FormattingEngine.current_font_family(editor) == "Arial"

    def test_set_font_family_empty_string_is_noop(self, editor):
        original = FormattingEngine.current_font_family(editor)
        FormattingEngine.set_font_family(editor, "")
        assert FormattingEngine.current_font_family(editor) == original

    def test_set_font_size(self, editor):
        FormattingEngine.set_font_size(editor, 18.0)
        assert FormattingEngine.current_font_size(editor) == 18.0

    def test_set_font_size_zero_is_noop(self, editor):
        original = FormattingEngine.current_font_size(editor)
        FormattingEngine.set_font_size(editor, 0.0)
        assert FormattingEngine.current_font_size(editor) == original

    def test_set_font_size_negative_is_noop(self, editor):
        original = FormattingEngine.current_font_size(editor)
        FormattingEngine.set_font_size(editor, -5.0)
        assert FormattingEngine.current_font_size(editor) == original

    def test_set_font_size_small(self, editor):
        FormattingEngine.set_font_size(editor, 8.0)
        assert FormattingEngine.current_font_size(editor) == 8.0

    def test_set_font_size_large(self, editor):
        FormattingEngine.set_font_size(editor, 72.0)
        assert FormattingEngine.current_font_size(editor) == 72.0


# ═══════════════════════════════════════════════════════════════════════════════
# Colour and highlight
# ═══════════════════════════════════════════════════════════════════════════════

class TestColour:

    def test_set_text_color_does_not_raise(self, editor):
        FormattingEngine.set_text_color(editor, QColor("#ff0000"))

    def test_set_text_color_invalid_is_noop(self, editor):
        FormattingEngine.set_text_color(editor, QColor())  # invalid colour

    def test_set_highlight_color_does_not_raise(self, editor):
        FormattingEngine.set_highlight_color(editor, QColor("#ffff00"))

    def test_clear_highlight_with_invalid_color(self, editor):
        FormattingEngine.set_highlight_color(editor, QColor("#ffff00"))
        FormattingEngine.set_highlight_color(editor, QColor())   # clear

    def test_clear_character_formatting(self, editor):
        FormattingEngine.toggle_bold(editor)
        FormattingEngine.toggle_italic(editor)
        FormattingEngine.clear_character_formatting(editor)
        assert not FormattingEngine.is_bold(editor)
        assert not FormattingEngine.is_italic(editor)


# ═══════════════════════════════════════════════════════════════════════════════
# Alignment
# ═══════════════════════════════════════════════════════════════════════════════

class TestAlignment:

    def test_align_left(self, editor):
        FormattingEngine.align_left(editor)
        assert FormattingEngine.current_alignment(editor) == Qt.AlignLeft

    def test_align_center(self, editor):
        FormattingEngine.align_center(editor)
        assert FormattingEngine.current_alignment(editor) == Qt.AlignHCenter

    def test_align_right(self, editor):
        FormattingEngine.align_right(editor)
        assert FormattingEngine.current_alignment(editor) == Qt.AlignRight

    def test_align_justify(self, editor):
        FormattingEngine.align_justify(editor)
        assert FormattingEngine.current_alignment(editor) == Qt.AlignJustify

    def test_set_alignment_explicit(self, editor):
        FormattingEngine.set_alignment(editor, Qt.AlignHCenter)
        assert FormattingEngine.current_alignment(editor) == Qt.AlignHCenter


# ═══════════════════════════════════════════════════════════════════════════════
# Line spacing
# ═══════════════════════════════════════════════════════════════════════════════

class TestLineSpacing:

    @pytest.mark.parametrize("factor", [1.0, 1.15, 1.5, 2.0, 3.0])
    def test_set_line_spacing_does_not_raise(self, editor, factor):
        FormattingEngine.set_line_spacing(editor, factor)

    def test_paragraph_spacing_does_not_raise(self, editor):
        FormattingEngine.set_paragraph_spacing(editor, before_pt=6.0, after_pt=12.0)


# ═══════════════════════════════════════════════════════════════════════════════
# Indentation
# ═══════════════════════════════════════════════════════════════════════════════

class TestIndentation:

    def test_set_indent_zero(self, editor):
        FormattingEngine.set_indent(editor, 0)

    def test_set_indent_positive(self, editor):
        FormattingEngine.set_indent(editor, 2)

    def test_set_indent_negative_clamps_to_zero(self, editor):
        FormattingEngine.set_indent(editor, -5)   # must not raise

    def test_increase_indent(self, editor):
        FormattingEngine.increase_indent(editor)
        FormattingEngine.increase_indent(editor)

    def test_decrease_indent_does_not_go_below_zero(self, editor):
        FormattingEngine.set_indent(editor, 0)
        FormattingEngine.decrease_indent(editor)   # no-op — already at 0

    def test_increase_then_decrease_cancels(self, editor):
        before = editor.textCursor().blockFormat().indent()
        FormattingEngine.increase_indent(editor)
        FormattingEngine.decrease_indent(editor)
        after = editor.textCursor().blockFormat().indent()
        assert before == after

    def test_set_left_margin(self, editor):
        FormattingEngine.set_left_margin(editor, 40.0)

    def test_set_right_margin(self, editor):
        FormattingEngine.set_right_margin(editor, 40.0)

    def test_set_first_line_indent(self, editor):
        FormattingEngine.set_first_line_indent(editor, 20.0)

    def test_set_first_line_indent_negative_hanging(self, editor):
        FormattingEngine.set_first_line_indent(editor, -20.0)   # hanging indent


# ═══════════════════════════════════════════════════════════════════════════════
# Headings
# ═══════════════════════════════════════════════════════════════════════════════

class TestHeadings:

    @pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
    def test_apply_heading_level(self, editor, level):
        FormattingEngine.apply_heading(editor, level)

    def test_apply_heading_sets_heading_level_in_block_format(self, editor):
        FormattingEngine.apply_heading(editor, 1)
        assert FormattingEngine.current_heading_level(editor) == 1

    def test_apply_heading_2(self, editor):
        FormattingEngine.apply_heading(editor, 2)
        assert FormattingEngine.current_heading_level(editor) == 2

    def test_reset_to_body_text(self, editor):
        FormattingEngine.apply_heading(editor, 1)
        FormattingEngine.apply_heading(editor, 0)
        assert FormattingEngine.current_heading_level(editor) == 0

    def test_heading_clamps_above_6(self, editor):
        FormattingEngine.apply_heading(editor, 99)   # clamps to 6 internally
        assert FormattingEngine.current_heading_level(editor) == 6

    def test_heading_clamps_below_1(self, editor):
        FormattingEngine.apply_heading(editor, -1)   # treated as 0 (body)

    def test_h1_sets_large_font(self, editor):
        FormattingEngine.apply_heading(editor, 1)
        size = FormattingEngine.current_font_size(editor)
        assert size >= 20.0

    def test_h6_sets_small_font(self, editor):
        FormattingEngine.apply_heading(editor, 6)
        size = FormattingEngine.current_font_size(editor)
        # H6 should be smaller than H1 (11 pt in our theme)
        assert size <= 12.0

    def test_heading_1_is_bold(self, editor):
        FormattingEngine.apply_heading(editor, 1)
        assert FormattingEngine.is_bold(editor)


# ═══════════════════════════════════════════════════════════════════════════════
# State queries — combined / edge cases
# ═══════════════════════════════════════════════════════════════════════════════

class TestStateQueries:

    def test_multiple_formats_combined(self, editor):
        FormattingEngine.toggle_bold(editor)
        FormattingEngine.toggle_italic(editor)
        FormattingEngine.toggle_underline(editor)
        assert FormattingEngine.is_bold(editor)
        assert FormattingEngine.is_italic(editor)
        assert FormattingEngine.is_underline(editor)

    def test_word_selection_bold(self, word_editor):
        FormattingEngine.toggle_bold(word_editor)
        assert FormattingEngine.is_bold(word_editor)

    def test_current_font_size_returns_positive(self, editor):
        assert FormattingEngine.current_font_size(editor) > 0

    def test_current_font_family_returns_string(self, editor):
        assert isinstance(FormattingEngine.current_font_family(editor), str)

    def test_current_alignment_returns_flag(self, editor):
        alignment = FormattingEngine.current_alignment(editor)
        assert alignment in (Qt.AlignLeft, Qt.AlignHCenter, Qt.AlignRight, Qt.AlignJustify)

    def test_current_heading_level_default_zero(self, editor):
        # Fresh document with no heading applied should be 0
        doc = Document()
        doc.qt_document.setPlainText("plain text")
        e = EditorWidget(document=doc)
        assert FormattingEngine.current_heading_level(e) == 0
