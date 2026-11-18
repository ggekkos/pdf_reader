"""Cleanup of text extracted from PDFs.

PDFs come in all shapes: LaTeX with "detached" accents, books with
typographic ligatures, hyphenation at line ends... Everything here is a
pure function, with no dependency on Qt or PyMuPDF, so it can be tested.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

# Accents that LaTeX draws as a separate character, before the letter
# (e.g. "an´alise", "informac¸˜ao"). Mapped to the combining form.
_ACCENTS_BEFORE = {
    "´": "́",  # ´ acute
    "`": "̀",  # ` grave
    "ˆ": "̂",  # ˆ circumflex
    "˜": "̃",  # ˜ tilde
    "¨": "̈",  # ¨ diaeresis
    "ˇ": "̌",  # ˇ caron
}
_CEDILLA = "¸"  # ¸ — in LaTeX it usually comes AFTER the "c"
_COMBINING_CEDILLA = "̧"

_RE_ACCENT_BEFORE = re.compile(
    "([" + "".join(_ACCENTS_BEFORE) + r"])([^\W\d_])"
)
_RE_CEDILLA_AFTER = re.compile("([cC])" + _CEDILLA)
_RE_CEDILLA_BEFORE = re.compile(_CEDILLA + "([cC])")
# "ı" (dotless i) + a combining accent should become an accented "i".
_RE_DOTLESS_I = re.compile("ı(?=[̀-ͯ])")

_LIGATURES = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
    "ﬅ": "st",
    "ﬆ": "st",
}
_INVISIBLE = dict.fromkeys(map(ord, "​‌‍﻿"))

SOFT_HYPHEN = "­"
_HYPHENS = ("-", "‐", SOFT_HYPHEN)


def normalize_word(word: str) -> str:
    """Fix accents, ligatures and invisible characters in a word.

    A trailing soft hyphen is kept: it marks a line break and is resolved
    later by :func:`join_lines`.
    """
    for ligature, replacement in _LIGATURES.items():
        word = word.replace(ligature, replacement)
    word = word.translate(_INVISIBLE)
    if word:
        word = word[:-1].replace(SOFT_HYPHEN, "") + word[-1]

    word = _RE_ACCENT_BEFORE.sub(
        lambda m: m.group(2) + _ACCENTS_BEFORE[m.group(1)], word
    )
    word = _RE_CEDILLA_AFTER.sub(r"\1" + _COMBINING_CEDILLA, word)
    word = _RE_CEDILLA_BEFORE.sub(r"\1" + _COMBINING_CEDILLA, word)
    word = _RE_DOTLESS_I.sub("i", word)
    return unicodedata.normalize("NFC", word).strip()


def _ends_with_hyphenation(word: str) -> bool:
    return len(word) > 1 and word[-1] in _HYPHENS and word[-2].isalpha()


Box = tuple[float, float, float, float]  # x0, y0, x1, y1 in PDF points


def join_lines(lines: Iterable[Sequence[str]]) -> list[str]:
    """Join a paragraph's lines, undoing hyphenation.

    "infor-" at the end of a line followed by "mação" on the next becomes
    "informação". Only joins when the continuation starts in lowercase, so
    legitimate hyphens before proper names aren't broken.
    """
    with_boxes = [[(word, ()) for word in line] for line in lines]
    return [word for word, _ in join_lines_with_boxes(with_boxes)]


def join_lines_with_boxes(
    lines: Iterable[Sequence[tuple[str, tuple[Box, ...]]]],
) -> list[tuple[str, tuple[Box, ...]]]:
    """Like :func:`join_lines`, but each word carries the boxes where it
    appears in the PDF. A hyphenated word keeps both boxes."""
    words: list[tuple[str, tuple[Box, ...]]] = []
    pending_break = False
    for line in lines:
        for i, (word, boxes) in enumerate(line):
            if i == 0 and pending_break and word[:1].islower():
                previous, previous_boxes = words[-1]
                words[-1] = (previous[:-1] + word, previous_boxes + boxes)
            else:
                words.append((word, boxes))
        if line:
            pending_break = _ends_with_hyphenation(words[-1][0])
    # Leftover soft hyphens (at the end of a page, for example) are invisible.
    return [(w.rstrip(SOFT_HYPHEN) or w, b) for w, b in words]


@dataclass
class ExtractedPage:
    paragraphs: list[list[str]]
    boxes: list[tuple[Box, ...]]  # one entry per word, in reading order


def extract_page(pdf_words: Iterable[Sequence]) -> ExtractedPage:
    """Group PyMuPDF's words (``page.get_text("words")``) into paragraphs.

    Each input item is ``(x0, y0, x1, y1, text, block, line, n)``.
    Each PDF block becomes a paragraph. The boxes let the word being read
    be marked on the original PDF.
    """
    blocks: dict[int, dict[int, list[tuple[str, tuple[Box, ...]]]]] = {}
    for item in pdf_words:
        text, block, line = item[4], item[5], item[6]
        word = normalize_word(text)
        if word:
            box = (float(item[0]), float(item[1]), float(item[2]), float(item[3]))
            blocks.setdefault(block, {}).setdefault(line, []).append((word, (box,)))

    page = ExtractedPage([], [])
    for lines in blocks.values():
        words = join_lines_with_boxes(lines.values())
        if words:
            page.paragraphs.append([w for w, _ in words])
            page.boxes.extend(b for _, b in words)
    return page


def build_paragraphs(pdf_words: Iterable[Sequence]) -> list[list[str]]:
    """Just the paragraphs from :func:`extract_page`."""
    return extract_page(pdf_words).paragraphs


def stitch_pages(
    previous: ExtractedPage | None,
    current: ExtractedPage,
    following: ExtractedPage | None,
) -> ExtractedPage:
    """Undo hyphenation that crosses a page turn.

    If the page ends in "infor-" and the next one starts with "mação", the
    whole word stays at the end of this page and leaves the start of the next.
    """
    paragraphs = [list(p) for p in current.paragraphs]
    boxes = list(current.boxes)

    def continues(end: ExtractedPage | None, start: ExtractedPage | None) -> bool:
        if not (end and start and end.paragraphs and start.paragraphs):
            return False
        return (_ends_with_hyphenation(end.paragraphs[-1][-1])
                and start.paragraphs[0][0][:1].islower())

    if continues(current, following):
        paragraphs[-1][-1] = paragraphs[-1][-1][:-1] + following.paragraphs[0][0]
    if continues(previous, current):
        del paragraphs[0][0]
        del boxes[0]
        if not paragraphs[0]:
            del paragraphs[0]
    return ExtractedPage(paragraphs, boxes)
