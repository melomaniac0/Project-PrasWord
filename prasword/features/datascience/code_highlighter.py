"""
prasword.features.datascience.code_highlighter
================================================
Syntax highlighting for code blocks using Pygments.

Modes
-----
highlight_block(editor, language)
    Colour the currently selected text (or the paragraph under the cursor)
    using QTextCharFormat colours derived from the Pygments token stream.
    Operates entirely inside beginEditBlock / endEditBlock so it is one
    undoable step.

insert_code_block(editor, language, code)
    Insert a new fenced block with language-specific stub code, then
    immediately highlight it.

highlight_document_blocks(editor)
    Scan every block in the document for fenced triple-backtick regions
    (```lang … ```) and apply syntax highlighting to each.

get_supported_languages()
    Return a sorted list of all language names Pygments can highlight.

Theme
-----
Two built-in themes: "dracula" (dark, default) and "solarized" (light).
The active theme is selected via CodeHighlighter.set_theme(name).

The token colour map walks up the Pygments token hierarchy until it finds
a match, so e.g. Token.Name.Function.Magic falls back through
Token.Name.Function → Token.Name → Token before using the default colour.

Dependencies
------------
pygments (pip install pygments)  — optional; degrades to monospace text.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor

if TYPE_CHECKING:
    from prasword.gui.editor_widget import EditorWidget

from prasword.utils.logger import get_logger

log = get_logger(__name__)

# ── Theme definitions ────────────────────────────────────────────────────────

_THEMES: dict[str, dict] = {
    "dracula": {
        "bg":      "#282a36",
        "fg":      "#f8f8f2",
        "colors": {
            "Token.Keyword":             "#ff79c6",
            "Token.Keyword.Constant":    "#bd93f9",
            "Token.Keyword.Declaration": "#ff79c6",
            "Token.Keyword.Namespace":   "#ff79c6",
            "Token.Keyword.Type":        "#8be9fd",
            "Token.Name.Builtin":        "#8be9fd",
            "Token.Name.Builtin.Pseudo": "#bd93f9",
            "Token.Name.Function":       "#50fa7b",
            "Token.Name.Function.Magic": "#50fa7b",
            "Token.Name.Class":          "#50fa7b",
            "Token.Name.Decorator":      "#50fa7b",
            "Token.Name.Exception":      "#ff5555",
            "Token.Name.Variable":       "#f8f8f2",
            "Token.Name.Attribute":      "#50fa7b",
            "Token.String":              "#f1fa8c",
            "Token.String.Doc":          "#6272a4",
            "Token.String.Interpol":     "#f1fa8c",
            "Token.String.Escape":       "#ff79c6",
            "Token.Number":              "#bd93f9",
            "Token.Number.Integer":      "#bd93f9",
            "Token.Number.Float":        "#bd93f9",
            "Token.Number.Hex":          "#bd93f9",
            "Token.Comment":             "#6272a4",
            "Token.Comment.Single":      "#6272a4",
            "Token.Comment.Multiline":   "#6272a4",
            "Token.Comment.Special":     "#6272a4",
            "Token.Operator":            "#ff79c6",
            "Token.Operator.Word":       "#ff79c6",
            "Token.Punctuation":         "#f8f8f2",
            "Token.Text":                "#f8f8f2",
            "Token.Text.Whitespace":     "#f8f8f2",
            "Token.Error":               "#ff5555",
            "Token.Generic.Heading":     "#50fa7b",
            "Token.Generic.Subheading":  "#50fa7b",
            "Token.Generic.Deleted":     "#ff5555",
            "Token.Generic.Inserted":    "#50fa7b",
            "Token.Generic.Error":       "#ff5555",
            "Token.Generic.Strong":      "#f8f8f2",
        },
    },
    "solarized": {
        "bg":      "#fdf6e3",
        "fg":      "#657b83",
        "colors": {
            "Token.Keyword":             "#859900",
            "Token.Keyword.Constant":    "#cb4b16",
            "Token.Keyword.Declaration": "#859900",
            "Token.Keyword.Namespace":   "#cb4b16",
            "Token.Name.Builtin":        "#268bd2",
            "Token.Name.Function":       "#268bd2",
            "Token.Name.Class":          "#268bd2",
            "Token.Name.Decorator":      "#cb4b16",
            "Token.String":              "#2aa198",
            "Token.String.Doc":          "#93a1a1",
            "Token.Number":              "#d33682",
            "Token.Comment":             "#93a1a1",
            "Token.Operator":            "#859900",
            "Token.Punctuation":         "#657b83",
            "Token.Text":                "#657b83",
            "Token.Error":               "#dc322f",
        },
    },
}

_active_theme: str = "dracula"

# Language-specific stub code inserted by insert_code_block()
_STUBS: dict[str, str] = {
    "python":     "# Python\ndef main():\n    pass\n\n\nif __name__ == '__main__':\n    main()\n",
    "r":          "# R\ndf <- data.frame(x = 1:5, y = c(2, 4, 1, 3, 5))\nplot(df$x, df$y)\n",
    "sql":        "-- SQL\nSELECT *\nFROM my_table\nWHERE condition = TRUE\nORDER BY id DESC\nLIMIT 10;\n",
    "julia":      "# Julia\nfunction greet(name::String)\n    println(\"Hello, $name!\")\nend\n\ngreet(\"World\")\n",
    "bash":       "#!/usr/bin/env bash\nset -euo pipefail\n\necho \"Hello, World!\"\n",
    "javascript": "// JavaScript\nconst greet = (name) => {\n  console.log(`Hello, ${name}!`);\n};\n\ngreet('World');\n",
    "typescript": "// TypeScript\nconst greet = (name: string): void => {\n  console.log(`Hello, ${name}!`);\n};\n\ngreet('World');\n",
    "rust":       "// Rust\nfn main() {\n    println!(\"Hello, world!\");\n}\n",
    "cpp":        "// C++\n#include <iostream>\n\nint main() {\n    std::cout << \"Hello, World!\" << std::endl;\n    return 0;\n}\n",
    "go":         "// Go\npackage main\n\nimport \"fmt\"\n\nfunc main() {\n    fmt.Println(\"Hello, World!\")\n}\n",
}


class CodeHighlighter:
    """
    Static helpers for syntax-highlighted code insertion and editing.
    """

    # ------------------------------------------------------------------ #
    # Theme management                                                      #
    # ------------------------------------------------------------------ #

    @classmethod
    def set_theme(cls, name: str) -> None:
        """
        Switch the active highlighting theme.

        Parameters
        ----------
        name : str
            One of "dracula" (dark) or "solarized" (light).
        """
        global _active_theme
        if name not in _THEMES:
            raise ValueError(f"Unknown theme {name!r}. Available: {list(_THEMES)}")
        _active_theme = name
        log.debug("Code highlighter theme → %s", name)

    @classmethod
    def available_themes(cls) -> list[str]:
        """Return the names of all available highlighting themes."""
        return list(_THEMES.keys())

    # ------------------------------------------------------------------ #
    # Highlight existing selection                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def highlight_block(
        editor: "EditorWidget",
        language: str = "python",
    ) -> bool:
        """
        Apply syntax highlighting to the currently selected text.

        If there is no selection the paragraph under the cursor is used.
        The operation is placed in a single undo block.

        Parameters
        ----------
        editor : EditorWidget
        language : str
            Any language name recognised by Pygments.

        Returns
        -------
        bool
            True if Pygments was available and highlighting was applied.
            False if Pygments is not installed (degrades silently).
        """
        try:
            from pygments.lexers import get_lexer_by_name
            from pygments.lexers.special import TextLexer
        except ImportError:
            log.warning("Pygments not installed — install with: pip install pygments")
            return False

        cursor = editor.textCursor()
        if not cursor.hasSelection():
            cursor.select(QTextCursor.BlockUnderCursor)

        # Qt uses U+2029 (paragraph separator) between paragraphs in selections
        code = cursor.selectedText().replace("\u2029", "\n")
        if not code.strip():
            return False

        try:
            lexer = get_lexer_by_name(language.lower(), stripall=False)
        except Exception:
            log.warning("Unknown language %r — using plain text.", language)
            from pygments.lexers.special import TextLexer
            lexer = TextLexer()

        tokens = list(lexer.get_tokens(code))
        theme  = _THEMES.get(_active_theme, _THEMES["dracula"])
        colors = theme["colors"]
        bg_hex = theme["bg"]

        mono = QFont()
        mono.setFamily("Courier New")
        mono.setPointSize(10)
        mono.setStyleHint(QFont.Monospace)
        mono.setFixedPitch(True)

        # Remember where our text starts
        start_pos = cursor.selectionStart()

        cursor.beginEditBlock()
        pos = start_pos

        for token_type, value in tokens:
            if not value:
                continue
            length    = len(value)
            color_hex = CodeHighlighter._resolve_color(str(token_type), colors)

            fmt = QTextCharFormat()
            fmt.setFont(mono)
            fmt.setForeground(QColor(color_hex))
            fmt.setBackground(QColor(bg_hex))

            seg = QTextCursor(editor.document())
            seg.setPosition(pos)
            seg.setPosition(pos + length, QTextCursor.KeepAnchor)
            seg.mergeCharFormat(fmt)
            pos += length

        cursor.endEditBlock()

        log.debug(
            "Highlighted %d token(s) in language=%s theme=%s",
            len(tokens), language, _active_theme,
        )
        return True

    # ------------------------------------------------------------------ #
    # Insert a new code block                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def insert_code_block(
        editor: "EditorWidget",
        language: str = "python",
        code: str = "",
    ) -> None:
        """
        Insert a language-labelled, syntax-highlighted code block.

        A blank line is inserted before and after the block. The block is
        automatically highlighted after insertion.

        Parameters
        ----------
        editor : EditorWidget
        language : str
        code : str
            Code to pre-fill.  Defaults to a language-specific hello-world stub.
        """
        lang_key  = language.lower()
        stub_code = code or _STUBS.get(lang_key, f"# {language}\n")
        theme     = _THEMES.get(_active_theme, _THEMES["dracula"])
        bg_hex    = theme["bg"]
        fg_hex    = theme["fg"]

        mono = QFont()
        mono.setFamily("Courier New")
        mono.setPointSize(10)
        mono.setStyleHint(QFont.Monospace)
        mono.setFixedPitch(True)

        cursor = editor.textCursor()
        cursor.beginEditBlock()

        # Separator block before
        cursor.insertBlock()

        # Language label line
        lbl_fmt = QTextCharFormat()
        lbl_fmt.setFont(mono)
        lbl_fmt.setForeground(QColor("#6272a4"))
        lbl_fmt.setBackground(QColor(bg_hex))
        cursor.insertText(f"# ── {language.upper()} ──────────────\n", lbl_fmt)

        # Code body
        start_pos = cursor.position()
        base_fmt  = QTextCharFormat()
        base_fmt.setFont(mono)
        base_fmt.setForeground(QColor(fg_hex))
        base_fmt.setBackground(QColor(bg_hex))
        cursor.insertText(stub_code, base_fmt)
        end_pos = cursor.position()

        # Separator block after
        cursor.insertBlock()
        cursor.endEditBlock()

        # Select the inserted code and highlight it
        sel = QTextCursor(editor.document())
        sel.setPosition(start_pos)
        sel.setPosition(end_pos, QTextCursor.KeepAnchor)
        editor.setTextCursor(sel)
        CodeHighlighter.highlight_block(editor, language)

        # Deselect — move cursor to end of block
        c = editor.textCursor()
        c.setPosition(end_pos)
        editor.setTextCursor(c)

        log.debug("Code block inserted: language=%s  lines=%d", language, stub_code.count("\n"))

    # ------------------------------------------------------------------ #
    # Highlight all fenced blocks in the document                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def highlight_document_blocks(editor: "EditorWidget") -> int:
        """
        Scan the entire document for triple-backtick fenced blocks and
        apply syntax highlighting to each.

        Fence format (GFM-compatible):
            ```python
            code here
            ```

        Parameters
        ----------
        editor : EditorWidget

        Returns
        -------
        int
            Number of fenced blocks highlighted.
        """
        import re
        text  = editor.document().toPlainText()
        count = 0

        # Find all fenced blocks: ```lang\\n...code...\\n```
        pattern = re.compile(r"```(\w*)\n(.*?)```", re.DOTALL)
        for match in pattern.finditer(text):
            lang     = match.group(1).strip() or "text"
            start    = match.start(2)
            end      = match.end(2)

            cursor = QTextCursor(editor.document())
            cursor.setPosition(start)
            cursor.setPosition(end, QTextCursor.KeepAnchor)
            editor.setTextCursor(cursor)
            CodeHighlighter.highlight_block(editor, lang)
            count += 1

        log.info("Document highlight scan: %d fenced block(s) highlighted.", count)
        return count

    # ------------------------------------------------------------------ #
    # Utility                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_supported_languages() -> list[str]:
        """
        Return a sorted list of all language names recognised by Pygments.

        Returns an empty list if Pygments is not installed.
        """
        try:
            from pygments.lexers import get_all_lexers
            names: list[str] = []
            for _, aliases, _, _ in get_all_lexers():
                if aliases:
                    names.append(aliases[0])
            return sorted(names)
        except ImportError:
            return []

    @staticmethod
    def is_pygments_available() -> bool:
        """Return True if Pygments is importable."""
        try:
            import pygments  # noqa: F401
            return True
        except ImportError:
            return False

    # ------------------------------------------------------------------ #
    # Private                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _resolve_color(token_str: str, colors: dict[str, str]) -> str:
        """
        Walk up the token type hierarchy until a colour is found.

        Token.Name.Function.Magic
        → Token.Name.Function
        → Token.Name
        → Token
        → default foreground colour
        """
        key = token_str
        while key:
            if key in colors:
                return colors[key]
            dot = key.rfind(".")
            if dot == -1:
                break
            key = key[:dot]
        return _THEMES.get(_active_theme, _THEMES["dracula"])["fg"]
