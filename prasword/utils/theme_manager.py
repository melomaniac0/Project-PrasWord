"""
prasword.utils.theme_manager
=============================
Runtime theme (dark / light) switching for PrasWord.

``ThemeManager`` owns two QSS (Qt Style Sheet) templates — one for dark mode
and one for light mode — and applies them to the running ``QApplication``.

The stylesheets use CSS variables emulated via Python string substitution so
that a single template can be parameterised for both themes.

Extending themes
----------------
Add a new entry to ``_THEMES`` dict with the required colour tokens and a
corresponding QSS template, then call ``ThemeManager.apply(app, "name")``.
"""

from __future__ import annotations

from typing import ClassVar

from PySide6.QtWidgets import QApplication

from prasword.utils.logger import get_logger

log = get_logger(__name__)

# ---------------------------------------------------------------------------
# Colour tokens per theme
# ---------------------------------------------------------------------------

_TOKENS: dict[str, dict[str, str]] = {
    "dark": {
        "bg_primary":     "#1e1e2e",
        "bg_secondary":   "#181825",
        "bg_tertiary":    "#11111b",
        "bg_surface":     "#313244",
        "bg_overlay":     "#45475a",
        "text_primary":   "#cdd6f4",
        "text_secondary": "#a6adc8",
        "text_muted":     "#6c7086",
        "accent":         "#89b4fa",
        "accent_hover":   "#b4befe",
        "accent_pressed": "#74c7ec",
        "success":        "#a6e3a1",
        "warning":        "#f9e2af",
        "error":          "#f38ba8",
        "border":         "#45475a",
        "scrollbar":      "#585b70",
        "selection_bg":   "#89b4fa44",
    },
    "light": {
        "bg_primary":     "#eff1f5",
        "bg_secondary":   "#e6e9ef",
        "bg_tertiary":    "#dce0e8",
        "bg_surface":     "#ccd0da",
        "bg_overlay":     "#bcc0cc",
        "text_primary":   "#4c4f69",
        "text_secondary": "#5c5f77",
        "text_muted":     "#9ca0b0",
        "accent":         "#1e66f5",
        "accent_hover":   "#209fb5",
        "accent_pressed": "#04a5e5",
        "success":        "#40a02b",
        "warning":        "#df8e1d",
        "error":          "#d20f39",
        "border":         "#bcc0cc",
        "scrollbar":      "#acb0be",
        "selection_bg":   "#1e66f522",
    },
}

# ---------------------------------------------------------------------------
# QSS template (shared by all themes, parameterised by tokens)
# ---------------------------------------------------------------------------

_QSS_TEMPLATE = """
/* ── PrasWord stylesheet ─────────────────────────────────── */

QWidget {{
    background-color: {bg_primary};
    color: {text_primary};
    font-family: 'Segoe UI', 'SF Pro Text', 'Helvetica Neue', sans-serif;
    font-size: 10pt;
    border: none;
    outline: none;
}}

/* ── Main window & docks ────────────────────────────────── */
QMainWindow, QDockWidget {{
    background-color: {bg_secondary};
}}
QDockWidget::title {{
    background-color: {bg_tertiary};
    padding: 4px 8px;
    font-weight: 600;
    color: {text_secondary};
    font-size: 9pt;
    letter-spacing: 0.04em;
}}

/* ── Menu bar ───────────────────────────────────────────── */
QMenuBar {{
    background-color: {bg_tertiary};
    color: {text_primary};
    padding: 2px 4px;
    spacing: 2px;
}}
QMenuBar::item {{
    background-color: transparent;
    padding: 4px 12px;
    border-radius: 4px;
}}
QMenuBar::item:selected {{
    background-color: {bg_surface};
}}
QMenu {{
    background-color: {bg_surface};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 4px;
}}
QMenu::item {{
    padding: 6px 24px 6px 12px;
    border-radius: 4px;
}}
QMenu::item:selected {{
    background-color: {accent};
    color: {bg_tertiary};
}}
QMenu::separator {{
    height: 1px;
    background-color: {border};
    margin: 4px 8px;
}}

/* ── Tool bar ───────────────────────────────────────────── */
QToolBar {{
    background-color: {bg_secondary};
    border-bottom: 1px solid {border};
    spacing: 2px;
    padding: 2px 4px;
}}
QToolButton {{
    background-color: transparent;
    border-radius: 5px;
    padding: 4px 6px;
    color: {text_secondary};
}}
QToolButton:hover {{
    background-color: {bg_surface};
    color: {text_primary};
}}
QToolButton:checked, QToolButton:pressed {{
    background-color: {accent};
    color: {bg_tertiary};
}}

/* ── Tab bar (document tabs) ────────────────────────────── */
QTabBar::tab {{
    background-color: {bg_secondary};
    color: {text_muted};
    padding: 6px 16px;
    border-top-left-radius: 5px;
    border-top-right-radius: 5px;
    margin-right: 2px;
    font-size: 9pt;
}}
QTabBar::tab:selected {{
    background-color: {bg_primary};
    color: {text_primary};
    font-weight: 600;
}}
QTabBar::tab:hover:!selected {{
    background-color: {bg_surface};
    color: {text_secondary};
}}
QTabWidget::pane {{
    border: none;
    background-color: {bg_primary};
}}

/* ── Editor (QTextEdit) ─────────────────────────────────── */
QTextEdit {{
    background-color: {bg_primary};
    color: {text_primary};
    selection-background-color: {selection_bg};
    border: none;
    padding: 48px 72px;
    font-family: 'Georgia', 'Times New Roman', serif;
    font-size: 11pt;
    line-height: 1.6;
}}

/* ── Sidebar / file tree ────────────────────────────────── */
QTreeView {{
    background-color: {bg_secondary};
    color: {text_secondary};
    border: none;
    show-decoration-selected: 1;
    alternate-background-color: {bg_tertiary};
}}
QTreeView::item {{
    padding: 3px 4px;
    border-radius: 3px;
}}
QTreeView::item:selected {{
    background-color: {accent};
    color: {bg_tertiary};
}}
QTreeView::item:hover:!selected {{
    background-color: {bg_surface};
}}

/* ── Status bar ─────────────────────────────────────────── */
QStatusBar {{
    background-color: {bg_tertiary};
    color: {text_muted};
    font-size: 8pt;
    padding: 0 8px;
}}
QStatusBar::item {{
    border: none;
}}

/* ── Scroll bars ─────────────────────────────────────────── */
QScrollBar:vertical {{
    background-color: transparent;
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {scrollbar};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {text_muted};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar:horizontal {{
    background-color: transparent;
    height: 10px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background-color: {scrollbar};
    border-radius: 5px;
    min-width: 24px;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}

/* ── Push buttons ───────────────────────────────────────── */
QPushButton {{
    background-color: {bg_surface};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: 6px;
    padding: 6px 16px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {bg_overlay};
    border-color: {accent};
}}
QPushButton:pressed {{
    background-color: {accent};
    color: {bg_tertiary};
}}
QPushButton:disabled {{
    color: {text_muted};
    border-color: {bg_surface};
}}

/* ── Line / combo inputs ────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background-color: {bg_secondary};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: 5px;
    padding: 4px 8px;
    selection-background-color: {accent};
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
    border-color: {accent};
}}
QComboBox::drop-down {{
    border: none;
    padding-right: 6px;
}}
QComboBox QAbstractItemView {{
    background-color: {bg_surface};
    border: 1px solid {border};
    selection-background-color: {accent};
}}

/* ── Sliders ────────────────────────────────────────────── */
QSlider::groove:horizontal {{
    background-color: {bg_surface};
    height: 4px;
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background-color: {accent};
    width: 14px;
    height: 14px;
    border-radius: 7px;
    margin: -5px 0;
}}

/* ── Progress bar ───────────────────────────────────────── */
QProgressBar {{
    background-color: {bg_surface};
    border-radius: 4px;
    text-align: center;
    color: {text_primary};
    height: 8px;
}}
QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 4px;
}}

/* ── Tooltips ───────────────────────────────────────────── */
QToolTip {{
    background-color: {bg_overlay};
    color: {text_primary};
    border: 1px solid {border};
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 9pt;
}}

/* ── Splitter handle ────────────────────────────────────── */
QSplitter::handle {{
    background-color: {border};
}}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical   {{ height: 1px; }}

/* ── Message / dialog ───────────────────────────────────── */
QMessageBox {{
    background-color: {bg_secondary};
}}
QDialog {{
    background-color: {bg_secondary};
}}
"""


class ThemeManager:
    """
    Static helper that applies a named theme to the running QApplication.

    Methods
    -------
    apply(app, theme_name)
        Apply a theme by name ("dark" | "light").
    available_themes()
        Return list of registered theme names.
    """

    _current_theme: ClassVar[str] = "dark"

    @classmethod
    def apply(cls, app: QApplication, theme_name: str) -> None:
        """
        Apply the named theme to *app*.

        Parameters
        ----------
        app : QApplication
        theme_name : str
            Must be one of the keys in the ``_TOKENS`` dict.
        """
        tokens = _TOKENS.get(theme_name)
        if tokens is None:
            log.warning(
                "Unknown theme %r; falling back to 'dark'.", theme_name
            )
            theme_name = "dark"
            tokens = _TOKENS["dark"]

        qss = _QSS_TEMPLATE.format(**tokens)
        app.setStyleSheet(qss)
        cls._current_theme = theme_name
        log.info("Theme applied: %s", theme_name)

    @classmethod
    def current_theme(cls) -> str:
        """Return the name of the currently active theme."""
        return cls._current_theme

    @classmethod
    def toggle(cls, app: QApplication) -> str:
        """
        Toggle between dark and light themes.

        Returns
        -------
        str
            The name of the newly active theme.
        """
        new_theme = "light" if cls._current_theme == "dark" else "dark"
        cls.apply(app, new_theme)
        return new_theme

    @staticmethod
    def available_themes() -> list[str]:
        """Return the list of registered theme names."""
        return list(_TOKENS.keys())
