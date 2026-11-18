"""Panel with the PDF's original page, to check the extracted text."""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QImage,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPixmap,
    QResizeEvent,
    QWheelEvent,
)
from PySide6.QtWidgets import QScrollArea, QWidget

from pdf_reader.core.document import PdfDocument
from pdf_reader.core.text import Box
from pdf_reader.ui.theme import DEFAULT_THEME, THEMES, Theme

_MARGIN = 16  # around the page, in pixels
_CLICK_TOLERANCE = 3.0  # click slack around a word, in points
_RENDER_DELAY_MS = 150  # wait for resizing to stop before redrawing
ZOOM_MIN, ZOOM_MAX = 0.5, 4.0  # 1.0 = page fits the panel width
_ZOOM_STEP = 1.15
_MAX_WIDTH_PX = 4500  # beyond this the image is only stretched (saves memory)


class _Sheet(QWidget):
    """Draws the (already rendered) page and the marker over the current word."""

    clicked = Signal(QPointF)  # position in PDF points

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.theme: Theme = THEMES[DEFAULT_THEME]
        self.image: QPixmap | None = None
        self.size_pt = (0.0, 0.0)  # page width and height, in points
        self.marked: tuple[Box, ...] = ()
        self.visible_width = 1  # panel width, without the scroll bar
        self.zoom = 1.0

    # --- geometry ---
    def page_area(self) -> QRectF:
        width_pt, height_pt = self.size_pt
        width = max((self.visible_width - 2 * _MARGIN) * self.zoom, 1)
        height = width * height_pt / width_pt if width_pt else 0
        x = max(_MARGIN, (self.width() - width) / 2)  # centered when smaller
        return QRectF(x, _MARGIN, width, height)

    def to_screen(self, box: Box) -> QRectF:
        area = self.page_area()
        factor = area.width() / self.size_pt[0] if self.size_pt[0] else 0
        x0, y0, x1, y1 = box
        return QRectF(area.x() + x0 * factor, area.y() + y0 * factor,
                      (x1 - x0) * factor, (y1 - y0) * factor)

    # --- events ---
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(self.theme.surface))
        if self.image is None:
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        area = self.page_area()
        painter.setPen(QColor(self.theme.border))
        painter.drawRect(area.adjusted(-1, -1, 0, 0))
        painter.drawPixmap(area, self.image, QRectF(self.image.rect()))

        # "Multiply" works like a highlighter pen: the PDF's text stays readable.
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Multiply)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(self.theme.highlight))
        for box in self.marked:
            painter.drawRoundedRect(self.to_screen(box).adjusted(-2, -1, 2, 1), 2, 2)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        area = self.page_area()
        if event.button() == Qt.MouseButton.LeftButton and area.width() and self.size_pt[0]:
            factor = self.size_pt[0] / area.width()
            point = event.position() - area.topLeft()
            self.clicked.emit(QPointF(point.x() * factor, point.y() * factor))
        super().mouseReleaseEvent(event)


class OriginalPanel(QScrollArea):
    """Shows the PDF's current page as it really is, fitted to the width.

    Useful to check the text when extraction goes wrong (accents, columns,
    formulas, scanned PDFs...). The word being read is marked here too, and
    clicking a word moves the reading there.
    """

    word_clicked = Signal(int)
    zoom_changed = Signal(float)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("originalPanel")
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setWidgetResizable(False)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setMinimumWidth(220)

        self._sheet = _Sheet()
        self._sheet.clicked.connect(self._click)
        self.setWidget(self._sheet)

        self._document: PdfDocument | None = None
        self._page = 0
        self._boxes: list[tuple[Box, ...]] = []
        self._index: int | None = None
        self._rendered: tuple[int, int] | None = None  # (page, width in px)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._render)

    # --- configuration ---
    def configure(self, theme: Theme) -> None:
        self._sheet.theme = theme
        self._sheet.update()

    @property
    def zoom(self) -> float:
        return self._sheet.zoom

    def set_zoom(self, zoom: float, anchor: QPointF | None = None) -> None:
        """Change the zoom keeping the ``anchor`` point (in the panel) or the center still."""
        zoom = min(max(zoom, ZOOM_MIN), ZOOM_MAX)
        if abs(zoom - self._sheet.zoom) < 1e-3:
            return
        if anchor is None:
            anchor = QPointF(self.viewport().width() / 2, self.viewport().height() / 2)
        horizontal, vertical = self.horizontalScrollBar(), self.verticalScrollBar()
        before = self._sheet.page_area()
        x = (horizontal.value() + anchor.x() - before.x()) / before.width()
        y = (vertical.value() + anchor.y() - before.y()) / max(before.height(), 1)

        self._sheet.zoom = zoom
        self._fit_size()
        after = self._sheet.page_area()
        horizontal.setValue(round(after.x() + x * after.width() - anchor.x()))
        vertical.setValue(round(after.y() + y * after.height() - anchor.y()))
        self._sheet.update()
        self._timer.start(_RENDER_DELAY_MS)
        self.zoom_changed.emit(zoom)

    def zoom_in(self, steps: float = 1) -> None:
        self.set_zoom(self._sheet.zoom * _ZOOM_STEP ** steps)

    # --- content ---
    def show_page(self, document: PdfDocument, page: int) -> None:
        self._document, self._page = document, page
        self._boxes = document.boxes(page)
        self._sheet.size_pt = document.page_size(page)
        self._sheet.marked = ()
        self._index = None
        self._fit_size()
        self._render()
        self.verticalScrollBar().setValue(0)

    def clear(self) -> None:
        self._document, self._boxes, self._index = None, [], None
        self._rendered = None
        self._sheet.image = None
        self._sheet.marked = ()
        self._sheet.update()

    def highlight(self, index: int, end: int | None = None) -> None:
        """Mark word ``index`` or, with ``end``, the whole chunk up to it."""
        self._index = index
        end = index + 1 if end is None else end
        self._sheet.marked = tuple(
            box for boxes in self._boxes[max(index, 0):end] for box in boxes)
        self._sheet.update()
        self._scroll_to_marked()

    # --- events ---
    def wheelEvent(self, event: QWheelEvent) -> None:
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            steps = event.angleDelta().y() / 120
            if steps:
                self.set_zoom(self._sheet.zoom * _ZOOM_STEP ** steps, event.position())
            event.accept()
            return
        super().wheelEvent(event)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._fit_size()
        self._timer.start(_RENDER_DELAY_MS)  # meanwhile, the old image is stretched

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._fit_size()
        self._render()
        if self._index is not None:
            QTimer.singleShot(0, self._scroll_to_marked)

    # --- internal ---
    def _fit_size(self) -> None:
        # The reference width ignores the vertical scroll bar, which comes
        # and goes with the height: that way the size doesn't keep flickering.
        bar = self.verticalScrollBar()
        visible = self.viewport().width() + (bar.width() if bar.isVisible() else 0)
        self._sheet.visible_width = max(visible - bar.sizeHint().width(), 1)
        area = self._sheet.page_area()
        width = max(round(area.width() + 2 * _MARGIN), self.viewport().width())
        height = max(round(area.height() + 2 * _MARGIN), self.viewport().height())
        self._sheet.resize(width, height)

    def _render(self) -> None:
        if self._document is None or not self.isVisible():
            return
        area = self._sheet.page_area()
        ratio = self.devicePixelRatioF()
        width_px = min(round(area.width() * ratio), _MAX_WIDTH_PX)
        if self._rendered == (self._page, width_px) or not self._sheet.size_pt[0]:
            return
        scale = width_px / self._sheet.size_pt[0]
        width, height, stride, pixels = self._document.render(self._page, scale)
        image = QImage(pixels, width, height, stride, QImage.Format.Format_RGB888).copy()
        pixmap = QPixmap.fromImage(image)
        pixmap.setDevicePixelRatio(ratio)
        self._sheet.image = pixmap
        self._rendered = (self._page, width_px)
        self._sheet.update()

    def _scroll_to_marked(self) -> None:
        if not self._sheet.marked:
            return
        box = self._sheet.to_screen(self._sheet.marked[0])
        # Only scrolls when the word leaves the middle third of the view.
        self.ensureVisible(round(box.center().x()), round(box.center().y()),
                           self.viewport().width() // 4, self.viewport().height() // 3)

    def _click(self, point: QPointF) -> None:
        x, y = point.x(), point.y()
        best, smallest_distance = None, _CLICK_TOLERANCE
        for index, boxes in enumerate(self._boxes):
            for x0, y0, x1, y1 in boxes:
                dx = max(x0 - x, 0.0, x - x1)
                dy = max(y0 - y, 0.0, y - y1)
                distance = max(dx, dy)
                if distance <= smallest_distance:
                    best, smallest_distance = index, distance
        if best is not None:
            self.word_clicked.emit(best)
