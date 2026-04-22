"""
prasword.gui.dialogs.math_dialog
=================================
LaTeX math insertion dialog with live preview and snippet library.

Features
--------
* Syntax-highlighted LaTeX source editor (monospace font, dark background).
* Snippet picker with 18 common expressions categorised by topic.
* Debounced live preview — rendered PNG via matplotlib if available,
  falling back to a styled raw-LaTeX label.
* Sympy/latex2sympy2 validation with green/amber feedback.
* Display mode ($$…$$) vs inline mode ($…$) toggle.
* Keyboard: Ctrl+Enter inserts; Escape cancels.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QFont, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from prasword.utils.logger import get_logger

log = get_logger(__name__)

# ── Snippet library ─────────────────────────────────────────────────────────

_SNIPPETS: dict[str, dict[str, str]] = {
    "── Algebra ──": {},
    "Fraction":              r"\frac{a}{b}",
    "Square root":           r"\sqrt{x}",
    "nth root":              r"\sqrt[n]{x}",
    "Power / exponent":      r"x^{n}",
    "── Calculus ──": {},
    "Derivative":            r"\frac{d}{dx} f(x)",
    "Partial derivative":    r"\frac{\partial f}{\partial x}",
    "Definite integral":     r"\int_{a}^{b} f(x)\,dx",
    "Double integral":       r"\iint_{D} f(x,y)\,dA",
    "Limit":                 r"\lim_{x \to \infty} \frac{1}{x} = 0",
    "── Summation ──": {},
    "Sum":                   r"\sum_{i=1}^{n} x_i",
    "Product":               r"\prod_{i=1}^{n} x_i",
    "── Linear Algebra ──": {},
    "Matrix 2×2":            r"\begin{pmatrix} a & b \\ c & d \end{pmatrix}",
    "Determinant":           r"\det\begin{vmatrix} a & b \\ c & d \end{vmatrix}",
    "Vector":                r"\vec{v} = \begin{pmatrix} v_1 \\ v_2 \\ v_3 \end{pmatrix}",
    "── Statistics ──": {},
    "Expected value":        r"\mathbb{E}[X] = \sum_{x} x\, P(X=x)",
    "Normal distribution":   r"X \sim \mathcal{N}(\mu, \sigma^2)",
    "── Physics ──": {},
    "Einstein energy":       r"E = mc^2",
    "Schrödinger":           r"i\hbar\frac{\partial}{\partial t}\Psi = \hat{H}\Psi",
    "Maxwell (Gauss E)":     r"\nabla \cdot \mathbf{E} = \frac{\rho}{\varepsilon_0}",
    "── Greek letters ──": {},
    "Greek (common)":        r"\alpha + \beta = \gamma \cdot \delta",
    "Greek (upper)":         r"\Gamma \Delta \Theta \Lambda \Xi \Pi \Sigma \Phi \Psi \Omega",
}


class MathDialog(QDialog):
    """
    LaTeX math insertion dialog.

    Call ``latex_text()`` after ``exec()`` returns ``Accepted`` to get
    the validated LaTeX source.
    """

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Insert Math — LaTeX")
        self.setMinimumSize(580, 440)
        self.resize(620, 480)
        self._build_ui()
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(450)
        self._preview_timer.timeout.connect(self._update_preview)
        self._connect_shortcuts()

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def latex_text(self) -> str:
        """Return the current LaTeX source (stripped, without delimiters)."""
        return self._source_edit.toPlainText().strip()

    def is_display_mode(self) -> bool:
        """True → $$…$$  display block; False → $…$ inline."""
        return self._chk_display.isChecked()

    # ------------------------------------------------------------------ #
    # Build UI                                                             #
    # ------------------------------------------------------------------ #

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # ── Snippet picker ────────────────────────────────────────────
        snip_row = QHBoxLayout()
        snip_row.addWidget(QLabel("Snippet:"))
        self._snip_combo = QComboBox()
        self._snip_combo.setMinimumWidth(220)
        for key, val in _SNIPPETS.items():
            if not val:          # section header
                self._snip_combo.addItem(key)
                idx = self._snip_combo.count() - 1
                # Make the header item non-selectable and visually distinct
                model = self._snip_combo.model()
                item = model.item(idx)
                if item:
                    item.setEnabled(False)
                    item.setForeground(Qt.gray)
            else:
                self._snip_combo.addItem(key)
        self._snip_combo.currentTextChanged.connect(self._on_snippet_chosen)
        snip_row.addWidget(self._snip_combo)
        snip_row.addStretch()
        self._chk_display = QCheckBox("Display block ($$)")
        self._chk_display.setChecked(True)
        snip_row.addWidget(self._chk_display)
        root.addLayout(snip_row)

        # ── Source editor ─────────────────────────────────────────────
        src_box = QGroupBox("LaTeX source  (without surrounding $$ or $ delimiters)")
        src_layout = QVBoxLayout(src_box)
        self._source_edit = QTextEdit()
        self._source_edit.setPlaceholderText(r"e.g.   \frac{a}{b} + \sqrt{c}")
        self._source_edit.setFont(QFont("Courier New", 11))
        self._source_edit.setStyleSheet(
            "QTextEdit {"
            "  background: #1e1e2e;"
            "  color: #cdd6f4;"
            "  border: 1px solid #45475a;"
            "  border-radius: 5px;"
            "  padding: 6px;"
            "}"
        )
        self._source_edit.setMinimumHeight(80)
        self._source_edit.setMaximumHeight(130)
        self._source_edit.textChanged.connect(self._preview_timer.start)
        src_layout.addWidget(self._source_edit)

        # Validation label
        self._valid_label = QLabel("")
        self._valid_label.setStyleSheet("font-size: 9pt;")
        src_layout.addWidget(self._valid_label)
        root.addWidget(src_box)

        # ── Preview ───────────────────────────────────────────────────
        prev_box = QGroupBox("Preview")
        prev_layout = QVBoxLayout(prev_box)
        self._preview_label = QLabel("(type LaTeX above to preview)")
        self._preview_label.setAlignment(Qt.AlignCenter)
        self._preview_label.setMinimumHeight(90)
        self._preview_label.setStyleSheet(
            "background: #11111b;"
            "border-radius: 6px;"
            "padding: 16px;"
            "color: #cdd6f4;"
            "font-size: 13pt;"
        )
        self._preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        prev_layout.addWidget(self._preview_label)
        root.addWidget(prev_box)

        # ── Buttons ───────────────────────────────────────────────────
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_cancel = QPushButton("Cancel")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        self._btn_insert = QPushButton("Insert  (Ctrl+Enter)")
        self._btn_insert.setDefault(True)
        self._btn_insert.clicked.connect(self.accept)
        btn_row.addWidget(self._btn_insert)
        root.addLayout(btn_row)

    def _connect_shortcuts(self) -> None:
        ins = QShortcut(QKeySequence("Ctrl+Return"), self)
        ins.activated.connect(self.accept)
        esc = QShortcut(QKeySequence("Escape"), self)
        esc.activated.connect(self.reject)

    # ------------------------------------------------------------------ #
    # Slots                                                                #
    # ------------------------------------------------------------------ #

    @Slot(str)
    def _on_snippet_chosen(self, name: str) -> None:
        if name in _SNIPPETS and _SNIPPETS[name]:
            self._source_edit.setPlainText(_SNIPPETS[name])
            self._source_edit.setFocus()

    @Slot()
    def _update_preview(self) -> None:
        latex = self.latex_text()
        if not latex:
            self._preview_label.setText("(type LaTeX above to preview)")
            self._valid_label.setText("")
            return

        # ── Validation ────────────────────────────────────────────────
        self._run_validation(latex)

        # ── Try matplotlib render ─────────────────────────────────────
        png = self._render_png(latex)
        if png:
            pixmap = QPixmap()
            pixmap.loadFromData(png)
            self._preview_label.setPixmap(
                pixmap.scaled(
                    self._preview_label.width() - 32,
                    self._preview_label.height() - 16,
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation,
                )
            )
        else:
            delimiter = "$$" if self._chk_display.isChecked() else "$"
            self._preview_label.setText(f"{delimiter} {latex} {delimiter}")

    def _run_validation(self, latex: str) -> None:
        """Try sympy/latex2sympy2; update _valid_label."""
        try:
            from prasword.features.datascience.math_renderer import MathRenderer
            ok, err = MathRenderer.validate_latex(latex)
            if ok:
                self._valid_label.setText("✓  Valid LaTeX")
                self._valid_label.setStyleSheet("color: #a6e3a1; font-size: 9pt;")
            else:
                short = err[:100] if len(err) > 100 else err
                self._valid_label.setText(f"⚠  {short}")
                self._valid_label.setStyleSheet("color: #f9e2af; font-size: 9pt;")
        except Exception:
            self._valid_label.setText("")

    def _render_png(self, latex: str) -> bytes | None:
        """Return PNG bytes from matplotlib, or None if unavailable."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            import io

            fig = plt.figure(figsize=(0.01, 0.01), facecolor="none")
            fig.patch.set_alpha(0)
            text = fig.text(0, 0, f"${latex}$", fontsize=14, color="#cdd6f4")
            fig.canvas.draw()
            bbox = text.get_window_extent(fig.canvas.get_renderer())
            fig.set_size_inches(
                max(0.5, bbox.width / fig.dpi + 0.2),
                max(0.3, bbox.height / fig.dpi + 0.2),
            )
            text.set_position((0.05, 0.1))
            buf = io.BytesIO()
            fig.savefig(buf, format="png", dpi=150, transparent=True,
                        bbox_inches="tight", facecolor="none")
            plt.close(fig)
            buf.seek(0)
            return buf.read()
        except Exception:
            return None
