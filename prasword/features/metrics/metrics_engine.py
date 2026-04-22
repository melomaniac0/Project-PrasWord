"""
prasword.features.metrics.metrics_engine
=========================================
Document metrics computation engine.

Architecture
------------
Two computation tiers:

  fast(document) → tuple[int, int, str]
      Runs on every keystroke. Regex word-split only.
      Returns (word_count, char_count, reading_time_str).
      Target: < 5 ms on a 50 000-word document.

  compute(document) → DocumentMetrics
      Full analysis triggered by status-bar timer (≥ 300 ms debounce)
      or on explicit user request (Tools → Word Count).
      Returns a frozen DocumentMetrics snapshot with 14 fields.

  compute_selection(text) → DocumentMetrics
      Same as compute() but operates on an arbitrary string — used when
      the editor has an active selection.

  flesch_reading_ease(text) → float
      Flesch Reading Ease score (0–100; higher = easier).

  top_words(text, n) → list[tuple[str, int]]
      Most frequent content words (stop-words removed).

DocumentMetrics
---------------
Frozen dataclass — all fields are read-only after construction.
Provides to_status_bar() and to_detail_text() serialisation helpers
consumed by StatusBarWidget and the word-count dialog.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from prasword.core.document import Document

from prasword.utils.logger import get_logger

log = get_logger(__name__)

# ── Constants ────────────────────────────────────────────────────────────────

_READING_WPM    = 238   # average adult silent reading speed
_SPEAKING_WPM   = 130   # average presentation speaking speed

# Compiled patterns
_WORD_RE        = re.compile(r"\b[a-zA-Z\u00C0-\u024F\u0400-\u04FF\w]+\b", re.UNICODE)
_SENTENCE_END   = re.compile(r"[.!?…]+[\s\"')\]]*")
_PARAGRAPH_SEP  = re.compile(r"\n{2,}|\r\n{2,}")
_WHITESPACE     = re.compile(r"[\s\u200b\u200c\u200d\ufeff]+")  # incl. zero-width

# Common English stop-words (for top_words)
_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "up", "about", "into", "through", "is",
    "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might",
    "shall", "can", "it", "its", "this", "that", "these", "those", "i",
    "me", "my", "we", "our", "you", "your", "he", "she", "they", "their",
    "his", "her", "not", "no", "so", "if", "as", "than", "then", "also",
    "which", "who", "what", "when", "where", "how", "all", "any", "both",
    "each", "more", "most", "other", "some", "such", "only", "own", "same",
    "s", "t", "re", "ve", "ll", "d", "m",
})


# ── DocumentMetrics dataclass ────────────────────────────────────────────────

@dataclass(frozen=True)
class DocumentMetrics:
    """
    Immutable snapshot of all computed document metrics.

    Attributes
    ----------
    word_count : int
        Total words (Unicode-aware, includes hyphenated words).
    char_count : int
        Total characters including spaces, newlines, punctuation.
    char_count_no_spaces : int
        Characters excluding all whitespace.
    paragraph_count : int
        Blocks of text separated by blank lines (minimum 1 if any text).
    sentence_count : int
        Sentences detected by terminal punctuation heuristic.
    unique_words : int
        Distinct lowercase word forms.
    avg_word_length : float
        Mean character count per word (rounded to 2 dp).
    avg_sentence_length : float
        Mean words per sentence (rounded to 2 dp).
    reading_time_seconds : int
        Estimated silent reading time in seconds (@238 wpm).
    speaking_time_seconds : int
        Estimated spoken presentation time in seconds (@130 wpm).
    reading_time_str : str
        Human-friendly reading time, e.g. "3 min 14 sec".
    speaking_time_str : str
        Human-friendly speaking time.
    flesch_score : float
        Flesch Reading Ease score (0–100). -1.0 if not computable.
    flesch_label : str
        Grade label for the Flesch score, e.g. "Standard".
    """

    word_count:            int
    char_count:            int
    char_count_no_spaces:  int
    paragraph_count:       int
    sentence_count:        int
    unique_words:          int
    avg_word_length:       float
    avg_sentence_length:   float
    reading_time_seconds:  int
    speaking_time_seconds: int
    reading_time_str:      str
    speaking_time_str:     str
    flesch_score:          float
    flesch_label:          str

    # ------------------------------------------------------------------ #
    # Derived properties                                                   #
    # ------------------------------------------------------------------ #

    @property
    def reading_time_minutes(self) -> float:
        """Reading time in fractional minutes."""
        return self.reading_time_seconds / 60.0

    @property
    def lexical_density(self) -> float:
        """
        Ratio of unique words to total words (vocabulary richness).
        Returns 0.0 when word_count is 0.
        """
        return self.unique_words / self.word_count if self.word_count else 0.0

    # ------------------------------------------------------------------ #
    # Serialisation helpers                                                #
    # ------------------------------------------------------------------ #

    def to_status_bar(self) -> str:
        """
        Compact one-line summary for the status bar.
        Example: "W: 1,234  C: 7,891  ~5 min read"
        """
        return (
            f"W: {self.word_count:,}  "
            f"C: {self.char_count:,}  "
            f"~{self.reading_time_str} read"
        )

    def to_detail_text(self) -> str:
        """
        Multi-line plain-text summary for the word-count dialog.
        """
        flesch = (
            f"{self.flesch_score:.1f}  ({self.flesch_label})"
            if self.flesch_score >= 0
            else "n/a"
        )
        ld = f"{self.lexical_density:.1%}"
        return (
            f"Words:                    {self.word_count:,}\n"
            f"Unique words:             {self.unique_words:,}\n"
            f"Lexical density:          {ld}\n"
            f"Characters (w/ spaces):   {self.char_count:,}\n"
            f"Characters (no spaces):   {self.char_count_no_spaces:,}\n"
            f"Paragraphs:               {self.paragraph_count:,}\n"
            f"Sentences:                {self.sentence_count:,}\n"
            f"Avg word length:          {self.avg_word_length:.1f} chars\n"
            f"Avg sentence length:      {self.avg_sentence_length:.1f} words\n"
            f"Flesch Reading Ease:      {flesch}\n"
            f"Reading time:             ~{self.reading_time_str}\n"
            f"Speaking time:            ~{self.speaking_time_str}"
        )

    def to_html(self) -> str:
        """
        HTML table version of to_detail_text(), used in the metrics dock.
        """
        flesch = (
            f"{self.flesch_score:.1f} ({self.flesch_label})"
            if self.flesch_score >= 0
            else "n/a"
        )
        rows = [
            ("Words",                  f"{self.word_count:,}"),
            ("Unique words",           f"{self.unique_words:,}"),
            ("Lexical density",        f"{self.lexical_density:.1%}"),
            ("Chars (w/ spaces)",      f"{self.char_count:,}"),
            ("Chars (no spaces)",      f"{self.char_count_no_spaces:,}"),
            ("Paragraphs",             f"{self.paragraph_count:,}"),
            ("Sentences",              f"{self.sentence_count:,}"),
            ("Avg word length",        f"{self.avg_word_length:.1f} ch"),
            ("Avg sentence length",    f"{self.avg_sentence_length:.1f} wds"),
            ("Flesch score",           flesch),
            ("Reading time",           f"~{self.reading_time_str}"),
            ("Speaking time",          f"~{self.speaking_time_str}"),
        ]
        trs = "".join(
            f"<tr>"
            f"<td style='color:#a6adc8;padding:2px 12px 2px 0'>{label}</td>"
            f"<td style='color:#cdd6f4;text-align:right'>{value}</td>"
            f"</tr>"
            for label, value in rows
        )
        return f"<table style='font-size:9pt;border-spacing:0'>{trs}</table>"


# ── MetricsEngine ────────────────────────────────────────────────────────────

class MetricsEngine:
    """
    Static factory and utility class for document metrics.

    Methods
    -------
    compute(document) → DocumentMetrics
        Full analysis from a Document object.
    compute_selection(text) → DocumentMetrics
        Full analysis from a raw string.
    fast(document) → tuple[int, int, str]
        Keystroke-safe minimal analysis.
    flesch_reading_ease(text) → float
        Flesch Reading Ease score.
    top_words(text, n, exclude_stop_words) → list[tuple[str, int]]
        Most frequent words.
    """

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    @staticmethod
    def compute(document: "Document") -> DocumentMetrics:
        """
        Full metrics analysis of *document*.

        Parameters
        ----------
        document : Document

        Returns
        -------
        DocumentMetrics
            Frozen snapshot of all 14 metrics fields.
        """
        text = document.qt_document.toPlainText()
        result = MetricsEngine._analyse(text)
        log.debug(
            "Metrics computed: %d words, %d chars, %d paras",
            result.word_count, result.char_count, result.paragraph_count,
        )
        return result

    @staticmethod
    def compute_selection(text: str) -> DocumentMetrics:
        """
        Full metrics analysis for an arbitrary string.

        Useful for analysing only the selected region of the editor,
        or for computing metrics on a pasted block before insertion.

        Parameters
        ----------
        text : str

        Returns
        -------
        DocumentMetrics
        """
        return MetricsEngine._analyse(text)

    @staticmethod
    def fast(document: "Document") -> tuple[int, int, str]:
        """
        Minimal metrics designed for keystroke-level updates.

        Uses a single regex pass with no sentence/paragraph analysis.

        Parameters
        ----------
        document : Document

        Returns
        -------
        tuple[int, int, str]
            (word_count, char_count, reading_time_str)
        """
        text = document.qt_document.toPlainText()
        words = _WORD_RE.findall(text)
        wc    = len(words)
        cc    = len(text)
        rt    = MetricsEngine._fmt_time(wc, _READING_WPM)
        return wc, cc, rt

    @staticmethod
    def flesch_reading_ease(text: str) -> float:
        """
        Compute the Flesch Reading Ease score for *text*.

        Formula
        -------
        206.835 − 1.015 × (words/sentences) − 84.6 × (syllables/words)

        Returns
        -------
        float
            Score 0–100 (clamped).  Returns -1.0 if not enough text to score.

        Interpretation
        --------------
        90–100  Very Easy  (5th grade)
        80–90   Easy
        70–80   Fairly Easy
        60–70   Standard  (8th–9th grade)
        50–60   Fairly Difficult
        30–50   Difficult
        0–30    Very Confusing  (college level)
        """
        words     = _WORD_RE.findall(text)
        sentences = [s for s in _SENTENCE_END.split(text) if s.strip()]
        wc  = len(words)
        sc  = len(sentences)
        if wc < 10 or sc < 1:
            return -1.0
        syl = sum(MetricsEngine._count_syllables(w) for w in words)
        score = 206.835 - 1.015 * (wc / sc) - 84.6 * (syl / wc)
        return round(max(0.0, min(100.0, score)), 1)

    @staticmethod
    def top_words(
        text: str,
        n: int = 10,
        exclude_stop_words: bool = True,
    ) -> list[tuple[str, int]]:
        """
        Return the *n* most frequent words in *text*.

        Parameters
        ----------
        text : str
        n : int
            Number of results to return.
        exclude_stop_words : bool
            If True, common English stop-words are removed before counting.

        Returns
        -------
        list[tuple[str, int]]
            Ordered list of (word, count) pairs, most frequent first.
        """
        words = [w.lower() for w in _WORD_RE.findall(text)]
        if exclude_stop_words:
            words = [w for w in words if w not in _STOP_WORDS and len(w) > 1]
        counter = Counter(words)
        return counter.most_common(n)

    # ------------------------------------------------------------------ #
    # Internal implementation                                             #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _analyse(text: str) -> DocumentMetrics:
        """Core analysis — called by both compute() and compute_selection()."""

        # ── Words ──────────────────────────────────────────────────────
        words = _WORD_RE.findall(text)
        wc    = len(words)

        # ── Characters ─────────────────────────────────────────────────
        cc    = len(text)
        # Strip all whitespace variants for no-space count
        cc_ns = len(_WHITESPACE.sub("", text))

        # ── Paragraphs ─────────────────────────────────────────────────
        paras = [p.strip() for p in _PARAGRAPH_SEP.split(text) if p.strip()]
        pc    = len(paras) if paras else (1 if text.strip() else 0)

        # ── Sentences ──────────────────────────────────────────────────
        # Split on sentence-terminal punctuation; keep non-empty fragments
        frags = [s.strip() for s in _SENTENCE_END.split(text) if s.strip()]
        sc    = max(1, len(frags)) if text.strip() else 0

        # ── Unique words ───────────────────────────────────────────────
        unique = len({w.lower() for w in words})

        # ── Average word length ────────────────────────────────────────
        avg_wl = (
            round(sum(len(w) for w in words) / wc, 2)
            if wc else 0.0
        )

        # ── Average sentence length ─────────────────────────────────────
        avg_sl = round(wc / sc, 2) if sc else 0.0

        # ── Reading / speaking time ────────────────────────────────────
        read_secs  = int((wc / _READING_WPM)  * 60) if wc else 0
        speak_secs = int((wc / _SPEAKING_WPM) * 60) if wc else 0
        read_str   = MetricsEngine._fmt_time(wc, _READING_WPM)
        speak_str  = MetricsEngine._fmt_time(wc, _SPEAKING_WPM)

        # ── Flesch Reading Ease ────────────────────────────────────────
        flesch = MetricsEngine.flesch_reading_ease(text)
        flesch_label = MetricsEngine._flesch_label(flesch)

        return DocumentMetrics(
            word_count=wc,
            char_count=cc,
            char_count_no_spaces=cc_ns,
            paragraph_count=pc,
            sentence_count=sc,
            unique_words=unique,
            avg_word_length=avg_wl,
            avg_sentence_length=avg_sl,
            reading_time_seconds=read_secs,
            speaking_time_seconds=speak_secs,
            reading_time_str=read_str,
            speaking_time_str=speak_str,
            flesch_score=flesch,
            flesch_label=flesch_label,
        )

    @staticmethod
    def _fmt_time(word_count: int, wpm: int) -> str:
        """Format a word count + speed into a human-readable time string."""
        if word_count == 0:
            return "< 1 min"
        total_secs = int((word_count / wpm) * 60)
        if total_secs < 60:
            return "< 1 min"
        minutes, secs = divmod(total_secs, 60)
        if secs == 0:
            return f"{minutes} min"
        return f"{minutes} min {secs} sec"

    @staticmethod
    def _count_syllables(word: str) -> int:
        """
        Heuristic English syllable counter.
        Accurate enough for Flesch scoring; not a full pronunciation model.
        """
        word = word.lower().strip("'\".,!?;:")
        if not word:
            return 0
        # Count vowel groups
        count = len(re.findall(r"[aeiouy]+", word))
        # Silent trailing 'e'
        if word.endswith("e") and count > 1:
            count -= 1
        # Every word has at least one syllable
        return max(1, count)

    @staticmethod
    def _flesch_label(score: float) -> str:
        """Return a grade label for a Flesch Reading Ease score."""
        if score < 0:
            return "n/a"
        if score >= 90: return "Very Easy"
        if score >= 80: return "Easy"
        if score >= 70: return "Fairly Easy"
        if score >= 60: return "Standard"
        if score >= 50: return "Fairly Difficult"
        if score >= 30: return "Difficult"
        return "Very Confusing"
