"""Tests for layout modules."""
import sys, os; os.environ["QT_QPA_PLATFORM"] = "offscreen"
import pytest
from PySide6.QtWidgets import QApplication
app = QApplication.instance() or QApplication(sys.argv[:1])

from prasword.core.document import Document
from prasword.features.layout.page_layout import PageLayout, Margins
from prasword.features.layout.header_footer import HeaderFooter, HeaderFooterTemplate
from prasword.features.layout.page_numbering import NumberingConfig, _to_roman, _to_alpha


def test_page_layout_set_a4():
    doc = Document()
    PageLayout.set_page_size(doc, "A4")
    sz = doc.qt_document.pageSize()
    assert sz.width() > 0


def test_page_layout_invalid_size():
    doc = Document()
    with pytest.raises(ValueError):
        PageLayout.set_page_size(doc, "INVALID")


def test_margins_roundtrip():
    doc = Document()
    m = Margins(top=30.0, bottom=20.0, left=25.0, right=25.0)
    PageLayout.set_margins(doc, m)
    got = PageLayout.get_margins(doc)
    assert abs(got.top - 30.0) < 0.5   # pt rounding tolerance


def test_header_footer_roundtrip():
    doc = Document()
    tmpl = HeaderFooterTemplate(center="{title}", right="Page {page} of {pages}")
    HeaderFooter.set_footer(doc, tmpl)
    got = HeaderFooter.get_footer(doc)
    assert "{title}" in got.center
    rendered = got.render(1, 10, "My Doc", "Alice")
    assert "My Doc" in rendered["center"]
    assert "1" in rendered["right"]


def test_roman_numerals():
    assert _to_roman(1) == "I"
    assert _to_roman(4) == "IV"
    assert _to_roman(9) == "IX"
    assert _to_roman(14) == "XIV"
    assert _to_roman(1, upper=False) == "i"


def test_alpha_labels():
    assert _to_alpha(1) == "A"
    assert _to_alpha(26) == "Z"
    assert _to_alpha(27) == "AA"


def test_numbering_config_arabic():
    cfg = NumberingConfig(style="arabic", show_total=True)
    assert cfg.format(1, 10) == "Page 1 of 10"


def test_numbering_config_roman():
    cfg = NumberingConfig(style="roman_lower")
    assert cfg.format(3, 10) == "iii"


def test_numbering_config_start():
    cfg = NumberingConfig(style="arabic", start=5)
    assert cfg.format(1, 10) == "5"
