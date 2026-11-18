"""Text search over a page's words, ignoring accents and case."""

from __future__ import annotations

import unicodedata
from bisect import bisect_right
from collections.abc import Sequence


def key(text: str) -> str:
    """"Informação" and "informacao" become the same thing."""
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if not unicodedata.combining(c)).casefold()


def find(
    words: Sequence[str],
    query: str,
    start: int | None = None,
    backwards: bool = False,
) -> int | None:
    """Index of the word where the next occurrence of ``query`` begins.

    Forwards, searches from word ``start`` on (default: the beginning).
    Backwards, searches before word ``start`` (default: the end).
    The query may span several words and may be just part of a word.
    """
    target = " ".join(key(query).split())
    if not target or not words:
        return None

    starts: list[int] = []
    pieces: list[str] = []
    position = 0
    for word in words:
        starts.append(position)
        piece = key(word)
        pieces.append(piece)
        position += len(piece) + 1
    text = " ".join(pieces)

    if backwards:
        limit = len(text) if start is None or start >= len(words) else starts[max(start, 0)]
        # The occurrence must BEGIN before the limit.
        found = text.rfind(target, 0, limit - 1 + len(target))
    else:
        if start is not None and start >= len(words):
            return None
        found = text.find(target, starts[max(start or 0, 0)])
    if found < 0:
        return None
    return bisect_right(starts, found) - 1
