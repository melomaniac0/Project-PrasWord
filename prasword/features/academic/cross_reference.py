"""
prasword.features.academic.cross_reference
===========================================
Anchor-based internal cross-referencing within a document.

Concept
-------
Any paragraph, figure caption, table, equation, or section can be given
a short *label* (e.g. "fig:results", "eq:bayes", "tbl:accuracy", "sec:intro").

When the user inserts a reference to that label anywhere else in the
document they get a clickable link — in the GUI the link scrolls to the
anchor; in exported PDF/HTML the link jumps to the target.

Label conventions (suggested, not enforced)
-------------------------------------------
sec:  — document section  (e.g. sec:methodology)
fig:  — figure            (e.g. fig:roc-curve)
tbl:  — table             (e.g. tbl:results)
eq:   — equation          (e.g. eq:loss-function)
alg:  — algorithm         (e.g. alg:gradient-descent)
lst:  — code listing      (e.g. lst:training-loop)

Storage
-------
Labels are stored in ``document.cross_refs`` as a plain dict:
    label → anchor_id  (e.g. "fig:1" → "xref_fig:1")

The companion display text stored alongside each label:
    "__disp_fig:1__" → "Figure 1"

Numbering
---------
``auto_number(document)`` walks the document in block order, detects
all labelled anchors, and assigns sequential numbers per prefix type:
fig:1, fig:2 … ; tbl:1, tbl:2 … etc.  It updates the display text and
refreshes all inserted cross-references in the document body.
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import TYPE_CHECKING

from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor

if TYPE_CHECKING:
    from prasword.core.document import Document
    from prasword.gui.editor_widget import EditorWidget

from prasword.utils.logger import get_logger

log = get_logger(__name__)

_ANCHOR_PREFIX  = "xref_"
_DISP_PREFIX    = "__disp_"

# Pretty display names for label prefixes
_PREFIX_NAMES = {
    "fig":  "Figure",
    "tbl":  "Table",
    "eq":   "Equation",
    "sec":  "Section",
    "alg":  "Algorithm",
    "lst":  "Listing",
    "app":  "Appendix",
    "ch":   "Chapter",
}


def _anchor_id(label: str) -> str:
    return _ANCHOR_PREFIX + re.sub(r"[^a-zA-Z0-9_:-]", "_", label)


def _disp_key(label: str) -> str:
    return _DISP_PREFIX + label + "__"


def _default_display(label: str) -> str:
    """Generate a default display text from a label, e.g. 'fig:1' → 'Figure 1'."""
    if ":" in label:
        prefix, rest = label.split(":", 1)
        name = _PREFIX_NAMES.get(prefix.lower(), prefix.capitalize())
        # Extract trailing number if present
        m = re.search(r"(\d+)\s*$", rest)
        num = m.group(1) if m else rest
        return f"{name} {num}"
    return f"[{label}]"


# ── CrossReference ────────────────────────────────────────────────────────────

class CrossReference:
    """
    Static helpers for labelling document elements and inserting cross-references.
    """

    # ------------------------------------------------------------------ #
    # Label management                                                     #
    # ------------------------------------------------------------------ #

    @staticmethod
    def set_label(
        editor: "EditorWidget",
        document: "Document",
        label: str,
        display_text: str = "",
    ) -> str:
        """
        Attach *label* to the element at the current cursor position.

        Inserts a zero-width HTML anchor ``<a name="xref_{label}"/>`` at
        the cursor and registers the label in ``document.cross_refs``.

        Parameters
        ----------
        editor : EditorWidget
        document : Document
        label : str
            Short identifier, e.g. "fig:results", "eq:bayes".
            Must be unique within the document (existing label is overwritten).
        display_text : str
            Text used when inserting a reference to this label.
            Defaults to an auto-generated string like "Figure 1".

        Returns
        -------
        str
            The anchor id that was inserted.
        """
        label      = label.strip()
        anchor     = _anchor_id(label)
        disp_text  = display_text or _default_display(label)

        # Write the invisible HTML anchor
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        cursor.insertHtml(
            f'<a name="{anchor}" style="font-size:0;color:transparent">​</a>'
        )
        cursor.endEditBlock()

        # Register in document metadata
        document.cross_refs[label]          = anchor
        document.cross_refs[_disp_key(label)] = disp_text
        document.mark_modified()

        log.debug("Label set: %s → %s  (display: %r)", label, anchor, disp_text)
        return anchor

    @staticmethod
    def remove_label(document: "Document", label: str) -> bool:
        """
        Remove a label from the document registry.

        Note: this does **not** remove the invisible anchor from the text
        (that requires a document scan).  Existing cross-references to this
        label will fall back to displaying ``[label]``.

        Parameters
        ----------
        document : Document
        label : str

        Returns
        -------
        bool
            True if the label existed and was removed.
        """
        existed = label in document.cross_refs
        document.cross_refs.pop(label, None)
        document.cross_refs.pop(_disp_key(label), None)
        if existed:
            document.mark_modified()
            log.debug("Label removed: %s", label)
        return existed

    @staticmethod
    def rename_label(
        document: "Document",
        old_label: str,
        new_label: str,
    ) -> bool:
        """
        Rename a label in the registry (does not update inserted refs in text).

        Returns True if old_label existed.
        """
        if old_label not in document.cross_refs:
            return False
        anchor = document.cross_refs.pop(old_label)
        disp   = document.cross_refs.pop(_disp_key(old_label), _default_display(new_label))
        document.cross_refs[new_label]          = anchor
        document.cross_refs[_disp_key(new_label)] = disp
        document.mark_modified()
        log.debug("Label renamed: %s → %s", old_label, new_label)
        return True

    # ------------------------------------------------------------------ #
    # Reference insertion                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def insert_ref(
        editor: "EditorWidget",
        document: "Document",
        label: str,
        display_text: str = "",
    ) -> None:
        """
        Insert a clickable cross-reference link to *label*.

        If *label* is not yet registered the reference is inserted as
        a greyed-out ``[label?]`` placeholder.

        Parameters
        ----------
        editor : EditorWidget
        document : Document
        label : str
        display_text : str
            Override the displayed text.  Defaults to the display text
            stored when the label was set.
        """
        anchor = document.cross_refs.get(label)
        if anchor is None:
            # Unresolved reference — insert placeholder
            anchor   = _anchor_id(label)
            vis_text = display_text or f"[{label}?]"
            colour   = "#f38ba8"   # error red
            log.warning("Cross-reference to unknown label: %s", label)
        else:
            vis_text = (
                display_text
                or document.cross_refs.get(_disp_key(label))
                or _default_display(label)
            )
            colour = "#89b4fa"

        html = (
            f'<a href="#{anchor}" '
            f'style="color:{colour};text-decoration:underline">'
            f'{vis_text}</a>'
        )
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        cursor.insertHtml(html)
        cursor.insertText(" ", QTextCharFormat())
        cursor.endEditBlock()
        log.debug("Cross-ref inserted: %s → %s", label, vis_text)

    @staticmethod
    def insert_page_ref(
        editor: "EditorWidget",
        document: "Document",
        label: str,
    ) -> None:
        """
        Insert "p. N" text where N is the estimated page number of the label.

        The page number is approximated from the QTextDocument block position
        and page height; it is not guaranteed to match the final printed output.

        Parameters
        ----------
        editor : EditorWidget
        document : Document
        label : str
        """
        anchor = document.cross_refs.get(label)
        if not anchor:
            CrossReference.insert_ref(editor, document, label)
            return

        # Find the block that contains the anchor and estimate page number
        qt_doc   = document.qt_document
        page_h   = qt_doc.pageSize().height()
        page_num = 1
        if page_h > 0:
            # Walk blocks to find the anchor's block position
            block = qt_doc.begin()
            while block.isValid():
                if anchor in block.text():
                    layout = qt_doc.documentLayout()
                    top    = layout.blockBoundingRect(block).top()
                    page_num = max(1, int(top / page_h) + 1)
                    break
                block = block.next()

        text = f"p. {page_num}"
        fmt  = QTextCharFormat()
        fmt.setForeground(QColor("#89b4fa"))
        cursor = editor.textCursor()
        cursor.beginEditBlock()
        cursor.insertText(text, fmt)
        cursor.insertText(" ", QTextCharFormat())
        cursor.endEditBlock()
        log.debug("Page ref inserted: %s → %s", label, text)

    # ------------------------------------------------------------------ #
    # Auto-numbering                                                        #
    # ------------------------------------------------------------------ #

    @staticmethod
    def auto_number(document: "Document") -> dict[str, str]:
        """
        Assign sequential numbers to all registered labels, grouped by prefix.

        Walk ``document.cross_refs`` (not the text), group by prefix,
        sort by label suffix, and assign numbers 1, 2, 3…

        Updates the display text stored for each label.
        Does **not** rewrite existing inserted cross-references in the text
        body (call ``refresh_refs`` for that).

        Returns
        -------
        dict[str, str]
            Mapping label → new display text after numbering.
        """
        # Group labels by prefix
        groups: dict[str, list[str]] = defaultdict(list)
        for label in document.cross_refs:
            if label.startswith("__"):
                continue
            prefix = label.split(":")[0].lower() if ":" in label else "item"
            groups[prefix].append(label)

        result: dict[str, str] = {}
        for prefix, labels in groups.items():
            # Sort by the part after the colon
            labels.sort(key=lambda l: l.split(":", 1)[-1])
            name = _PREFIX_NAMES.get(prefix, prefix.capitalize())
            for n, label in enumerate(labels, start=1):
                disp = f"{name} {n}"
                document.cross_refs[_disp_key(label)] = disp
                result[label] = disp

        log.info("Auto-numbered %d cross-reference labels.", len(result))
        return result

    @staticmethod
    def refresh_refs(
        editor: "EditorWidget",
        document: "Document",
    ) -> int:
        """
        Scan the document text for inserted cross-references and update their
        displayed text to match the current display strings in the registry.

        This is a best-effort text substitution — it searches for patterns
        like "Figure N" or "[label]" and replaces them where it finds a
        match in the registry.

        Returns
        -------
        int
            Number of references updated.
        """
        qt_doc = document.qt_document
        text   = qt_doc.toPlainText()
        count  = 0

        for label, anchor in document.cross_refs.items():
            if label.startswith("__"):
                continue
            new_disp = document.cross_refs.get(_disp_key(label), _default_display(label))
            # Search for the old display pattern in text
            old_disp = _default_display(label)
            if old_disp == new_disp:
                continue
            cursor = qt_doc.find(old_disp)
            while not cursor.isNull():
                cursor.insertText(new_disp)
                count += 1
                cursor = qt_doc.find(old_disp, cursor)

        if count:
            log.info("Cross-reference refresh: %d update(s).", count)
        return count

    # ------------------------------------------------------------------ #
    # Query helpers                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def list_labels(document: "Document") -> list[str]:
        """
        Return all user-defined labels in the document (excludes internal keys).
        """
        return sorted(
            k for k in document.cross_refs
            if not k.startswith("__")
        )

    @staticmethod
    def get_display_text(document: "Document", label: str) -> str:
        """
        Return the display text registered for *label*, or a generated default.
        """
        return (
            document.cross_refs.get(_disp_key(label))
            or _default_display(label)
        )

    @staticmethod
    def label_exists(document: "Document", label: str) -> bool:
        """Return True if *label* is registered in this document."""
        return label in document.cross_refs and not label.startswith("__")

    @staticmethod
    def labels_by_prefix(document: "Document") -> dict[str, list[str]]:
        """
        Return labels grouped by their prefix.

        Returns
        -------
        dict[str, list[str]]
            E.g. {"fig": ["fig:roc", "fig:loss"], "tbl": ["tbl:results"]}
        """
        groups: dict[str, list[str]] = defaultdict(list)
        for label in CrossReference.list_labels(document):
            prefix = label.split(":")[0].lower() if ":" in label else "other"
            groups[prefix].append(label)
        return dict(groups)
