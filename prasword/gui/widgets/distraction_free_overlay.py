"""
prasword.gui.widgets.distraction_free_overlay
=============================================
Distraction-free (zen) mode implementation.

When activated:
* All toolbars, menu bar, status bar, and docks are hidden.
* The editor canvas is centred with a configurable max-width.
* A subtle full-screen ambient background is applied.
* A hover-activated top strip shows a minimal exit button.
* The Escape key exits distraction-free mode.
* A word-count badge floats in the bottom-centre.

Toggling is managed by ``DistractionFreeMode.toggle(main_window)``.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, Slot
from PySide6.QtGui import QColor, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QWidget,
)

if TYPE_CHECKING:
    from prasword.gui.main_window import MainWindow

from prasword.utils.logger import get_logger

log = get_logger(__name__)


class _ExitBanner(QWidget):
    """
    A translucent banner at the top of the screen shown on mouse hover.
    Contains an "Exit" button and the document title.
    """

    def __init__(self, parent: QWidget, on_exit) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setFixedHeight(40)
        self.setStyleSheet(
            "background: rgba(17,17,27,0.92);"
            "color: #cdd6f4;"
            "font-size: 9pt;"
        )
        from PySide6.QtWidgets import QHBoxLayout, QPushButton
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 4, 16, 4)

        self._title_lbl = QLabel("PrasWord — Distraction-Free Mode")
        layout.addWidget(self._title_lbl)
        layout.addStretch()

        exit_btn = QPushButton("✕ Exit  (Esc)")
        exit_btn.setStyleSheet(
            "QPushButton { background: #45475a; border-radius: 4px; "
            "padding: 3px 12px; color: #cdd6f4; }"
            "QPushButton:hover { background: #585b70; }"
        )
        exit_btn.clicked.connect(on_exit)
        layout.addWidget(exit_btn)
        self.hide()

    def set_title(self, title: str) -> None:
        self._title_lbl.setText(f"PrasWord  ·  {title}")


class _WordCountBadge(QLabel):
    """Floating word-count label at the bottom-centre of the screen."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__("", parent)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet(
            "background: rgba(30,30,46,0.7);"
            "color: #6c7086;"
            "font-size: 9pt;"
            "padding: 3px 14px;"
            "border-radius: 10px;"
        )
        self._timer = QTimer(self)
        self._timer.setInterval(500)
        self._timer.timeout.connect(self._refresh)
        self._doc = None

    def bind_document(self, doc) -> None:
        self._doc = doc
        self._timer.start()
        self._refresh()

    @Slot()
    def _refresh(self) -> None:
        if self._doc:
            wc = self._doc.word_count()
            self.setText(f"{wc:,} words")
            self.adjustSize()


class DistractionFreeMode:
    """
    Manages distraction-free mode for the main window.

    Usage
    -----
    >>> DistractionFreeMode.enter(main_window)
    >>> DistractionFreeMode.exit(main_window)
    >>> DistractionFreeMode.toggle(main_window)
    """

    _active: bool = False
    _banner: Optional[_ExitBanner] = None
    _badge: Optional[_WordCountBadge] = None
    _shortcut: Optional[QShortcut] = None

    @classmethod
    def is_active(cls) -> bool:
        return cls._active

    @classmethod
    def toggle(cls, window: "MainWindow") -> bool:
        """
        Toggle distraction-free mode.

        Returns
        -------
        bool
            ``True`` if mode was just entered, ``False`` if just exited.
        """
        if cls._active:
            cls.exit(window)
            return False
        else:
            cls.enter(window)
            return True

    @classmethod
    def enter(cls, window: "MainWindow") -> None:
        """
        Enter distraction-free mode.

        Parameters
        ----------
        window : MainWindow
        """
        if cls._active:
            return

        cls._active = True
        log.info("Entering distraction-free mode.")

        # ── Hide all chrome ───────────────────────────────────────────
        window.menuBar().hide()
        for tb in window.findChildren(type(window.findChild(__import__("PySide6.QtWidgets", fromlist=["QToolBar"]).QToolBar))):
            tb.hide()
        window.statusBar().hide()
        for dock in window.findChildren(__import__("PySide6.QtWidgets", fromlist=["QDockWidget"]).QDockWidget):
            dock.hide()

        # ── Wide, centred margins on the active editor ───────────────
        editor = cls._get_editor(window)
        if editor:
            editor.set_distraction_free(True)

        # ── Floating exit banner ──────────────────────────────────────
        cls._banner = _ExitBanner(window.centralWidget(), lambda: cls.exit(window))
        cls._banner.setGeometry(0, 0, window.width(), 40)
        doc = window._doc_manager.active_document
        if doc:
            cls._banner.set_title(doc.title)

        # ── Floating word-count badge ─────────────────────────────────
        cls._badge = _WordCountBadge(window.centralWidget())
        cls._badge.show()
        if doc:
            cls._badge.bind_document(doc)
        cls._reposition_badge(window)

        # ── Escape shortcut ───────────────────────────────────────────
        cls._shortcut = QShortcut(QKeySequence("Escape"), window)
        cls._shortcut.activated.connect(lambda: cls.exit(window))

        # ── Mouse tracking to show/hide banner ───────────────────────
        window.centralWidget().setMouseTracking(True)
        window.centralWidget().installEventFilter(_BannerFilter(cls._banner))

        log.debug("Distraction-free mode active.")

    @classmethod
    def exit(cls, window: "MainWindow") -> None:
        """
        Exit distraction-free mode and restore all UI chrome.

        Parameters
        ----------
        window : MainWindow
        """
        if not cls._active:
            return

        cls._active = False
        log.info("Exiting distraction-free mode.")

        # ── Restore chrome ────────────────────────────────────────────
        window.menuBar().show()
        for tb in window.findChildren(__import__("PySide6.QtWidgets", fromlist=["QToolBar"]).QToolBar):
            tb.show()
        window.statusBar().show()
        for dock in window.findChildren(__import__("PySide6.QtWidgets", fromlist=["QDockWidget"]).QDockWidget):
            dock.show()

        editor = cls._get_editor(window)
        if editor:
            editor.set_distraction_free(False)

        # ── Clean up overlays ─────────────────────────────────────────
        if cls._banner:
            cls._banner.deleteLater()
            cls._banner = None
        if cls._badge:
            cls._badge._timer.stop()
            cls._badge.deleteLater()
            cls._badge = None
        if cls._shortcut:
            cls._shortcut.setEnabled(False)
            cls._shortcut.deleteLater()
            cls._shortcut = None

        # Update the toolbar toggle button state if it exists.
        action = getattr(window, "action_distraction_free", None)
        if action:
            action.setChecked(False)

    @classmethod
    def _get_editor(cls, window):
        doc = getattr(window, "_doc_manager", None)
        if doc and doc.active_document:
            editors = getattr(window, "_editors", {})
            return editors.get(doc.active_document.id)
        return None

    @classmethod
    def _reposition_badge(cls, window) -> None:
        if cls._badge:
            cw = window.centralWidget()
            bw = 160; bh = 26
            cls._badge.setGeometry(
                (cw.width() - bw) // 2,
                cw.height() - bh - 20,
                bw, bh
            )


class _BannerFilter:
    """Event filter that shows the exit banner on mouse-near-top."""

    def __init__(self, banner: _ExitBanner) -> None:
        self._banner = banner

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent
        if event.type() == QEvent.MouseMove:
            y = event.position().y() if hasattr(event, "position") else event.y()
            if y < 60:
                self._banner.show()
            else:
                self._banner.hide()
        return False
