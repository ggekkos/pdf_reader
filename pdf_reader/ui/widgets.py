"""Small widgets reused by the screens."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QWidget


def label(text: str, role: str | None = None) -> QLabel:
    """QLabel with a visual role from the stylesheet (title, muted, section...)."""
    widget = QLabel(text)
    if role:
        widget.setProperty("role", role)
    return widget


def button(text: str, *, primary: bool = False, plain: bool = False,
           tip: str = "") -> QPushButton:
    """A button that doesn't steal the keyboard: arrows and space control reading."""
    b = QPushButton(text)
    b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    b.setCursor(Qt.CursorShape.PointingHandCursor)
    if primary:
        b.setObjectName("primary")
    if plain:
        b.setProperty("plain", True)
    if tip:
        b.setToolTip(tip)
    return b


def no_focus(widget: QWidget) -> QWidget:
    widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
    return widget


class Card(QFrame):
    """A rounded, clickable frame."""

    clicked = Signal()

    def __init__(self, clickable: bool = True, parent=None) -> None:
        super().__init__(parent)
        self.setProperty("card", True)
        self._clickable = clickable
        if clickable:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if self._clickable and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mouseReleaseEvent(event)
