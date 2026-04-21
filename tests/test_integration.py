"""
tests/test_integration.py
==========================
End-to-end integration tests that exercise multiple modules together.
"""
import sys, os; os.environ["QT_QPA_PLATFORM"] = "offscreen"
import pytest
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv[:1])
app.setApplicationName("PrasWordTest")
app.setOrganizationName("PrasWordTest")

from pathlib import Path
from prasword.core.document import Document, DocumentState
from prasword.core.document_manager import DocumentManager
from prasword.features.filemanagement.file_io import FileIO
from prasword.features.formatting.formatting_engine import FormattingEngine
from prasword.features.metrics.metrics_engine import MetricsEngine
from prasword.features.academic.bibtex_manager import BibTeXManager
from prasword.gui.editor_widget import EditorWidget
from prasword.gui.widgets.word_count_widget import WordCountWidget
from prasword.gui.widgets.status_bar_widget import StatusBarWidget

SAMPLE_BIB = """
@article{einstein05,
  author = {Einstein, Albert},
  title = {On the Electrodynamics of Moving Bodies},
  year = {1905},
  journal = {Annalen der Physik},
}
"""


class TestDocumentLifecycleFull:
    """Open → edit → save → reload cycle."""

    def test_save_and_reload_txt(self, tmp_path):
        mgr = DocumentManager()
        doc = mgr.new_document()
        doc.qt_document.setPlainText("Integration test content.")
        path = tmp_path / "test.txt"
        assert mgr.save_document(doc, path)
        assert doc.state is DocumentState.CLEAN

        doc2 = mgr.open_document(path)
        assert "Integration test content." in doc2.qt_document.toPlainText()

    def test_double_open_returns_same_doc(self, tmp_path):
        p = tmp_path / "dbl.txt"
        p.write_text("hello", encoding="utf-8")
        mgr = DocumentManager()
        d1 = mgr.open_document(p)
        d2 = mgr.open_document(p)
        assert d1 is d2
        assert mgr.document_count == 1


class TestFormattingAndMetrics:
    """Apply formatting, then verify metrics are unaffected."""

    def test_bold_does_not_change_word_count(self):
        doc = Document()
        doc.qt_document.setPlainText("five words are right here")
        editor = EditorWidget(document=doc)
        from PySide6.QtGui import QTextCursor
        c = editor.textCursor()
        c.select(QTextCursor.Document)
        editor.setTextCursor(c)
        FormattingEngine.toggle_bold(editor)
        m = MetricsEngine.compute(doc)
        assert m.word_count == 5

    def test_heading_applied_and_metrics_correct(self):
        doc = Document()
        doc.qt_document.setPlainText("Introduction")
        editor = EditorWidget(document=doc)
        from PySide6.QtGui import QTextCursor
        c = editor.textCursor(); c.select(QTextCursor.Document); editor.setTextCursor(c)
        FormattingEngine.apply_heading(editor, 1)
        m = MetricsEngine.compute(doc)
        assert m.word_count == 1


class TestAcademicAndCitation:
    """Import BibTeX, search, format."""

    def test_import_then_search_then_format(self):
        doc = Document()
        BibTeXManager.import_string(doc, SAMPLE_BIB)
        results = BibTeXManager.search(doc, "einstein")
        assert "einstein05" in results
        html = BibTeXManager.generate_bibliography(doc, "apa")
        assert "1905" in html

    def test_cross_reference_roundtrip(self):
        doc = Document()
        editor = EditorWidget(document=doc)
        from prasword.features.academic.cross_reference import CrossReference
        CrossReference.set_label(editor, doc, "fig:1")
        assert "fig:1" in CrossReference.list_labels(doc)


class TestMetricsWidget:
    """WordCountWidget binds and refreshes."""

    def test_widget_binds_without_error(self):
        doc = Document()
        doc.qt_document.setPlainText("Hello world from metrics widget test.")
        editor = EditorWidget(document=doc)
        widget = WordCountWidget()
        widget.bind_editor(editor, doc)
        widget._refresh()
        # No exception = pass


class TestStatusBar:
    """StatusBarWidget binds to document and reflects state."""

    def test_bind_and_refresh(self):
        doc = Document()
        doc.qt_document.setPlainText("Status bar test.")
        sb = StatusBarWidget()
        sb.bind_document(doc)
        sb._refresh()   # Should not raise.

    def test_cursor_position(self):
        sb = StatusBarWidget()
        sb.on_cursor_moved(5, 12)
        assert "5" in sb._lbl_pos.text()
        assert "12" in sb._lbl_pos.text()
