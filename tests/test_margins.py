from pdf_reader.core.margins import is_page_number, margin_blocks

HEIGHT = 800


def page(number, header="Chapter 2 — The Beginning"):
    return [
        (50, 20, 300, 35, w, 0, 0, i) for i, w in enumerate(header.split())
    ] + [
        (50, 100, 300, 700, "Running", 1, 0, 0),
        (50, 100, 300, 700, f"text{number}", 1, 0, 1),
        (290, 770, 310, 785, str(number), 2, 0, 0),
    ]


def test_page_number():
    assert is_page_number(["12"])
    assert is_page_number(["xiv"])
    assert is_page_number(["Page", "3", "of", "120"])
    assert is_page_number(["Página", "3", "de", "120"])
    assert is_page_number(["—", "7", "—"])
    assert not is_page_number(["Introduction"])
    assert not is_page_number([])


def test_repeated_header_and_number_are_margin():
    neighbors = [(page(n), HEIGHT) for n in (10, 11, 13, 14)]
    assert margin_blocks(page(12), HEIGHT, neighbors) == {0, 2}


def test_header_that_does_not_repeat_stays():
    neighbors = [(page(n, "Some other title"), HEIGHT) for n in (10, 11)]
    assert margin_blocks(page(12), HEIGHT, neighbors) == {2}


def test_block_extending_past_the_band_is_not_margin():
    words = [(50, 20, 300, 400, "Beginning", 0, 0, 0)]
    assert margin_blocks(words, HEIGHT, [(words, HEIGHT)]) == set()
