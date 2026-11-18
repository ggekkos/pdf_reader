from pdf_reader.core.speech import (
    HEADING_PAUSE_MS,
    PARAGRAPH_PAUSE_MS,
    SENTENCE_PAUSE_MS,
    chunks_from,
    split_sentences,
)

PARAGRAPHS = [
    ["Capítulo", "Um"],
    ["O", "rato", "roeu.", "A", "rainha", "riu!"],
    ["E", "a", "frase", "continua"],
]


def test_splits_into_sentences_with_pauses():
    chunks = split_sentences(PARAGRAPHS, page=3)
    assert [(c.start, c.end, c.text, c.pause_ms) for c in chunks] == [
        (0, 2, "Capítulo Um", HEADING_PAUSE_MS),
        (2, 5, "O rato roeu.", SENTENCE_PAUSE_MS),
        (5, 8, "A rainha riu!", PARAGRAPH_PAUSE_MS),
        (8, 12, "E a frase continua", 0),  # continues on the next page
    ]
    assert all(c.page == 3 for c in chunks)


def test_long_sentence_is_cut_at_a_comma():
    words = [f"w{i}" for i in range(30)]
    words[20] = "comma,"
    chunks = split_sentences([words], max_words=25)
    assert [(c.start, c.end) for c in chunks] == [(0, 21), (21, 30)]


def test_long_sentence_without_comma_is_cut_forcibly():
    chunks = split_sentences([[f"w{i}" for i in range(12)]], max_words=5)
    assert [(c.start, c.end) for c in chunks] == [(0, 5), (5, 10), (10, 12)]


def test_starts_mid_sentence():
    chunks = chunks_from(PARAGRAPHS, 0, 3)
    assert chunks[0].text == "rato roeu."
    assert chunks[0].start == 3
    assert len(chunks) == 3
