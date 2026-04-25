"""
prasword.features.datascience.math_renderer
============================================
LaTeX math rendering for inline and display equations.

Rendering pipeline
------------------
1. validate_latex(latex)     — sympy / latex2sympy2 parse check (optional).
2. render_to_png(latex, …)   — matplotlib mathtext → PNG bytes (optional).
3. insert_rendered(…)        — PNG as inline QTextDocument image, or
                               styled monospace fallback if matplotlib absent.
4. insert_display_block(…)   — display-mode ($$…$$) equation on its own line.
5. insert_inline(…)          — inline ($…$) equation inside running text.

Image resource management
--------------------------
Each rendered PNG is added to the QTextDocument as a named resource using
``addResource(ImageResource, name, QByteArray)``.  The resource name encodes
both the hash of the LaTeX source and a counter so the same expression can be
inserted multiple times without collision.

Colour themes
-------------
Two built-in colour presets — "dark" (default, cream text on transparent) and
"light" (dark text on transparent) — which can be switched via
``MathRenderer.set_theme(name)``.

No external LaTeX installation is required; rendering uses matplotlib's
built-in mathtext engine (a subset of LaTeX).  If matplotlib is not installed
the expression is shown verbatim in a styled monospace block.

Dependencies
------------
Optional:
  matplotlib  (pip install matplotlib)  for PNG rendering
  latex2sympy2 or sympy  for expression validation
"""

from __future__ import annotations

import io
from typing import TYPE_CHECKING

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextImageFormat

if TYPE_CHECKING:
    from prasword.gui.editor_widget import EditorWidget

from prasword.utils.logger import get_logger

log = get_logger(__name__)

# ── Colour themes ─────────────────────────────────────────────────────────────

_THEMES: dict[str, dict] = {
    "dark": {
        "text_color": "#cdd6f4",
        "bg_color":   "#11111b",
        "dpi":        150,
    },
    "light": {
        "text_color": "#4c4f69",
        "bg_color":   "#eff1f5",
        "dpi":        150,
    },
}
_active_theme: str = "dark"

# Counter for unique image resource names within a session
_render_counter: int = 0


class MathRenderer:
    """
    Static helpers for LaTeX math rendering and insertion.
    """

    # ------------------------------------------------------------------ #
    # Theme                                                                #
    # ------------------------------------------------------------------ #

    @classmethod
    def set_theme(cls, name: str) -> None:
        """Switch the rendering colour theme ("dark" or "light")."""
        global _active_theme
        if name not in _THEMES:
            raise ValueError(f"Unknown theme {name!r}. Available: {list(_THEMES)}")
        _active_theme = name

    # ------------------------------------------------------------------ #
    # Public insertion API                                                  #
    # ------------------------------------------------------------------ #

    @staticmethod
    def insert_rendered(
        editor: "EditorWidget",
        latex: str,
        font_size: float = 14.0,
        display_mode: bool = False,
    ) -> bool:
        """
        Render *latex* and insert it at the cursor position.

        Tries matplotlib first; falls back to styled text if unavailable.

        Parameters
        ----------
        editor : EditorWidget
        latex : str
            LaTeX source without surrounding delimiters.
        font_size : float
            Rendered text size in points.
        display_mode : bool
            If True, insert as a centred display block; otherwise inline.

        Returns
        -------
        bool
            True if a PNG was rendered and inserted; False if text fallback.
        """
        latex = latex.strip()
        if not latex:
            return False

        theme    = _THEMES.get(_active_theme, _THEMES["dark"])
        color    = theme["text_color"]
        png      = MathRenderer._render_to_png(latex, font_size, color, theme["dpi"])

        if png:
            MathRenderer._insert_as_image(editor, png, latex, display_mode)
            return True

        MathRenderer._insert_as_text(editor, latex, display_mode)
        return False

    @staticmethod
    def insert_inline(editor: "EditorWidget", latex: str) -> bool:
        """Insert a $…$ inline equation at the cursor."""
        return MathRenderer.insert_rendered(editor, latex, font_size=11.0, display_mode=False)

    @staticmethod
    def insert_display_block(editor: "EditorWidget", latex: str) -> bool:
        """Insert a $$…$$ display equation on its own centred line."""
        return MathRenderer.insert_rendered(editor, latex, font_size=14.0, display_mode=True)

    # ------------------------------------------------------------------ #
    # Validation                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def validate_latex(latex: str) -> tuple[bool, str]:
        """
        Attempt to parse *latex* as a mathematical expression.

        Tries latex2sympy2 first, then bare sympy parsing.
        Returns (True, "") if valid or if neither library is available.

        Parameters
        ----------
        latex : str

        Returns
        -------
        tuple[bool, str]
            (is_valid, error_message)
        """
        latex = latex.strip()
        if not latex:
            return False, "Empty expression."

        # Try latex2sympy2
        try:
            from latex2sympy2 import latex2sympy
            latex2sympy(latex)
            return True, ""
        except Exception as exc:
            return False, str(exc)
        except ImportError:
            pass

        # Try sympy directly
        try:
            from sympy.parsing.latex import parse_latex
            parse_latex(latex)
            return True, ""
        except Exception as exc:
            return False, str(exc)
        except ImportError:
            pass

        # Neither library available — assume OK, matplotlib will catch bad syntax
        return True, ""

    # ------------------------------------------------------------------ #
    # Rendering                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _render_to_png(
        latex: str,
        font_size: float,
        color: str,
        dpi: int,
    ) -> bytes | None:
        """
        Render *latex* to a PNG byte string using matplotlib mathtext.

        Returns None if matplotlib is not installed or rendering fails.
        """
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError:
            log.debug("matplotlib not available — math will render as text.")
            return None

        try:
            # Create a minimal figure; we'll resize it to fit the text
            fig = plt.figure(figsize=(0.1, 0.1), facecolor="none")
            fig.patch.set_alpha(0.0)

            expr = f"${latex}$"
            txt  = fig.text(
                0.0, 0.0, expr,
                fontsize=font_size,
                color=color,
                usetex=False,
                ha="left",
                va="bottom",
            )

            # Draw once to get the bounding box
            fig.canvas.draw()
            renderer = fig.canvas.get_renderer()
            bbox     = txt.get_window_extent(renderer)

            # Resize figure to wrap tightly around the text
            pad = 0.15
            w_in = max(0.5, bbox.width  / dpi + pad)
            h_in = max(0.3, bbox.height / dpi + pad)
            fig.set_size_inches(w_in, h_in)
            txt.set_position((pad / 2 / w_in, pad / 2 / h_in))

            buf = io.BytesIO()
            fig.savefig(
                buf,
                format="png",
                dpi=dpi,
                transparent=True,
                bbox_inches="tight",
                facecolor="none",
            )
            plt.close(fig)
            buf.seek(0)
            data = buf.read()
            log.debug("Math PNG rendered: %d bytes  latex=%r", len(data), latex[:40])
            return data

        except Exception as exc:
            log.warning("Math render failed (%s): %s", type(exc).__name__, exc)
            return None

    @staticmethod
    def _insert_as_image(
        editor: "EditorWidget",
        png_bytes: bytes,
        latex: str,
        display_mode: bool,
    ) -> None:
        """Embed a rendered PNG as a QTextDocument image resource."""
        global _render_counter
        _render_counter += 1
        name = f"math_{_render_counter}_{abs(hash(latex)) % 99999}.png"

        # Register the image with the document
        editor.document().addResource(
            3,  # QTextDocument.ImageResource
            name,
            QByteArray(png_bytes),
        )

        img_fmt = QTextImageFormat()
        img_fmt.setName(name)
        img_fmt.setToolTip(f"LaTeX: {latex}")

        cursor = editor.textCursor()
        cursor.beginEditBlock()

        if display_mode:
            # Centre the image on its own line
            from PySide6.QtGui import QTextBlockFormat
            from PySide6.QtCore import Qt
            blk_fmt = editor.textCursor().blockFormat()
            blk_fmt.setAlignment(Qt.AlignHCenter)
            cursor.setBlockFormat(blk_fmt)
            cursor.insertBlock()
            cursor.setBlockFormat(blk_fmt)

        cursor.insertImage(img_fmt)

        if display_mode:
            # Restore left alignment after the image block
            from PySide6.QtGui import QTextBlockFormat
            from PySide6.QtCore import Qt
            restore = editor.textCursor().blockFormat()
            restore.setAlignment(Qt.AlignLeft)
            cursor.insertBlock()
            cursor.setBlockFormat(restore)

        cursor.endEditBlock()
        log.debug("Math image inserted: %s  display=%s", name, display_mode)

    @staticmethod
    def _insert_as_text(
        editor: "EditorWidget",
        latex: str,
        display_mode: bool,
    ) -> None:
        """
        Fallback: insert the raw LaTeX source as styled monospace text.
        """
        theme   = _THEMES.get(_active_theme, _THEMES["dark"])
        delim   = "$$" if display_mode else "$"
        display = f"{delim}{latex}{delim}"

        fmt = QTextCharFormat()
        fmt.setFont(QFont("Courier New", 11))
        fmt.setForeground(QColor("#f9e2af"))   # amber — signals "unrendered"
        fmt.setBackground(QColor(theme["bg_color"]))

        cursor = editor.textCursor()
        cursor.beginEditBlock()
        if display_mode:
            cursor.insertBlock()
        cursor.insertText(display, fmt)
        cursor.insertText(" ", QTextCharFormat())   # reset format
        if display_mode:
            cursor.insertBlock()
        cursor.endEditBlock()
