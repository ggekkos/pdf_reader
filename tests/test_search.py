from pdf_reader.core.search import find

WORDS = ["A", "Informação", "chegou", "cedo;", "a", "informação", "saiu."]


def test_ignores_accents_and_case():
    assert find(WORDS, "informacao") == 1
    assert find(WORDS, "INFORMAÇÃO", start=2) == 5


def test_multiple_words_and_fragments():
    assert find(WORDS, "chegou  cedo") == 2
    assert find(WORDS, "egou ce") == 2
    assert find(WORDS, "nada") is None


def test_backwards():
    assert find(WORDS, "informação", backwards=True) == 5
    assert find(WORDS, "informação", start=5, backwards=True) == 1
    assert find(WORDS, "informação", start=1, backwards=True) is None


def test_bounds():
    assert find(WORDS, "saiu", start=7) is None
    assert find([], "a") is None
    assert find(WORDS, "   ") is None
