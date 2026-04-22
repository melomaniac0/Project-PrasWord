"""Tests for MetricsEngine."""
import sys, os; os.environ["QT_QPA_PLATFORM"] = "offscreen"
import pytest
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv)

from prasword.core.document import Document
from prasword.features.metrics.metrics_engine import MetricsEngine, DocumentMetrics


def make_doc(text: str) -> Document:
    doc = Document()
    doc.qt_document.setPlainText(text)
    return doc


def test_empty_document():
    doc = make_doc("")
    m = MetricsEngine.compute(doc)
    assert m.word_count == 0
    assert m.char_count == 0


def test_word_count():
    doc = make_doc("one two three four five")
    m = MetricsEngine.compute(doc)
    assert m.word_count == 5


def test_char_count():
    doc = make_doc("hello")
    m = MetricsEngine.compute(doc)
    assert m.char_count == 5


def test_unique_words():
    doc = make_doc("the cat sat on the mat the")
    m = MetricsEngine.compute(doc)
    assert m.unique_words < m.word_count   # "the" is repeated


def test_reading_time_str_short():
    doc = make_doc("word " * 10)
    m = MetricsEngine.compute(doc)
    assert "min" in m.reading_time_str


def test_metrics_dataclass_frozen():
    doc = make_doc("test")
    m = MetricsEngine.compute(doc)
    with pytest.raises(Exception):
        m.word_count = 999   # frozen dataclass


def test_fast_returns_tuple():
    doc = make_doc("hello world")
    wc, cc, rt = MetricsEngine.fast(doc)
    assert wc == 2
    assert cc == 11
    assert "min" in rt


def test_selection_metrics():
    m = MetricsEngine.compute_selection("alpha beta gamma")
    assert m.word_count == 3


# ── New field tests for expanded MetricsEngine ─────────────────────────────

def test_speaking_time_in_metrics():
    doc = make_doc("word " * 130)
    m = MetricsEngine.compute(doc)
    assert m.speaking_time_seconds >= 60
    assert "min" in m.speaking_time_str


def test_flesch_score_range():
    doc = make_doc("The cat sat on the mat. It was a big cat.")
    m = MetricsEngine.compute(doc)
    assert -1.0 <= m.flesch_score <= 100.0


def test_flesch_label_not_empty():
    doc = make_doc("The quick brown fox jumps over the lazy dog.")
    m = MetricsEngine.compute(doc)
    assert m.flesch_label != ""


def test_lexical_density():
    doc = make_doc("the the the cat")
    m = MetricsEngine.compute(doc)
    assert 0.0 < m.lexical_density <= 1.0


def test_to_html_contains_table():
    doc = make_doc("test document content here with several words")
    m = MetricsEngine.compute(doc)
    html = m.to_html()
    assert "<table" in html
    assert "Words" in html


def test_top_words():
    text = "data science data analysis data machine learning science"
    result = MetricsEngine.top_words(text, n=3)
    assert result[0][0] == "data"
    assert result[0][1] == 3


def test_top_words_excludes_stopwords():
    text = "the the the cat sat on the mat"
    result = MetricsEngine.top_words(text, n=5, exclude_stop_words=True)
    words = [w for w, _ in result]
    assert "the" not in words


def test_flesch_reading_ease_static():
    # Need >= 10 words and >= 2 sentences for a valid score
    text = " ".join(["The cat sat on the mat."] * 5)
    score = MetricsEngine.flesch_reading_ease(text)
    assert score >= 0   # Simple repeated sentences should score well


def test_compute_selection_independent():
    m1 = MetricsEngine.compute_selection("hello world")
    m2 = MetricsEngine.compute_selection("alpha beta gamma delta epsilon")
    assert m1.word_count == 2
    assert m2.word_count == 5


def test_to_detail_text_has_flesch():
    doc = make_doc("Simple clear text with short words.")
    m = MetricsEngine.compute(doc)
    detail = m.to_detail_text()
    assert "Flesch" in detail
    assert "Speaking" in detail
