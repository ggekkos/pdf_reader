"""The PDF's table of contents: which chapter you're in and where it ends."""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class TocItem:
    level: int  # 1 = top
    title: str
    page: int  # zero-based


def chapter_level(items: Sequence[TocItem]) -> int:
    """The highest level with at least three items.

    In a book split into "Part I" and "Part II", the chapters are on the
    level below. With a single top item (the book's title), too.
    """
    counts = Counter(item.level for item in items)
    for level in sorted(counts):
        if counts[level] > 2:
            return level
    return min(counts, default=1)


def current_item(items: Sequence[TocItem], page: int) -> int | None:
    """Index of the most specific item that ``page`` is in."""
    current = None
    for index, item in enumerate(items):
        if item.page <= page:
            current = index
        else:
            break
    return current


def chapter_end(items: Sequence[TocItem], page: int, page_count: int) -> int:
    """First page AFTER the current chapter (or ``page_count``)."""
    level = chapter_level(items)
    for item in items:
        if item.level <= level and item.page > page:
            return min(item.page, page_count)
    return page_count
