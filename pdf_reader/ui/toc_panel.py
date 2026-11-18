"""Side panel with the PDF's table of contents (its bookmarks)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QTreeWidget, QTreeWidgetItem, QVBoxLayout

from pdf_reader.core.toc import TocItem, current_item
from pdf_reader.ui.widgets import label, no_focus

_PAGE_ROLE = Qt.ItemDataRole.UserRole


class TocPanel(QFrame):
    """Lists the chapters and takes the reading to the chosen one."""

    page_chosen = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("tocPanel")
        self.setFixedWidth(300)

        self._tree = no_focus(QTreeWidget())
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(2)
        self._tree.setIndentation(14)
        self._tree.setUniformRowHeights(True)
        self._tree.setCursor(Qt.CursorShape.PointingHandCursor)
        self._tree.itemClicked.connect(self._clicked)

        self._empty = label("This PDF has no table of contents.", "muted")
        self._empty.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 24, 8, 16)
        layout.setSpacing(10)
        layout.addWidget(label("CONTENTS", "section"))
        layout.addWidget(self._empty)
        layout.addWidget(self._tree, stretch=1)

        self._items: list[TocItem] = []
        self._widgets: list[QTreeWidgetItem] = []

    def show_items(self, items: list[TocItem]) -> None:
        self._tree.clear()
        self._items, self._widgets = items, []
        stack: list[tuple[int, QTreeWidgetItem]] = []  # (level, item) of the open "parents"
        for item in items:
            while stack and stack[-1][0] >= item.level:
                stack.pop()
            widget = QTreeWidgetItem([item.title, str(item.page + 1)])
            widget.setData(0, _PAGE_ROLE, item.page)
            widget.setToolTip(0, item.title)
            widget.setTextAlignment(1, Qt.AlignmentFlag.AlignRight)
            if stack:
                stack[-1][1].addChild(widget)
            else:
                self._tree.addTopLevelItem(widget)
            stack.append((item.level, widget))
            self._widgets.append(widget)

        self._tree.expandToDepth(0)
        self._tree.resizeColumnToContents(1)
        header = self._tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, header.ResizeMode.Stretch)
        header.setSectionResizeMode(1, header.ResizeMode.ResizeToContents)
        self._empty.setVisible(not items)
        self._tree.setVisible(bool(items))

    def mark(self, page: int) -> None:
        """Select the chapter the page is in."""
        index = current_item(self._items, page)
        if index is None:
            self._tree.clearSelection()
            return
        widget = self._widgets[index]
        parent = widget.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        self._tree.setCurrentItem(widget)
        self._tree.scrollToItem(widget)

    def _clicked(self, widget: QTreeWidgetItem) -> None:
        self.page_chosen.emit(widget.data(0, _PAGE_ROLE))
