"""Access to the PDF file (the only part of the core that knows about PyMuPDF)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pymupdf

from pdf_reader.core.margins import margin_blocks
from pdf_reader.core.text import Box, ExtractedPage, extract_page, stitch_pages
from pdf_reader.core.toc import TocItem

_MARGIN_NEIGHBORS = 2  # pages before and after compared to find headers


class PdfDocument:
    """An open PDF, serving the text of each page as paragraphs."""

    def __init__(self, path: Path, skip_margins: bool = True) -> None:
        self.path = Path(path)
        self._pdf = pymupdf.open(self.path)
        self._skip_margins = skip_margins
        self._words: dict[int, list] = {}  # what PyMuPDF returns, untouched
        self._base: dict[int, ExtractedPage] = {}  # text of each page on its own
        self._cache: dict[int, ExtractedPage] = {}  # already stitched to its neighbors

    @property
    def page_count(self) -> int:
        return len(self._pdf)

    @property
    def skip_margins(self) -> bool:
        return self._skip_margins

    @skip_margins.setter
    def skip_margins(self, value: bool) -> None:
        if value != self._skip_margins:
            self._skip_margins = value
            self._base.clear()
            self._cache.clear()

    def paragraphs(self, page: int) -> list[list[str]]:
        return self._extracted(page).paragraphs

    def boxes(self, page: int) -> list[tuple[Box, ...]]:
        """Where each word of :meth:`paragraphs` sits on the page, in points."""
        return self._extracted(page).boxes

    def count_words(self, page: int) -> int:
        return len(self._extracted(page).boxes)

    def toc(self) -> list[TocItem]:
        """The PDF's bookmarks that point to an existing page."""
        items = []
        for level, title, page, *_ in self._pdf.get_toc(simple=True):
            if 1 <= page <= self.page_count and title.strip():
                items.append(TocItem(level, " ".join(title.split()), page - 1))
        return items

    def page_size(self, page: int) -> tuple[float, float]:
        """Page width and height, in points."""
        rect = self._pdf[page].rect
        return rect.width, rect.height

    def render(self, page: int, scale: float) -> tuple[int, int, int, bytes]:
        """Draw the page as an RGB image: (width, height, bytes per line, pixels)."""
        image = self._pdf[page].get_pixmap(
            matrix=pymupdf.Matrix(scale, scale), alpha=False
        )
        return image.width, image.height, image.stride, bytes(image.samples)

    def close(self) -> None:
        self._pdf.close()
        self._words.clear()
        self._base.clear()
        self._cache.clear()

    # --- internal ---
    def _pdf_words(self, page: int) -> list:
        if page not in self._words:
            self._words[page] = self._pdf[page].get_text("words")
        return self._words[page]

    def _base_of(self, page: int) -> ExtractedPage | None:
        if not 0 <= page < self.page_count:
            return None
        if page not in self._base:
            words = self._pdf_words(page)
            if self._skip_margins:
                neighbors = [
                    (self._pdf_words(n), self.page_size(n)[1])
                    for n in range(page - _MARGIN_NEIGHBORS, page + _MARGIN_NEIGHBORS + 1)
                    if n != page and 0 <= n < self.page_count
                ]
                skip = margin_blocks(words, self.page_size(page)[1], neighbors)
                words = [w for w in words if w[5] not in skip]
            self._base[page] = extract_page(words)
        return self._base[page]

    def _extracted(self, page: int) -> ExtractedPage:
        if page not in self._cache:
            self._cache[page] = stitch_pages(
                self._base_of(page - 1), self._base_of(page), self._base_of(page + 1)
            )
        return self._cache[page]


def file_id(path: Path, sample: int = 64 * 1024) -> str:
    """Build an identifier from the file's CONTENT.

    Uses the size plus the start and end of the file: fast even for huge
    books, and it doesn't change if the PDF is moved or renamed.
    """
    path = Path(path)
    size = path.stat().st_size
    digest = hashlib.sha256(str(size).encode())
    with path.open("rb") as file:
        digest.update(file.read(sample))
        if size > sample:
            file.seek(max(sample, size - sample))
            digest.update(file.read())
    return digest.hexdigest()[:32]
