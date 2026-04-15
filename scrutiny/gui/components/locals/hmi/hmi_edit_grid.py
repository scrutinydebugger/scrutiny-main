#    hmi_edit_grid.py
#        The Grid used in Edit Mode
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['HMIEditGrid']


from PySide6.QtCore import QRectF, QPointF, QSize
from PySide6.QtWidgets import QStyleOptionGraphicsItem, QGraphicsView, QGraphicsItem, QWidget
from PySide6.QtGui import QPainter
from scrutiny.gui.themes import scrutiny_get_theme

from scrutiny.tools.typing import *


class HMIEditGrid(QGraphicsItem):
    GRID_SPACING = 16

    _view: QGraphicsView
    _visible: bool
    _size: QSize

    def __init__(self, view: QGraphicsView) -> None:
        super().__init__()
        self._visible = False
        self._view = view
        self._size = QSize()

    def show(self) -> None:
        self._visible = True

    def hide(self) -> None:
        self._visible = False

    def set_size(self, size: QSize) -> None:
        self._size = size
        self.update()

    def boundingRect(self) -> QRectF:
        return QRectF(QPointF(0, 0), self._size)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        painter.setPen(scrutiny_get_theme().palette().text().color())
        zone = self.boundingRect().toRect()

        for x in range(zone.left(), zone.right(), self.GRID_SPACING):
            for y in range(zone.top(), zone.bottom(), self.GRID_SPACING):
                painter.drawPoint(QPointF(x, y))
