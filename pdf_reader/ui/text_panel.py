"""The area where the text shows, with the marker and focus mode."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import (
    QColor,
    QMouseEvent,
    QResizeEvent,
    QTextBlockFormat,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtWidgets import QTextEdit

from pdf_reader.ui.theme import DEFAULT_THEME, THEMES, Theme, mix

_EMPTY_PAGE_NOTICE = (
    "This page has no selectable text.\n"
    "It may be an image or a scanned PDF."
)
_MIN_MARGIN = 32
_VERTICAL_MARGIN = 32


@dataclass(frozen=True)
class TextStyle:
    theme: Theme = THEMES[DEFAULT_THEME]
    font: str = "Georgia"
    size: int = 18
    line_spacing: int = 150  # line height, in %
    max_width: int = 780  # 0 = no limit
    highlight_word: bool = True
    focus_mode: bool = True
    visibility: float = 0.3  # of the text outside the current line, in focus mode


class TextPanel(QTextEdit):
    """Shows a page's paragraphs and marks the current word.

    While building the text, the exact position of each word in Qt's
    document is recorded. That way the marker never depends on counting
    characters by hand.
    """

    word_clicked = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setReadOnly(True)
        self.setUndoRedoEnabled(False)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.viewport().setCursor(Qt.CursorShape.PointingHandCursor)

        self._style = TextStyle()
        self._starts: list[int] = []
        self._ends: list[int] = []
        self._index: int | None = None
        self._end: int | None = None  # end of the marked chunk (reading aloud)

    # --- configuration ---
    def configure(self, style: TextStyle) -> None:
        self._style = style
        cursor = QTextCursor(self.document())
        cursor.select(QTextCursor.SelectionType.Document)
        cursor.mergeCharFormat(self._text_format())
        cursor.mergeBlockFormat(self._block_format())
        self._fit_margins()
        self._rehighlight()

    # --- content ---
    def show_paragraphs(self, paragraphs: list[list[str]]) -> None:
        document = self.document()
        document.clear()
        self._starts, self._ends, self._index, self._end = [], [], None, None

        cursor = QTextCursor(document)
        block_format = self._block_format()
        cursor.setBlockFormat(block_format)
        cursor.setCharFormat(self._text_format())

        if not paragraphs:
            cursor.insertText(_EMPTY_PAGE_NOTICE)
        for n, paragraph in enumerate(paragraphs):
            if n:
                cursor.insertBlock(block_format)
            for i, word in enumerate(paragraph):
                if i:
                    cursor.insertText(" ")
                self._starts.append(cursor.position())
                cursor.insertText(word)
                self._ends.append(cursor.position())

        self._fit_margins()
        self.setExtraSelections([])
        self.verticalScrollBar().setValue(0)

    def highlight(self, index: int, end: int | None = None) -> None:
        """Mark word ``index`` or, with ``end``, the whole chunk up to it."""
        if not 0 <= index < len(self._starts):
            self.setExtraSelections([])
            return
        self._index, self._end = index, end
        style, theme = self._style, self._style.theme
        selections = []

        if end is not None and end > index:
            # The sentence being spoken: fully lit, with a soft background.
            chunk = QTextEdit.ExtraSelection()
            chunk.cursor = QTextCursor(self.document())
            chunk.cursor.setPosition(self._starts[index])
            chunk.cursor.setPosition(self._ends[min(end, len(self._ends)) - 1],
                                     QTextCursor.MoveMode.KeepAnchor)
            chunk.format.setBackground(mix(theme.background, theme.highlight, 0.28))
            chunk.format.setForeground(QColor(theme.text_strong))
            self.setExtraSelections([chunk])
            self._center_on(self._starts[index])
            return

        # The current line: lit in focus mode; without focus mode and without
        # the word marker, it gets a subtle background so you don't get lost.
        if style.focus_mode or not style.highlight_word:
            line = QTextEdit.ExtraSelection()
            line.cursor = self._line_cursor(index)
            if style.focus_mode:
                line.format.setForeground(QColor(theme.text_strong))
            else:
                line.format.setBackground(mix(theme.background, theme.text, 0.1))
            selections.append(line)

        if style.highlight_word:
            word = QTextEdit.ExtraSelection()
            word.cursor = QTextCursor(self.document())
            word.cursor.setPosition(self._starts[index])
            word.cursor.setPosition(self._ends[index], QTextCursor.MoveMode.KeepAnchor)
            word.format.setBackground(QColor(theme.highlight))
            word.format.setForeground(QColor(theme.text_on_highlight))
            selections.append(word)

        self.setExtraSelections(selections)
        self._center_on(self._starts[index])

    # --- line navigation ---
    def word_on_adjacent_line(self, index: int, direction: int) -> int | None:
        """First word of the line above (-1) or below (+1); None if there is none."""
        if not 0 <= index < len(self._starts):
            return None
        cursor = QTextCursor(self.document())
        cursor.setPosition(self._starts[index])
        operation = (
            QTextCursor.MoveOperation.Down if direction > 0 else QTextCursor.MoveOperation.Up
        )
        if not cursor.movePosition(operation):
            return None
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        target = bisect_left(self._starts, cursor.position())
        return target if target < len(self._starts) else None

    def line_start(self, index: int) -> int:
        """Index of the first word on the line where ``index`` is."""
        if not 0 <= index < len(self._starts):
            return index
        return bisect_left(self._starts, self._line_cursor(index).selectionStart())

    # --- events ---
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._starts:
            position = self.cursorForPosition(event.position().toPoint()).position()
            index = bisect_right(self._starts, position) - 1
            if index >= 0:
                self.word_clicked.emit(index)
        super().mouseReleaseEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_margins()
        self._rehighlight()

    # --- internal ---
    def _line_cursor(self, index: int) -> QTextCursor:
        cursor = QTextCursor(self.document())
        cursor.setPosition(self._starts[index])
        cursor.movePosition(QTextCursor.MoveOperation.StartOfLine)
        cursor.movePosition(QTextCursor.MoveOperation.EndOfLine, QTextCursor.MoveMode.KeepAnchor)
        return cursor

    def _text_format(self) -> QTextCharFormat:
        style, theme = self._style, self._style.theme
        color = (
            mix(theme.background, theme.text, style.visibility)
            if style.focus_mode
            else QColor(theme.text)
        )
        fmt = QTextCharFormat()
        fmt.setForeground(color)
        # The font goes on the text itself: that way the app's stylesheet
        # (which sets the interface font) doesn't override it.
        fmt.setFontFamilies([style.font])
        fmt.setFontPointSize(style.size)
        return fmt

    def _block_format(self) -> QTextBlockFormat:
        fmt = QTextBlockFormat()
        fmt.setLineHeight(
            self._style.line_spacing,
            QTextBlockFormat.LineHeightTypes.ProportionalHeight.value,
        )
        fmt.setBottomMargin(self._style.size * 0.9)
        return fmt

    def _fit_margins(self) -> None:
        """Center the text column and, in focus mode, leave room above and
        below so the current line always stays in the middle of the screen."""
        max_width = self._style.max_width
        spare = self.viewport().width() - max_width
        side = max(_MIN_MARGIN, spare / 2) if max_width else _MIN_MARGIN
        vertical = self.viewport().height() / 2 if self._style.focus_mode else _VERTICAL_MARGIN

        frame = self.document().rootFrame()
        fmt = frame.frameFormat()
        if (fmt.topMargin(), fmt.leftMargin()) == (vertical, side):
            return
        fmt.setTopMargin(vertical)
        fmt.setBottomMargin(vertical)
        fmt.setLeftMargin(side)
        fmt.setRightMargin(side)
        frame.setFrameFormat(fmt)

    def _center_on(self, position: int) -> None:
        cursor = QTextCursor(self.document())
        cursor.setPosition(position)
        rect = self.cursorRect(cursor)
        bar = self.verticalScrollBar()
        bar.setValue(bar.value() + rect.center().y() - self.viewport().height() // 2)

    def _rehighlight(self) -> None:
        if self._index is not None:
            self.highlight(self._index, self._end)
