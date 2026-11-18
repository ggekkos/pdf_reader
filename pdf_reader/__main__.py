"""Entry point: ``python -m pdf_reader [file.pdf]``."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QStandardPaths
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from pdf_reader.storage import Repository, migrate_legacy_folder
from pdf_reader.ui.main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    app.setApplicationName("PDFReader")
    app.setWindowIcon(QIcon(str(Path(__file__).parent / "assets" / "icon.png")))

    data_folder = Path(
        QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    )
    migrate_legacy_folder(data_folder)
    window = MainWindow(Repository(data_folder / "data.json"))
    window.show()

    # A PDF passed on the command line opens right away; otherwise, the home screen shows.
    if len(argv) > 1 and Path(argv[1]).is_file():
        window.open(Path(argv[1]))

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
