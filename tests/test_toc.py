from pdf_reader.core.toc import TocItem, chapter_end, chapter_level, current_item

BOOK = [
    TocItem(1, "Part I", 2),
    TocItem(2, "Ch. 1", 2),
    TocItem(3, "1.1", 4),
    TocItem(2, "Ch. 2", 10),
    TocItem(1, "Part II", 20),
    TocItem(2, "Ch. 3", 20),
]


def test_chapters_sit_below_the_parts():
    assert chapter_level(BOOK) == 2


def test_chapter_end():
    assert chapter_end(BOOK, 5, 40) == 10
    assert chapter_end(BOOK, 0, 40) == 2  # before the first chapter
    assert chapter_end(BOOK, 25, 40) == 40
    assert chapter_end([], 3, 40) == 40


def test_current_item():
    assert current_item(BOOK, 5) == 2
    assert current_item(BOOK, 0) is None
