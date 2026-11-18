"""Detection of headers, footers and page numbers.

A text block counts as "margin" when it sits entirely within the top or
bottom band of the page and, on top of that, is just a page number or
repeats (ignoring numbers) on the neighboring pages. That way the chapter
title at the top of every page isn't read again at each page turn.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

MARGIN_BAND = 0.10  # fraction of the page height, at the top and bottom

_RE_NUMBERS = re.compile(r"\d+")
_RE_ROMAN = re.compile(r"^[ivxlcdm]+$")
# Words that appear around page numbers ("Página 3 de 120", "Page 3 of 120").
_PAGE_WORDS = {"página", "pagina", "pág", "pág.", "pag", "pag.", "p", "p.",
               "page", "de", "of", "/", "-", "–", "—", "|"}


def _blocks(pdf_words: Iterable[Sequence]) -> dict[int, tuple[float, float, list[str]]]:
    """Block -> (top, bottom, words)."""
    blocks: dict[int, tuple[float, float, list[str]]] = {}
    for item in pdf_words:
        y0, y1, text, block = float(item[1]), float(item[3]), str(item[4]), item[5]
        top, bottom, words = blocks.get(block, (y0, y1, []))
        words.append(text)
        blocks[block] = (min(top, y0), max(bottom, y1), words)
    return blocks


def signature(words: Sequence[str]) -> str:
    """The block's text without numbers, to compare different pages."""
    text = " ".join(words).casefold()
    return " ".join(_RE_NUMBERS.sub("", text).split())


def is_page_number(words: Sequence[str]) -> bool:
    """E.g. "12", "xiv", "Page 3 of 120", "— 7 —"."""
    leftover = [
        w for w in (w.casefold().strip(".,;:()[]") for w in words)
        if w and not w.isdigit() and not _RE_ROMAN.match(w) and w not in _PAGE_WORDS
        and not _RE_NUMBERS.fullmatch(w.replace("/", ""))
    ]
    return not leftover and bool(words)


def _candidates(pdf_words: Iterable[Sequence], height: float) -> dict[int, list[str]]:
    """Blocks that fit entirely within the top or bottom band."""
    top_limit, bottom_limit = height * MARGIN_BAND, height * (1 - MARGIN_BAND)
    return {
        block: words
        for block, (top, bottom, words) in _blocks(pdf_words).items()
        if bottom <= top_limit or top >= bottom_limit
    }


def margin_blocks(
    pdf_words: Sequence[Sequence],
    height: float,
    neighbors: Iterable[tuple[Sequence[Sequence], float]],
) -> set[int]:
    """Numbers of the page's blocks that are a header, footer or page number.

    ``neighbors`` are the words and height of nearby pages (ideally two
    before and two after: books alternate headers between even and odd pages).
    """
    candidates = _candidates(pdf_words, height)
    if not candidates:
        return set()
    repeated = {
        signature(words)
        for neighbor_words, neighbor_height in neighbors
        for words in _candidates(neighbor_words, neighbor_height).values()
    }
    return {
        block
        for block, words in candidates.items()
        if is_page_number(words) or (signature(words) and signature(words) in repeated)
    }
