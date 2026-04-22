"""
prasword.features.academic.citation_engine
===========================================
In-text citation insertion and bibliography management.

In-text citation formats
------------------------
APA       (Last, Year)               e.g. (Knuth, 1984)
MLA       (Last Page)                e.g. (Knuth 42)
Chicago   (Last Year, Page)          e.g. (Knuth 1984, 42)
IEEE      [N]                        e.g. [1]
Vancouver [N]                        e.g. [1]
Numeric   [N]                        e.g. [1]

Multiple citations
------------------
``insert_multiple`` inserts e.g. "(Smith, 2020; Jones, 2021)" (APA) or
"[1,3,5]" (IEEE/numeric) in a single edit block.

Footnote / endnote style
------------------------
``insert_footnote_ref`` inserts a superscript number at the cursor and
records the full reference text; ``collect_footnotes`` returns all
footnotes in insertion order for export rendering.

Bibliography insertion
----------------------
``insert_bibliography`` appends or refreshes the reference list at the
end of the document.  It is idempotent: if a bibliography section already
exists (detected by the sentinel string) it replaces it in-place.

Cite-key tracking
-----------------
All cite-keys inserted into a document are tracked in
``document.cross_refs["__cited__"]`` as a semicolon-separated list,
so the sidebar References panel can highlight cited entries.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor

if TYPE_CHECKING:
    from prasword.core.document import Document
    from prasword.gui.editor_widget import EditorWidget

from prasword.features.academic.bibtex_manager import BibTeXManager, _last_name, _split_authors, _strip_braces
from prasword.utils.logger import get_logger

log = get_logger(__name__)

# Sentinel embedded (invisibly) before the bibliography block
_BIB_SENTINEL = "<!--prasword-bibliography-->"

# Key in document.cross_refs used to track which keys have been cited
_CITED_KEY = "__cited__"


# ── Styling helpers ───────────────────────────────────────────────────────────

def _citation_char_fmt(colour: str = "#89b4fa") -> QTextCharFormat:
    fmt = QTextCharFormat()
    fmt.setForeground(QColor(colour))
    return fmt

def _reset_fmt() -> QTextCharFormat:
    return QTextCharFormat()


# ── CitationEngine ────────────────────────────────────────────────────────────

class CitationEngine:
    """
    Static helpers for in-text citation insertion and bibliography management.
    """

    # ------------------------------------------------------------------ #
    # Single citation                                                       #
    # ------------------------------------------------------------------ #

    @staticmethod
    def insert_citation(
        editor: "EditorWidget",
        document: "Document",
        citekey: str,
        style: str = "apa",
        page: str = "",
    ) -> None:
        """
        Insert an in-text citation at the current cursor position.

        Parameters
        ----------
        editor : EditorWidget
        document : Document
        citekey : str
            Must be registered in ``document.bib_entries``.
        style : str
            One of "apa", "mla", "chicago", "ieee", "vancouver", "numeric".
        page : str
            Optional page number suffix (used in MLA and Chicago styles).

        Raises
        ------
        KeyError
            If *citekey* is not in the bibliography.
        """
        entry = document.bib_entries.get(citekey)
        if entry is None:
            raise KeyError(
                f"Citation key [{citekey}] not found in bibliography. "
                "Import a .bib file first."
            )

        text = CitationEngine._fmt_intext(citekey, entry, style, document, page)
        CitationEngine._insert_text_with_fmt(editor, text, colour="#89b4fa")
        CitationEngine._record_cited(document, citekey)
        log.debug("Citation inserted: [%s] → %s", citekey, text)

    # ------------------------------------------------------------------ #
    # Multiple citations                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def insert_multiple(
        editor: "EditorWidget",
        document: "Document",
        citekeys: list[str],
        style: str = "apa",
    ) -> None:
        """
        Insert multiple citations as a single grouped reference.

        APA / MLA / Chicago → "(Last1, Year1; Last2, Year2)"
        IEEE / numeric       → "[1,3,5]"

        Parameters
        ----------
        editor : EditorWidget
        document : Document
        citekeys : list[str]
            Ordered list of cite-keys to group.
        style : str
        """
        if not citekeys:
            return

        parts: list[str] = []
        for ck in citekeys:
            entry = document.bib_entries.get(ck, {})
            parts.append(
                CitationEngine._fmt_intext(ck, entry, style, document)
            )
            CitationEngine._record_cited(document, ck)

        style_lower = style.lower()
        if style_lower in ("ieee", "vancouver", "numeric"):
            # Numeric refs are already "[N]" — merge the numbers
            nums = [re.search(r"\d+", p).group() for p in parts if re.search(r"\d+", p)]
            text = f"[{','.join(nums)}]"
        else:
            # Strip outer parens from individual parts, rejoin
            inner = "; ".join(
                p.strip("()") for p in parts
            )
            text = f"({inner})"

        CitationEngine._insert_text_with_fmt(editor, text, colour="#89b4fa")
        log.debug("Multiple citations inserted: %s", citekeys)

    # ------------------------------------------------------------------ #
    # Footnote / endnote                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def insert_footnote_ref(
        editor: "EditorWidget",
        document: "Document",
        citekey: str,
        style: str = "apa",
    ) -> int:
        """
        Insert a superscript footnote number at the cursor.

        The full reference text is stored in document.cross_refs under
        key ``__fn_{n}__`` so it can be collected for export.

        Returns
        -------
        int
            The footnote number assigned (1-based, sequential within doc).
        """
        # Count existing footnotes
        n = 1 + sum(
            1 for k in document.cross_refs if k.startswith("__fn_")
        )
        entry = document.bib_entries.get(citekey, {})
        ref_text = BibTeXManager.format_entry(entry, style)

        # Store the full reference
        document.cross_refs[f"__fn_{n}__"] = ref_text

        # Insert superscript marker
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        sup_fmt = QTextCharFormat()
        sup_fmt.setVerticalAlignment(QTextCharFormat.AlignSuperScript)
        sup_fmt.setForeground(QColor("#89b4fa"))
        sup_fmt.setFontPointSize(8)
        cursor.insertText(str(n), sup_fmt)
        cursor.insertText("", _reset_fmt())
        cursor.endEditBlock()

        CitationEngine._record_cited(document, citekey)
        log.debug("Footnote reference %d inserted for [%s].", n, citekey)
        return n

    @staticmethod
    def collect_footnotes(document: "Document") -> list[tuple[int, str]]:
        """
        Return all footnote references in insertion order.

        Returns
        -------
        list[tuple[int, str]]
            List of (number, formatted_reference) tuples.
        """
        result: list[tuple[int, str]] = []
        for k, v in document.cross_refs.items():
            m = re.match(r"^__fn_(\d+)__$", k)
            if m:
                result.append((int(m.group(1)), v))
        return sorted(result, key=lambda t: t[0])

    # ------------------------------------------------------------------ #
    # Bibliography block                                                    #
    # ------------------------------------------------------------------ #

    @staticmethod
    def insert_bibliography(
        editor: "EditorWidget",
        document: "Document",
        style: str = "apa",
        cited_only: bool = True,
        sort_by: str = "author",
    ) -> None:
        """
        Append or refresh the bibliography section at the end of the document.

        If a bibliography sentinel is found the existing block is replaced
        in-place; otherwise a new block is appended after a horizontal rule.

        Parameters
        ----------
        editor : EditorWidget
        document : Document
        style : str
        cited_only : bool
            Include only cited entries (default True).
        sort_by : str
            "author" | "year" | "title" | "citekey".
        """
        qt_doc  = document.qt_document
        bib_html = BibTeXManager.generate_bibliography(
            document, style, cited_only, sort_by
        )
        sentinel_html = (
            f'<span style="font-size:1px;color:transparent">{_BIB_SENTINEL}</span>'
        )

        cursor = editor.textCursor()
        cursor.beginEditBlock()

        # Try to find and replace an existing bibliography
        find_cur = qt_doc.find(_BIB_SENTINEL)
        if not find_cur.isNull():
            # Select from sentinel block to end of document
            bib_start = find_cur.block()
            sel = QTextCursor(qt_doc)
            sel.setPosition(bib_start.position())
            sel.movePosition(QTextCursor.End, QTextCursor.KeepAnchor)
            sel.removeSelectedText()
            cursor = sel
        else:
            # Move to end, add a separator
            cursor.movePosition(QTextCursor.End)
            cursor.insertHtml("<hr/>")

        cursor.insertHtml(sentinel_html + bib_html)
        cursor.endEditBlock()
        log.info("Bibliography inserted/refreshed (style=%s, cited_only=%s).", style, cited_only)

    # ------------------------------------------------------------------ #
    # Cited-key tracking                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def cited_keys(document: "Document") -> list[str]:
        """
        Return an ordered list of all cite-keys that have been inserted
        into this document as in-text citations.
        """
        raw = document.cross_refs.get(_CITED_KEY, "")
        if not raw:
            return []
        return [k for k in raw.split(";") if k]

    @staticmethod
    def scan_cited_keys(document: "Document") -> list[str]:
        """
        Scan the document's plain text for [citekey] patterns and return
        all that match an entry in the bibliography.

        Useful for synchronising the cited-key list after pasting or
        editing text directly.
        """
        body    = document.plain_text()
        pattern = re.findall(r"\[([^\]\s,]+)\]", body)
        known   = set(document.bib_entries)
        found   = list(dict.fromkeys(k for k in pattern if k in known))  # unique, ordered
        # Update the tracked set
        document.cross_refs[_CITED_KEY] = ";".join(found)
        return found

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _fmt_intext(
        citekey: str,
        entry: dict,
        style: str,
        document: "Document",
        page: str = "",
    ) -> str:
        """Format an in-text citation string for the given style."""
        raw_author = entry.get("author", "Unknown")
        year       = _strip_braces(entry.get("year", "n.d."))
        authors    = _split_authors(raw_author)
        last       = _last_name(authors[0]) if authors else "Unknown"
        et_al      = " et al." if len(authors) > 2 else ""

        page_suffix = f", p. {page}" if page else ""

        style = style.lower()
        if style == "apa":
            return f"({last}{et_al}, {year}{page_suffix})"

        elif style == "mla":
            pg = f" {page}" if page else ""
            return f"({last}{et_al}{pg})"

        elif style == "chicago":
            return f"({last}{et_al} {year}{page_suffix})"

        elif style in ("ieee", "vancouver", "numeric"):
            keys = [k for k in document.bib_entries if not k.startswith("__")]
            n    = keys.index(citekey) + 1 if citekey in keys else "?"
            return f"[{n}]"

        # Fallback
        return f"({last}{et_al}, {year})"

    @staticmethod
    def _insert_text_with_fmt(
        editor: "EditorWidget",
        text: str,
        colour: str = "#89b4fa",
    ) -> None:
        """Insert *text* at the cursor with citation styling, then reset."""
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        cursor.insertText(text, _citation_char_fmt(colour))
        cursor.insertText(" ", _reset_fmt())
        cursor.endEditBlock()

    @staticmethod
    def _record_cited(document: "Document", citekey: str) -> None:
        """Add *citekey* to the tracked cited-keys list (deduplicating)."""
        existing = document.cross_refs.get(_CITED_KEY, "")
        keys     = [k for k in existing.split(";") if k]
        if citekey not in keys:
            keys.append(citekey)
            document.cross_refs[_CITED_KEY] = ";".join(keys)
