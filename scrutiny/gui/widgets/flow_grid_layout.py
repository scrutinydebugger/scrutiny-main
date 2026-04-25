#    flow_grid_layout.py
#        A layout that behaves liek a Flex layout in CSS. Make a grid by laying out from left
#        to right, starting from top
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import math

from PySide6.QtWidgets import QWidget, QLayout, QLayoutItem
from PySide6.QtCore import QSize, QRect
from scrutiny.tools.typing import *


class FlowGridLayout(QLayout):
    """Arranges widgets in a uniform grid, computing column count from available
    width and each item's sizeHint. Supports heightForWidth so parent layouts
    allocate the correct vertical space when columns reflow."""

    _items: List[QLayoutItem]

    def __init__(self, spacing: int = 0, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._items = []
        self.setSpacing(spacing)

    def addItem(self, item: QLayoutItem) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int) -> Optional[QLayoutItem]:
        if 0 <= index < len(self._items):
            return self._items[index]
        return None

    def takeAt(self, index: int) -> QLayoutItem:
        return self._items.pop(index)

    def _cell_size(self) -> QSize:
        """Uniform cell size = max sizeHint across all items."""
        w = h = 0
        for item in self._items:
            hint = item.sizeHint()
            w = max(w, hint.width())
            h = max(h, hint.height())
        return QSize(w, h)

    def _nb_col(self, avail_w: int, cell_w: int) -> int:
        if not self._items or cell_w == 0:
            return 1
        sp = self.spacing()
        m = self.contentsMargins()
        avail_w = max(1, avail_w - m.left() - m.right())
        nb_col = (avail_w + sp) // (cell_w + sp)
        return max(1, min(nb_col, len(self._items)))

    def _get_row_col(self, width: int, cell: QSize) -> Tuple[int, int]:
        nb_col = self._nb_col(width, cell.width())
        nb_row = math.ceil(len(self._items) / nb_col)
        return (nb_row, nb_col)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        if not self._items:
            return
        m = self.contentsMargins()
        cell = self._cell_size()
        nb_col = self._nb_col(rect.width(), cell.width())
        sp = self.spacing()
        x0 = rect.x() + m.left()
        y0 = rect.y() + m.top()
        for i, item in enumerate(self._items):
            row, col = divmod(i, nb_col)
            item.setGeometry(QRect(
                x0 + col * (cell.width() + sp),
                y0 + row * (cell.height() + sp),
                cell.width(),
                cell.height()
            ))

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        if not self._items:
            return 0
        m = self.contentsMargins()
        cell = self._cell_size()
        nb_row, nb_col = self._get_row_col(width, cell)
        return nb_row * cell.height() + max(0, nb_row - 1) * self.spacing() + m.top() + m.bottom()

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        parent = self.parentWidget()
        if not self._items or parent is None:
            return QSize(0, 0)
        m = self.contentsMargins()
        cell = self._cell_size()
        nb_row, nb_col = self._get_row_col(parent.width(), cell)
        width = nb_col * cell.width() + max(0, nb_col - 1) * self.spacing()
        height = nb_row * cell.height() + max(0, nb_row - 1) * self.spacing()
        return QSize(width + m.left() + m.right(), height + m.top() + m.bottom())

    def minimumHeightForWidth(self, width: int) -> int:
        return self.heightForWidth(width)
