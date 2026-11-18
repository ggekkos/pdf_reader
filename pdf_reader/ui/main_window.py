"""Main window: switches between the home screen and the reading screen."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QByteArray
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QFileDialog, QMainWindow, QStackedWidget

from pdf_reader.storage import Repository
from pdf_reader.ui.home_screen import HomeScreen
from pdf_reader.ui.reading_screen import ReadingScreen
from pdf_reader.ui.theme import build_stylesheet, theme

APP_TITLE = "PDF Reader"


def _dragged_pdf(event: QDragEnterEvent | QDropEvent) -> Path | None:
    for url in event.mimeData().urls():
        path = Path(url.toLocalFile())
        if path.suffix.lower() == ".pdf":
            return path
    return None


class MainWindow(QMainWindow):
    def __init__(self, repository: Repository) -> None:
        super().__init__()
        self._repository = repository
        self._settings = repository.settings()

        self._home = HomeScreen(repository)
        self._reading = ReadingScreen(repository, self._settings)
        self._home.open_file.connect(lambda path: self.open(Path(path)))
        self._home.choose_file.connect(self.choose_file)
        self._reading.back.connect(self.show_home)
        self._reading.theme_changed.connect(self._apply_theme)

        self._stack = QStackedWidget()
        self._stack.setObjectName("root")  # gets the theme's background color
        self._stack.addWidget(self._home)
        self._stack.addWidget(self._reading)
        self.setCentralWidget(self._stack)

        self.setWindowTitle(APP_TITLE)
        if not (self._settings.geometry and self.restoreGeometry(
                QByteArray.fromBase64(self._settings.geometry.encode()))):
            self.resize(1100, 780)
        self.setAcceptDrops(True)
        QShortcut(QKeySequence.StandardKey.Open, self).activated.connect(self.choose_file)

        self._apply_theme()
        self.show_home()

    def show_home(self) -> None:
        self._reading.close_document()
        self._home.refresh()
        self._stack.setCurrentWidget(self._home)
        self.setWindowTitle(APP_TITLE)

    def open(self, path: Path) -> bool:
        if not self._reading.open(path):
            return False
        self._stack.setCurrentWidget(self._reading)
        self._reading.setFocus()
        self.setWindowTitle(f"{path.stem} — {APP_TITLE}")
        return True

    def choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Open PDF", self._start_folder(), "PDF files (*.pdf)"
        )
        if path:
            self.open(Path(path))

    def _start_folder(self) -> str:
        recent = self._repository.recent(limit=1)
        return str(Path(recent[0][1].path).parent) if recent else ""

    def _apply_theme(self) -> None:
        QApplication.instance().setStyleSheet(build_stylesheet(theme(self._settings.theme)))

    # --- drag and drop ---
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if _dragged_pdf(event):
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:
        path = _dragged_pdf(event)
        if path:
            self.open(path)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._reading.shutdown()
        self._settings.geometry = bytes(self.saveGeometry().toBase64()).decode()
        self._repository.save_settings(self._settings)
        super().closeEvent(event)
