"""Split a page's text into chunks for reading aloud.

Each chunk is a sentence (or a piece of a very long one) and carries the
pause that should follow it: longer at the end of a paragraph, shorter at
the end of a sentence, almost none when the sentence continues on the next page.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from pdf_reader.core.pacing import ends_sentence

MAX_WORDS = 40  # longer sentences are cut at a comma (or forcibly)

PARAGRAPH_PAUSE_MS = 450
SENTENCE_PAUSE_MS = 200
HEADING_PAUSE_MS = 300  # paragraph with no final punctuation, like a heading
COMMA_PAUSE_MS = 60


@dataclass(frozen=True)
class Chunk:
    page: int
    start: int  # index of the first word on the page
    end: int  # index after the last word
    text: str
    pause_ms: int


def _pause_after(word: str) -> bool:
    last = word.rstrip("\"'”’»)]")[-1:]
    return bool(last) and last in ",;:—–"


def split_sentences(
    paragraphs: Sequence[Sequence[str]], page: int = 0, max_words: int = MAX_WORDS
) -> list[Chunk]:
    chunks: list[Chunk] = []
    base = 0
    for n, paragraph in enumerate(paragraphs):
        last_paragraph = n == len(paragraphs) - 1
        start = 0
        while start < len(paragraph):
            end, pause = _chunk_end(paragraph, start, max_words)
            if end == len(paragraph):  # end of the paragraph
                if ends_sentence(paragraph[-1]):
                    pause = PARAGRAPH_PAUSE_MS
                elif not last_paragraph:
                    pause = HEADING_PAUSE_MS
                # Last paragraph without a period: the sentence continues on the next page.
            chunks.append(Chunk(page, base + start, base + end,
                                " ".join(paragraph[start:end]), pause))
            start = end
        base += len(paragraph)
    return chunks


def _chunk_end(paragraph: Sequence[str], start: int, max_words: int) -> tuple[int, int]:
    """Where the chunk beginning at ``start`` ends, and the pause after it."""
    limit = min(len(paragraph), start + max_words)
    comma = None
    for i in range(start, limit):
        if ends_sentence(paragraph[i]):
            return i + 1, SENTENCE_PAUSE_MS
        if _pause_after(paragraph[i]) and i - start >= max_words // 3:
            comma = i + 1
    if limit == len(paragraph):
        return limit, 0
    if comma is not None:
        return comma, COMMA_PAUSE_MS
    return limit, 0


def chunks_from(
    paragraphs: Sequence[Sequence[str]], page: int, index: int
) -> list[Chunk]:
    """The page's chunks starting at word ``index``.

    The chunk that ``index`` falls in is trimmed to begin exactly there.
    """
    result = []
    words = [w for paragraph in paragraphs for w in paragraph]
    for chunk in split_sentences(paragraphs, page):
        if chunk.end <= index:
            continue
        if chunk.start < index:
            chunk = Chunk(page, index, chunk.end,
                          " ".join(words[index:chunk.end]), chunk.pause_ms)
        result.append(chunk)
    return result
