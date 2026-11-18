from pdf_reader.core.session import Session


class FakeSource:
    def __init__(self, pages):
        self._pages = pages

    @property
    def page_count(self):
        return len(self._pages)

    def paragraphs(self, page):
        return self._pages[page]


PAGES = [[["a", "b"], ["c"]], [], [["d", "e"]]]


def test_advances_to_the_end_of_the_page():
    session = Session(FakeSource(PAGES))
    assert session.current_word == "a"
    assert session.advance() and session.advance()
    assert session.current_word == "c"
    assert not session.advance()


def test_invalid_progress_is_corrected():
    session = Session(FakeSource(PAGES), page=99, index=99)
    assert session.page == 2
    assert session.current_word == "e"


def test_empty_page_does_not_break():
    session = Session(FakeSource(PAGES), page=1)
    assert session.current_word == ""
    assert not session.advance()
    assert session.next_page()
    assert session.current_word == "d"


def test_previous_page_can_go_to_the_end():
    session = Session(FakeSource(PAGES), page=1)
    assert session.previous_page(to_end=True)
    assert session.current_word == "c"
    assert not session.previous_page()


def test_document_without_pages():
    session = Session(FakeSource([]))
    assert session.current_word == ""
    assert not session.next_page()


def test_reload_keeps_the_position():
    pages = [[["a", "b", "c"]]]
    session = Session(FakeSource(pages), index=2)
    pages[0] = [["a", "b"]]
    session.reload()
    assert session.current_word == "b"
