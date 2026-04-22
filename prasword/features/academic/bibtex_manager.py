"""
prasword.features.academic.bibtex_manager
==========================================
BibTeX file import, bibliography generation, and entry formatting.

Dependency: ``bibtexparser`` (``pip install bibtexparser``).
All methods degrade gracefully — if bibtexparser is not installed an
ImportError with a helpful install message is raised only at the
import_file() / import_string() call site, not at module import time.

Features
--------
* Import .bib files (UTF-8, with LaTeX-escape → Unicode conversion).
* Import raw BibTeX strings (via a temporary file).
* Manual entry creation without bibtexparser.
* Format single entries in APA / MLA / Chicago / IEEE / Vancouver.
* Generate full or cited-only bibliography as an HTML ordered list.
* Search entries by author, title, year, journal, or cite-key.
* Export all entries back to a .bib file.
* Merge two Documents' bibliographies (deduplication by cite-key).

Author name handling
--------------------
BibTeX stores author names as "Last, First and Last, First and …" or
"First Last and First Last and …".  The normaliser tries both forms and
produces "Last" for the first-author last-name used in in-text citations,
and "Last, F." or "Last, F., & Last, F." for bibliography entries.
"""

from __future__ import annotations

import re
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prasword.core.document import Document

from prasword.utils.logger import get_logger

log = get_logger(__name__)

# ── Author parsing ────────────────────────────────────────────────────────────

def _split_authors(raw: str) -> list[str]:
    """Split a BibTeX author field on ' and ' (case-insensitive)."""
    return [a.strip() for a in re.split(r"\s+and\s+", raw.strip("{} "), flags=re.I) if a.strip()]


def _last_name(author_raw: str) -> str:
    """
    Extract the last name from a single BibTeX author token.
    Handles both "Last, First" and "First Last" forms.
    """
    a = author_raw.strip("{} ")
    if "," in a:
        return a.split(",")[0].strip()
    parts = a.split()
    return parts[-1] if parts else a


def _format_author_list(raw: str, max_authors: int = 3, et_al: str = "et al.") -> str:
    """
    Format an author list for bibliography display.

    Parameters
    ----------
    raw : str            Raw BibTeX author field.
    max_authors : int    Show this many authors before truncating with et_al.
    et_al : str          Truncation suffix.

    Returns
    -------
    str
        E.g. "Knuth, D. E., Lamport, L., & Mittelbach, F."
             "Einstein, A. et al."
    """
    authors = _split_authors(raw)
    if not authors:
        return "Unknown"
    if len(authors) > max_authors:
        return f"{_last_name(authors[0])} {et_al}"
    if len(authors) == 1:
        return authors[0].strip("{} ")
    # Build "Last1, Last2, & Last3"
    parts = [a.strip("{} ") for a in authors]
    if len(parts) == 2:
        return f"{parts[0]} & {parts[1]}"
    return ", ".join(parts[:-1]) + f", & {parts[-1]}"


def _strip_braces(s: str) -> str:
    """Remove outer LaTeX braces from a BibTeX field value."""
    return s.strip("{} \t\n\r")


# ── BibTeXManager ────────────────────────────────────────────────────────────

class BibTeXManager:
    """
    Static helpers for BibTeX operations on Document objects.

    Every method is stateless and thread-safe.
    """

    # ------------------------------------------------------------------ #
    # Import                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def import_file(document: "Document", path: Path) -> int:
        """
        Parse a .bib file and load all entries into *document*.

        Parameters
        ----------
        document : Document
        path : Path
            Must exist and be readable.

        Returns
        -------
        int
            Number of entries successfully imported.

        Raises
        ------
        FileNotFoundError
        ImportError   if bibtexparser is not installed.
        """
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"BibTeX file not found: {path}")

        try:
            import bibtexparser
            from bibtexparser.bparser import BibTexParser
            from bibtexparser.customization import convert_to_unicode
        except ImportError:
            raise ImportError(
                "bibtexparser is required for BibTeX import.\n"
                "  pip install bibtexparser"
            )

        parser = BibTexParser(common_strings=True)
        parser.customization = convert_to_unicode

        with path.open("r", encoding="utf-8", errors="replace") as fh:
            bib_db = bibtexparser.load(fh, parser=parser)

        imported = 0
        skipped  = 0
        for entry in bib_db.entries:
            citekey = entry.get("ID", "").strip()
            if not citekey:
                skipped += 1
                continue
            # Normalise all field names to lowercase; preserve ENTRYTYPE
            fields = {k.lower(): v for k, v in entry.items() if k != "ID"}
            # bibtexparser stores the entry type in "ENTRYTYPE"
            if "entrytype" not in fields and "ENTRYTYPE" in entry:
                fields["entrytype"] = entry["ENTRYTYPE"].lower()
            document.add_bib_entry(citekey, fields)
            imported += 1

        log.info("BibTeX import: %d imported, %d skipped from %s", imported, skipped, path.name)
        return imported

    @staticmethod
    def import_string(document: "Document", bib_text: str) -> int:
        """
        Parse a raw BibTeX string and load entries into *document*.

        Writes to a temporary file and delegates to import_file().

        Parameters
        ----------
        document : Document
        bib_text : str

        Returns
        -------
        int
            Number of entries imported.
        """
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".bib", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(bib_text)
            tmp_path = Path(fh.name)
        try:
            return BibTeXManager.import_file(document, tmp_path)
        finally:
            tmp_path.unlink(missing_ok=True)

    @staticmethod
    def add_entry(
        document: "Document",
        citekey: str,
        entrytype: str,
        fields: dict[str, str],
    ) -> None:
        """
        Manually add a single BibTeX entry without importing a .bib file.

        Parameters
        ----------
        document : Document
        citekey : str
            Must be unique; existing entries with the same key are overwritten.
        entrytype : str
            BibTeX entry type, e.g. "article", "book", "inproceedings".
        fields : dict[str, str]
            BibTeX fields; keys should be lowercase.
        """
        entry = {"entrytype": entrytype.lower(), **fields}
        document.add_bib_entry(citekey, entry)
        log.debug("Entry added manually: [%s] (%s)", citekey, entrytype)

    # ------------------------------------------------------------------ #
    # Export                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def export_file(document: "Document", path: Path) -> int:
        """
        Write all bibliography entries back to a .bib file.

        Parameters
        ----------
        document : Document
        path : Path
            Output file path; parent directory must exist.

        Returns
        -------
        int
            Number of entries written.
        """
        lines: list[str] = []
        for citekey, fields in document.bib_entries.items():
            if citekey.startswith("__"):
                continue   # skip internal metadata keys
            etype = fields.get("entrytype", fields.get("ENTRYTYPE", "misc"))
            lines.append(f"@{etype}{{{citekey},")
            for k, v in fields.items():
                if k in ("entrytype", "ENTRYTYPE"):
                    continue
                v_clean = v.strip("{}")
                lines.append(f"  {k} = {{{v_clean}}},")
            lines.append("}\n")
        path.write_text("\n".join(lines), encoding="utf-8")
        n = len([c for c in document.bib_entries if not c.startswith("__")])
        log.info("BibTeX export: %d entries written to %s", n, path)
        return n

    # ------------------------------------------------------------------ #
    # Format single entry                                                   #
    # ------------------------------------------------------------------ #

    @staticmethod
    def format_entry(entry: dict, style: str = "apa") -> str:
        """
        Format a single BibTeX entry dict as an HTML string.

        Parameters
        ----------
        entry : dict
            Lowercase-keyed field dict as stored in document.bib_entries.
        style : str
            One of: "apa", "mla", "chicago", "ieee", "vancouver".

        Returns
        -------
        str
            HTML-safe bibliography reference string.
        """
        # Extract and clean common fields
        raw_author = entry.get("author", "Unknown Author")
        raw_title  = _strip_braces(entry.get("title",  "Untitled"))
        year       = _strip_braces(entry.get("year",   "n.d."))
        journal    = _strip_braces(entry.get("journal", entry.get("booktitle", "")))
        volume     = _strip_braces(entry.get("volume",  ""))
        issue      = _strip_braces(entry.get("number",  entry.get("issue", "")))
        pages      = _strip_braces(entry.get("pages",   ""))
        doi        = _strip_braces(entry.get("doi",     ""))
        url        = _strip_braces(entry.get("url",     ""))
        publisher  = _strip_braces(entry.get("publisher", ""))
        edition    = _strip_braces(entry.get("edition",   ""))
        etype      = entry.get("entrytype", entry.get("ENTRYTYPE", "article")).lower()

        authors = _split_authors(raw_author)
        author_list = _format_author_list(raw_author)
        first_last  = _last_name(authors[0]) if authors else "Unknown"

        # Pages formatted with en-dash
        pages_fmt = pages.replace("--", "–").replace("-", "–")

        doi_link = (
            f' <a href="https://doi.org/{doi}" style="color:#89b4fa">'
            f'https://doi.org/{doi}</a>'
            if doi else ""
        )

        style = style.lower()

        if style == "apa":
            # Author, A. A., & Author, B. B. (Year). Title. Journal, V(N), pp. DOI
            base = f"{author_list} ({year}). <i>{raw_title}</i>."
            if journal:
                vol_iss = volume
                if issue:
                    vol_iss += f"({issue})"
                pg = f", {pages_fmt}" if pages_fmt else ""
                base += f" <i>{journal}</i>, <i>{vol_iss}</i>{pg}."
            elif publisher:
                base += f" {publisher}."
            return base + doi_link

        elif style == "mla":
            # Last, First. "Title." Journal, vol. V, no. N, Year, pp. P.
            parts = [a.strip("{}") for a in authors]
            if len(parts) == 1:
                author_mla = parts[0]
            elif len(parts) == 2:
                author_mla = f"{parts[0]}, and {parts[1]}"
            else:
                author_mla = f"{parts[0]}, et al."
            pg = f"pp. {pages_fmt}" if pages_fmt else ""
            vol_part = f"vol. {volume}, " if volume else ""
            iss_part = f"no. {issue}, " if issue else ""
            src = f"<i>{journal}</i>, {vol_part}{iss_part}{year}, {pg}." if journal else f"{year}."
            return f'{author_mla}. "{raw_title}." {src}'

        elif style == "chicago":
            # Last, First. "Title." Journal V, no. N (Year): pp. DOI
            pg = f": {pages_fmt}" if pages_fmt else ""
            vol_iss = f" {volume}, no. {issue}" if volume and issue else (f" {volume}" if volume else "")
            src = f"<i>{journal}</i>{vol_iss} ({year}){pg}." if journal else f"{publisher}, {year}."
            return f'{author_list}. "{raw_title}." {src}{doi_link}'

        elif style == "ieee":
            # [N] A. Last, "Title," Journal, vol. V, no. N, pp. P, Year.
            # (numbering is handled by generate_bibliography)
            author_ieee = ", ".join(
                f"{_last_name(a)}" for a in authors[:3]
            ) + (" et al." if len(authors) > 3 else "")
            vol_iss = f", vol. {volume}" if volume else ""
            iss_part = f", no. {issue}" if issue else ""
            pg = f", pp. {pages_fmt}" if pages_fmt else ""
            src = f"<i>{journal}</i>{vol_iss}{iss_part}{pg}, {year}." if journal else f"{publisher}, {year}."
            return f'{author_ieee}, "{raw_title}," {src}{doi_link}'

        elif style == "vancouver":
            # Last AB, Last CD. Title. Journal. Year;V(N):pp. doi:…
            def _initials(author_str: str) -> str:
                a = author_str.strip("{} ")
                if "," in a:
                    last, first = a.split(",", 1)
                    inits = "".join(p[0].upper() for p in first.strip().split() if p)
                    return f"{last.strip()} {inits}"
                parts = a.split()
                if len(parts) >= 2:
                    return f"{parts[-1]} {''.join(p[0].upper() for p in parts[:-1])}"
                return a
            auth_str = ", ".join(_initials(a) for a in authors[:6])
            if len(authors) > 6:
                auth_str += " et al"
            vol_pg = f"{volume}" if volume else ""
            if issue:
                vol_pg += f"({issue})"
            if pages_fmt:
                vol_pg += f":{pages_fmt}"
            src = f"<i>{journal}</i>. {year};{vol_pg}." if journal else f"{publisher}; {year}."
            doi_v = f" doi:{doi}" if doi else ""
            return f"{auth_str}. {raw_title}. {src}{doi_v}"

        # Fallback — plain author (year) title
        return f"{author_list} ({year}). {raw_title}."

    # ------------------------------------------------------------------ #
    # Bibliography generation                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def generate_bibliography(
        document: "Document",
        style: str = "apa",
        cited_only: bool = False,
        sort_by: str = "author",
    ) -> str:
        """
        Generate an HTML bibliography section for the document.

        Parameters
        ----------
        document : Document
        style : str
            Citation style: "apa" | "mla" | "chicago" | "ieee" | "vancouver".
        cited_only : bool
            If True, include only entries that appear as in-text citations
            in the document body (detected by ``[citekey]`` pattern).
        sort_by : str
            "author" (default), "year", "title", or "citekey".

        Returns
        -------
        str
            HTML string — a <section> with <h2>References</h2> and <ol>.
        """
        entries: dict[str, dict] = {
            k: v for k, v in document.bib_entries.items()
            if not k.startswith("__")
        }

        if cited_only:
            body_text   = document.plain_text()
            cited_keys  = set(re.findall(r"\[([^\]\s,]+)\]", body_text))
            entries     = {k: v for k, v in entries.items() if k in cited_keys}

        if not entries:
            return (
                "<section class='bibliography'>"
                "<p><i>No bibliography entries found.</i></p>"
                "</section>"
            )

        # Sort entries
        def _sort_key(kv: tuple[str, dict]):
            k, v = kv
            if sort_by == "year":
                return (_strip_braces(v.get("year", "0000")), _last_name(v.get("author", "")))
            if sort_by == "title":
                return _strip_braces(v.get("title", k)).lower()
            if sort_by == "citekey":
                return k.lower()
            # Default: author then year
            return (
                _last_name(v.get("author", k)).lower(),
                _strip_braces(v.get("year", "0000")),
            )

        sorted_entries = sorted(entries.items(), key=_sort_key)

        items: list[str] = []
        for idx, (citekey, entry) in enumerate(sorted_entries, start=1):
            formatted = BibTeXManager.format_entry(entry, style)
            ieee_num  = f"[{idx}] " if style == "ieee" else ""
            items.append(
                f'<li id="bib_{citekey}" style="margin-bottom:8px">'
                f'{ieee_num}{formatted}'
                f'</li>'
            )

        style_label = style.upper()
        return (
            "<section class='bibliography'>"
            f"<h2 style='color:#89b4fa'>References ({style_label})</h2>"
            f"<ol style='padding-left:20px'>{''.join(items)}</ol>"
            "</section>"
        )

    # ------------------------------------------------------------------ #
    # Search                                                               #
    # ------------------------------------------------------------------ #

    @staticmethod
    def search(
        document: "Document",
        query: str,
        fields: tuple[str, ...] = ("author", "title", "year", "journal", "abstract"),
    ) -> dict[str, dict]:
        """
        Case-insensitive substring search across specified fields.

        Also searches the cite-key itself.

        Parameters
        ----------
        document : Document
        query : str
        fields : tuple[str, ...]
            Field names to search.

        Returns
        -------
        dict[str, dict]
            Matching entries keyed by cite-key, in original order.
        """
        q = query.strip().lower()
        if not q:
            return dict(document.bib_entries)

        results: dict[str, dict] = {}
        for citekey, entry in document.bib_entries.items():
            if citekey.startswith("__"):
                continue
            # Always search the cite-key
            haystack = citekey.lower() + " " + " ".join(
                _strip_braces(entry.get(f, "")).lower() for f in fields
            )
            if q in haystack:
                results[citekey] = entry

        return results

    # ------------------------------------------------------------------ #
    # Merge                                                                 #
    # ------------------------------------------------------------------ #

    @staticmethod
    def merge(
        target: "Document",
        source: "Document",
        overwrite: bool = False,
    ) -> tuple[int, int]:
        """
        Copy all bibliography entries from *source* into *target*.

        Parameters
        ----------
        target : Document
        source : Document
        overwrite : bool
            If True, overwrite existing entries with the same cite-key.
            If False, skip conflicting keys.

        Returns
        -------
        tuple[int, int]
            (added, skipped) counts.
        """
        added   = 0
        skipped = 0
        for citekey, fields in source.bib_entries.items():
            if citekey.startswith("__"):
                continue
            if citekey in target.bib_entries and not overwrite:
                skipped += 1
            else:
                target.add_bib_entry(citekey, fields)
                added += 1
        log.info("Bibliography merge: %d added, %d skipped.", added, skipped)
        return added, skipped
