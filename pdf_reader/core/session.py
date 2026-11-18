"""Reading state: which page and which word you're on."""

from __future__ import annotations

from typing import Protocol


class PageSource(Protocol):
    """Anything that serves pages as paragraphs (e.g. PdfDocument)."""

    @property
    def page_count(self) -> int: ...

    def paragraphs(self, page: int) -> list[list[str]]: ...


class Session:
    """Reading position within a document.

    Every position change goes through here and is always kept within
    valid bounds, even with outdated saved progress.
    """

    def __init__(self, source: PageSource, page: int = 0, index: int = 0) -> None:
        self._source = source
        self._page = 0
        self._index = 0
        self._paragraphs: list[list[str]] = []
        self._words: list[str] = []
        self._load(page)
        self.go_to_word(index)

    # --- queries ---
    @property
    def page(self) -> int:
        return self._page

    @property
    def page_count(self) -> int:
        return self._source.page_count

    @property
    def index(self) -> int:
        return self._index

    @property
    def paragraphs(self) -> list[list[str]]:
        return self._paragraphs

    @property
    def words(self) -> list[str]:
        return self._words

    @property
    def current_word(self) -> str:
        return self._words[self._index] if self._words else ""

    @property
    def has_next_page(self) -> bool:
        return self._page < self.page_count - 1

    @property
    def has_previous_page(self) -> bool:
        return self._page > 0

    # --- movement ---
    def go_to_word(self, index: int) -> None:
        last = max(len(self._words) - 1, 0)
        self._index = min(max(index, 0), last)

    def advance(self) -> bool:
        """Move to the next word. Returns False if already on the last one."""
        if self._index >= len(self._words) - 1:
            return False
        self._index += 1
        return True

    def step_back(self) -> bool:
        if self._index == 0:
            return False
        self._index -= 1
        return True

    def go_to_page(self, page: int) -> bool:
        """Open the page at its start. Returns False if it doesn't exist."""
        if not 0 <= page < self.page_count or page == self._page:
            return False
        self._load(page)
        return True

    def next_page(self) -> bool:
        return self.go_to_page(self._page + 1)

    def previous_page(self, to_end: bool = False) -> bool:
        if not self.go_to_page(self._page - 1):
            return False
        if to_end:
            self.go_to_word(len(self._words) - 1)
        return True

    def reload(self) -> None:
        """Read the current page again (its text changed), keeping the position if possible."""
        index = self._index
        self._load(self._page)
        self.go_to_word(index)

    def _load(self, page: int) -> None:
        total = self.page_count
        self._page = min(max(page, 0), max(total - 1, 0))
        self._paragraphs = self._source.paragraphs(self._page) if total else []
        self._words = [w for paragraph in self._paragraphs for w in paragraph]
        self._index = 0
