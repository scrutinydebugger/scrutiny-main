#    gauge_hmi_widget.py
#        An HMI widget that display a dial gauge that goes from minimum to maximum
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['GaugeHMIWidget']

import math
import enum

from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import QSize, QRect, QPoint, Qt, QPointF
from PySide6.QtWidgets import QWidget, QFormLayout, QComboBox


from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets
from scrutiny import tools
from scrutiny.tools.typing import *

if TYPE_CHECKING:
    from scrutiny.gui.components.locals.hmi.hmi_component import HMIComponent

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory

class OverflowBehavior(enum.Enum):
    CLIP = enum.auto()
    SHOW_NA = enum.auto()

class GaugeHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Basics
    _NAME = 'Gauge'
    _ICON = assets.Icons.Copy

    _text_color: QColor
    _base_color: QColor

    _config_widget:QWidget
    _cmb_overflow_behavior:QWidget


    def __init__(self, hmi_component: "HMIComponent") -> None:
        super().__init__(hmi_component)
        self.declare_value_slot('val', 'Value')
        self.declare_value_slot('min', 'Minimum')
        self.declare_value_slot('max', 'Maximum')
        self._text_color = scrutiny_get_theme().palette().text().color()
        self._base_color = scrutiny_get_theme().palette().base().color()


        self._cmb_overflow_behavior = QComboBox()
        self._cmb_overflow_behavior.addItem("Clip", OverflowBehavior.CLIP)
        self._cmb_overflow_behavior.addItem("Show Invalid", OverflowBehavior.SHOW_NA)

        self._config_widget = QWidget()
        layout = QFormLayout(self._config_widget)

        layout.addRow("Overflow", self._cmb_overflow_behavior)

    def draw(self,
             configured: bool,
             values: Dict[str, Union[float, int, bool, None]],
             draw_zone_size: QSize,
             painter: QPainter
             ) -> None:
        CENTER_SIZE = 4
        MARGIN = 10
        pointer_length = draw_zone_size.width() / 2 - MARGIN

        aspect_ratio = draw_zone_size.height() / draw_zone_size.width()

        painter.setPen(self._text_color)
        painter.setBrush(self._base_color)
        half_w = draw_zone_size.width() / 2
        half_h = draw_zone_size.height() / 2
        center = QPointF(half_w, half_h)
        painter.drawEllipse(center, half_w, half_h)
        painter.drawArc(QRect(QPoint(MARGIN, MARGIN), QSize(draw_zone_size.width() - 2 *
                        MARGIN, draw_zone_size.height() - 2 * MARGIN)), -45 * 16, 270 * 16)

        painter.setBrush(self._text_color)
        painter.drawEllipse(center, CENTER_SIZE, CENTER_SIZE)

        value = values['val']
        val_min = values['min']
        val_max = values['max']

        if value is None or val_min is None or val_max is None:
            return

        ratio = (float(value) - float(val_min)) / (float(val_max) - float(val_min))
        ratio = min(max(ratio, 0), 1)
        pointer_angle_deg = (225 - 270 * ratio)

        pointer_tip_y = -pointer_length * math.sin(math.radians(pointer_angle_deg)) * aspect_ratio
        pointer_tip_x = pointer_length * math.cos(math.radians(pointer_angle_deg))

        p1_y = -CENTER_SIZE * math.sin(math.radians(pointer_angle_deg + 90)) * aspect_ratio
        p1_x = CENTER_SIZE * math.cos(math.radians(pointer_angle_deg + 90))
        p2_y = -CENTER_SIZE * math.sin(math.radians(pointer_angle_deg - 90)) * aspect_ratio
        p2_x = CENTER_SIZE * math.cos(math.radians(pointer_angle_deg - 90))

        painter.drawPolygon([
            QPointF(p1_x, p1_y) + center,
            QPointF(pointer_tip_x, pointer_tip_y) + center,
            QPointF(p2_x, p2_y) + center,
        ])


    def get_config_widget(self) -> Optional[QWidget]:
        return None
