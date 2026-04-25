"""
tests/test_document.py
======================
Comprehensive unit tests for the Document data model.

Covers
------
* Initial state for new and file-backed documents.
* All state transitions: NEW → MODIFIED, CLEAN → MODIFIED → CLEAN.
* Signal emissions: state_changed, title_changed, metadata_changed.
* Word / character count helpers.
* Bibliography entry CRUD (add, remove, update, nonexistent key safety).
* Cross-reference registration and retrieval.
* TOC entry storage via set_toc_entries().
* Author / keyword metadata accessors.
* qt_document sharing between Document and the model.
* Repr string.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication
import sys

# ── Session-scoped QApplication ──────────────────────────────────────────────

@pytest.fixture(scope="session")
def qapp():
    return QApplication.instance() or QApplication(sys.argv[:1])


# ── Helpers ───────────────────────────────────────────────────────────────────

from prasword.core.document import Document, DocumentState


def make_doc(text: str = "") -> Document:
    doc = Document()
    if text:
        doc.qt_document.setPlainText(text)
    return doc


def file_doc(tmp_path, name: str = "test.txt", text: str = "") -> Document:
    p = tmp_path / name
    p.write_text(text or "hello", encoding="utf-8")
    return Document(file_path=p)


# ═══════════════════════════════════════════════════════════════════════════════
# Initial state
# ═══════════════════════════════════════════════════════════════════════════════

class TestInitialState:

    def test_new_doc_state_is_new(self, qapp):
        assert make_doc().state is DocumentState.NEW

    def test_new_doc_title_is_untitled(self, qapp):
        assert make_doc().title == "Untitled"

    def test_new_doc_is_not_modified(self, qapp):
        assert not make_doc().is_modified

    def test_new_doc_is_new_flag(self, qapp):
        assert make_doc().is_new

    def test_file_doc_state_is_clean(self, qapp, tmp_path):
        assert file_doc(tmp_path).state is DocumentState.CLEAN

    def test_file_doc_title_from_stem(self, qapp, tmp_path):
        p = tmp_path / "my_report.docx"
        p.touch()
        assert Document(file_path=p).title == "my_report"

    def test_file_doc_is_not_new(self, qapp, tmp_path):
        assert not file_doc(tmp_path).is_new

    def test_id_is_string(self, qapp):
        assert isinstance(make_doc().id, str)

    def test_two_docs_have_different_ids(self, qapp):
        assert make_doc().id != make_doc().id

    def test_qt_document_is_empty_by_default(self, qapp):
        assert make_doc().qt_document.toPlainText() == ""

    def test_repr_contains_title(self, qapp):
        doc = make_doc()
        assert "Untitled" in repr(doc)

    def test_repr_contains_state(self, qapp):
        doc = make_doc()
        assert "NEW" in repr(doc)


# ═══════════════════════════════════════════════════════════════════════════════
# State transitions
# ═══════════════════════════════════════════════════════════════════════════════

class TestStateTransitions:

    def test_new_doc_mark_modified_stays_new(self, qapp):
        doc = make_doc()
        doc.mark_modified()
        assert doc.state is DocumentState.NEW

    def test_file_doc_mark_modified_becomes_modified(self, qapp, tmp_path):
        doc = file_doc(tmp_path)
        doc.mark_modified()
        assert doc.state is DocumentState.MODIFIED
        assert doc.is_modified

    def test_modified_mark_saved_becomes_clean(self, qapp, tmp_path):
        doc = file_doc(tmp_path)
        doc.mark_modified()
        doc.mark_saved()
        assert doc.state is DocumentState.CLEAN
        assert not doc.is_modified

    def test_mark_saved_with_new_path_updates_file_path(self, qapp, tmp_path):
        doc = make_doc()
        p = tmp_path / "saved.txt"
        doc.mark_saved(p)
        assert doc.file_path == p
        assert doc.state is DocumentState.CLEAN

    def test_mark_saved_updates_title(self, qapp, tmp_path):
        doc = make_doc()
        p = tmp_path / "my_paper.md"
        doc.mark_saved(p)
        assert doc.title == "my_paper"

    def test_qt_modification_triggers_state_change(self, qapp, tmp_path):
        doc = file_doc(tmp_path)
        doc.qt_document.setModified(True)
        assert doc.is_modified

    def test_multiple_round_trips(self, qapp, tmp_path):
        doc = file_doc(tmp_path)
        for _ in range(5):
            doc.mark_modified()
            assert doc.is_modified
            doc.mark_saved()
            assert not doc.is_modified


# ═══════════════════════════════════════════════════════════════════════════════
# Signal emissions
# ═══════════════════════════════════════════════════════════════════════════════

class TestSignals:

    def test_state_changed_emitted_on_modify(self, qapp, tmp_path):
        doc    = file_doc(tmp_path)
        states = []
        doc.state_changed.connect(states.append)
        doc.mark_modified()
        assert DocumentState.MODIFIED in states

    def test_state_changed_emitted_on_save(self, qapp, tmp_path):
        doc    = file_doc(tmp_path)
        states = []
        doc.state_changed.connect(states.append)
        doc.mark_modified()
        doc.mark_saved()
        assert DocumentState.CLEAN in states

    def test_title_changed_emitted_on_path_change(self, qapp, tmp_path):
        doc    = make_doc()
        titles = []
        doc.title_changed.connect(titles.append)
        doc.file_path = tmp_path / "new_title.txt"
        assert "new_title" in titles

    def test_metadata_changed_emitted_on_bib_add(self, qapp):
        doc    = make_doc()
        fired  = []
        doc.metadata_changed.connect(lambda: fired.append(1))
        doc.add_bib_entry("key1", {"title": "T"})
        assert fired

    def test_metadata_changed_emitted_on_bib_remove(self, qapp):
        doc = make_doc()
        doc.add_bib_entry("key1", {"title": "T"})
        fired = []
        doc.metadata_changed.connect(lambda: fired.append(1))
        doc.remove_bib_entry("key1")
        assert fired

    def test_state_changed_not_emitted_twice_for_same_state(self, qapp, tmp_path):
        doc    = file_doc(tmp_path)
        states = []
        doc.state_changed.connect(states.append)
        doc.mark_modified()
        doc.mark_modified()  # already MODIFIED — should not emit again
        assert states.count(DocumentState.MODIFIED) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# Word / character count
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetrics:

    def test_word_count_empty(self, qapp):
        assert make_doc().word_count() == 0

    def test_word_count_single_word(self, qapp):
        assert make_doc("hello").word_count() == 1

    def test_word_count_multiple(self, qapp):
        assert make_doc("one two three four five").word_count() == 5

    def test_word_count_extra_whitespace(self, qapp):
        assert make_doc("  hello   world  ").word_count() == 2

    def test_char_count_includes_spaces(self, qapp):
        assert make_doc("hello world").character_count() == 11

    def test_char_count_excludes_spaces(self, qapp):
        assert make_doc("hello world").character_count(include_spaces=False) == 10

    def test_char_count_empty(self, qapp):
        assert make_doc().character_count() == 0

    def test_plain_text_returns_content(self, qapp):
        doc = make_doc("sample text")
        assert doc.plain_text() == "sample text"

    def test_html_contains_text(self, qapp):
        doc = make_doc("hello")
        assert "hello" in doc.html()


# ═══════════════════════════════════════════════════════════════════════════════
# Bibliography CRUD
# ═══════════════════════════════════════════════════════════════════════════════

class TestBibliography:

    def test_add_entry_stores_fields(self, qapp):
        doc = make_doc()
        doc.add_bib_entry("k1", {"title": "My Paper", "year": "2024"})
        assert "k1" in doc.bib_entries
        assert doc.bib_entries["k1"]["title"] == "My Paper"

    def test_add_multiple_entries(self, qapp):
        doc = make_doc()
        doc.add_bib_entry("a", {"title": "A"})
        doc.add_bib_entry("b", {"title": "B"})
        assert len(doc.bib_entries) == 2

    def test_add_overwrites_existing_key(self, qapp):
        doc = make_doc()
        doc.add_bib_entry("k1", {"title": "Old"})
        doc.add_bib_entry("k1", {"title": "New"})
        assert doc.bib_entries["k1"]["title"] == "New"

    def test_remove_existing_entry(self, qapp):
        doc = make_doc()
        doc.add_bib_entry("k1", {"title": "T"})
        doc.remove_bib_entry("k1")
        assert "k1" not in doc.bib_entries

    def test_remove_nonexistent_is_safe(self, qapp):
        doc = make_doc()
        doc.remove_bib_entry("nope")   # must not raise

    def test_bib_entries_starts_empty(self, qapp):
        assert make_doc().bib_entries == {}

    def test_add_marks_modified(self, qapp, tmp_path):
        doc = file_doc(tmp_path)
        doc.add_bib_entry("x", {"title": "X"})
        assert doc.is_modified

    def test_remove_marks_modified(self, qapp, tmp_path):
        doc = file_doc(tmp_path)
        doc.add_bib_entry("x", {"title": "X"})
        doc.mark_saved()
        doc.remove_bib_entry("x")
        assert doc.is_modified


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-references
# ═══════════════════════════════════════════════════════════════════════════════

class TestCrossReferences:

    def test_cross_refs_starts_empty(self, qapp):
        assert make_doc().cross_refs == {}

    def test_can_set_cross_ref(self, qapp):
        doc = make_doc()
        doc.cross_refs["fig:1"] = "xref_fig_1"
        assert doc.cross_refs["fig:1"] == "xref_fig_1"

    def test_cross_refs_are_mutable(self, qapp):
        doc = make_doc()
        doc.cross_refs["sec:intro"] = "anchor1"
        doc.cross_refs["sec:intro"] = "anchor2"
        assert doc.cross_refs["sec:intro"] == "anchor2"


# ═══════════════════════════════════════════════════════════════════════════════
# TOC entries
# ═══════════════════════════════════════════════════════════════════════════════

class TestTocEntries:

    def test_toc_entries_starts_empty(self, qapp):
        assert make_doc().toc_entries == []

    def test_set_toc_entries_stores_list(self, qapp):
        doc = make_doc()
        entries = [
            {"level": 1, "text": "Introduction", "anchor": "toc_h_0"},
            {"level": 2, "text": "Background",   "anchor": "toc_h_1"},
        ]
        doc.set_toc_entries(entries)
        assert doc.toc_entries == entries

    def test_set_toc_entries_emits_metadata_changed(self, qapp):
        doc   = make_doc()
        fired = []
        doc.metadata_changed.connect(lambda: fired.append(1))
        doc.set_toc_entries([{"level": 1, "text": "H", "anchor": "a"}])
        assert fired

    def test_set_toc_entries_replaces_previous(self, qapp):
        doc = make_doc()
        doc.set_toc_entries([{"level": 1, "text": "Old", "anchor": "a"}])
        doc.set_toc_entries([{"level": 2, "text": "New", "anchor": "b"}])
        assert len(doc.toc_entries) == 1
        assert doc.toc_entries[0]["text"] == "New"


# ═══════════════════════════════════════════════════════════════════════════════
# Metadata: author / keywords
# ═══════════════════════════════════════════════════════════════════════════════

class TestMetadata:

    def test_author_defaults_empty(self, qapp):
        assert make_doc().author == ""

    def test_set_author(self, qapp):
        doc = make_doc()
        doc.author = "Alice"
        assert doc.author == "Alice"

    def test_set_author_emits_metadata_changed(self, qapp):
        doc   = make_doc()
        fired = []
        doc.metadata_changed.connect(lambda: fired.append(1))
        doc.author = "Bob"
        assert fired

    def test_keywords_defaults_empty(self, qapp):
        assert make_doc().keywords == []

    def test_qt_document_shared(self, qapp):
        """The same QTextDocument object is accessible from doc.qt_document."""
        doc = make_doc()
        doc.qt_document.setPlainText("shared")
        assert doc.plain_text() == "shared"
