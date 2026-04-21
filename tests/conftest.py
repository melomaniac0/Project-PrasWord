"""
tests/conftest.py
=================
Shared pytest fixtures available to every test module.
"""
import os
import sys

# Force Qt offscreen platform before any Qt import.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication (created once for the whole test run)."""
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("PrasWordTest")
    app.setOrganizationName("PrasWordTest")
    yield app


@pytest.fixture
def blank_document(qapp):
    """A fresh, empty Document."""
    from prasword.core.document import Document
    return Document()


@pytest.fixture
def saved_document(qapp, tmp_path):
    """A Document backed by a real .txt file on disk."""
    from prasword.core.document import Document
    p = tmp_path / "test.txt"
    p.write_text("Fixture document content.", encoding="utf-8")
    return Document(file_path=p)


@pytest.fixture
def doc_manager(qapp):
    """A fresh DocumentManager with no open documents."""
    from prasword.core.document_manager import DocumentManager
    return DocumentManager()


@pytest.fixture
def editor(blank_document):
    """An EditorWidget bound to a blank document."""
    from prasword.gui.editor_widget import EditorWidget
    return EditorWidget(document=blank_document)


@pytest.fixture
def editor_with_text(blank_document):
    """An EditorWidget pre-filled with sample text."""
    from prasword.gui.editor_widget import EditorWidget
    blank_document.qt_document.setPlainText(
        "The quick brown fox jumps over the lazy dog.\n"
        "Pack my box with five dozen liquor jugs.\n"
        "How razorback-jumping frogs can level six piqued gymnasts!\n"
    )
    return EditorWidget(document=blank_document)
