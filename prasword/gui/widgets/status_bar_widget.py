"""
prasword.gui.widgets.status_bar_widget
========================================
Enhanced status bar that shows per-document live metrics, cursor position,
document state, zoom level, and encoding.

Replaces the simple QLabel approach in MainWindow with a proper composited
widget that the MainWindow can swap in on startup.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QStatusBar,
    QWidget,
)

from prasword.features.metrics.metrics_engine import MetricsEngine
from prasword.utils.logger import get_logger

log = get_logger(__name__)

_SEP = "  ·  "


class StatusBarWidget(QStatusBar):
    """
    Drop-in replacement for QStatusBar that shows rich document metrics.

    Sections (left → right)
    -----------------------
    [temp messages]  [word count]  [chars]  [reading time]  [line:col]  [state]
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._document = None

        # Debounce timer — recompute at most every 350 ms.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(350)
        self._timer.timeout.connect(self._refresh)

        self._build_widgets()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_widgets(self) -> None:
        def _lbl(tip="") -> QLabel:
            l = QLabel("—")
            l.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            l.setContentsMargins(6, 0, 6, 0)
            if tip:
                l.setToolTip(tip)
            return l

        self._lbl_words   = _lbl("Word count")
        self._lbl_chars   = _lbl("Character count (including spaces)")
        self._lbl_reading = _lbl("Estimated reading time")
        self._lbl_pos     = _lbl("Line : Column")
        self._lbl_state   = _lbl("Document state")
        self._lbl_zoom    = _lbl("Zoom level")

        for w in (
            self._lbl_words,
            self._lbl_chars,
            self._lbl_reading,
            self._lbl_pos,
            self._lbl_state,
            self._lbl_zoom,
        ):
            self.addPermanentWidget(w)

        self._set_zoom(100)
        self._clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def bind_document(self, doc) -> None:
        """Bind to *doc* and its editor."""
        self._document = doc
        if doc:
            doc.state_changed.connect(self._on_state_changed)
            self._on_state_changed(doc.state)
        self._refresh()

    def on_cursor_moved(self, line: int, col: int) -> None:
        """Call this from EditorWidget.cursor_position_changed."""
        self._lbl_pos.setText(f"Ln {line} : Col {col}")

    def schedule_refresh(self) -> None:
        """Debounced refresh — call on every keystroke."""
        self._timer.start()

    def set_zoom(self, percent: int) -> None:
        self._set_zoom(percent)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    @Slot(object)
    def _on_state_changed(self, state) -> None:
        from prasword.core.document import DocumentState
        labels = {
            DocumentState.NEW:      ("New", "#a6e3a1"),
            DocumentState.CLEAN:    ("Saved", "#a6adc8"),
            DocumentState.MODIFIED: ("Modified ●", "#f9e2af"),
        }
        text, color = labels.get(state, ("—", "#a6adc8"))
        self._lbl_state.setText(text)
        self._lbl_state.setStyleSheet(f"color: {color};")

    @Slot()
    def _refresh(self) -> None:
        if not self._document:
            self._clear()
            return
        try:
            wc, cc, rt = MetricsEngine.fast(self._document)
            self._lbl_words.setText(f"W: {wc:,}")
            self._lbl_chars.setText(f"C: {cc:,}")
            self._lbl_reading.setText(f"~{rt} read")
        except Exception as exc:
            log.debug("Status bar refresh error: %s", exc)

    def _clear(self) -> None:
        self._lbl_words.setText("W: 0")
        self._lbl_chars.setText("C: 0")
        self._lbl_reading.setText("~0 min read")

    def _set_zoom(self, percent: int) -> None:
        self._lbl_zoom.setText(f"{percent}%")
