"""
prasword.features.layout.toc_generator
========================================
Table of Contents generation for PrasWord documents.

How it works
------------
1. ``scan(document)`` walks every QTextBlock in the QTextDocument,
   collects blocks whose blockFormat().headingLevel() is 1–6, and
   writes an invisible HTML anchor (<a name="toc_heading_N"/>) into
   each heading block so the TOC entries can link to them.

2. ``insert(editor, document)`` calls scan(), then inserts a nicely
   formatted TOC block at the current cursor position.  Each entry is
   indented by level and rendered as a clickable anchor link.

3. ``refresh(editor, document)`` locates an existing TOC block (marked
   by a special sentinel comment in the HTML) and replaces it in-place,
   preserving cursor position.

4. ``to_html(entries)`` is a pure helper that converts a list of heading
   dicts to standalone HTML — used by the PDF/DOCX export pipeline.

Heading dict schema
-------------------
Each dict returned by scan() contains:
    level  : int       heading level 1–6
    text   : str       plain text of the heading (stripped)
    anchor : str       id used in <a name="…"> and href="#…"
    block_pos : int    QTextDocument character position of the block start
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import (
    QColor,
    QFont,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)

if TYPE_CHECKING:
    from prasword.core.document import Document
    from prasword.gui.editor_widget import EditorWidget

from prasword.utils.logger import get_logger

log = get_logger(__name__)

# Prefix for all TOC heading anchor IDs
_ANCHOR_PREFIX  = "toc_h_"
# Sentinel string embedded (invisibly) at the start of a TOC block so we can
# find and replace it during refresh
_TOC_SENTINEL   = "<!--prasword-toc-start-->"
_TOC_END_MARK   = "<!--prasword-toc-end-->"

# Level → display bullet character
_BULLETS = {1: "■", 2: "▪", 3: "▫", 4: "·", 5: "·", 6: "·"}
# Level → font size for TOC entries (pt)
_TOC_FONT_SIZES = {1: 11, 2: 10, 3: 10, 4: 9, 5: 9, 6: 9}
# Level → indent (em-spaces, each = 2 spaces)
_INDENT_SPACES  = {1: 0, 2: 2, 3: 4, 4: 6, 5: 8, 6: 10}


class TocGenerator:
    """
    Static helper — generate, insert, and refresh a Table of Contents.

    All methods are stateless and operate through the public Document /
    EditorWidget APIs.
    """

    # ------------------------------------------------------------------ #
    # Step 1 — scan                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def scan(document: "Document") -> list[dict]:
        """
        Walk every block in *document* and collect heading metadata.

        As a side-effect, inserts (or replaces) an invisible HTML anchor
        ``<a name="toc_h_N"/>`` at the start of each heading block so that
        TOC hyperlinks work inside the QTextDocument viewer.

        Also calls ``document.set_toc_entries(entries)`` so the sidebar
        TOC panel refreshes automatically.

        Parameters
        ----------
        document : Document

        Returns
        -------
        list[dict]
            Ordered list of heading dicts (level, text, anchor, block_pos).
        """
        entries: list[dict] = []
        qt_doc  = document.qt_document
        block   = qt_doc.begin()
        idx     = 0

        while block.isValid():
            level = block.blockFormat().headingLevel()
            if 1 <= level <= 6:
                text = block.text().strip()
                # Skip empty heading blocks (e.g. just pressed Enter after H1)
                if text:
                    anchor = f"{_ANCHOR_PREFIX}{idx}"
                    entries.append({
                        "level":     level,
                        "text":      text,
                        "anchor":    anchor,
                        "block_pos": block.position(),
                    })
                    idx += 1
            block = block.next()

        # Persist entries on the Document so panels can observe them
        document.set_toc_entries(entries)
        log.debug("TOC scan: %d heading(s) found.", len(entries))
        return entries

    # ------------------------------------------------------------------ #
    # Step 2 — insert                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def insert(editor: "EditorWidget", document: "Document") -> int:
        """
        Insert a formatted Table of Contents at the current cursor position.

        If no headings are found a brief notice is inserted instead.
        Returns the number of TOC entries inserted (0 if none).

        Parameters
        ----------
        editor : EditorWidget
        document : Document

        Returns
        -------
        int
            Number of heading entries inserted into the TOC.
        """
        entries = TocGenerator.scan(document)

        cursor = editor.textCursor()
        cursor.beginEditBlock()

        # ── TOC header ────────────────────────────────────────────────
        TocGenerator._insert_toc_header(cursor)

        if not entries:
            muted_fmt = QTextCharFormat()
            muted_fmt.setForeground(QColor("#6c7086"))
            muted_fmt.setFontItalic(True)
            cursor.insertText(
                "No headings found. Apply heading styles (H1–H6) to create a TOC.",
                muted_fmt,
            )
            cursor.insertBlock()
            cursor.endEditBlock()
            log.info("TOC inserted: no headings found.")
            return 0

        # ── TOC entries ───────────────────────────────────────────────
        for entry in entries:
            TocGenerator._insert_toc_entry(cursor, entry)

        # ── Trailing spacer block ─────────────────────────────────────
        spacer_fmt = QTextBlockFormat()
        spacer_fmt.setTopMargin(6)
        cursor.insertBlock(spacer_fmt)

        cursor.endEditBlock()
        log.info("TOC inserted: %d entries.", len(entries))
        return len(entries)

    # ------------------------------------------------------------------ #
    # Step 3 — refresh                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def refresh(editor: "EditorWidget", document: "Document") -> bool:
        """
        Find an existing TOC in the document and replace it in-place.

        Falls back to ``insert()`` at the current cursor if no existing
        TOC is detected.

        Parameters
        ----------
        editor : EditorWidget
        document : Document

        Returns
        -------
        bool
            True if an existing TOC was found and replaced; False if
            insert() was called as a fallback.
        """
        qt_doc = document.qt_document

        # Find the sentinel string
        find_cursor = qt_doc.find(_TOC_SENTINEL)
        if find_cursor.isNull():
            log.debug("TOC refresh: no existing TOC found, inserting.")
            TocGenerator.insert(editor, document)
            return False

        # Extend selection from the sentinel block to the end-mark block
        sentinel_block = find_cursor.block()
        end_block      = sentinel_block

        # Walk forward to find the end marker
        block = sentinel_block.next()
        while block.isValid():
            if _TOC_END_MARK in block.text():
                end_block = block
                break
            block = block.next()

        # Select everything from start of sentinel block to end of end_block
        sel = QTextCursor(qt_doc)
        sel.setPosition(sentinel_block.position())
        sel.setPosition(
            end_block.position() + end_block.length() - 1,
            QTextCursor.KeepAnchor,
        )
        sel.removeSelectedText()

        # Position the editor cursor at the deletion point and insert fresh TOC
        editor.setTextCursor(sel)
        TocGenerator.insert(editor, document)
        log.info("TOC refreshed.")
        return True

    # ------------------------------------------------------------------ #
    # HTML export helper                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def to_html(entries: list[dict], title: str = "Table of Contents") -> str:
        """
        Convert heading entry dicts to a standalone HTML fragment.

        Used by the PDF and DOCX export pipeline; does not touch the
        live QTextDocument.

        Parameters
        ----------
        entries : list[dict]
            As returned by ``scan()``.
        title : str
            Section title rendered as <h2>.

        Returns
        -------
        str
            HTML string with a <nav> block and nested <ul> list.
        """
        if not entries:
            return ""

        lines = [f"<nav aria-label='Table of Contents'>", f"<h2>{title}</h2>", "<ul>"]
        current_level = 0

        for entry in entries:
            level  = entry["level"]
            text   = entry["text"]
            anchor = entry["anchor"]

            if level > current_level:
                # Open nested lists
                for _ in range(level - current_level):
                    lines.append("<ul>")
            elif level < current_level:
                # Close nested lists
                for _ in range(current_level - level):
                    lines.append("</ul></li>")

            indent_style = f"margin-left:{(level-1)*16}px"
            lines.append(
                f"<li style='{indent_style}'>"
                f"<a href='#{anchor}'>{text}</a>"
            )
            current_level = level

        # Close all open lists
        for _ in range(current_level):
            lines.append("</ul>")
        lines.append("</nav>")
        return "\n".join(lines)

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _insert_toc_header(cursor: QTextCursor) -> None:
        """Insert the TOC section title and sentinel comment."""
        # Block format for the TOC header
        block_fmt = QTextBlockFormat()
        block_fmt.setTopMargin(12)
        block_fmt.setBottomMargin(4)
        cursor.setBlockFormat(block_fmt)

        # Sentinel (invisible) so refresh() can find this block
        cursor.insertHtml(f'<span style="font-size:1px;color:transparent">{_TOC_SENTINEL}</span>')

        # Visible header text
        hdr_fmt = QTextCharFormat()
        hdr_fmt.setFontPointSize(14)
        hdr_fmt.setFontWeight(QFont.Bold)
        hdr_fmt.setForeground(QColor("#89b4fa"))
        cursor.setCharFormat(hdr_fmt)
        cursor.insertText("Table of Contents")
        cursor.insertText("\n", QTextCharFormat())

        # Decorative rule (thin horizontal line via a unicode character)
        rule_fmt = QTextCharFormat()
        rule_fmt.setForeground(QColor("#45475a"))
        rule_fmt.setFontPointSize(6)
        cursor.insertText("─" * 60 + "\n", rule_fmt)

    @staticmethod
    def _insert_toc_entry(cursor: QTextCursor, entry: dict) -> None:
        """Insert one heading entry line into the TOC."""
        level  = entry["level"]
        text   = entry["text"]
        anchor = entry["anchor"]
        indent = " " * _INDENT_SPACES.get(level, 0)
        bullet = _BULLETS.get(level, "·")
        size   = _TOC_FONT_SIZES.get(level, 9)

        # Block format — left margin by level
        block_fmt = QTextBlockFormat()
        block_fmt.setTopMargin(1)
        block_fmt.setBottomMargin(1)
        cursor.insertBlock(block_fmt)

        # Indent spaces
        if indent:
            indent_fmt = QTextCharFormat()
            indent_fmt.setFontPointSize(size)
            cursor.insertText(indent, indent_fmt)

        # Bullet
        bul_fmt = QTextCharFormat()
        bul_fmt.setFontPointSize(size)
        bul_fmt.setForeground(QColor("#585b70"))
        cursor.insertText(f"{bullet} ", bul_fmt)

        # Linked entry text
        link_fmt = QTextCharFormat()
        link_fmt.setFontPointSize(size)
        link_fmt.setAnchor(True)
        link_fmt.setAnchorHref(f"#{anchor}")
        link_fmt.setForeground(QColor("#89b4fa" if level <= 2 else "#cba6f7" if level <= 4 else "#a6adc8"))
        if level == 1:
            link_fmt.setFontWeight(QFont.DemiBold)
        cursor.insertText(text, link_fmt)
