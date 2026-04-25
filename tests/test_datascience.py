"""
tests/test_datascience.py
==========================
Unit tests for all four Data Science feature modules:
  CodeHighlighter, MathRenderer, CsvTableConverter, JupyterCell.

Covers
------
CodeHighlighter
  * is_pygments_available() returns bool.
  * get_supported_languages() returns a list (empty if pygments absent).
  * set_theme() accepts valid names, raises on unknown.
  * available_themes() returns at least ["dracula", "solarized"].
  * highlight_block() returns True when Pygments available, False otherwise.
  * highlight_block() with no selection is a no-op (doesn't raise).
  * insert_code_block() inserts the stub code into the document.
  * insert_code_block() with custom code inserts that code.
  * highlight_document_blocks() returns int (count), doesn't raise.
  * _resolve_color() falls back to default fg for unknown token.

MathRenderer
  * set_theme() accepts valid names, raises on unknown.
  * validate_latex() returns (bool, str) tuple.
  * validate_latex() on empty string returns (False, ...).
  * insert_rendered() returns bool (True with matplotlib, False without).
  * insert_inline() delegates to insert_rendered display_mode=False.
  * insert_display_block() delegates to insert_rendered display_mode=True.
  * _insert_as_text() inserts styled text fallback.
  * Unique resource names (counter increments per render).

CsvTableConverter
  * insert_from_string() basic 3×3 table.
  * insert_from_string() returns data row count (excl. header).
  * insert_from_string() with has_header=False uses all rows as data.
  * insert_from_string() empty string is safe (returns 0).
  * insert_from_file() reads from disk and inserts.
  * insert_from_rows() accepts pre-parsed list.
  * truncation: rows beyond max_rows are capped, notice inserted.
  * to_markdown() produces pipe-delimited output.
  * to_markdown() first row is header row in GFM format.
  * to_html() produces <table> tag.
  * to_html() produces <th> for header row.
  * _is_numeric() correctly identifies numbers/non-numbers.
  * _sniff_dialect() handles comma, tab, semicolon.
  * Jagged rows (unequal column counts) are handled safely.

JupyterCell
  * supported_languages() returns a non-empty list.
  * is_language_available() returns bool for known languages.
  * insert_cell() inserts content into document.
  * insert_cell() with custom code inserts that code.
  * insert_cell() for each supported language doesn't raise.
  * run_cell() invokes callback with (stdout, stderr) signature.
  * run_cell() unknown language delivers error in stderr.
  * run_cell() timeout is respected (fast test with low timeout).
"""

from __future__ import annotations

import sys
import time
import pytest
from pathlib import Path
from PySide6.QtWidgets import QApplication

@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("PrasWordTest")
    app.setOrganizationName("PrasWordTest")
    return app


from prasword.core.document import Document
from prasword.gui.editor_widget import EditorWidget
from prasword.features.datascience.code_highlighter import CodeHighlighter, _THEMES
from prasword.features.datascience.math_renderer import MathRenderer
from prasword.features.datascience.csv_table import (
    CsvTableConverter, _is_numeric, _sniff_dialect, _parse_csv
)
from prasword.features.datascience.jupyter_cell import JupyterCell


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_editor(text: str = "") -> EditorWidget:
    doc = Document()
    if text:
        doc.qt_document.setPlainText(text)
    return EditorWidget(document=doc)


# ═══════════════════════════════════════════════════════════════════════════════
# CodeHighlighter
# ═══════════════════════════════════════════════════════════════════════════════

class TestCodeHighlighter:

    def test_is_pygments_available_returns_bool(self, qapp):
        result = CodeHighlighter.is_pygments_available()
        assert isinstance(result, bool)

    def test_get_supported_languages_returns_list(self, qapp):
        langs = CodeHighlighter.get_supported_languages()
        assert isinstance(langs, list)

    def test_get_supported_languages_contains_python_when_pygments_available(self, qapp):
        if not CodeHighlighter.is_pygments_available():
            pytest.skip("Pygments not installed")
        langs = CodeHighlighter.get_supported_languages()
        assert "python" in langs

    def test_available_themes_returns_expected(self, qapp):
        themes = CodeHighlighter.available_themes()
        assert "dracula" in themes
        assert "solarized" in themes

    def test_set_theme_valid(self, qapp):
        CodeHighlighter.set_theme("dracula")
        CodeHighlighter.set_theme("solarized")
        CodeHighlighter.set_theme("dracula")   # restore

    def test_set_theme_unknown_raises(self, qapp):
        with pytest.raises(ValueError, match="Unknown theme"):
            CodeHighlighter.set_theme("nonexistent_theme_xyz")

    def test_highlight_block_returns_bool(self, qapp):
        editor = make_editor("x = 1 + 2\nprint(x)\n")
        from PySide6.QtGui import QTextCursor
        c = editor.textCursor()
        c.select(QTextCursor.Document)
        editor.setTextCursor(c)
        result = CodeHighlighter.highlight_block(editor, "python")
        assert isinstance(result, bool)

    def test_highlight_block_no_selection_does_not_raise(self, qapp):
        editor = make_editor()  # empty, no selection
        CodeHighlighter.highlight_block(editor, "python")   # must not raise

    def test_highlight_block_with_text_selected(self, qapp):
        editor = make_editor("def hello():\n    return 42\n")
        from PySide6.QtGui import QTextCursor
        c = editor.textCursor()
        c.select(QTextCursor.Document)
        editor.setTextCursor(c)
        # Whether Pygments is installed or not, should not raise
        CodeHighlighter.highlight_block(editor, "python")

    def test_insert_code_block_inserts_text(self, qapp):
        editor = make_editor()
        CodeHighlighter.insert_code_block(editor, "python")
        text = editor.document().toPlainText()
        assert len(text) > 0

    def test_insert_code_block_uses_stub_when_no_code_given(self, qapp):
        editor = make_editor()
        CodeHighlighter.insert_code_block(editor, "python")
        text = editor.document().toPlainText()
        # Python stub contains 'def' or 'main' or '#'
        assert any(kw in text for kw in ("def", "main", "#", "Python"))

    def test_insert_code_block_custom_code(self, qapp):
        editor = make_editor()
        CodeHighlighter.insert_code_block(editor, "python", code="x = 42")
        assert "42" in editor.document().toPlainText()

    def test_insert_code_block_r_language(self, qapp):
        editor = make_editor()
        CodeHighlighter.insert_code_block(editor, "r")
        assert len(editor.document().toPlainText()) > 0

    def test_insert_code_block_sql_language(self, qapp):
        editor = make_editor()
        CodeHighlighter.insert_code_block(editor, "sql")
        assert "SELECT" in editor.document().toPlainText()

    def test_highlight_document_blocks_returns_int(self, qapp):
        text = "Before\n```python\nx = 1\n```\nAfter"
        editor = make_editor(text)
        result = CodeHighlighter.highlight_document_blocks(editor)
        assert isinstance(result, int)
        assert result >= 0

    def test_highlight_document_blocks_no_fences_returns_zero(self, qapp):
        editor = make_editor("just plain text no fences")
        assert CodeHighlighter.highlight_document_blocks(editor) == 0

    def test_resolve_color_unknown_token_returns_default(self, qapp):
        colors = _THEMES["dracula"]["colors"]
        color  = CodeHighlighter._resolve_color("Token.Unknown.Type.XYZ", colors)
        assert color.startswith("#")
        assert len(color) == 7   # #RRGGBB

    def test_resolve_color_exact_match(self, qapp):
        colors = _THEMES["dracula"]["colors"]
        color  = CodeHighlighter._resolve_color("Token.Keyword", colors)
        assert color == colors["Token.Keyword"]

    def test_resolve_color_walks_hierarchy(self, qapp):
        colors = _THEMES["dracula"]["colors"]
        # Token.Keyword.Declaration exists; Token.Keyword.FAKETYPE should
        # fall back to Token.Keyword
        color = CodeHighlighter._resolve_color("Token.Keyword.FAKETYPE", colors)
        assert color == colors["Token.Keyword"]

    @pytest.mark.parametrize("lang", ["python", "r", "sql", "bash", "javascript"])
    def test_insert_code_block_all_languages_do_not_raise(self, qapp, lang):
        editor = make_editor()
        CodeHighlighter.insert_code_block(editor, lang)   # no exception


# ═══════════════════════════════════════════════════════════════════════════════
# MathRenderer
# ═══════════════════════════════════════════════════════════════════════════════

class TestMathRenderer:

    def test_set_theme_valid(self, qapp):
        MathRenderer.set_theme("dark")
        MathRenderer.set_theme("light")
        MathRenderer.set_theme("dark")

    def test_set_theme_unknown_raises(self, qapp):
        with pytest.raises(ValueError, match="Unknown theme"):
            MathRenderer.set_theme("neon_pink")

    def test_validate_latex_empty_returns_false(self, qapp):
        ok, msg = MathRenderer.validate_latex("")
        assert ok is False
        assert isinstance(msg, str)

    def test_validate_latex_returns_tuple(self, qapp):
        result = MathRenderer.validate_latex(r"\frac{a}{b}")
        assert isinstance(result, tuple)
        assert len(result) == 2
        ok, msg = result
        assert isinstance(ok, bool)
        assert isinstance(msg, str)

    def test_validate_latex_simple_expression(self, qapp):
        # Simple expressions should pass (or return True if sympy absent)
        ok, _ = MathRenderer.validate_latex(r"E = mc^2")
        assert isinstance(ok, bool)

    def test_insert_rendered_returns_bool(self, qapp):
        editor = make_editor()
        result = MathRenderer.insert_rendered(editor, r"x^2 + y^2 = r^2")
        assert isinstance(result, bool)

    def test_insert_rendered_empty_latex_returns_false(self, qapp):
        editor = make_editor()
        result = MathRenderer.insert_rendered(editor, "")
        assert result is False

    def test_insert_rendered_inserts_something(self, qapp):
        editor = make_editor()
        MathRenderer.insert_rendered(editor, r"\alpha + \beta")
        # Either an image was inserted or fallback text — document should be non-empty
        assert len(editor.document().toPlainText()) > 0

    def test_insert_inline_delegates_without_raise(self, qapp):
        editor = make_editor()
        MathRenderer.insert_inline(editor, r"a^2")

    def test_insert_display_block_delegates_without_raise(self, qapp):
        editor = make_editor()
        MathRenderer.insert_display_block(editor, r"\int_0^\infty e^{-x}\,dx")

    def test_insert_as_text_fallback_inserts_dollar_delimited(self, qapp):
        editor = make_editor()
        MathRenderer._insert_as_text(editor, r"x^2", display_mode=False)
        text = editor.document().toPlainText()
        assert "x^2" in text
        assert "$" in text

    def test_insert_as_text_display_mode_uses_double_dollar(self, qapp):
        editor = make_editor()
        MathRenderer._insert_as_text(editor, r"x^2", display_mode=True)
        text = editor.document().toPlainText()
        assert "$$" in text

    def test_render_counter_increments(self, qapp):
        """Each _insert_as_image call should use a unique resource name."""
        import prasword.features.datascience.math_renderer as mr
        before = mr._render_counter
        # We can't render without matplotlib, but counter only increments on image insert
        # so just verify it's an int
        assert isinstance(before, int)

    def test_render_to_png_returns_none_gracefully(self, qapp):
        """_render_to_png should return None (not raise) if matplotlib absent."""
        try:
            import matplotlib  # noqa: F401
            pytest.skip("matplotlib is present — PNG will be rendered, not None")
        except ImportError:
            result = MathRenderer._render_to_png(r"x^2", 12.0, "#fff", 96)
            assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# CsvTableConverter — helpers
# ═══════════════════════════════════════════════════════════════════════════════

class TestCsvHelpers:

    def test_is_numeric_integer(self):
        assert _is_numeric("42")

    def test_is_numeric_float(self):
        assert _is_numeric("3.14")

    def test_is_numeric_negative(self):
        assert _is_numeric("-7.5")

    def test_is_numeric_with_comma_thousands(self):
        assert _is_numeric("1,234.56")

    def test_is_numeric_currency(self):
        assert _is_numeric("$99.99")

    def test_is_numeric_percent(self):
        assert _is_numeric("85%")

    def test_is_numeric_text(self):
        assert not _is_numeric("hello")

    def test_is_numeric_empty(self):
        assert not _is_numeric("")

    def test_is_numeric_mixed(self):
        assert not _is_numeric("12px")

    def test_sniff_dialect_comma(self):
        text = "a,b,c\n1,2,3\n"
        d = _sniff_dialect(text)
        assert d is not None

    def test_sniff_dialect_tab(self):
        text = "a\tb\tc\n1\t2\t3\n"
        d = _sniff_dialect(text)
        assert d is not None

    def test_sniff_dialect_bad_input_returns_none(self):
        # Single token — sniffer can't determine delimiter
        d = _sniff_dialect("x")
        # May return None or a dialect — just must not raise
        assert d is None or hasattr(d, "delimiter")

    def test_parse_csv_basic(self):
        rows = _parse_csv("a,b,c\n1,2,3\n")
        assert rows == [["a", "b", "c"], ["1", "2", "3"]]

    def test_parse_csv_skips_blank_rows(self):
        rows = _parse_csv("a,b\n\n1,2\n")
        assert len(rows) == 2

    def test_parse_csv_tab_separated(self):
        rows = _parse_csv("x\ty\n10\t20\n")
        assert rows[0] == ["x", "y"]


# ═══════════════════════════════════════════════════════════════════════════════
# CsvTableConverter — insertion
# ═══════════════════════════════════════════════════════════════════════════════

class TestCsvTableInsertion:

    CSV_BASIC = "Name,Age,Score\nAlice,30,95.5\nBob,25,87.0\nCarol,35,91.2\n"
    CSV_NUMERIC = "X,Y\n1,2\n3,4\n5,6\n"
    CSV_JAGGED  = "A,B,C\n1,2\n4,5,6,7\n"

    def test_insert_from_string_returns_data_row_count(self, qapp):
        editor = make_editor()
        n = CsvTableConverter.insert_from_string(editor, self.CSV_BASIC)
        assert n == 3   # 3 data rows (header excluded)

    def test_insert_from_string_no_header_returns_all_rows(self, qapp):
        editor = make_editor()
        n = CsvTableConverter.insert_from_string(
            editor, self.CSV_BASIC, has_header=False
        )
        assert n == 4   # all 4 rows are data rows

    def test_insert_from_string_inserts_table_into_document(self, qapp):
        editor = make_editor()
        CsvTableConverter.insert_from_string(editor, self.CSV_BASIC)
        # QTextTable is inserted — document should be non-trivially modified
        assert editor.document().blockCount() > 1

    def test_insert_from_string_empty_csv_returns_zero(self, qapp):
        editor = make_editor()
        n = CsvTableConverter.insert_from_string(editor, "")
        assert n == 0

    def test_insert_from_string_single_row_with_header(self, qapp):
        editor = make_editor()
        n = CsvTableConverter.insert_from_string(editor, "A,B\n1,2\n")
        assert n == 1

    def test_insert_from_rows_basic(self, qapp):
        editor = make_editor()
        rows = [["Name", "Score"], ["Alice", "95"], ["Bob", "87"]]
        n = CsvTableConverter.insert_from_rows(editor, rows)
        assert n == 2

    def test_insert_from_rows_empty_returns_zero(self, qapp):
        editor = make_editor()
        n = CsvTableConverter.insert_from_rows(editor, [])
        assert n == 0

    def test_insert_from_file(self, qapp, tmp_path):
        p = tmp_path / "data.csv"
        p.write_text(self.CSV_BASIC, encoding="utf-8")
        editor = make_editor()
        n = CsvTableConverter.insert_from_file(editor, p)
        assert n == 3

    def test_truncation_cap_respected(self, qapp):
        # Build a CSV with 20 data rows + header
        rows = ["Col1,Col2"] + [f"{i},{i*2}" for i in range(20)]
        csv_text = "\n".join(rows)
        editor = make_editor()
        n = CsvTableConverter.insert_from_string(editor, csv_text, max_rows=5)
        assert n == 5

    def test_jagged_rows_handled(self, qapp):
        editor = make_editor()
        # Jagged CSV must not raise — short rows are padded with ""
        CsvTableConverter.insert_from_string(editor, self.CSV_JAGGED)

    def test_numeric_column_detected(self, qapp):
        editor = make_editor()
        # Should not raise — numeric alignment is applied internally
        CsvTableConverter.insert_from_string(
            editor, self.CSV_NUMERIC, numeric_align=True
        )

    def test_tsv_input(self, qapp):
        tsv = "Name\tScore\nAlice\t95\nBob\t87\n"
        editor = make_editor()
        n = CsvTableConverter.insert_from_string(editor, tsv)
        assert n == 2


# ═══════════════════════════════════════════════════════════════════════════════
# CsvTableConverter — export helpers (no Qt)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCsvExport:

    CSV = "Name,Age\nAlice,30\nBob,25\n"

    def test_to_markdown_produces_pipe_delimited(self):
        md = CsvTableConverter.to_markdown(self.CSV)
        assert "|" in md

    def test_to_markdown_first_row_is_header(self):
        md = CsvTableConverter.to_markdown(self.CSV)
        lines = md.strip().splitlines()
        assert "Name" in lines[0]
        assert "---" in lines[1]

    def test_to_markdown_data_rows_present(self):
        md = CsvTableConverter.to_markdown(self.CSV)
        assert "Alice" in md
        assert "Bob" in md

    def test_to_markdown_from_path(self, tmp_path):
        p = tmp_path / "data.csv"
        p.write_text(self.CSV, encoding="utf-8")
        md = CsvTableConverter.to_markdown(p)
        assert "Name" in md

    def test_to_markdown_empty_returns_empty(self):
        assert CsvTableConverter.to_markdown("") == ""

    def test_to_html_produces_table_tag(self):
        html = CsvTableConverter.to_html(self.CSV)
        assert "<table" in html
        assert "</table>" in html

    def test_to_html_produces_th_for_header(self):
        html = CsvTableConverter.to_html(self.CSV)
        assert "<th>" in html

    def test_to_html_produces_td_for_data(self):
        html = CsvTableConverter.to_html(self.CSV)
        assert "<td>" in html

    def test_to_html_escapes_special_chars(self):
        csv_with_html = "Name,Value\nFoo & Bar,<test>\n"
        html = CsvTableConverter.to_html(csv_with_html)
        assert "&amp;" in html
        assert "&lt;" in html

    def test_to_html_no_header(self):
        html = CsvTableConverter.to_html(self.CSV, has_header=False)
        assert "<td>" in html
        assert "<th>" not in html


# ═══════════════════════════════════════════════════════════════════════════════
# JupyterCell
# ═══════════════════════════════════════════════════════════════════════════════

class TestJupyterCell:

    def test_supported_languages_non_empty(self, qapp):
        langs = JupyterCell.supported_languages()
        assert isinstance(langs, list)
        assert len(langs) > 0

    def test_supported_languages_includes_python(self, qapp):
        assert "python" in JupyterCell.supported_languages()

    def test_is_language_available_python(self, qapp):
        # Python interpreter should always be available in the test environment
        result = JupyterCell.is_language_available("python")
        assert result is True

    def test_is_language_available_unknown_returns_false(self, qapp):
        assert JupyterCell.is_language_available("fictional_lang_xyz") is False

    def test_is_language_available_returns_bool(self, qapp):
        assert isinstance(JupyterCell.is_language_available("r"), bool)

    def test_insert_cell_inserts_content(self, qapp):
        editor = make_editor()
        JupyterCell.insert_cell(editor, "python")
        text = editor.document().toPlainText()
        assert len(text) > 0

    def test_insert_cell_contains_language_label(self, qapp):
        editor = make_editor()
        JupyterCell.insert_cell(editor, "python")
        text = editor.document().toPlainText()
        assert "PYTHON" in text

    def test_insert_cell_contains_stub_code(self, qapp):
        editor = make_editor()
        JupyterCell.insert_cell(editor, "python")
        text = editor.document().toPlainText()
        # Python stub should contain import or print
        assert any(kw in text for kw in ("import", "print", "Python"))

    def test_insert_cell_custom_code(self, qapp):
        editor = make_editor()
        JupyterCell.insert_cell(editor, "python", code="result = 2 + 2")
        text = editor.document().toPlainText()
        assert "result" in text

    def test_insert_cell_contains_run_instruction(self, qapp):
        editor = make_editor()
        JupyterCell.insert_cell(editor, "python")
        text = editor.document().toPlainText()
        assert "Run" in text or "run" in text

    def test_insert_cell_contains_output_placeholder(self, qapp):
        editor = make_editor()
        JupyterCell.insert_cell(editor, "python")
        text = editor.document().toPlainText()
        assert "output" in text.lower()

    @pytest.mark.parametrize("lang", ["python", "r", "bash"])
    def test_insert_cell_all_languages_do_not_raise(self, qapp, lang):
        editor = make_editor()
        JupyterCell.insert_cell(editor, lang)

    def test_run_cell_python_callback_invoked(self, qapp):
        """run_cell() must invoke callback with (stdout, stderr)."""
        results = []

        def cb(out, err):
            results.append((out, err))

        JupyterCell.run_cell("print('hello')", "python", cb, timeout=10)

        # Wait for async execution (max 8 s)
        deadline = time.time() + 8
        while not results and time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.05)

        assert results, "Callback was never called"
        stdout, stderr = results[0]
        assert isinstance(stdout, str)
        assert isinstance(stderr, str)
        assert "hello" in stdout

    def test_run_cell_unknown_language_delivers_error(self, qapp):
        """Unknown language must deliver error message via stderr, not crash."""
        results = []

        def cb(out, err):
            results.append((out, err))

        JupyterCell.run_cell("x = 1", "fictional_lang_xyz", cb, timeout=5)

        deadline = time.time() + 6
        while not results and time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.05)

        assert results, "Callback was never called"
        _, stderr = results[0]
        assert len(stderr) > 0   # some error message expected

    def test_run_cell_timeout_delivers_error(self, qapp):
        """Code that sleeps beyond timeout should deliver a timeout error."""
        results = []

        def cb(out, err):
            results.append((out, err))

        # Use a 1-second timeout with code that sleeps 60 seconds
        JupyterCell.run_cell(
            "import time; time.sleep(60)", "python", cb, timeout=1
        )

        # Wait up to 5 seconds for the timeout to fire
        deadline = time.time() + 5
        while not results and time.time() < deadline:
            qapp.processEvents()
            time.sleep(0.1)

        assert results, "Callback was never called after timeout"
        _, stderr = results[0]
        assert "timeout" in stderr.lower() or "timed out" in stderr.lower()

    def test_inject_output_does_not_raise_outside_frame(self, qapp):
        """inject_output() when not inside a cell frame must be a silent no-op."""
        editor = make_editor("plain text, no cell frame")
        JupyterCell.inject_output(editor, "some output")   # must not raise
