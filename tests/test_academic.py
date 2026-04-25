"""
tests/test_academic.py
======================
Comprehensive unit tests for all academic feature modules:
  BibTeXManager, CitationEngine, CrossReference.

Covers
------
BibTeXManager
  * import_string: parses entries, populates bib_entries.
  * import_file: reads a .bib file on disk.
  * add_entry: manual entry without bibtexparser.
  * export_file: writes .bib file, re-importable.
  * merge: combines two bibliographies with dedup.
  * format_entry: all five styles (APA, MLA, Chicago, IEEE, Vancouver).
  * generate_bibliography: HTML output, sort_by options, cited_only.
  * search: filters by author, title, year, citekey.
  * Error: missing file, missing cite-key in entry dict.

CitationEngine
  * insert_citation: inserts styled text at cursor, all five styles.
  * insert_multiple: grouped APA and numeric citations.
  * insert_footnote_ref: superscript number, stores full reference.
  * collect_footnotes: retrieves in insertion order.
  * insert_bibliography: appends HTML bibliography block.
  * cited_keys: returns tracked list.
  * scan_cited_keys: detects [citekey] patterns in text.
  * KeyError for unknown cite-key.

CrossReference
  * set_label: registers label and anchor.
  * remove_label: removes from registry.
  * rename_label: moves label to new key.
  * auto_number: assigns sequential fig:/tbl: numbers.
  * list_labels: filters internal keys.
  * get_display_text: returns stored display text.
  * label_exists: True/False query.
  * labels_by_prefix: groups by prefix.
  * insert_ref: no-op on unknown label (inserts placeholder).
"""

from __future__ import annotations

import sys
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
from prasword.features.academic.bibtex_manager import BibTeXManager
from prasword.features.academic.citation_engine import CitationEngine
from prasword.features.academic.cross_reference import CrossReference


# ── Sample BibTeX ─────────────────────────────────────────────────────────────

SAMPLE_BIB = """\
@article{knuth84,
  author  = {Knuth, Donald E.},
  title   = {The {TeX}book},
  year    = {1984},
  journal = {Computers and Typesetting},
  volume  = {A},
  pages   = {1--483},
}

@book{lamport94,
  author    = {Lamport, Leslie},
  title     = {{LaTeX}: A Document Preparation System},
  year      = {1994},
  publisher = {Addison-Wesley},
  edition   = {2nd},
}

@inproceedings{einstein05,
  author    = {Einstein, Albert},
  title     = {On the Electrodynamics of Moving Bodies},
  year      = {1905},
  booktitle = {Annalen der Physik},
}
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_doc(text: str = "") -> Document:
    doc = Document()
    if text:
        doc.qt_document.setPlainText(text)
    return doc


def doc_with_bib() -> Document:
    doc = make_doc()
    BibTeXManager.import_string(doc, SAMPLE_BIB)
    return doc


def editor_for(doc: Document) -> EditorWidget:
    return EditorWidget(document=doc)


# ═══════════════════════════════════════════════════════════════════════════════
# BibTeXManager — import
# ═══════════════════════════════════════════════════════════════════════════════

class TestBibTeXImport:

    def test_import_string_returns_count(self, qapp):
        doc   = make_doc()
        count = BibTeXManager.import_string(doc, SAMPLE_BIB)
        assert count == 3

    def test_import_string_populates_bib_entries(self, qapp):
        doc = doc_with_bib()
        assert "knuth84" in doc.bib_entries
        assert "lamport94" in doc.bib_entries
        assert "einstein05" in doc.bib_entries

    def test_import_string_stores_title(self, qapp):
        doc = doc_with_bib()
        assert "TeX" in doc.bib_entries["knuth84"]["title"]

    def test_import_string_stores_year(self, qapp):
        doc = doc_with_bib()
        assert "1984" in doc.bib_entries["knuth84"]["year"]

    def test_import_string_stores_author(self, qapp):
        doc = doc_with_bib()
        assert "Knuth" in doc.bib_entries["knuth84"]["author"]

    def test_import_string_stores_entrytype(self, qapp):
        doc = doc_with_bib()
        etype = doc.bib_entries["knuth84"].get("entrytype", "")
        assert etype.lower() == "article"

    def test_import_string_marks_document_modified(self, qapp, tmp_path):
        p   = tmp_path / "f.txt"
        p.write_text("x", encoding="utf-8")
        doc = Document(file_path=p)
        BibTeXManager.import_string(doc, SAMPLE_BIB)
        assert doc.is_modified

    def test_import_file(self, qapp, tmp_path):
        p = tmp_path / "sample.bib"
        p.write_text(SAMPLE_BIB, encoding="utf-8")
        doc = make_doc()
        count = BibTeXManager.import_file(doc, p)
        assert count == 3
        assert "knuth84" in doc.bib_entries

    def test_import_file_not_found_raises(self, qapp, tmp_path):
        doc = make_doc()
        with pytest.raises(FileNotFoundError):
            BibTeXManager.import_file(doc, tmp_path / "ghost.bib")

    def test_import_empty_string_returns_zero(self, qapp):
        doc = make_doc()
        assert BibTeXManager.import_string(doc, "") == 0

    def test_import_string_idempotent_on_reimport(self, qapp):
        doc = make_doc()
        BibTeXManager.import_string(doc, SAMPLE_BIB)
        BibTeXManager.import_string(doc, SAMPLE_BIB)
        # After re-import same keys are overwritten — count still 3
        assert len([k for k in doc.bib_entries if not k.startswith("__")]) == 3


# ═══════════════════════════════════════════════════════════════════════════════
# BibTeXManager — add_entry / export / merge
# ═══════════════════════════════════════════════════════════════════════════════

class TestBibTeXCRUD:

    def test_add_entry_manual(self, qapp):
        doc = make_doc()
        BibTeXManager.add_entry(doc, "mykey", "article", {"title": "My Work", "year": "2025"})
        assert "mykey" in doc.bib_entries
        assert doc.bib_entries["mykey"]["title"] == "My Work"

    def test_add_entry_sets_entrytype(self, qapp):
        doc = make_doc()
        BibTeXManager.add_entry(doc, "k", "book", {"title": "T"})
        assert doc.bib_entries["k"]["entrytype"] == "book"

    def test_export_file_creates_bib(self, qapp, tmp_path):
        doc = doc_with_bib()
        p   = tmp_path / "exported.bib"
        n   = BibTeXManager.export_file(doc, p)
        assert n == 3
        assert p.exists()

    def test_exported_bib_contains_citekeys(self, qapp, tmp_path):
        doc     = doc_with_bib()
        p       = tmp_path / "exported.bib"
        BibTeXManager.export_file(doc, p)
        content = p.read_text(encoding="utf-8")
        assert "knuth84" in content
        assert "lamport94" in content

    def test_exported_bib_is_reimportable(self, qapp, tmp_path):
        doc = doc_with_bib()
        p   = tmp_path / "reimport.bib"
        BibTeXManager.export_file(doc, p)
        doc2  = make_doc()
        count = BibTeXManager.import_file(doc2, p)
        assert count == 3

    def test_merge_adds_entries(self, qapp):
        src = doc_with_bib()
        tgt = make_doc()
        added, skipped = BibTeXManager.merge(tgt, src)
        assert added == 3
        assert skipped == 0
        assert "knuth84" in tgt.bib_entries

    def test_merge_no_overwrite_skips_duplicates(self, qapp):
        src = doc_with_bib()
        tgt = doc_with_bib()
        added, skipped = BibTeXManager.merge(tgt, src, overwrite=False)
        assert skipped == 3

    def test_merge_with_overwrite_replaces(self, qapp):
        src = make_doc()
        BibTeXManager.add_entry(src, "knuth84", "article", {"title": "New Title"})
        tgt = doc_with_bib()
        BibTeXManager.merge(tgt, src, overwrite=True)
        assert tgt.bib_entries["knuth84"]["title"] == "New Title"


# ═══════════════════════════════════════════════════════════════════════════════
# BibTeXManager — format_entry
# ═══════════════════════════════════════════════════════════════════════════════

class TestBibTeXFormat:

    @pytest.fixture
    def entry(self):
        return {
            "author":  "Knuth, Donald E.",
            "title":   "The TeXbook",
            "year":    "1984",
            "journal": "Computers and Typesetting",
            "volume":  "A",
            "pages":   "1--483",
        }

    def test_format_apa_contains_year(self, qapp, entry):
        result = BibTeXManager.format_entry(entry, "apa")
        assert "1984" in result

    def test_format_apa_contains_title_italic(self, qapp, entry):
        result = BibTeXManager.format_entry(entry, "apa")
        assert "TeXbook" in result
        assert "<i>" in result

    def test_format_apa_contains_author(self, qapp, entry):
        result = BibTeXManager.format_entry(entry, "apa")
        assert "Knuth" in result

    def test_format_mla(self, qapp, entry):
        result = BibTeXManager.format_entry(entry, "mla")
        assert "Knuth" in result
        assert "1984" in result

    def test_format_chicago(self, qapp, entry):
        result = BibTeXManager.format_entry(entry, "chicago")
        assert "Knuth" in result
        assert "TeXbook" in result

    def test_format_ieee(self, qapp, entry):
        result = BibTeXManager.format_entry(entry, "ieee")
        assert "Knuth" in result
        assert "TeXbook" in result

    def test_format_vancouver(self, qapp, entry):
        result = BibTeXManager.format_entry(entry, "vancouver")
        assert "Knuth" in result

    def test_format_unknown_style_fallback(self, qapp, entry):
        result = BibTeXManager.format_entry(entry, "xyz")
        assert "Knuth" in result

    def test_format_with_doi_includes_doi_link(self, qapp):
        entry = {
            "author":  "Author, A.",
            "title":   "Paper",
            "year":    "2020",
            "doi":     "10.1234/test",
        }
        result = BibTeXManager.format_entry(entry, "apa")
        assert "10.1234/test" in result

    def test_format_book_entry(self, qapp):
        entry = {
            "author":    "Lamport, Leslie",
            "title":     "LaTeX",
            "year":      "1994",
            "publisher": "Addison-Wesley",
            "entrytype": "book",
        }
        result = BibTeXManager.format_entry(entry, "apa")
        assert "Lamport" in result


# ═══════════════════════════════════════════════════════════════════════════════
# BibTeXManager — generate_bibliography
# ═══════════════════════════════════════════════════════════════════════════════

class TestBibTeXGenerate:

    def test_generate_returns_html(self, qapp):
        doc  = doc_with_bib()
        html = BibTeXManager.generate_bibliography(doc, "apa")
        assert "<ol" in html
        assert "<li" in html

    def test_generate_contains_all_citekeys(self, qapp):
        doc  = doc_with_bib()
        html = BibTeXManager.generate_bibliography(doc, "apa")
        assert "knuth84" in html
        assert "lamport94" in html
        assert "einstein05" in html

    def test_generate_empty_doc_returns_notice(self, qapp):
        doc  = make_doc()
        html = BibTeXManager.generate_bibliography(doc, "apa")
        assert "No bibliography" in html

    def test_generate_cited_only(self, qapp):
        doc = doc_with_bib()
        doc.qt_document.setPlainText("See [knuth84] for details.")
        html = BibTeXManager.generate_bibliography(doc, "apa", cited_only=True)
        assert "knuth84" in html
        assert "lamport94" not in html

    def test_generate_sort_by_year(self, qapp):
        doc  = doc_with_bib()
        html = BibTeXManager.generate_bibliography(doc, "apa", sort_by="year")
        assert html.index("1984") < html.index("1994")

    def test_generate_sort_by_title(self, qapp):
        doc  = doc_with_bib()
        html = BibTeXManager.generate_bibliography(doc, "apa", sort_by="title")
        assert "References" in html

    @pytest.mark.parametrize("style", ["apa", "mla", "chicago", "ieee", "vancouver"])
    def test_generate_all_styles(self, qapp, style):
        doc  = doc_with_bib()
        html = BibTeXManager.generate_bibliography(doc, style)
        assert "<ol" in html


# ═══════════════════════════════════════════════════════════════════════════════
# BibTeXManager — search
# ═══════════════════════════════════════════════════════════════════════════════

class TestBibTeXSearch:

    def test_search_by_author(self, qapp):
        doc     = doc_with_bib()
        results = BibTeXManager.search(doc, "knuth")
        assert "knuth84" in results
        assert "lamport94" not in results

    def test_search_by_title(self, qapp):
        doc     = doc_with_bib()
        results = BibTeXManager.search(doc, "latex")
        assert "lamport94" in results

    def test_search_by_year(self, qapp):
        doc     = doc_with_bib()
        results = BibTeXManager.search(doc, "1905")
        assert "einstein05" in results

    def test_search_by_citekey(self, qapp):
        doc     = doc_with_bib()
        results = BibTeXManager.search(doc, "lamport")
        assert "lamport94" in results

    def test_search_empty_query_returns_all(self, qapp):
        doc     = doc_with_bib()
        results = BibTeXManager.search(doc, "")
        assert len(results) == 3

    def test_search_no_match_returns_empty(self, qapp):
        doc     = doc_with_bib()
        results = BibTeXManager.search(doc, "zzznomatch999")
        assert results == {}

    def test_search_case_insensitive(self, qapp):
        doc     = doc_with_bib()
        results = BibTeXManager.search(doc, "KNUTH")
        assert "knuth84" in results


# ═══════════════════════════════════════════════════════════════════════════════
# CitationEngine — insert_citation
# ═══════════════════════════════════════════════════════════════════════════════

class TestCitationInsert:

    @pytest.mark.parametrize("style,expected", [
        ("apa",     "(Knuth"),
        ("mla",     "(Knuth"),
        ("chicago", "(Knuth"),
        ("ieee",    "["),
        ("numeric", "["),
    ])
    def test_insert_citation_style(self, qapp, style, expected):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        CitationEngine.insert_citation(editor, doc, "knuth84", style)
        text = editor.document().toPlainText()
        assert expected in text

    def test_insert_citation_apa_year(self, qapp):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        CitationEngine.insert_citation(editor, doc, "knuth84", "apa")
        assert "1984" in editor.document().toPlainText()

    def test_insert_citation_unknown_key_raises(self, qapp):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        with pytest.raises(KeyError):
            CitationEngine.insert_citation(editor, doc, "nonexistent_key", "apa")

    def test_insert_citation_records_cited_key(self, qapp):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        CitationEngine.insert_citation(editor, doc, "knuth84", "apa")
        assert "knuth84" in CitationEngine.cited_keys(doc)

    def test_insert_citation_with_page(self, qapp):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        CitationEngine.insert_citation(editor, doc, "knuth84", "apa", page="42")
        text = editor.document().toPlainText()
        assert "42" in text


# ═══════════════════════════════════════════════════════════════════════════════
# CitationEngine — insert_multiple
# ═══════════════════════════════════════════════════════════════════════════════

class TestCitationMultiple:

    def test_insert_multiple_apa_grouped(self, qapp):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        CitationEngine.insert_multiple(editor, doc, ["knuth84", "lamport94"], "apa")
        text = editor.document().toPlainText()
        assert "Knuth" in text
        assert "Lamport" in text

    def test_insert_multiple_numeric_brackets(self, qapp):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        CitationEngine.insert_multiple(editor, doc, ["knuth84", "lamport94"], "ieee")
        text = editor.document().toPlainText()
        assert "[" in text

    def test_insert_multiple_empty_list_is_noop(self, qapp):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        before = editor.document().toPlainText()
        CitationEngine.insert_multiple(editor, doc, [], "apa")
        assert editor.document().toPlainText() == before

    def test_insert_multiple_records_all_cited_keys(self, qapp):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        CitationEngine.insert_multiple(editor, doc, ["knuth84", "einstein05"], "apa")
        cited = CitationEngine.cited_keys(doc)
        assert "knuth84" in cited
        assert "einstein05" in cited


# ═══════════════════════════════════════════════════════════════════════════════
# CitationEngine — footnotes
# ═══════════════════════════════════════════════════════════════════════════════

class TestFootnotes:

    def test_insert_footnote_ref_returns_number(self, qapp):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        n = CitationEngine.insert_footnote_ref(editor, doc, "knuth84", "apa")
        assert n == 1

    def test_insert_multiple_footnotes_increments(self, qapp):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        n1 = CitationEngine.insert_footnote_ref(editor, doc, "knuth84", "apa")
        n2 = CitationEngine.insert_footnote_ref(editor, doc, "lamport94", "apa")
        assert n1 == 1
        assert n2 == 2

    def test_collect_footnotes_in_order(self, qapp):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        CitationEngine.insert_footnote_ref(editor, doc, "knuth84",  "apa")
        CitationEngine.insert_footnote_ref(editor, doc, "lamport94","apa")
        fn = CitationEngine.collect_footnotes(doc)
        assert len(fn) == 2
        assert fn[0][0] == 1
        assert fn[1][0] == 2

    def test_collect_footnotes_contains_author(self, qapp):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        CitationEngine.insert_footnote_ref(editor, doc, "knuth84", "apa")
        fn = CitationEngine.collect_footnotes(doc)
        assert "Knuth" in fn[0][1]


# ═══════════════════════════════════════════════════════════════════════════════
# CitationEngine — bibliography insertion & scanning
# ═══════════════════════════════════════════════════════════════════════════════

class TestBibliographyInsertion:

    def test_insert_bibliography_appends_html(self, qapp):
        doc    = doc_with_bib()
        editor = editor_for(doc)
        CitationEngine.insert_bibliography(editor, doc, "apa", cited_only=False)
        html = editor.document().toHtml()
        assert "References" in html or "knuth84" in html

    def test_scan_cited_keys_detects_brackets(self, qapp):
        doc = doc_with_bib()
        doc.qt_document.setPlainText("See [knuth84] and [lamport94] for details.")
        found = CitationEngine.scan_cited_keys(doc)
        assert "knuth84" in found
        assert "lamport94" in found

    def test_scan_cited_keys_ignores_unknown(self, qapp):
        doc = doc_with_bib()
        doc.qt_document.setPlainText("See [unknown_key] for details.")
        found = CitationEngine.scan_cited_keys(doc)
        assert "unknown_key" not in found

    def test_cited_keys_empty_by_default(self, qapp):
        doc = make_doc()
        assert CitationEngine.cited_keys(doc) == []


# ═══════════════════════════════════════════════════════════════════════════════
# CrossReference
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrossReference:

    def test_set_label_registers_in_cross_refs(self, qapp):
        doc    = make_doc("Some content.")
        editor = editor_for(doc)
        CrossReference.set_label(editor, doc, "fig:1")
        assert CrossReference.label_exists(doc, "fig:1")

    def test_set_label_returns_anchor_id(self, qapp):
        doc    = make_doc("content")
        editor = editor_for(doc)
        anchor = CrossReference.set_label(editor, doc, "fig:roc")
        assert "fig" in anchor or "xref" in anchor

    def test_set_label_custom_display_text(self, qapp):
        doc    = make_doc("content")
        editor = editor_for(doc)
        CrossReference.set_label(editor, doc, "fig:1", display_text="Figure 1")
        assert CrossReference.get_display_text(doc, "fig:1") == "Figure 1"

    def test_set_label_default_display_text_generated(self, qapp):
        doc    = make_doc("content")
        editor = editor_for(doc)
        CrossReference.set_label(editor, doc, "fig:3")
        disp = CrossReference.get_display_text(doc, "fig:3")
        assert "Figure" in disp or "fig" in disp.lower()

    def test_remove_label(self, qapp):
        doc    = make_doc("content")
        editor = editor_for(doc)
        CrossReference.set_label(editor, doc, "tbl:1")
        result = CrossReference.remove_label(doc, "tbl:1")
        assert result is True
        assert not CrossReference.label_exists(doc, "tbl:1")

    def test_remove_nonexistent_label_returns_false(self, qapp):
        doc    = make_doc()
        result = CrossReference.remove_label(doc, "nope")
        assert result is False

    def test_rename_label(self, qapp):
        doc    = make_doc("content")
        editor = editor_for(doc)
        CrossReference.set_label(editor, doc, "fig:old")
        result = CrossReference.rename_label(doc, "fig:old", "fig:new")
        assert result is True
        assert CrossReference.label_exists(doc, "fig:new")
        assert not CrossReference.label_exists(doc, "fig:old")

    def test_rename_nonexistent_label_returns_false(self, qapp):
        doc    = make_doc()
        result = CrossReference.rename_label(doc, "nope", "also_nope")
        assert result is False

    def test_list_labels_excludes_internal_keys(self, qapp):
        doc    = make_doc("content")
        editor = editor_for(doc)
        CrossReference.set_label(editor, doc, "fig:1")
        CrossReference.set_label(editor, doc, "tbl:1")
        labels = CrossReference.list_labels(doc)
        assert "fig:1" in labels
        assert "tbl:1" in labels
        for l in labels:
            assert not l.startswith("__")

    def test_label_exists_true(self, qapp):
        doc    = make_doc("content")
        editor = editor_for(doc)
        CrossReference.set_label(editor, doc, "sec:intro")
        assert CrossReference.label_exists(doc, "sec:intro")

    def test_label_exists_false_for_unknown(self, qapp):
        doc = make_doc()
        assert not CrossReference.label_exists(doc, "unknown")

    def test_auto_number_assigns_sequential_numbers(self, qapp):
        doc    = make_doc("content")
        editor = editor_for(doc)
        CrossReference.set_label(editor, doc, "fig:roc")
        CrossReference.set_label(editor, doc, "fig:loss")
        result = CrossReference.auto_number(doc)
        assert len(result) >= 2
        values = list(result.values())
        assert any("1" in v for v in values)
        assert any("2" in v for v in values)

    def test_auto_number_groups_by_prefix(self, qapp):
        doc    = make_doc("content")
        editor = editor_for(doc)
        CrossReference.set_label(editor, doc, "fig:a")
        CrossReference.set_label(editor, doc, "tbl:b")
        result = CrossReference.auto_number(doc)
        fig_labels = [v for k, v in result.items() if k.startswith("fig:")]
        tbl_labels = [v for k, v in result.items() if k.startswith("tbl:")]
        assert fig_labels
        assert tbl_labels
        assert "Figure" in fig_labels[0]
        assert "Table" in tbl_labels[0]

    def test_labels_by_prefix(self, qapp):
        doc    = make_doc("content")
        editor = editor_for(doc)
        CrossReference.set_label(editor, doc, "fig:1")
        CrossReference.set_label(editor, doc, "fig:2")
        CrossReference.set_label(editor, doc, "tbl:1")
        groups = CrossReference.labels_by_prefix(doc)
        assert "fig" in groups
        assert len(groups["fig"]) == 2
        assert "tbl" in groups

    def test_insert_ref_known_label(self, qapp):
        doc    = make_doc("content")
        editor = editor_for(doc)
        CrossReference.set_label(editor, doc, "fig:1", display_text="Figure 1")
        CrossReference.insert_ref(editor, doc, "fig:1")
        text = editor.document().toPlainText()
        assert "Figure 1" in text or "fig:1" in text

    def test_insert_ref_unknown_label_inserts_placeholder(self, qapp):
        doc    = make_doc("content")
        editor = editor_for(doc)
        CrossReference.insert_ref(editor, doc, "fig:unknown")
        text = editor.document().toPlainText()
        assert "unknown" in text or "?" in text

    def test_get_display_text_unknown_label_returns_default(self, qapp):
        doc  = make_doc()
        disp = CrossReference.get_display_text(doc, "fig:5")
        assert "5" in disp or "fig" in disp.lower()
