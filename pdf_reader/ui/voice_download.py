"""Download a voice while showing progress (and allowing it to be cancelled)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QEventLoop, QThread, Signal
from PySide6.QtWidgets import QMessageBox, QProgressDialog, QWidget

from pdf_reader.core.voices import DownloadCancelled, Voice, download


class _Download(QThread):
    progress = Signal(int, int)  # downloaded, total (in bytes)

    def __init__(self, voice: Voice, folder: Path) -> None:
        super().__init__()
        self._voice, self._folder = voice, folder
        self.cancelled = False
        self.error = ""

    def run(self) -> None:
        def report(downloaded: int, total: int) -> bool:
            self.progress.emit(downloaded, total)
            return not self.cancelled

        try:
            download(self._voice, self._folder, report)
        except DownloadCancelled:
            pass
        except Exception as error:  # no internet, disk full...
            self.error = str(error) or type(error).__name__


def ensure_voice(parent: QWidget, voice: Voice, folder: Path) -> bool:
    """True if the voice is already (or was just) downloaded."""
    if voice.is_downloaded(folder):
        return True
    answer = QMessageBox.question(
        parent,
        "Download voice",
        f"To listen to the text, the voice {voice.name} needs to be downloaded once "
        f"(about {voice.size_mb} MB).\n\nDownload now?",
    )
    if answer != QMessageBox.StandardButton.Yes:
        return False

    dialog = QProgressDialog(f"Downloading the voice {voice.name}…", "Cancel", 0, 0, parent)
    dialog.setWindowTitle("Download voice")
    dialog.setMinimumDuration(0)
    dialog.setAutoClose(False)
    dialog.setAutoReset(False)

    task = _Download(voice, folder)
    wait = QEventLoop()

    def progress(downloaded: int, total: int) -> None:
        if total > 1_000_000:  # the small config file doesn't count
            dialog.setMaximum(total // 1024)
            dialog.setValue(downloaded // 1024)
            dialog.setLabelText(
                f"Downloading the voice {voice.name}…  "
                f"{downloaded / 1e6:.0f} of {total / 1e6:.0f} MB")

    def cancel() -> None:
        task.cancelled = True

    task.progress.connect(progress)
    task.finished.connect(wait.quit)
    dialog.canceled.connect(cancel)
    dialog.show()
    task.start()
    wait.exec()
    dialog.close()

    if task.error:
        QMessageBox.warning(parent, "Download voice",
                            f"Couldn't download the voice.\n\n{task.error}")
    return voice.is_downloaded(folder)
