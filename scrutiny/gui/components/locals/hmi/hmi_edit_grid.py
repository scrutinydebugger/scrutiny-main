#    hmi_edit_grid.py
#        The Grid used in Edit Mode
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['HMIEditGrid']


from PySide6.QtCore import QRectF, QPointF
from PySide6.QtWidgets import QStyleOptionGraphicsItem, QGraphicsView, QGraphicsItem, QWidget
from PySide6.QtGui import QPainter
from scrutiny.gui.themes import scrutiny_get_theme

from scrutiny.tools.typing import *


class HMIEditGrid(QGraphicsItem):
    GRID_SPACING = 16

    _view: QGraphicsView
    _visible: bool

    def __init__(self, view: QGraphicsView) -> None:
        super().__init__()
        self._visible = False
        self._view = view

    def show(self) -> None:
        self._visible = True

    def hide(self) -> None:
        self._visible = False

    def boundingRect(self) -> QRectF:
        return self.mapRectToScene(self._view.viewport().rect())

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        painter.setPen(scrutiny_get_theme().palette().text().color())
        zone = self.boundingRect().toRect()

        for x in range(zone.left(), zone.right(), self.GRID_SPACING):
            for y in range(zone.top(), zone.bottom(), self.GRID_SPACING):
                painter.drawPoint(QPointF(x, y))
