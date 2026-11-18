"""Home screen: open a PDF or continue a recent reading."""

from __future__ import annotations

from functools import partial
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QHBoxLayout,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from pdf_reader.core.formatting import time_ago
from pdf_reader.storage import Progress, Repository
from pdf_reader.ui.widgets import Card, button, label

_COLUMN_WIDTH = 760


def _bar(percent: int) -> QProgressBar:
    bar = QProgressBar()
    bar.setRange(0, 100)
    bar.setValue(percent)
    bar.setTextVisible(False)
    return bar


class HomeScreen(QWidget):
    open_file = Signal(str)
    choose_file = Signal()

    def __init__(self, repository: Repository, parent=None) -> None:
        super().__init__(parent)
        self._repository = repository

        # Fixed header.
        open_button = button("Open PDF", primary=True, tip="Ctrl+O")
        open_button.clicked.connect(self.choose_file)
        actions = QHBoxLayout()
        actions.addWidget(open_button)
        actions.addSpacing(12)
        actions.addWidget(label("or drag a file onto this window", "muted"))
        actions.addStretch()

        header = QVBoxLayout()
        header.setSpacing(6)
        header.addWidget(label("PDF Reader", "title"))
        header.addWidget(label("Guided reading, one line at a time.", "muted"))
        header.addSpacing(18)
        header.addLayout(actions)

        # Content that changes: "continue reading" and the list of recent files.
        self._content = QVBoxLayout()
        self._content.setSpacing(8)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 8, 0)
        content_layout.addLayout(self._content)
        content_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)

        column = QWidget()
        column.setMaximumWidth(_COLUMN_WIDTH)
        column_layout = QVBoxLayout(column)
        column_layout.setContentsMargins(24, 56, 24, 24)
        column_layout.addLayout(header)
        column_layout.addSpacing(32)
        column_layout.addWidget(scroll, stretch=1)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addStretch()
        layout.addWidget(column, stretch=100)
        layout.addStretch()

    def refresh(self) -> None:
        """Rebuild the list from what is saved."""
        while self._content.count():
            item = self._content.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        recent = self._repository.recent()
        if not recent:
            empty = label("Nothing read yet. Open a PDF to get started.", "muted")
            empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._content.addSpacing(40)
            self._content.addWidget(empty)
            return

        available = [(i, p) for i, p in recent if Path(p.path).is_file()]
        if available:
            self._content.addWidget(label("CONTINUE READING", "section"))
            self._content.addWidget(self._continue_card(available[0][1]))
            self._content.addSpacing(24)
            recent = [r for r in recent if r[0] != available[0][0]]

        if recent:
            self._content.addWidget(label("RECENT", "section"))
            for document_id, progress in recent:
                self._content.addWidget(self._recent_card(document_id, progress))

    # --- cards ---
    def _continue_card(self, progress: Progress) -> Card:
        card = Card()
        card.clicked.connect(partial(self.open_file.emit, progress.path))

        texts = QVBoxLayout()
        texts.setSpacing(6)
        texts.addWidget(label(progress.name, "highlight"))
        texts.addWidget(label(
            f"Page {progress.page + 1} of {progress.page_count}"
            f"  ·  {progress.percent}%  ·  {time_ago(progress.last_read)}",
            "muted",
        ))
        texts.addSpacing(6)
        texts.addWidget(_bar(progress.percent))

        btn = button("Continue", primary=True)
        btn.clicked.connect(partial(self.open_file.emit, progress.path))

        layout = QHBoxLayout(card)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.addLayout(texts, stretch=1)
        layout.addSpacing(24)
        layout.addWidget(btn)
        return card

    def _recent_card(self, document_id: str, progress: Progress) -> Card:
        exists = Path(progress.path).is_file()
        card = Card(clickable=exists)
        if exists:
            card.clicked.connect(partial(self.open_file.emit, progress.path))

        name = label(progress.name, "name" if exists else "muted")
        folder = label(str(Path(progress.path).parent), "muted")
        folder.setText(folder.fontMetrics().elidedText(
            folder.text(), Qt.TextElideMode.ElideMiddle, 420))
        texts = QVBoxLayout()
        texts.setSpacing(2)
        texts.addWidget(name)
        texts.addWidget(folder)

        if exists:
            info = (f"p. {progress.page + 1}/{progress.page_count}  ·  "
                    f"{time_ago(progress.last_read)}")
        else:
            info = "file not found"
        remove = button("✕", plain=True, tip="Remove from the list (deletes the progress)")
        remove.clicked.connect(partial(self._remove, document_id))

        layout = QHBoxLayout(card)
        layout.setContentsMargins(18, 12, 10, 12)
        layout.addLayout(texts, stretch=1)
        layout.addWidget(label(info, "muted"))
        layout.addWidget(remove)
        return card

    def _remove(self, document_id: str) -> None:
        self._repository.remove(document_id)
        self.refresh()
