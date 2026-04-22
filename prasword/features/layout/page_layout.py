"""
prasword.features.layout.page_layout
======================================
Page size, orientation, and margin management.

All measurements are stored in millimetres in the public API and converted
to Qt's internal point unit (1 pt = 1/72 inch; 1 mm ≈ 2.8346 pt) when
writing to the QTextDocument.

Supported page sizes
--------------------
A6, A5, A4, A3, A2, A1        (ISO 216)
Letter, Legal, Executive, Tabloid  (North American)
B5 (ISO 12473)

Custom sizes can be set via ``set_page_size_mm(document, width_mm, height_mm)``.

Orientation
-----------
Portrait is the default.  ``set_landscape(document, True)`` swaps the
current page width and height.

Margins
-------
The ``Margins`` dataclass carries top/bottom/left/right in mm, plus an
optional gutter (extra inner margin for binding) and mirror flag (for
double-sided printing where left/right swap on even pages).

Column layout
-------------
``set_columns(document, n, gutter_mm)`` distributes the text area into
*n* equal columns separated by *gutter_mm* gaps.  This is stored in the
document metadata and honoured during PDF export.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from PySide6.QtCore import QSizeF
from PySide6.QtGui import QTextFrameFormat

if TYPE_CHECKING:
    from prasword.core.document import Document

from prasword.utils.logger import get_logger

log = get_logger(__name__)

# ── Unit conversion ──────────────────────────────────────────────────────────

_MM_TO_PT  = 2.8346    # 1 mm in Qt points
_IN_TO_PT  = 72.0      # 1 inch in Qt points
_CM_TO_PT  = 28.346    # 1 cm in Qt points


def mm_to_pt(mm: float) -> float:
    return mm * _MM_TO_PT

def pt_to_mm(pt: float) -> float:
    return pt / _MM_TO_PT

def in_to_pt(inches: float) -> float:
    return inches * _IN_TO_PT


# ── Page-size catalogue ──────────────────────────────────────────────────────

# (width_mm, height_mm) in portrait orientation
PAGE_SIZES_MM: dict[str, tuple[float, float]] = {
    # ISO 216
    "A6":        ( 105.0,  148.0),
    "A5":        ( 148.0,  210.0),
    "A4":        ( 210.0,  297.0),
    "A3":        ( 297.0,  420.0),
    "A2":        ( 420.0,  594.0),
    "A1":        ( 594.0,  841.0),
    # ISO 12473
    "B5":        ( 176.0,  250.0),
    # North American
    "Letter":    ( 215.9,  279.4),
    "Legal":     ( 215.9,  355.6),
    "Executive": ( 184.2,  266.7),
    "Tabloid":   ( 279.4,  431.8),
}


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass
class Margins:
    """
    Page margins in millimetres.

    Attributes
    ----------
    top, bottom, left, right : float
        Primary margins in mm (default 25.4 mm = 1 inch).
    gutter : float
        Extra binding margin added to the inner edge (mm). Default 0.
    mirror : bool
        If True, left/right swap on even pages (double-sided printing).
    """
    top:    float = 25.4
    bottom: float = 25.4
    left:   float = 25.4
    right:  float = 25.4
    gutter: float = 0.0
    mirror: bool  = False

    @classmethod
    def narrow(cls) -> "Margins":
        """1.27 cm (0.5 in) on all sides."""
        return cls(top=12.7, bottom=12.7, left=12.7, right=12.7)

    @classmethod
    def wide(cls) -> "Margins":
        """3.81 cm (1.5 in) on left/right, 2.54 cm top/bottom."""
        return cls(top=25.4, bottom=25.4, left=38.1, right=38.1)

    @classmethod
    def book(cls) -> "Margins":
        """Typical book/thesis margins with binding gutter."""
        return cls(top=25.4, bottom=25.4, left=31.8, right=25.4, gutter=12.7, mirror=True)


@dataclass
class PageConfig:
    """
    Complete page layout configuration stored on a document.

    Attributes
    ----------
    size_name : str
        Key from PAGE_SIZES_MM, or "Custom".
    width_mm, height_mm : float
        Actual page dimensions (already swapped if landscape).
    landscape : bool
    margins : Margins
    columns : int
        Number of text columns (default 1).
    column_gutter_mm : float
        Space between columns in mm (default 6.35 mm = 0.25 in).
    """
    size_name:         str     = "A4"
    width_mm:          float   = 210.0
    height_mm:         float   = 297.0
    landscape:         bool    = False
    margins:           Margins = field(default_factory=Margins)
    columns:           int     = 1
    column_gutter_mm:  float   = 6.35


# ── Storage key on Document._bib_entries (repurposed as metadata store) ──────

_CONFIG_KEY = "__page_config__"


# ── PageLayout ───────────────────────────────────────────────────────────────

class PageLayout:
    """
    Static helpers to read and write page-layout properties on a Document.

    Qt's QTextDocument stores layout dimensions in:
      - ``QTextDocument.setPageSize(QSizeF)``          → page width/height in pt
      - ``rootFrame().frameFormat()`` margins          → text-area insets in pt

    PageLayout also persists a ``PageConfig`` in the document's metadata
    (``_bib_entries[_CONFIG_KEY]``) so that PDF/DOCX exporters can read
    columns, gutter, mirror, etc.
    """

    # ------------------------------------------------------------------ #
    # Page size                                                            #
    # ------------------------------------------------------------------ #

    @staticmethod
    def set_page_size(
        document: "Document",
        name: str,
        landscape: bool = False,
    ) -> None:
        """
        Set the page size by catalogue name.

        Parameters
        ----------
        document : Document
        name : str
            Key from ``PAGE_SIZES_MM``.  Case-sensitive.
        landscape : bool
            If True, swaps width and height.

        Raises
        ------
        ValueError
            If *name* is not in the catalogue.
        """
        if name not in PAGE_SIZES_MM:
            valid = ", ".join(sorted(PAGE_SIZES_MM))
            raise ValueError(
                f"Unknown page size {name!r}.  Valid sizes: {valid}"
            )
        w_mm, h_mm = PAGE_SIZES_MM[name]
        if landscape:
            w_mm, h_mm = h_mm, w_mm

        PageLayout._write_page_size(document, w_mm, h_mm)

        # Update stored config
        cfg = PageLayout.get_config(document)
        cfg.size_name = name
        cfg.width_mm  = w_mm
        cfg.height_mm = h_mm
        cfg.landscape = landscape
        PageLayout._save_config(document, cfg)

        log.debug(
            "Page size → %s (%s): %.1f × %.1f mm",
            name, "landscape" if landscape else "portrait", w_mm, h_mm,
        )

    @staticmethod
    def set_page_size_mm(
        document: "Document",
        width_mm: float,
        height_mm: float,
    ) -> None:
        """
        Set a custom page size in millimetres.

        Parameters
        ----------
        document : Document
        width_mm : float
        height_mm : float
        """
        if width_mm <= 0 or height_mm <= 0:
            raise ValueError("Page dimensions must be positive.")

        PageLayout._write_page_size(document, width_mm, height_mm)

        cfg = PageLayout.get_config(document)
        cfg.size_name = "Custom"
        cfg.width_mm  = width_mm
        cfg.height_mm = height_mm
        PageLayout._save_config(document, cfg)
        log.debug("Custom page size → %.1f × %.1f mm", width_mm, height_mm)

    @staticmethod
    def set_landscape(document: "Document", landscape: bool) -> None:
        """
        Toggle orientation without changing the logical page size name.
        Swaps width and height if the current orientation differs from *landscape*.
        """
        cfg = PageLayout.get_config(document)
        if cfg.landscape == landscape:
            return
        # Swap dimensions
        cfg.width_mm, cfg.height_mm = cfg.height_mm, cfg.width_mm
        cfg.landscape = landscape
        PageLayout._write_page_size(document, cfg.width_mm, cfg.height_mm)
        PageLayout._save_config(document, cfg)
        log.debug("Orientation → %s", "landscape" if landscape else "portrait")

    # ------------------------------------------------------------------ #
    # Margins                                                              #
    # ------------------------------------------------------------------ #

    @staticmethod
    def set_margins(document: "Document", margins: Margins) -> None:
        """
        Set page margins (in mm).

        Parameters
        ----------
        document : Document
        margins : Margins
        """
        root = document.qt_document.rootFrame()
        fmt  = root.frameFormat()
        fmt.setTopMargin(mm_to_pt(margins.top))
        fmt.setBottomMargin(mm_to_pt(margins.bottom))
        fmt.setLeftMargin(mm_to_pt(margins.left + margins.gutter))
        fmt.setRightMargin(mm_to_pt(margins.right))
        root.setFrameFormat(fmt)

        cfg = PageLayout.get_config(document)
        cfg.margins = margins
        PageLayout._save_config(document, cfg)
        log.debug(
            "Margins → T=%.1f B=%.1f L=%.1f R=%.1f Gutter=%.1f mm",
            margins.top, margins.bottom, margins.left, margins.right, margins.gutter,
        )

    @staticmethod
    def get_margins(document: "Document") -> Margins:
        """
        Read current margins from the document's root frame format.

        Returns
        -------
        Margins
            Margins in mm.  Gutter and mirror are read from stored config.
        """
        fmt = document.qt_document.rootFrame().frameFormat()
        cfg = PageLayout.get_config(document)
        gutter = cfg.margins.gutter
        mirror = cfg.margins.mirror
        return Margins(
            top    = pt_to_mm(fmt.topMargin()),
            bottom = pt_to_mm(fmt.bottomMargin()),
            left   = pt_to_mm(fmt.leftMargin()) - gutter,
            right  = pt_to_mm(fmt.rightMargin()),
            gutter = gutter,
            mirror = mirror,
        )

    # ------------------------------------------------------------------ #
    # Column layout                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def set_columns(
        document: "Document",
        columns: int,
        gutter_mm: float = 6.35,
    ) -> None:
        """
        Set the number of text columns.

        Note: QTextDocument does not natively support multi-column layout;
        this value is stored in the PageConfig and applied during export.

        Parameters
        ----------
        document : Document
        columns : int
            Number of columns (1–8).
        gutter_mm : float
            Space between columns in mm.
        """
        columns = max(1, min(8, columns))
        cfg = PageLayout.get_config(document)
        cfg.columns          = columns
        cfg.column_gutter_mm = gutter_mm
        PageLayout._save_config(document, cfg)
        log.debug("Columns → %d (gutter=%.1f mm)", columns, gutter_mm)

    # ------------------------------------------------------------------ #
    # Full config                                                          #
    # ------------------------------------------------------------------ #

    @staticmethod
    def get_config(document: "Document") -> PageConfig:
        """
        Return the stored PageConfig, or a default A4 config if none set.
        """
        raw = document.bib_entries.get(_CONFIG_KEY)
        if raw is None:
            return PageConfig()
        # Reconstruct from stored dict
        margins_data = raw.get("margins", {})
        margins = Margins(
            top    = margins_data.get("top",    25.4),
            bottom = margins_data.get("bottom", 25.4),
            left   = margins_data.get("left",   25.4),
            right  = margins_data.get("right",  25.4),
            gutter = margins_data.get("gutter", 0.0),
            mirror = margins_data.get("mirror", False),
        )
        return PageConfig(
            size_name        = raw.get("size_name",        "A4"),
            width_mm         = raw.get("width_mm",         210.0),
            height_mm        = raw.get("height_mm",        297.0),
            landscape        = raw.get("landscape",        False),
            margins          = margins,
            columns          = raw.get("columns",          1),
            column_gutter_mm = raw.get("column_gutter_mm", 6.35),
        )

    @staticmethod
    def apply_defaults(document: "Document") -> None:
        """
        Apply A4 portrait with standard 1-inch (25.4 mm) margins.
        Convenience method called when a new document is created.
        """
        PageLayout.set_page_size(document, "A4", landscape=False)
        PageLayout.set_margins(document, Margins())
        log.debug("Default page layout applied (A4, 25.4 mm margins).")

    @staticmethod
    def available_sizes() -> list[str]:
        """Return the list of named page sizes in display order."""
        return list(PAGE_SIZES_MM.keys())

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _write_page_size(document: "Document", w_mm: float, h_mm: float) -> None:
        """Write width×height (mm) to the QTextDocument page size."""
        document.qt_document.setPageSize(
            QSizeF(mm_to_pt(w_mm), mm_to_pt(h_mm))
        )

    @staticmethod
    def _save_config(document: "Document", cfg: PageConfig) -> None:
        """Persist PageConfig in the document's metadata store."""
        document.bib_entries[_CONFIG_KEY] = {
            "size_name":        cfg.size_name,
            "width_mm":         cfg.width_mm,
            "height_mm":        cfg.height_mm,
            "landscape":        cfg.landscape,
            "columns":          cfg.columns,
            "column_gutter_mm": cfg.column_gutter_mm,
            "margins": {
                "top":    cfg.margins.top,
                "bottom": cfg.margins.bottom,
                "left":   cfg.margins.left,
                "right":  cfg.margins.right,
                "gutter": cfg.margins.gutter,
                "mirror": cfg.margins.mirror,
            },
        }
