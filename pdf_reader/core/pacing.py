"""How long the marker stays on each word."""

from __future__ import annotations

_SENTENCE_END = ".!?…"
_SHORT_PAUSE = ",;:"
_LONG_WORD = 9


def ends_sentence(word: str) -> bool:
    last = word.rstrip("\"'”’»)]")[-1:]
    return bool(last) and last in _SENTENCE_END


def delay_ms(word: str, words_per_minute: int) -> int:
    """How long a word is shown, with natural pauses at punctuation."""
    base = 60_000 / max(words_per_minute, 1)
    last = word.rstrip("\"'”’»)]")[-1:]
    if last and last in _SENTENCE_END:
        factor = 2.0
    elif last and last in _SHORT_PAUSE:
        factor = 1.5
    elif len(word) >= _LONG_WORD:
        factor = 1.3
    else:
        factor = 1.0
    return round(base * factor)
