from pdf_reader.core.text import (
    ExtractedPage,
    build_paragraphs,
    extract_page,
    join_lines,
    normalize_word,
    stitch_pages,
)


def test_detached_latex_accents():
    assert normalize_word("an´alise") == "análise"
    assert normalize_word("informac¸˜ao") == "informação"
    assert normalize_word("ˆenfase") == "ênfase"
    assert normalize_word("`a") == "à"


def test_dotless_i_with_accent():
    assert normalize_word("cr´ıtica") == "crítica"
    assert normalize_word("ve´ıculo") == "veículo"


def test_ligatures_and_invisible_characters():
    assert normalize_word("ﬁm") == "fim"
    assert normalize_word("eﬃciente") == "efficiente"
    assert normalize_word("pa​lavra") == "palavra"


def test_ordinary_word_is_unchanged():
    assert normalize_word("Olá,") == "Olá,"
    assert normalize_word("guarda-chuva") == "guarda-chuva"


def test_joins_hyphenation_across_lines():
    assert join_lines([["a", "infor-"], ["mação", "chegou"]]) == [
        "a",
        "informação",
        "chegou",
    ]


def test_does_not_join_before_uppercase():
    assert join_lines([["ex-"], ["Presidente"]]) == ["ex-", "Presidente"]


def test_leftover_soft_hyphen_disappears():
    assert join_lines([["pala­"]]) == ["pala"]


def test_build_paragraphs_groups_by_block():
    words = [
        (0, 0, 0, 0, "Primeiro", 0, 0, 0),
        (0, 0, 0, 0, "par´agrafo", 0, 0, 1),
        (0, 0, 0, 0, "Segundo", 1, 0, 0),
        (0, 0, 0, 0, "​", 1, 0, 1),
    ]
    assert build_paragraphs(words) == [["Primeiro", "parágrafo"], ["Segundo"]]


def test_extract_page_keeps_each_word_box():
    words = [
        (10, 10, 40, 20, "Uma", 0, 0, 0),
        (45, 10, 80, 20, "infor-", 0, 0, 1),
        (10, 30, 50, 40, "mação", 0, 1, 0),
        (10, 60, 50, 70, "Fim", 1, 0, 0),
    ]
    page = extract_page(words)
    assert page.paragraphs == [["Uma", "informação"], ["Fim"]]
    assert page.boxes == [
        ((10, 10, 40, 20),),
        ((45, 10, 80, 20), (10, 30, 50, 40)),  # hyphenated: both halves
        ((10, 60, 50, 70),),
    ]


def _page(*paragraphs):
    boxes = [((0, 0, 1, 1),) for p in paragraphs for _ in p]
    return ExtractedPage([list(p) for p in paragraphs], boxes)


def test_stitches_hyphenation_across_pages():
    previous = _page(["fim", "da", "infor-"])
    current = _page(["mação", "segue"], ["Outro"])
    following = _page(["Maiúscula"])
    stitched = stitch_pages(previous, current, following)
    assert stitched.paragraphs == [["segue"], ["Outro"]]
    assert len(stitched.boxes) == 2
    assert stitch_pages(None, previous, current).paragraphs == [["fim", "da", "informação"]]
    assert stitch_pages(current, following, None).paragraphs == [["Maiúscula"]]
