"""
prasword.gui.widgets.word_count_widget
========================================
Floating/dockable live metrics widget — word count, char count, reading time.
Updates in real-time via a debounced timer connected to the active editor.
"""
from __future__ import annotations
from typing import Optional
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QProgressBar, QFrame,
)
from prasword.features.metrics.metrics_engine import MetricsEngine
from prasword.utils.logger import get_logger
log = get_logger(__name__)


class _MetricRow(QWidget):
    """One labelled metric row."""
    def __init__(self, label: str, parent=None) -> None:
        super().__init__(parent)
        h = QHBoxLayout(self); h.setContentsMargins(0, 0, 0, 0)
        self._lbl = QLabel(label + ":")
        self._lbl.setFixedWidth(100)
        self._val = QLabel("—")
        self._val.setAlignment(Qt.AlignRight)
        h.addWidget(self._lbl); h.addWidget(self._val)

    def set_value(self, text: str) -> None:
        self._val.setText(text)


class WordCountWidget(QWidget):
    """
    Live document metrics panel.

    Connect to an editor via ``bind_editor(editor, document)``.
    The widget auto-refreshes on a 300 ms debounce timer.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._refresh)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(2)

        header = QLabel("Document Metrics")
        header.setAlignment(Qt.AlignCenter)
        header.setStyleSheet("font-weight: bold; font-size: 10pt;")
        layout.addWidget(header)

        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self._row_words    = _MetricRow("Words")
        self._row_chars    = _MetricRow("Characters")
        self._row_chars_ns = _MetricRow("Chars (no sp.)")
        self._row_paras    = _MetricRow("Paragraphs")
        self._row_sents    = _MetricRow("Sentences")
        self._row_unique   = _MetricRow("Unique words")
        self._row_avgword  = _MetricRow("Avg word len")
        self._row_avgsent  = _MetricRow("Avg sent len")
        self._row_reading  = _MetricRow("Reading time")

        for row in (
            self._row_words, self._row_chars, self._row_chars_ns,
            self._row_paras, self._row_sents, self._row_unique,
            self._row_avgword, self._row_avgsent, self._row_reading,
        ):
            layout.addWidget(row)

        layout.addStretch()

    def bind_editor(self, editor, document) -> None:
        """Bind this widget to *editor* and *document*."""
        self._document = document
        if editor:
            editor.document().contentsChanged.connect(self._timer.start)
        self._refresh()

    @Slot()
    def _refresh(self) -> None:
        if not self._document:
            return
        try:
            m = MetricsEngine.compute(self._document)
            self._row_words.set_value(f"{m.word_count:,}")
            self._row_chars.set_value(f"{m.char_count:,}")
            self._row_chars_ns.set_value(f"{m.char_count_no_spaces:,}")
            self._row_paras.set_value(f"{m.paragraph_count:,}")
            self._row_sents.set_value(f"{m.sentence_count:,}")
            self._row_unique.set_value(f"{m.unique_words:,}")
            self._row_avgword.set_value(f"{m.avg_word_length:.1f} ch")
            self._row_avgsent.set_value(f"{m.avg_sentence_length:.1f} wds")
            self._row_reading.set_value(m.reading_time_str)
        except Exception as exc:
            log.debug("Metrics refresh error: %s", exc)
