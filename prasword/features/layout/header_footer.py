"""
prasword.features.layout.header_footer
========================================
Header and footer management.

Qt's QTextDocument does not natively support repeating headers/footers the
way a desktop word processor does.  We implement them as:

1. A stored text template (stored in the Document's metadata dict).
2. Rendering into the QPrinter paint device during PDF export.
3. A visual overlay painted by the EditorWidget's viewport.

For the initial implementation we focus on storing the template and
rendering it during print/PDF export.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prasword.core.document import Document

from prasword.utils.logger import get_logger

log = get_logger(__name__)

# Metadata keys used on Document._bib_entries (repurposing as a general store)
_KEY_HEADER = "__header__"
_KEY_FOOTER = "__footer__"


@dataclass
class HeaderFooterTemplate:
    """
    Template for a header or footer.

    Supports the following placeholders:
        {page}    Current page number.
        {pages}   Total page count.
        {title}   Document title.
        {author}  Document author.
        {date}    Today's date (ISO format).
    """
    left: str = ""
    center: str = ""
    right: str = ""
    font_size: float = 9.0
    show_rule: bool = True   # horizontal rule between header/footer and body

    def render(self, page: int, pages: int, title: str, author: str) -> dict[str, str]:
        """Return rendered left/center/right strings."""
        import datetime
        ctx = {
            "page": str(page),
            "pages": str(pages),
            "title": title,
            "author": author,
            "date": datetime.date.today().isoformat(),
        }
        return {
            "left":   self.left.format(**ctx),
            "center": self.center.format(**ctx),
            "right":  self.right.format(**ctx),
        }


class HeaderFooter:
    """
    Static helpers to get/set header and footer templates on a Document.
    """

    @staticmethod
    def set_header(document: "Document", template: HeaderFooterTemplate) -> None:
        """Persist the header template in the document's metadata."""
        import json
        document._bib_entries[_KEY_HEADER] = {
            "left": template.left,
            "center": template.center,
            "right": template.right,
            "font_size": template.font_size,
            "show_rule": template.show_rule,
        }
        document.mark_modified()
        log.debug("Header template set.")

    @staticmethod
    def set_footer(document: "Document", template: HeaderFooterTemplate) -> None:
        """Persist the footer template in the document's metadata."""
        document._bib_entries[_KEY_FOOTER] = {
            "left": template.left,
            "center": template.center,
            "right": template.right,
            "font_size": template.font_size,
            "show_rule": template.show_rule,
        }
        document.mark_modified()
        log.debug("Footer template set.")

    @staticmethod
    def get_header(document: "Document") -> HeaderFooterTemplate:
        """Return the stored header template, or a default blank one."""
        data = document._bib_entries.get(_KEY_HEADER, {})
        return HeaderFooterTemplate(**data) if data else HeaderFooterTemplate()

    @staticmethod
    def get_footer(document: "Document") -> HeaderFooterTemplate:
        """Return the stored footer template, or a page-number default."""
        data = document._bib_entries.get(_KEY_FOOTER, {})
        if not data:
            return HeaderFooterTemplate(center="{title}", right="Page {page} of {pages}")
        return HeaderFooterTemplate(**data)

    @staticmethod
    def clear_header(document: "Document") -> None:
        document._bib_entries.pop(_KEY_HEADER, None)

    @staticmethod
    def clear_footer(document: "Document") -> None:
        document._bib_entries.pop(_KEY_FOOTER, None)
