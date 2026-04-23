#    rectangle_hmi_widget.py
#        A graphical only HMI widget that draws a rectangle
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['RectangleHMIWidget']

from PySide6.QtGui import QPainter
from PySide6.QtCore import QSizeF, Qt, QRectF, QPointF
from PySide6.QtWidgets import QVBoxLayout, QWidget, QGroupBox


from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui import assets
from scrutiny.tools.typing import *

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory
from scrutiny.gui.components.locals.hmi.common.pen_config import PenConfigWidget
from scrutiny.gui.components.locals.hmi.common.brush_config import BrushConfigWidget

if TYPE_CHECKING:
    from scrutiny.gui.components.locals.hmi.hmi_component import HMIComponent


class RectangleHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Graphic
    _NAME = 'Rectangle'
    _ICON = assets.Icons.TestSquare

    _config_widget: QWidget
    _pen_config: PenConfigWidget
    _brush_config: BrushConfigWidget

    def __init__(self, hmi_component: "HMIComponent") -> None:
        super().__init__(hmi_component)

        self._config_widget = QWidget()
        self._pen_config = PenConfigWidget()
        self._brush_config = BrushConfigWidget()

        layout = QVBoxLayout(self._config_widget)

        gb_border = QGroupBox("Border")
        gb_fill = QGroupBox("Fill")

        gb_border_layout = QVBoxLayout(gb_border)
        gb_fill_layout = QVBoxLayout(gb_fill)

        gb_border_layout.addWidget(self._pen_config)
        gb_fill_layout.addWidget(self._brush_config)

        layout.addWidget(gb_border)
        layout.addWidget(gb_fill)

        self._pen_config.signals.changed.connect(self._update)
        self._brush_config.signals.changed.connect(self._update)

    def _update(self, *args: Any, **kwargs: Any) -> None:
        self.update()

    def get_config_widget(self) -> QWidget | None:
        return self._config_widget

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             painter: QPainter
             ) -> None:

        pen = self._pen_config.get_pen()
        painter.setPen(pen)
        painter.setBrush(self._brush_config.get_brush())
        bounding_rect = self.boundingRect()
        draw_rect = QRectF(
            QPointF(pen.widthF() / 2, pen.widthF() / 2),
            QSizeF(bounding_rect.width() - pen.widthF(), bounding_rect.height() - pen.widthF())
        )

        painter.drawRect(draw_rect)
