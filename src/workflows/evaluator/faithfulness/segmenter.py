"""
Sentence Segmentation Utility for Faithfulness Evaluation

Berdasarkan pendekatan STORYSUMM, segmentasi dilakukan pada level kalimat
utuh (bukan atomic claims) karena evaluasi pada tingkat kalimat sudah memadai
untuk menghasilkan ketelitian yang tinggi, sekaligus menjaga keutuhan konteks
alur cerita.

Dua mode segmentasi:
  1. segment_all_sentences()       -- semua kalimat dalam teks
  2. segment_citation_sentences()  -- hanya kalimat yang mengandung citation marker
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

# ---------------------------------------------------------------------------
# Default citation pattern: [1], [2,3], [1, 2, 3], etc.
# ---------------------------------------------------------------------------
CITATION_PATTERN = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")

# ---------------------------------------------------------------------------
# Sentence splitting regex
#
# Rule-based splitter yang menangani:
#   - Titik diikuti spasi + huruf kapital (kalimat standar)
#   - Tanda seru dan tanda tanya sebagai pemisah kalimat
#   - Menghindari split pada abbreviation umum (e.g., "Dr.", "No.", "vs.")
#   - Menghindari split pada angka desimal (e.g., "3.14")
#   - Menghindari split pada ellipsis ("...")
# ---------------------------------------------------------------------------
_ABBREVIATIONS = frozenset({
    "dr", "mr", "mrs", "ms", "prof", "sr", "jr", "st", "vs", "etc",
    "inc", "ltd", "corp", "no", "vol", "dept", "est", "approx",
    "fig", "ref", "eq", "al", "ed", "trans",
})

_SENTENCE_BOUNDARY = re.compile(
    r"(?<=[.!?])"     # lookbehind: sentence-ending punctuation
    r"(?:\s+)"         # whitespace between sentences
    r"(?=[A-Z\u00C0-\u024F\[\"\u201C(])"  # lookahead: capital letter, bracket, quote
)


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences using rule-based regex.

    Returns non-empty stripped sentences.
    """
    text = text.strip()
    if not text:
        return []

    # Protect abbreviations by temporarily replacing their dots
    protected = text
    _PLACEHOLDER_DOT = "\x00"
    for abbr in _ABBREVIATIONS:
        # Case-insensitive replacement of "abbr." with "abbr<placeholder>"
        pattern = re.compile(
            rf"\b({re.escape(abbr)})\.",
            re.IGNORECASE,
        )
        protected = pattern.sub(lambda m: m.group(1) + _PLACEHOLDER_DOT, protected)

    # Protect decimal numbers (e.g., "3.14" -> "3<placeholder>14")
    protected = re.sub(
        r"(\d)\.(\d)",
        lambda m: m.group(1) + _PLACEHOLDER_DOT + m.group(2),
        protected,
    )


    # Protect ellipsis
    protected = protected.replace("...", "\x01\x01\x01")

    # Split on sentence boundaries
    raw_sentences = _SENTENCE_BOUNDARY.split(protected)

    # Restore protected characters
    sentences = []
    for s in raw_sentences:
        s = s.replace("\x00", ".").replace("\x01\x01\x01", "...")
        s = s.strip()
        if s:
            sentences.append(s)

    return sentences


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SentenceSegment:
    """Satu kalimat yang tersegmentasi dari teks response."""

    index: int
    """Posisi kalimat dalam teks asli (0-indexed)."""

    text: str
    """Kalimat utuh."""

    has_citation: bool
    """True jika kalimat mengandung citation marker."""

    citation_ids: List[int] = field(default_factory=list)
    """Daftar ID citation yang ditemukan, e.g. [1, 3] dari '[1,3]'."""


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _extract_citation_ids(text: str) -> List[int]:
    """Extract semua citation IDs dari teks.

    Contoh:
        "[1]"       -> [1]
        "[2,3]"     -> [2, 3]
        "[1] ... [4, 5]" -> [1, 4, 5]
    """
    ids: List[int] = []
    for match in CITATION_PATTERN.finditer(text):
        inner = match.group(1)
        for num_str in inner.split(","):
            num_str = num_str.strip()
            if num_str.isdigit():
                ids.append(int(num_str))
    return sorted(set(ids))


def segment_all_sentences(text: str) -> List[SentenceSegment]:
    """Segmentasi semua kalimat dari teks.

    Setiap kalimat di-tag apakah mengandung citation marker atau tidak.
    """
    raw_sentences = _split_sentences(text)
    segments: List[SentenceSegment] = []

    for i, sent in enumerate(raw_sentences):
        cit_ids = _extract_citation_ids(sent)
        segments.append(
            SentenceSegment(
                index=i,
                text=sent,
                has_citation=bool(cit_ids),
                citation_ids=cit_ids,
            )
        )

    return segments


def segment_citation_sentences(
    text: str,
    pattern: re.Pattern = CITATION_PATTERN,
) -> List[SentenceSegment]:
    """Segmentasi hanya kalimat yang mengandung citation marker.

    Default pattern mencocokkan: [1], [2,3], [1, 2, 3], dsb.
    Kalimat tanpa citation dilewati.
    """
    all_segments = segment_all_sentences(text)
    return [seg for seg in all_segments if seg.has_citation]
