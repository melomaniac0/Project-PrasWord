"""
prasword.features.datascience.jupyter_cell
===========================================
Jupyter-style executable code cells embedded in the document.

Cell anatomy
------------
Each cell is a QTextFrame with:

  ┌─────────────────────────────────────────────────┐
  │ [PYTHON]  ▶ Run cell  ·  Ctrl+Enter  ·  ✕ Clear │  ← header bar
  ├─────────────────────────────────────────────────┤
  │ # code goes here                                │  ← editable code body
  ├─────────────────────────────────────────────────┤
  │ (output will appear here)                       │  ← output area
  └─────────────────────────────────────────────────┘

Execution
---------
``run_cell(code, language, callback)`` launches a subprocess so the kernel
runs in a separate process and cannot crash the editor.  A 30-second timeout
protects against infinite loops.

Supported languages: python, r, bash, julia (if interpreters are on PATH).

Output handling
---------------
``inject_output(editor, output_text, is_error)`` locates the output
placeholder in the cell frame and replaces it with stdout/stderr.

Security
--------
Code execution is intentionally obvious — the cell header is highlighted and
must be explicitly triggered.  No auto-execution on load or paste.

Thread safety
-------------
_ExecutionWorker uses QThread and emits ``finished(stdout, stderr)`` on the
main thread via Qt's signal/slot queued-connection mechanism.
"""

from __future__ import annotations

import subprocess
import sys
from typing import TYPE_CHECKING, Callable

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import (
    QColor,
    QFont,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
    QTextFrameFormat,
)

if TYPE_CHECKING:
    from prasword.gui.editor_widget import EditorWidget

from prasword.utils.logger import get_logger

log = get_logger(__name__)

# ── Style constants ───────────────────────────────────────────────────────────

_CELL_BG        = "#11111b"
_HEADER_BG      = "#181825"
_OUTPUT_BG      = "#1e1e2e"
_BORDER_COL     = "#45475a"
_HEADER_FG      = "#89b4fa"
_RUN_FG         = "#a6e3a1"
_CODE_FG        = "#cdd6f4"
_OUTPUT_FG      = "#a6adc8"
_ERROR_FG       = "#f38ba8"
_PLACEHOLDER_FG = "#585b70"

# Language → interpreter command
_INTERPRETERS: dict[str, list[str]] = {
    "python": [sys.executable, "-c"],
    "r":      ["Rscript", "-e"],
    "bash":   ["bash", "-c"],
    "julia":  ["julia", "-e"],
}

# Language → default stub code
_STUBS: dict[str, str] = {
    "python": (
        "# Python execution cell\n"
        "import sys\n"
        "print(f'Python {sys.version.split()[0]}')\n"
        "result = sum(range(1, 11))\n"
        "print(f'Sum 1..10 = {result}')\n"
    ),
    "r": (
        "# R execution cell\n"
        "cat(paste('R', R.version$major, R.version$minor), '\\n')\n"
        "x <- 1:10\n"
        "cat('Mean:', mean(x), '\\n')\n"
    ),
    "bash": (
        "#!/usr/bin/env bash\n"
        "echo \"Bash $(bash --version | head -1)\"\n"
        "echo \"Working dir: $(pwd)\"\n"
    ),
    "julia": (
        "# Julia execution cell\n"
        "println(\"Julia \", VERSION)\n"
        "println(\"Sum 1..10 = \", sum(1:10))\n"
    ),
}

# Keep thread references alive to avoid premature GC
_active_threads: list[tuple[QThread, QObject]] = []


# ── Worker ────────────────────────────────────────────────────────────────────

class _ExecutionWorker(QObject):
    """
    Runs code in a subprocess and emits stdout/stderr when done.

    Runs on a QThread; emits ``finished`` on that thread (Qt delivers
    the signal to the main thread through a queued connection).
    """

    finished = Signal(str, str)   # stdout, stderr

    def __init__(self, code: str, language: str, timeout: int = 30) -> None:
        super().__init__()
        self._code     = code
        self._language = language.lower()
        self._timeout  = timeout

    def run(self) -> None:
        cmd_prefix = _INTERPRETERS.get(self._language)
        if cmd_prefix is None:
            self.finished.emit("", f"Unsupported language: {self._language!r}")
            return

        try:
            result = subprocess.run(
                cmd_prefix + [self._code],
                capture_output=True,
                text=True,
                timeout=self._timeout,
            )
            self.finished.emit(result.stdout, result.stderr)
        except FileNotFoundError:
            interp = cmd_prefix[0]
            self.finished.emit(
                "",
                f"Interpreter not found: '{interp}'\n"
                f"Install it or add it to your PATH.",
            )
        except subprocess.TimeoutExpired:
            self.finished.emit(
                "",
                f"Execution timed out after {self._timeout} seconds.",
            )
        except Exception as exc:
            self.finished.emit("", f"Execution error: {exc}")


# ── JupyterCell ───────────────────────────────────────────────────────────────

class JupyterCell:
    """
    Static helpers for inserting and executing Jupyter-style cells.
    """

    # ------------------------------------------------------------------ #
    # Insert                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def insert_cell(
        editor: "EditorWidget",
        language: str = "python",
        code: str = "",
    ) -> None:
        """
        Insert a styled, executable code cell at the cursor position.

        Parameters
        ----------
        editor : EditorWidget
        language : str
            One of "python", "r", "bash", "julia".
        code : str
            Initial cell content.  Defaults to a language-specific stub.
        """
        lang_key   = language.lower()
        cell_code  = code or _STUBS.get(lang_key, f"# {language}\n")
        lang_label = language.upper()

        # ── Fonts ─────────────────────────────────────────────────────
        mono = QFont("Courier New", 10)
        mono.setStyleHint(QFont.Monospace)
        mono.setFixedPitch(True)

        ui_font = QFont("Segoe UI", 9)

        cursor = editor.textCursor()
        cursor.beginEditBlock()

        # ── Outer frame ───────────────────────────────────────────────
        frame_fmt = QTextFrameFormat()
        frame_fmt.setBorder(1)
        frame_fmt.setBorderBrush(QColor(_BORDER_COL))
        frame_fmt.setBackground(QColor(_CELL_BG))
        frame_fmt.setPadding(0)
        frame_fmt.setTopMargin(10)
        frame_fmt.setBottomMargin(10)

        frame  = cursor.insertFrame(frame_fmt)
        inner  = frame.firstCursorPosition()

        # ── Header bar ────────────────────────────────────────────────
        hdr_blk = QTextBlockFormat()
        hdr_blk.setBackground(QColor(_HEADER_BG))
        hdr_blk.setTopMargin(0)
        hdr_blk.setBottomMargin(0)
        hdr_blk.setLeftMargin(8)
        inner.setBlockFormat(hdr_blk)

        # Language tag
        tag_fmt = QTextCharFormat()
        tag_fmt.setFont(ui_font)
        tag_fmt.setFontWeight(QFont.Bold)
        tag_fmt.setForeground(QColor(_HEADER_FG))
        tag_fmt.setBackground(QColor(_HEADER_BG))
        inner.insertText(f"[{lang_label}]  ", tag_fmt)

        # Run instruction
        run_fmt = QTextCharFormat()
        run_fmt.setFont(ui_font)
        run_fmt.setForeground(QColor(_RUN_FG))
        run_fmt.setBackground(QColor(_HEADER_BG))
        inner.insertText("▶ Run  (Ctrl+Enter)  ", run_fmt)

        # Separator
        sep_fmt = QTextCharFormat()
        sep_fmt.setFont(ui_font)
        sep_fmt.setForeground(QColor(_BORDER_COL))
        sep_fmt.setBackground(QColor(_HEADER_BG))
        inner.insertText("│  ✕ Clear output", sep_fmt)

        # ── Code body ────────────────────────────────────────────────
        code_blk = QTextBlockFormat()
        code_blk.setBackground(QColor(_CELL_BG))
        code_blk.setTopMargin(4)
        code_blk.setBottomMargin(0)
        code_blk.setLeftMargin(8)
        inner.insertBlock(code_blk)

        code_fmt = QTextCharFormat()
        code_fmt.setFont(mono)
        code_fmt.setForeground(QColor(_CODE_FG))
        code_fmt.setBackground(QColor(_CELL_BG))
        inner.insertText(cell_code, code_fmt)

        # ── Output area ───────────────────────────────────────────────
        out_blk = QTextBlockFormat()
        out_blk.setBackground(QColor(_OUTPUT_BG))
        out_blk.setTopMargin(4)
        out_blk.setBottomMargin(4)
        out_blk.setLeftMargin(8)
        inner.insertBlock(out_blk)

        ph_fmt = QTextCharFormat()
        ph_fmt.setFont(ui_font)
        ph_fmt.setFontItalic(True)
        ph_fmt.setForeground(QColor(_PLACEHOLDER_FG))
        ph_fmt.setBackground(QColor(_OUTPUT_BG))
        inner.insertText("(output will appear here)", ph_fmt)

        cursor.endEditBlock()
        log.debug("Cell inserted: language=%s  lines=%d", lang_label, cell_code.count("\n"))

    # ------------------------------------------------------------------ #
    # Execution                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def run_cell(
        code: str,
        language: str,
        callback: Callable[[str, str], None],
        timeout: int = 30,
    ) -> None:
        """
        Execute *code* asynchronously in a subprocess.

        ``callback(stdout, stderr)`` is invoked on the main thread when
        execution completes (including on timeout or error).

        Parameters
        ----------
        code : str
        language : str
        callback : callable(stdout: str, stderr: str) → None
        timeout : int
            Maximum execution time in seconds.
        """
        worker = _ExecutionWorker(code, language, timeout)
        thread = QThread()
        worker.moveToThread(thread)

        # Queued connection delivers signal on main thread
        worker.finished.connect(callback)
        worker.finished.connect(thread.quit)
        thread.started.connect(worker.run)

        # Prevent GC
        _active_threads.append((thread, worker))
        thread.finished.connect(
            lambda: _active_threads.remove((thread, worker))
            if (thread, worker) in _active_threads else None
        )

        thread.start()
        log.debug("Cell execution started: language=%s  timeout=%ds", language, timeout)

    # ------------------------------------------------------------------ #
    # Output injection                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def inject_output(
        editor: "EditorWidget",
        output_text: str,
        is_error: bool = False,
    ) -> None:
        """
        Replace the output-area placeholder in the cell at the cursor
        with *output_text*.

        If the cursor is not inside a cell frame this method is a no-op.

        Parameters
        ----------
        editor : EditorWidget
        output_text : str
        is_error : bool
            If True, the output is coloured with the error colour.
        """
        cursor = editor.textCursor()
        frame  = cursor.currentFrame()
        if frame is None or frame == editor.document().rootFrame():
            log.debug("inject_output: cursor not inside a cell frame.")
            return

        qt_doc   = editor.document()
        ph_cursor = qt_doc.find("(output will appear here)", frame.firstPosition())
        if ph_cursor.isNull():
            ph_cursor = qt_doc.find("(output will appear here)")
        if ph_cursor.isNull():
            return

        mono = QFont("Courier New", 9)
        mono.setStyleHint(QFont.Monospace)

        out_fmt = QTextCharFormat()
        out_fmt.setFont(mono)
        out_fmt.setForeground(QColor(_ERROR_FG if is_error else _OUTPUT_FG))
        out_fmt.setBackground(QColor(_OUTPUT_BG))

        ph_cursor.beginEditBlock()
        ph_cursor.select(QTextCursor.LineUnderCursor)
        ph_cursor.insertText(
            output_text.rstrip("\n") or "(no output)",
            out_fmt,
        )
        ph_cursor.endEditBlock()
        log.debug("Cell output injected: %d chars  error=%s", len(output_text), is_error)

    # ------------------------------------------------------------------ #
    # Utilities                                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def supported_languages() -> list[str]:
        """Return the list of languages that JupyterCell can execute."""
        return list(_INTERPRETERS.keys())

    @staticmethod
    def is_language_available(language: str) -> bool:
        """
        Check whether the interpreter for *language* is accessible on PATH.

        Parameters
        ----------
        language : str

        Returns
        -------
        bool
        """
        import shutil
        cmd = _INTERPRETERS.get(language.lower())
        if not cmd:
            return False
        return shutil.which(cmd[0]) is not None
