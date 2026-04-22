"""
prasword.gui.dialogs.preferences_dialog
========================================
Application preferences dialog — four tabs:

  Appearance   Theme, editor font family & size, UI scale.
  Editor       Line spacing, tab width, line numbers, auto-save, page view.
  Metrics      Which counters appear in the status bar and metrics dock.
  Advanced     Log level, data directory, reset factory defaults.

Changes are applied live (theme switch, font change) via AppConfig.
"""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from PySide6.QtCore import Qt, Slot
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QSlider,
    QSpinBox,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from prasword.utils.config import AppConfig

from prasword.utils.logger import get_logger
from prasword.utils.theme_manager import ThemeManager

log = get_logger(__name__)


class PreferencesDialog(QDialog):
    """
    Multi-tab preferences dialog backed by AppConfig.

    Parameters
    ----------
    config : AppConfig
    parent : QWidget | None
    """

    def __init__(self, config: "AppConfig", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._config = config
        self._pending_theme: str = config.get("appearance/theme", "dark")
        self.setWindowTitle("Preferences")
        self.setMinimumSize(520, 460)
        self.resize(560, 500)
        self._build_ui()
        self._load_values()

    # ------------------------------------------------------------------ #
    # UI construction                                                      #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        self._tabs = QTabWidget()

        self._tabs.addTab(self._build_appearance_tab(), "🎨 Appearance")
        self._tabs.addTab(self._build_editor_tab(),     "✏️  Editor")
        self._tabs.addTab(self._build_metrics_tab(),    "📊 Metrics")
        self._tabs.addTab(self._build_advanced_tab(),   "⚙️  Advanced")

        root.addWidget(self._tabs, 1)

        # ── Bottom buttons ────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_reset = QPushButton("Reset to Defaults")
        btn_reset.clicked.connect(self._reset_defaults)
        btn_row.addWidget(btn_reset)
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_apply = QPushButton("Apply")
        btn_apply.clicked.connect(self._apply)
        btn_row.addWidget(btn_apply)
        btn_ok = QPushButton("OK")
        btn_ok.setDefault(True)
        btn_ok.clicked.connect(self._ok)
        btn_row.addWidget(btn_ok)
        root.addLayout(btn_row)

    # ── Tab: Appearance ───────────────────────────────────────────────

    def _build_appearance_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(12)
        form.setContentsMargins(16, 16, 16, 8)

        # Theme
        self._theme_combo = QComboBox()
        self._theme_combo.addItems(ThemeManager.available_themes())
        self._theme_combo.currentTextChanged.connect(self._on_theme_preview)
        form.addRow("Colour theme:", self._theme_combo)

        # Editor font family
        self._font_combo = QComboBox()
        self._font_combo.setEditable(True)
        self._font_combo.setInsertPolicy(QComboBox.NoInsert)
        db = QFontDatabase()
        self._font_combo.addItems(sorted(db.families()))
        self._font_combo.setMinimumWidth(200)
        form.addRow("Editor font:", self._font_combo)

        # Font size
        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(7, 48)
        self._font_size_spin.setSuffix(" pt")
        form.addRow("Font size:", self._font_size_spin)

        # UI scale note
        note = QLabel(
            "Note: UI element scaling follows your OS display settings."
        )
        note.setStyleSheet("color: #6c7086; font-size: 8pt;")
        note.setWordWrap(True)
        form.addRow(note)

        return w

    # ── Tab: Editor ────────────────────────────────────────────────────

    def _build_editor_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 8)

        # Line spacing
        self._line_spacing_spin = QDoubleSpinBox()
        self._line_spacing_spin.setRange(1.0, 4.0)
        self._line_spacing_spin.setSingleStep(0.25)
        self._line_spacing_spin.setDecimals(2)
        self._line_spacing_spin.setSuffix("×")
        form.addRow("Default line spacing:", self._line_spacing_spin)

        # Tab width
        self._tab_width_spin = QSpinBox()
        self._tab_width_spin.setRange(2, 8)
        self._tab_width_spin.setSuffix(" spaces")
        form.addRow("Tab width:", self._tab_width_spin)

        # Paragraph spacing
        self._para_spacing_spin = QDoubleSpinBox()
        self._para_spacing_spin.setRange(0.0, 48.0)
        self._para_spacing_spin.setSingleStep(2.0)
        self._para_spacing_spin.setSuffix(" pt")
        form.addRow("Paragraph spacing (after):", self._para_spacing_spin)

        # Checkboxes
        self._chk_line_nums = QCheckBox("Show line numbers")
        form.addRow(self._chk_line_nums)

        self._chk_autosave = QCheckBox("Auto-save open documents")
        form.addRow(self._chk_autosave)

        self._autosave_spin = QSpinBox()
        self._autosave_spin.setRange(10, 600)
        self._autosave_spin.setSingleStep(10)
        self._autosave_spin.setSuffix(" seconds")
        form.addRow("Auto-save interval:", self._autosave_spin)

        self._chk_spell = QCheckBox("Enable spell check  (requires pyenchant)")
        self._chk_spell.setEnabled(False)   # placeholder for future feature
        form.addRow(self._chk_spell)

        return w

    # ── Tab: Metrics ───────────────────────────────────────────────────

    def _build_metrics_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 8)
        layout.setSpacing(10)

        status_box = QGroupBox("Status bar")
        sl = QVBoxLayout(status_box)
        self._chk_wc  = QCheckBox("Show word count")
        self._chk_cc  = QCheckBox("Show character count")
        self._chk_rt  = QCheckBox("Show reading time estimate")
        self._chk_pos = QCheckBox("Show cursor line / column")
        for chk in (self._chk_wc, self._chk_cc, self._chk_rt, self._chk_pos):
            sl.addWidget(chk)
        layout.addWidget(status_box)

        dock_box = QGroupBox("Metrics dock panel")
        dl = QVBoxLayout(dock_box)
        self._chk_unique  = QCheckBox("Show unique word count")
        self._chk_para    = QCheckBox("Show paragraph count")
        self._chk_sent    = QCheckBox("Show sentence count")
        self._chk_avgword = QCheckBox("Show average word length")
        for chk in (self._chk_unique, self._chk_para, self._chk_sent, self._chk_avgword):
            dl.addWidget(chk)
        layout.addWidget(dock_box)
        layout.addStretch()
        return w

    # ── Tab: Advanced ──────────────────────────────────────────────────

    def _build_advanced_tab(self) -> QWidget:
        w = QWidget()
        form = QFormLayout(w)
        form.setSpacing(10)
        form.setContentsMargins(16, 16, 16, 8)

        # Log level
        self._log_combo = QComboBox()
        self._log_combo.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        form.addRow("Log level:", self._log_combo)

        # Git auto-commit
        self._chk_git_auto = QCheckBox("Auto-commit on save (requires gitpython)")
        form.addRow(self._chk_git_auto)

        # Config file location
        try:
            from PySide6.QtCore import QSettings
            cfg_path = QSettings().fileName()
        except Exception:
            cfg_path = "~/.config/PrasWord/PrasWord.ini"
        loc_label = QLabel(cfg_path)
        loc_label.setStyleSheet("color: #6c7086; font-size: 8pt;")
        loc_label.setWordWrap(True)
        form.addRow("Settings file:", loc_label)

        # Reset button (inside tab too)
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_reset = QPushButton("🗑  Reset All to Factory Defaults")
        btn_reset.setStyleSheet("color: #f38ba8;")
        btn_reset.clicked.connect(self._reset_defaults)
        btn_row.addWidget(btn_reset)
        form.addRow(btn_row)

        return w

    # ------------------------------------------------------------------ #
    # Load / Save values                                                   #
    # ------------------------------------------------------------------ #

    def _load_values(self) -> None:
        c = self._config

        # Appearance
        theme = c.get("appearance/theme", "dark")
        idx = self._theme_combo.findText(theme)
        self._theme_combo.setCurrentIndex(max(0, idx))
        self._font_combo.setCurrentText(c.get("appearance/font_family", "Georgia"))
        self._font_size_spin.setValue(int(c.get("appearance/font_size", 11)))

        # Editor
        self._line_spacing_spin.setValue(float(c.get("editor/line_spacing", 1.5)))
        self._tab_width_spin.setValue(int(c.get("editor/tab_width", 4)))
        self._para_spacing_spin.setValue(float(c.get("editor/paragraph_spacing_after", 6.0)))
        self._chk_line_nums.setChecked(bool(c.get("editor/show_line_numbers", True)))
        self._chk_autosave.setChecked(bool(c.get("editor/auto_save", True)))
        self._autosave_spin.setValue(int(c.get("editor/auto_save_interval_seconds", 60)))

        # Metrics
        self._chk_wc.setChecked(bool(c.get("metrics/show_word_count", True)))
        self._chk_cc.setChecked(bool(c.get("metrics/show_char_count", True)))
        self._chk_rt.setChecked(bool(c.get("metrics/show_reading_time", True)))
        self._chk_pos.setChecked(bool(c.get("metrics/show_cursor_pos", True)))
        self._chk_unique.setChecked(bool(c.get("metrics/show_unique_words", True)))
        self._chk_para.setChecked(bool(c.get("metrics/show_paragraph_count", True)))
        self._chk_sent.setChecked(bool(c.get("metrics/show_sentence_count", True)))
        self._chk_avgword.setChecked(bool(c.get("metrics/show_avg_word_length", True)))

        # Advanced
        log_level = c.get("logging/level", "INFO")
        lidx = self._log_combo.findText(log_level)
        self._log_combo.setCurrentIndex(max(0, lidx))
        self._chk_git_auto.setChecked(bool(c.get("git/auto_commit", False)))

    def _save_values(self) -> None:
        c = self._config
        c.set("appearance/theme",                  self._theme_combo.currentText())
        c.set("appearance/font_family",             self._font_combo.currentText())
        c.set("appearance/font_size",               self._font_size_spin.value())
        c.set("editor/line_spacing",                self._line_spacing_spin.value())
        c.set("editor/tab_width",                   self._tab_width_spin.value())
        c.set("editor/paragraph_spacing_after",     self._para_spacing_spin.value())
        c.set("editor/show_line_numbers",           self._chk_line_nums.isChecked())
        c.set("editor/auto_save",                   self._chk_autosave.isChecked())
        c.set("editor/auto_save_interval_seconds",  self._autosave_spin.value())
        c.set("metrics/show_word_count",            self._chk_wc.isChecked())
        c.set("metrics/show_char_count",            self._chk_cc.isChecked())
        c.set("metrics/show_reading_time",          self._chk_rt.isChecked())
        c.set("metrics/show_cursor_pos",            self._chk_pos.isChecked())
        c.set("metrics/show_unique_words",          self._chk_unique.isChecked())
        c.set("metrics/show_paragraph_count",       self._chk_para.isChecked())
        c.set("metrics/show_sentence_count",        self._chk_sent.isChecked())
        c.set("metrics/show_avg_word_length",       self._chk_avgword.isChecked())
        c.set("logging/level",                      self._log_combo.currentText())
        c.set("git/auto_commit",                    self._chk_git_auto.isChecked())

    # ------------------------------------------------------------------ #
    # Slots                                                                #
    # ------------------------------------------------------------------ #

    @Slot(str)
    def _on_theme_preview(self, theme: str) -> None:
        """Live-preview the theme while the combo changes."""
        self._pending_theme = theme
        ThemeManager.apply(QApplication.instance(), theme)

    @Slot()
    def _apply(self) -> None:
        self._save_values()
        # Apply font change live
        family = self._font_combo.currentText()
        size   = self._font_size_spin.value()
        QApplication.instance().setFont(QFont(family, size))
        log.info("Preferences applied.")

    @Slot()
    def _ok(self) -> None:
        self._apply()
        self.accept()

    @Slot()
    def _reset_defaults(self) -> None:
        reply = QMessageBox.question(
            self, "Reset Preferences",
            "Reset all preferences to factory defaults?\n\n"
            "This cannot be undone.",
            QMessageBox.Yes | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        if reply == QMessageBox.Yes:
            self._config.reset_all()
            self._load_values()
            ThemeManager.apply(QApplication.instance(), "dark")
            log.info("Preferences reset to defaults.")
