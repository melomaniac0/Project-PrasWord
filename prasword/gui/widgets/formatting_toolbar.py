"""
prasword.gui.widgets.formatting_toolbar
========================================
A rich formatting toolbar widget that wraps ``FormattingEngine``.

Provides font family/size pickers, colour buttons, alignment toggles,
heading selector, and line-spacing dropdown — all wired to the active editor.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QDoubleSpinBox,
    QLabel,
    QSizePolicy,
    QSpinBox,
    QToolBar,
    QToolButton,
    QWidget,
)

from prasword.features.formatting.formatting_engine import FormattingEngine
from prasword.utils.logger import get_logger

log = get_logger(__name__)


class FormattingToolbar(QToolBar):
    """
    Formatting toolbar — bind to an ``EditorWidget`` via ``set_editor()``.

    Signals
    -------
    formatting_applied()
        Emitted after any formatting operation so the parent can update state.
    """

    formatting_applied = Signal()

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__("Character Formatting", parent)
        self.setObjectName("CharFormattingToolbar")
        self.setMovable(False)
        self._editor = None

        self._build_font_section()
        self.addSeparator()
        self._build_style_section()
        self.addSeparator()
        self._build_color_section()
        self.addSeparator()
        self._build_alignment_section()
        self.addSeparator()
        self._build_heading_section()
        self.addSeparator()
        self._build_spacing_section()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_editor(self, editor) -> None:
        """Bind this toolbar to *editor*."""
        self._editor = editor
        if editor:
            editor.cursorPositionChanged.connect(self._sync_state)
            editor.selectionChanged.connect(self._sync_state)

    # ------------------------------------------------------------------
    # Build sections
    # ------------------------------------------------------------------

    def _build_font_section(self) -> None:
        # Font family combo
        self._font_combo = QComboBox()
        self._font_combo.setMinimumWidth(160)
        self._font_combo.setMaximumWidth(200)
        self._font_combo.setEditable(True)
        db = QFontDatabase()
        self._font_combo.addItems(sorted(db.families()))
        self._font_combo.currentTextChanged.connect(self._on_font_family)
        self.addWidget(QLabel(" Font "))
        self.addWidget(self._font_combo)

        # Font size spinner
        self._size_spin = QSpinBox()
        self._size_spin.setRange(6, 144)
        self._size_spin.setValue(11)
        self._size_spin.setMaximumWidth(56)
        self._size_spin.valueChanged.connect(self._on_font_size)
        self.addWidget(QLabel(" Size "))
        self.addWidget(self._size_spin)

    def _build_style_section(self) -> None:
        def _btn(label: str, tip: str, checkable=True) -> QToolButton:
            b = QToolButton()
            b.setText(label)
            b.setToolTip(tip)
            b.setCheckable(checkable)
            b.setFixedWidth(30)
            return b

        self._btn_bold = _btn("B", "Bold (Ctrl+B)")
        self._btn_bold.setFont(QFont("", -1, QFont.Bold))
        self._btn_bold.clicked.connect(self._on_bold)
        self.addWidget(self._btn_bold)

        self._btn_italic = _btn("I", "Italic (Ctrl+I)")
        f = QFont(); f.setItalic(True)
        self._btn_italic.setFont(f)
        self._btn_italic.clicked.connect(self._on_italic)
        self.addWidget(self._btn_italic)

        self._btn_underline = _btn("U", "Underline (Ctrl+U)")
        fu = QFont(); fu.setUnderline(True)
        self._btn_underline.setFont(fu)
        self._btn_underline.clicked.connect(self._on_underline)
        self.addWidget(self._btn_underline)

        self._btn_strike = _btn("S̶", "Strikethrough")
        self._btn_strike.clicked.connect(self._on_strikethrough)
        self.addWidget(self._btn_strike)

        self._btn_sub = _btn("X₂", "Subscript", checkable=False)
        self._btn_sub.clicked.connect(self._on_subscript)
        self.addWidget(self._btn_sub)

        self._btn_sup = _btn("X²", "Superscript", checkable=False)
        self._btn_sup.clicked.connect(self._on_superscript)
        self.addWidget(self._btn_sup)

    def _build_color_section(self) -> None:
        self._btn_text_color = QToolButton()
        self._btn_text_color.setText("A")
        self._btn_text_color.setToolTip("Text Colour")
        self._btn_text_color.clicked.connect(self._on_text_color)
        self.addWidget(self._btn_text_color)

        self._btn_highlight = QToolButton()
        self._btn_highlight.setText("H")
        self._btn_highlight.setToolTip("Highlight Colour")
        self._btn_highlight.clicked.connect(self._on_highlight)
        self.addWidget(self._btn_highlight)

    def _build_alignment_section(self) -> None:
        align_data = [
            ("≡L", "Align Left",    Qt.AlignLeft),
            ("≡C", "Align Centre",  Qt.AlignHCenter),
            ("≡R", "Align Right",   Qt.AlignRight),
            ("≡J", "Justify",       Qt.AlignJustify),
        ]
        self._align_btns: list[QToolButton] = []
        for label, tip, flag in align_data:
            btn = QToolButton()
            btn.setText(label)
            btn.setToolTip(tip)
            btn.setCheckable(True)
            btn.setProperty("align_flag", flag)
            btn.clicked.connect(lambda _, f=flag: self._on_align(f))
            self._align_btns.append(btn)
            self.addWidget(btn)

    def _build_heading_section(self) -> None:
        self._heading_combo = QComboBox()
        self._heading_combo.addItems(
            ["Body", "H1", "H2", "H3", "H4", "H5", "H6"]
        )
        self._heading_combo.setMaximumWidth(70)
        self._heading_combo.currentIndexChanged.connect(self._on_heading)
        self.addWidget(QLabel(" ¶ "))
        self.addWidget(self._heading_combo)

    def _build_spacing_section(self) -> None:
        self._spacing_combo = QComboBox()
        self._spacing_combo.setToolTip("Line Spacing")
        self._spacing_combo.addItems(["1.0×", "1.15×", "1.5×", "2.0×", "3.0×"])
        self._spacing_combo.setCurrentIndex(2)  # default 1.5×
        self._spacing_combo.setMaximumWidth(70)
        self._spacing_combo.currentTextChanged.connect(self._on_spacing)
        self.addWidget(QLabel(" ↕ "))
        self.addWidget(self._spacing_combo)

        # Indent controls
        btn_in = QToolButton(); btn_in.setText("→|"); btn_in.setToolTip("Increase Indent")
        btn_in.clicked.connect(self._on_indent_in)
        self.addWidget(btn_in)

        btn_out = QToolButton(); btn_out.setText("|←"); btn_out.setToolTip("Decrease Indent")
        btn_out.clicked.connect(self._on_indent_out)
        self.addWidget(btn_out)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_font_family(self, family: str) -> None:
        if self._editor and family:
            FormattingEngine.set_font_family(self._editor, family)

    @Slot(int)
    def _on_font_size(self, size: int) -> None:
        if self._editor:
            FormattingEngine.set_font_size(self._editor, float(size))

    @Slot()
    def _on_bold(self) -> None:
        if self._editor:
            active = FormattingEngine.toggle_bold(self._editor)
            self._btn_bold.setChecked(active)

    @Slot()
    def _on_italic(self) -> None:
        if self._editor:
            active = FormattingEngine.toggle_italic(self._editor)
            self._btn_italic.setChecked(active)

    @Slot()
    def _on_underline(self) -> None:
        if self._editor:
            active = FormattingEngine.toggle_underline(self._editor)
            self._btn_underline.setChecked(active)

    @Slot()
    def _on_strikethrough(self) -> None:
        if self._editor:
            FormattingEngine.toggle_strikethrough(self._editor)

    @Slot()
    def _on_subscript(self) -> None:
        if self._editor:
            FormattingEngine.toggle_subscript(self._editor)

    @Slot()
    def _on_superscript(self) -> None:
        if self._editor:
            FormattingEngine.toggle_superscript(self._editor)

    @Slot()
    def _on_text_color(self) -> None:
        if not self._editor:
            return
        color = QColorDialog.getColor(Qt.white, self, "Choose Text Colour")
        if color.isValid():
            FormattingEngine.set_text_color(self._editor, color)

    @Slot()
    def _on_highlight(self) -> None:
        if not self._editor:
            return
        color = QColorDialog.getColor(QColor("#ffff00"), self, "Choose Highlight Colour")
        if color.isValid():
            FormattingEngine.set_highlight_color(self._editor, color)

    def _on_align(self, flag: Qt.AlignmentFlag) -> None:
        if self._editor:
            FormattingEngine.set_alignment(self._editor, flag)
        for btn in self._align_btns:
            btn.setChecked(btn.property("align_flag") == flag)

    @Slot(int)
    def _on_heading(self, index: int) -> None:
        if self._editor:
            FormattingEngine.apply_heading(self._editor, index)  # 0 = Body

    @Slot(str)
    def _on_spacing(self, text: str) -> None:
        if self._editor:
            factor = float(text.replace("×", ""))
            FormattingEngine.set_line_spacing(self._editor, factor)

    @Slot()
    def _on_indent_in(self) -> None:
        if self._editor:
            FormattingEngine.increase_indent(self._editor)

    @Slot()
    def _on_indent_out(self) -> None:
        if self._editor:
            FormattingEngine.decrease_indent(self._editor)

    # ------------------------------------------------------------------
    # State sync (cursor moved → update toolbar checked states)
    # ------------------------------------------------------------------

    @Slot()
    def _sync_state(self) -> None:
        if not self._editor:
            return
        self._btn_bold.setChecked(FormattingEngine.is_bold(self._editor))
        self._btn_italic.setChecked(FormattingEngine.is_italic(self._editor))
        self._btn_underline.setChecked(FormattingEngine.is_underline(self._editor))
        self._btn_strike.setChecked(FormattingEngine.is_strikethrough(self._editor))

        family = FormattingEngine.current_font_family(self._editor)
        idx = self._font_combo.findText(family)
        if idx >= 0:
            self._font_combo.blockSignals(True)
            self._font_combo.setCurrentIndex(idx)
            self._font_combo.blockSignals(False)

        size = int(FormattingEngine.current_font_size(self._editor))
        self._size_spin.blockSignals(True)
        self._size_spin.setValue(size)
        self._size_spin.blockSignals(False)
