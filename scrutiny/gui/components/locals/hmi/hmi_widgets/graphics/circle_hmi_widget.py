#    circle_hmi_widget.py
#        A graphical only HMI widget that draws a circle
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['CircleHMIWidget']

from PySide6.QtGui import QPainter, QPen, QBrush
from PySide6.QtCore import QSizeF, Qt, QRectF, QPointF
from PySide6.QtWidgets import QVBoxLayout, QWidget, QGroupBox


from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui import assets
from scrutiny.tools.typing import *

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory
from scrutiny.gui.components.locals.hmi.common.pen_config import PenConfigWidget, PenConfigStateDict
from scrutiny.gui.components.locals.hmi.common.brush_config import BrushConfigWidget, BrushConfigStateDict

if TYPE_CHECKING:
    from scrutiny.gui.components.locals.hmi.hmi_component import HMIComponent


class CircleHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Graphic
    _UNIQUE_NAME = 'circle'
    _DISPLAY_NAME = 'Circle'
    _ICON = assets.Icons.HMICircle

    _config_widget: QWidget

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

    def set_border_pen(self, pen: QPen) -> None:
        self._pen_config.set_pen(pen)

    def get_border_pen(self) -> QPen:
        return self._pen_config.get_pen()

    def set_fill_brush(self, brush: QBrush) -> None:
        self._brush_config.set_brush(brush)

    def get_fill_brush(self) -> QBrush:
        return self._brush_config.get_brush()

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

        painter.drawEllipse(draw_rect)

    def get_implementation_config_dict(self) -> Dict[str, Any]:
        return {
            'border': self._pen_config.get_state_dict(),
            'fill': self._brush_config.get_state_dict()
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        border_valid = False
        fill_valid = False

        if 'border' in d and isinstance(d['border'], dict):
            border_valid = self._pen_config.set_state_dict(cast(PenConfigStateDict, d['border']))

        if 'fill' in d and isinstance(d['fill'], dict):
            fill_valid = self._brush_config.set_state_dict(cast(BrushConfigStateDict, d['fill']))

        if not border_valid:
            self._logger.warning(f"Invalid border settings for HMI Widget: {self.get_display_name()}")

        if not fill_valid:
            self._logger.warning(f"Invalid fill settings for HMI Widget: {self.get_display_name()}")

        return fill_valid and border_valid
