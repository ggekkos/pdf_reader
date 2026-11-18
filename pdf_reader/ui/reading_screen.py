"""Reading screen: ties together the session, the text panel and the controls."""

from __future__ import annotations

import time
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QSlider,
    QSpinBox,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from pdf_reader.core.document import PdfDocument, file_id
from pdf_reader.core.formatting import duration
from pdf_reader.core.pacing import delay_ms, ends_sentence
from pdf_reader.core.search import find
from pdf_reader.core.session import Session
from pdf_reader.core.speech import Chunk
from pdf_reader.core.toc import TocItem, chapter_end
from pdf_reader.core.voices import voice
from pdf_reader.storage import Progress, Repository, Settings
from pdf_reader.ui.appearance_panel import AppearancePanel
from pdf_reader.ui.narrator import Narrator
from pdf_reader.ui.original_panel import OriginalPanel
from pdf_reader.ui.text_panel import TextPanel, TextStyle
from pdf_reader.ui.theme import WIDTHS, theme
from pdf_reader.ui.toc_panel import TocPanel
from pdf_reader.ui.voice_download import ensure_voice
from pdf_reader.ui.widgets import button, label, no_focus

_PAGE_TURN_PAUSE_MS = 800  # only when the page ends at the end of a sentence
_WPM_MIN, _WPM_MAX = 60, 900
_PAGES_COUNTED = 30  # for the time left; beyond this, estimate from the average
_PAUSE_FACTOR = 1.15  # pauses at punctuation make reading a little slower
_VOICE_RESTART_DELAY_MS = 350  # after moving the position with the voice on


def style_from(settings: Settings) -> TextStyle:
    return TextStyle(
        theme=theme(settings.theme),
        font=settings.font,
        size=settings.font_size,
        line_spacing=settings.line_spacing,
        max_width=WIDTHS.get(settings.width, WIDTHS["medium"])[1],
        highlight_word=settings.highlight_word,
        focus_mode=settings.focus_mode,
        visibility=settings.focus_visibility / 100,
    )


class ReadingScreen(QWidget):
    back = Signal()
    theme_changed = Signal()

    def __init__(self, repository: Repository, settings: Settings, parent=None) -> None:
        super().__init__(parent)
        self._repository = repository
        self._settings = settings
        self._document: PdfDocument | None = None
        self._session: Session | None = None
        self._document_id: str | None = None
        self._toc: list[TocItem] = []
        self._words_after = 0  # from the end of this page to the end of the chapter
        self._reading = False
        self._searching = False

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._auto_step)

        # Reading aloud.
        self._voices_folder = repository.path.parent / "voices"
        self._voice_in_use = ""
        self._voice_moving = False  # the voice itself is changing the position
        self._narrator = Narrator(self)
        self._narrator.chunk_started.connect(self._chunk_spoken)
        self._narrator.state_changed.connect(self._voice_state)
        self._narrator.finished.connect(lambda: self._progress_label.setText("End"))
        self._narrator.error.connect(self._voice_error)
        self._voice_timer = QTimer(self)
        self._voice_timer.setSingleShot(True)
        self._voice_timer.setInterval(_VOICE_RESTART_DELAY_MS)
        self._voice_timer.timeout.connect(self._restart_voice)

        self._build_interface()
        self._create_shortcuts()
        self.apply_style()
        self._update_controls()

    # ------------------------------------------------------------------
    # Document
    # ------------------------------------------------------------------
    def open(self, path: Path) -> bool:
        try:
            document = PdfDocument(path, skip_margins=self._settings.skip_margins)
            document_id = file_id(path)
            toc = document.toc()
        except Exception as error:  # PyMuPDF raises assorted types
            QMessageBox.warning(self, "Error", f"Couldn't open the PDF.\n\n{error}")
            return False

        self.close_document()
        progress = self._repository.progress(document_id)
        self._document = document
        self._document_id = document_id
        self._toc = toc
        self._toc_panel.show_items(toc)
        self._session = Session(document, progress.page, progress.index)

        metrics = self._title.fontMetrics()
        self._title.setText(metrics.elidedText(path.stem, Qt.TextElideMode.ElideMiddle, 420))
        self._title.setToolTip(str(path))
        self._show_page()
        return True

    def shutdown(self) -> None:
        """When closing the app: save everything and turn the voice off."""
        self.close_document()
        self._narrator.shutdown()

    def close_document(self) -> None:
        self._pause()
        self._narrator.stop()
        if self._document is not None:
            self._save_progress()
            self._document.close()
        self._original.clear()
        self._toc_panel.show_items([])
        self._close_search()
        self._toc = []
        self._document = self._session = self._document_id = None

    def _save_progress(self) -> None:
        if not (self._session and self._document_id and self._document):
            return
        self._repository.save_progress(
            self._document_id,
            Progress(
                page=self._session.page,
                index=self._session.index,
                name=self._document.path.stem,
                path=str(self._document.path),
                page_count=self._session.page_count,
                last_read=time.time(),
            ),
        )

    # ------------------------------------------------------------------
    # Display
    # ------------------------------------------------------------------
    def apply_style(self) -> None:
        style = style_from(self._settings)
        self._text_panel.configure(style)
        self._original.configure(style.theme)
        document = self._document
        if document and document.skip_margins != self._settings.skip_margins:
            document.skip_margins = self._settings.skip_margins
            self._session.reload()
            self._show_page()
        self._narrator.speed = self._settings.voice_speed / 100
        if self._narrator.active and self._settings.voice != self._voice_in_use:
            self._toggle_voice()  # stops the old voice...
            self._toggle_voice()  # ...and starts the new one (downloading it, if needed)

    def _show_page(self) -> None:
        """Show the session's current page, with the current word already highlighted."""
        if self._session is None:
            return
        self._text_panel.show_paragraphs(self._session.paragraphs)
        self._original.show_page(self._document, self._session.page)
        self._toc_panel.mark(self._session.page)
        self._count_remaining()
        self._highlight()
        self._update_controls()
        self._save_progress()

    def _move_to(self, index: int) -> None:
        if self._session is None:
            return
        self._session.go_to_word(index)
        self._highlight()
        self._update_progress()
        if self._reading:
            self._schedule_next()

    def _go_to(self, page: int, index: int = 0) -> None:
        if self._session is None:
            return
        if self._session.go_to_page(page):
            self._show_page()
        self._move_to(index)

    def _highlight(self) -> None:
        """Mark the current word in the text and in the original PDF."""
        self._text_panel.highlight(self._session.index)
        self._original.highlight(self._session.index)
        if self._narrator.active and not self._voice_moving:
            self._voice_timer.start()  # you moved the position: the voice restarts from there

    def _update_controls(self) -> None:
        session = self._session
        self._read_button.setEnabled(session is not None)
        self._read_button.setText("❚❚  Pause" if self._reading else "▶  Read")
        self._listen_button.setEnabled(session is not None)
        self._listen_button.setText("■  Stop voice" if self._narrator.active else "🔊  Listen")
        self._previous_button.setEnabled(bool(session and session.has_previous_page))
        self._next_button.setEnabled(bool(session and session.has_next_page))

        self._page_spin.blockSignals(True)
        if session:
            self._page_spin.setRange(1, max(session.page_count, 1))
            self._page_spin.setValue(session.page + 1)
            self._total_label.setText(f"of {session.page_count}")
        self._page_spin.blockSignals(False)
        self._update_progress()

    def _update_progress(self) -> None:
        session = self._session
        if not session or not session.page_count:
            self._remaining_label.setText("")
            return
        within_page = session.index / max(len(session.words), 1)
        fraction = (session.page + within_page) / session.page_count
        self._progress_bar.setValue(round(fraction * 1000))
        self._progress_label.setText(f"{fraction:.0%}")

        remaining = max(len(session.words) - session.index - 1, 0) + self._words_after
        if self._narrator.active and self._narrator.words_per_minute:
            minutes = remaining / self._narrator.words_per_minute  # the voice's measured pace
        else:
            minutes = remaining / max(self._settings.words_per_minute, 1) * _PAUSE_FACTOR
        target = "chapter" if self._toc else "document"
        approx = "" if minutes < 1 else "~"
        self._remaining_label.setText(f"{approx}{duration(minutes)} left in {target}")

    def _count_remaining(self) -> None:
        """Count the words on the next pages up to the end of the chapter.

        The first ones are actually counted; in a very long chapter, the
        rest is estimated from the average, so as not to read the whole book at once.
        """
        session, document = self._session, self._document
        end = chapter_end(self._toc, session.page, session.page_count)
        pages = range(session.page + 1, end)
        counted = pages[:_PAGES_COUNTED]
        total = sum(document.count_words(p) for p in counted)
        if len(pages) > len(counted):
            average = total / len(counted) if counted else len(session.words)
            total += round(average * (len(pages) - len(counted)))
        self._words_after = total

    # ------------------------------------------------------------------
    # Automatic reading
    # ------------------------------------------------------------------
    def _space(self) -> None:
        """Space pauses whatever is playing; when stopped, it starts the marker."""
        if self._narrator.active:
            self._narrator.stop()
        else:
            self._toggle_reading()

    def _toggle_reading(self) -> None:
        if self._reading:
            self._pause()
        elif self._session is not None:
            self._narrator.stop()
            self._reading = True
            self._schedule_next()
            self._update_controls()

    def _pause(self) -> None:
        self._timer.stop()
        self._reading = False
        self._update_controls()

    def _schedule_next(self) -> None:
        word = self._session.current_word if self._session else ""
        self._timer.start(delay_ms(word, self._settings.words_per_minute))

    def _auto_step(self) -> None:
        session = self._session
        if session is None or not self._reading:
            return
        if session.advance():
            self._highlight()
            self._update_progress()
            self._schedule_next()
            return
        last = session.current_word
        if session.next_page():
            self._show_page()
            # Sentence cut by the page turn: keep going without an extra pause.
            if ends_sentence(last) or not last:
                self._timer.start(_PAGE_TURN_PAUSE_MS)
            else:
                self._schedule_next()
        else:
            self._pause()
            self._progress_label.setText("End")

    # ------------------------------------------------------------------
    # Reading aloud
    # ------------------------------------------------------------------
    def _toggle_voice(self) -> None:
        if self._narrator.active:
            self._narrator.stop()
            return
        if self._session is None:
            return
        chosen = voice(self._settings.voice)
        downloaded = ensure_voice(self, chosen, self._voices_folder)
        self._appearance_panel.refresh_voices()
        if downloaded and self._session is not None:
            self._pause()
            self._speak_from_here()

    def _speak_from_here(self) -> None:
        chosen = voice(self._settings.voice)
        self._voice_in_use = chosen.id
        self._narrator.speed = self._settings.voice_speed / 100
        self._narrator.speak(self._document, self._session.page, self._session.index,
                             chosen, self._voices_folder)

    def _restart_voice(self) -> None:
        if self._narrator.active and self._session is not None:
            self._speak_from_here()

    def _chunk_spoken(self, chunk: Chunk) -> None:
        """The voice started a sentence: the screen follows (turning the page, if needed)."""
        session = self._session
        if session is None:
            return
        self._voice_moving = True
        try:
            if chunk.page != session.page:
                session.go_to_page(chunk.page)
                self._show_page()
            session.go_to_word(chunk.start)
            self._text_panel.highlight(chunk.start, chunk.end)
            self._original.highlight(chunk.start, chunk.end)
            self._update_progress()
            self._save_progress()
        finally:
            self._voice_moving = False

    def _voice_state(self, speaking: bool) -> None:
        if not speaking:
            self._voice_timer.stop()
            if self._session is not None:
                self._highlight()  # back to marking just the word
        self._update_controls()

    def _voice_error(self, message: str) -> None:
        QMessageBox.warning(self, "Read aloud",
                            f"Couldn't use the voice.\n\n{message}")

    # ------------------------------------------------------------------
    # Manual navigation
    # ------------------------------------------------------------------
    def _next_page(self) -> None:
        if self._session and self._session.next_page():
            self._show_page()

    def _previous_page(self, to_end: bool = False) -> None:
        if self._session and self._session.previous_page(to_end):
            self._show_page()
            if to_end:
                self._move_to(self._text_panel.line_start(self._session.index))

    def _go_to_typed_page(self) -> None:
        if self._session and self._session.go_to_page(self._page_spin.value() - 1):
            self._show_page()
        self.setFocus()

    def _next_word(self) -> None:
        if self._session is None:
            return
        if self._session.advance():
            self._move_to(self._session.index)
        else:
            self._next_page()

    def _previous_word(self) -> None:
        if self._session is None:
            return
        if self._session.step_back():
            self._move_to(self._session.index)
        else:
            self._previous_page(to_end=True)

    def _change_line(self, direction: int) -> None:
        if self._session is None:
            return
        target = self._text_panel.word_on_adjacent_line(self._session.index, direction)
        if target is not None:
            self._move_to(target)
        elif direction > 0:
            self._next_page()
        else:
            self._previous_page(to_end=True)

    def _escape(self) -> None:
        """Esc closes whatever is open, one at a time; at the end, goes back home."""
        if self._search_bar.isVisible():
            self._close_search()
        elif self._appearance_panel.isVisible():
            self._appearance_button.setChecked(False)
        elif self._toc_panel.isVisible():
            self._toc_button.setChecked(False)
        else:
            self.back.emit()

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    def _open_search(self) -> None:
        if self._session is None:
            return
        self._search_bar.setVisible(True)
        self._search_field.setFocus()
        self._search_field.selectAll()

    def _close_search(self) -> None:
        self._search_bar.setVisible(False)
        self._search_label.setText("")
        self.setFocus()

    def _search(self, backwards: bool = False) -> None:
        """Search from the current word, page by page, wrapping around the PDF."""
        session, document = self._session, self._document
        query = self._search_field.text().strip()
        if self._searching or session is None or not query or not session.page_count:
            return
        if not self._search_bar.isVisible():
            self._open_search()

        self._searching = True
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            total, current = session.page_count, session.page
            for step in range(total + 1):
                page = (current - step if backwards else current + step) % total
                if step == 0:
                    start = session.index if backwards else session.index + 1
                elif step == total:  # wrapped around: the rest of the current page
                    start = None if backwards else 0
                else:
                    start = None
                words = [w for paragraph in document.paragraphs(page) for w in paragraph]
                found = find(words, query, start, backwards)
                if found is not None:
                    wrapped = (page > current) if backwards else (page < current)
                    self._search_label.setText(
                        f"Page {page + 1}" + ("  (wrapped around)" if wrapped else ""))
                    self._go_to(page, found)
                    return
                if step % 25 == 24:  # big books: show that it's working
                    self._search_label.setText(f"Searching… page {page + 1}")
                    QApplication.processEvents()
                    if self._document is not document:  # closed midway
                        return
            self._search_label.setText("Not found")
        finally:
            QApplication.restoreOverrideCursor()
            self._searching = False

    # ------------------------------------------------------------------
    # Preferences
    # ------------------------------------------------------------------
    def _show_original(self, visible: bool) -> None:
        self._settings.show_original = visible
        self._original.setVisible(visible)
        if visible:
            self._apply_split()

    def _apply_split(self) -> None:
        text = min(max(self._settings.original_split, 20), 80)
        self._splitter.setSizes([text * 100, (100 - text) * 100])

    def _split_moved(self) -> None:
        text, original = self._splitter.sizes()
        if text + original:
            self._settings.original_split = round(100 * text / (text + original))

    def _zoom(self, steps: int) -> None:
        if not self._original.isVisible():
            return
        if steps:
            self._original.zoom_in(steps)
        else:
            self._original.set_zoom(1.0)

    def _zoom_changed(self, zoom: float) -> None:
        self._settings.original_zoom = round(zoom * 100)

    def _change_speed(self, wpm: int) -> None:
        self._settings.words_per_minute = wpm
        self._speed_label.setText(f"{wpm} wpm")
        if hasattr(self, "_remaining_label"):
            self._update_progress()

    # ------------------------------------------------------------------
    # Layout
    # ------------------------------------------------------------------
    def _build_interface(self) -> None:
        # Top bar: navigation, title and reading.
        home_button = button("←  Home", plain=True, tip="Back to home (Esc)")
        home_button.clicked.connect(self.back)
        self._toc_button = button("☰", plain=True, tip="Table of contents (S)")
        self._toc_button.setCheckable(True)
        self._toc_button.setStyleSheet("font-size: 13pt;")
        search_button = button("⌕", plain=True, tip="Search the PDF (Ctrl+F)")
        search_button.setStyleSheet("font-size: 14pt;")
        search_button.clicked.connect(self._open_search)
        self._title = label("", "name")

        self._listen_button = button("🔊  Listen", tip="Read aloud / stop (V)")
        self._listen_button.setMinimumWidth(120)
        self._listen_button.clicked.connect(self._toggle_voice)

        self._read_button = button("▶  Read", primary=True, tip="Read / pause (Space)")
        self._read_button.setMinimumWidth(110)
        self._read_button.clicked.connect(self._toggle_reading)

        speed_slider = no_focus(QSlider(Qt.Orientation.Horizontal))
        speed_slider.setRange(_WPM_MIN, _WPM_MAX)
        speed_slider.setSingleStep(10)
        speed_slider.setPageStep(50)
        speed_slider.setFixedWidth(150)
        speed_slider.setToolTip("Speed (words per minute)")
        self._speed_label = label("", "muted")
        self._speed_label.setMinimumWidth(56)
        speed_slider.valueChanged.connect(self._change_speed)
        speed_slider.setValue(self._settings.words_per_minute)
        self._change_speed(speed_slider.value())

        self._original_button = button("PDF", plain=True,
                                       tip="Show the original PDF alongside (P)")
        self._original_button.setCheckable(True)
        self._original_button.setStyleSheet("font-weight: 600;")

        self._appearance_button = button("Aa", plain=True, tip="Appearance and options")
        self._appearance_button.setCheckable(True)
        self._appearance_button.setStyleSheet("font-family: Georgia; font-size: 13pt;")

        bar = QFrame()
        bar.setObjectName("topBar")
        top = QHBoxLayout(bar)
        top.setContentsMargins(12, 8, 12, 8)
        top.addWidget(home_button)
        top.addWidget(self._toc_button)
        top.addWidget(search_button)
        top.addSpacing(8)
        top.addWidget(self._title)
        top.addStretch()
        top.addWidget(self._speed_label)
        top.addWidget(speed_slider)
        top.addSpacing(12)
        top.addWidget(self._listen_button)
        top.addWidget(self._read_button)
        top.addSpacing(4)
        top.addWidget(self._original_button)
        top.addWidget(self._appearance_button)

        # Search bar (hidden until Ctrl+F).
        self._search_field = QLineEdit()
        self._search_field.setPlaceholderText(
            "Search the PDF…  (Enter: next, Shift+Enter: previous)")
        self._search_field.setClearButtonEnabled(True)
        self._search_field.setMaximumWidth(460)
        self._search_field.returnPressed.connect(self._search)
        previous_match = QShortcut(QKeySequence("Shift+Return"), self._search_field)
        previous_match.setContext(Qt.ShortcutContext.WidgetShortcut)
        previous_match.activated.connect(lambda: self._search(backwards=True))
        previous_match_button = button("↑", plain=True, tip="Previous match (Shift+F3)")
        previous_match_button.clicked.connect(lambda: self._search(backwards=True))
        next_match_button = button("↓", plain=True, tip="Next match (F3)")
        next_match_button.clicked.connect(lambda: self._search())
        close_search_button = button("✕", plain=True, tip="Close search (Esc)")
        close_search_button.clicked.connect(self._close_search)
        self._search_label = label("", "muted")

        self._search_bar = QFrame()
        self._search_bar.setObjectName("searchBar")
        search_row = QHBoxLayout(self._search_bar)
        search_row.setContentsMargins(12, 6, 12, 6)
        search_row.addWidget(self._search_field, stretch=1)
        search_row.addWidget(previous_match_button)
        search_row.addWidget(next_match_button)
        search_row.addSpacing(8)
        search_row.addWidget(self._search_label)
        search_row.addStretch()
        search_row.addWidget(close_search_button)
        self._search_bar.setVisible(False)

        # Center: contents, text, original PDF and appearance (the optional ones hidden).
        self._toc_panel = TocPanel()
        self._toc_panel.setVisible(False)
        self._toc_panel.page_chosen.connect(self._go_to)
        self._toc_button.toggled.connect(self._toc_panel.setVisible)

        self._text_panel = TextPanel()
        self._text_panel.word_clicked.connect(self._move_to)
        self._original = OriginalPanel()
        self._original.word_clicked.connect(self._move_to)
        self._original.setVisible(False)
        self._original.set_zoom(self._settings.original_zoom / 100)
        self._original.zoom_changed.connect(self._zoom_changed)

        self._splitter = QSplitter(Qt.Orientation.Horizontal)
        self._splitter.setChildrenCollapsible(False)
        self._splitter.setHandleWidth(3)
        self._splitter.addWidget(self._text_panel)
        self._splitter.addWidget(self._original)
        self._splitter.splitterMoved.connect(self._split_moved)
        self._original_button.toggled.connect(self._show_original)
        self._original_button.setChecked(self._settings.show_original)

        self._appearance_panel = AppearancePanel(self._settings, self._voices_folder)
        self._appearance_panel.setVisible(False)
        self._appearance_panel.changed.connect(self.apply_style)
        self._appearance_panel.theme_changed.connect(self.theme_changed)
        self._appearance_button.toggled.connect(self._appearance_panel.setVisible)

        center = QHBoxLayout()
        center.setContentsMargins(0, 0, 0, 0)
        center.setSpacing(0)
        center.addWidget(self._toc_panel)
        center.addWidget(self._splitter, stretch=1)
        center.addWidget(self._appearance_panel)

        # Footer: pages, time left and progress.
        self._previous_button = button("‹", plain=True, tip="Previous page (PgUp)")
        self._previous_button.clicked.connect(lambda: self._previous_page())
        self._next_button = button("›", plain=True, tip="Next page (PgDn)")
        self._next_button.clicked.connect(self._next_page)
        for b in (self._previous_button, self._next_button):
            b.setStyleSheet("font-size: 16pt; padding: 0 10px;")
        self._page_spin = QSpinBox()
        self._page_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_spin.setMinimumWidth(56)
        self._page_spin.editingFinished.connect(self._go_to_typed_page)
        self._total_label = label("", "muted")

        self._remaining_label = label("", "muted")
        self._remaining_label.setToolTip("Estimate at the current speed")
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 1000)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setFixedWidth(220)
        self._progress_label = label("", "muted")
        self._progress_label.setMinimumWidth(36)

        footer = QFrame()
        footer.setObjectName("footer")
        bottom = QHBoxLayout(footer)
        bottom.setContentsMargins(12, 6, 16, 6)
        bottom.addWidget(self._previous_button)
        bottom.addWidget(label("Page", "muted"))
        bottom.addWidget(self._page_spin)
        bottom.addWidget(self._total_label)
        bottom.addWidget(self._next_button)
        bottom.addStretch()
        bottom.addWidget(self._remaining_label)
        bottom.addSpacing(16)
        bottom.addWidget(self._progress_bar)
        bottom.addWidget(self._progress_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(bar)
        layout.addWidget(self._search_bar)
        layout.addLayout(center, stretch=1)
        layout.addWidget(footer)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def _create_shortcuts(self) -> None:
        # Shortcuts tied to this screen: they only work while it is visible.
        # While typing in the search field, the field gets the letters and space.
        shortcuts = {
            Qt.Key.Key_Space: self._space,
            Qt.Key.Key_V: self._toggle_voice,
            Qt.Key.Key_Down: lambda: self._change_line(+1),
            Qt.Key.Key_Up: lambda: self._change_line(-1),
            Qt.Key.Key_Right: self._next_word,
            Qt.Key.Key_Left: self._previous_word,
            Qt.Key.Key_PageDown: self._next_page,
            Qt.Key.Key_PageUp: lambda: self._previous_page(),
            Qt.Key.Key_P: self._original_button.toggle,
            Qt.Key.Key_S: self._toc_button.toggle,
            Qt.Key.Key_Escape: self._escape,
            QKeySequence.StandardKey.Find: self._open_search,
            QKeySequence.StandardKey.FindNext: lambda: self._search(),
            QKeySequence.StandardKey.FindPrevious: lambda: self._search(backwards=True),
            "Ctrl+=": lambda: self._zoom(+1),
            "Ctrl++": lambda: self._zoom(+1),
            "Ctrl+-": lambda: self._zoom(-1),
            "Ctrl+0": lambda: self._zoom(0),
        }
        for key, action in shortcuts.items():
            QShortcut(QKeySequence(key), self).activated.connect(action)
