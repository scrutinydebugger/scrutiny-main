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

from PySide6.QtGui import QPainter, QColor, QPen
from PySide6.QtCore import QSize, QRect, QPoint, Qt, QPointF, QRectF, QSizeF
from PySide6.QtWidgets import QWidget, QFormLayout, QComboBox, QLineEdit, QSpinBox, QGroupBox, QVBoxLayout


from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny.gui.components.locals.hmi.common.numerical_text_display import NumericalTextDisplay
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

    _CATEGORY = LibraryCategory.Display
    _NAME = 'Gauge'
    _ICON = assets.Icons.HMIGauge

    _config_widget: QWidget
    _numerical_display: NumericalTextDisplay
    _cmb_overflow_behavior: QComboBox
    _spn_ticks: QSpinBox
    _txt_name: QLineEdit

    def __init__(self, hmi_component: "HMIComponent") -> None:
        super().__init__(hmi_component)
        self.declare_value_slot('val', 'Value', require_redraw=False, value_update_callback=self._value_update)
        self.declare_value_slot('min', 'Minimum')
        self.declare_value_slot('max', 'Maximum')

        self._numerical_display = NumericalTextDisplay(self)

        self._cmb_overflow_behavior = QComboBox()
        self._cmb_overflow_behavior.addItem("Clip", OverflowBehavior.CLIP)
        self._cmb_overflow_behavior.addItem("Show Invalid", OverflowBehavior.SHOW_NA)

        self._spn_ticks = QSpinBox()
        self._spn_ticks.setMinimum(0)
        self._spn_ticks.setMaximum(12)
        self._spn_ticks.setValue(8)

        self._txt_name = QLineEdit()

        self._config_widget = QWidget()
        gb_text_display = QGroupBox("Text Display")
        gb_dial_display = QGroupBox("Dial")
        layout = QVBoxLayout(self._config_widget)
        layout.addWidget(gb_dial_display)
        layout.addWidget(gb_text_display)

        gb_dial_display_layout = QFormLayout(gb_dial_display)
        gb_dial_display_layout.addRow("Name", self._txt_name)
        gb_dial_display_layout.addRow("Overflow", self._cmb_overflow_behavior)
        gb_dial_display_layout.addRow("Ticks", self._spn_ticks)

        gb_text_display_layout = QFormLayout(gb_text_display)
        gb_text_display_layout.addWidget(self._numerical_display.get_config_widget())

        self._cmb_overflow_behavior.currentIndexChanged.connect(self._config_changed_slot)
        self._spn_ticks.valueChanged.connect(self._config_changed_slot)
        self._txt_name.textChanged.connect(self._config_changed_slot)
        self._txt_name.textChanged.connect(self._config_changed_slot)
        self._numerical_display.signals.config_changed.connect(self._config_changed_slot)

    def destroy(self) -> None:
        self._txt_name.textChanged.disconnect()
        super().destroy()

    def _config_changed_slot(self) -> None:
        self.update()

    def _value_update(self, val: Optional[Union[bool, int, float]]) -> None:
        self.update()
        pass

    @classmethod
    def default_size(cls) -> QSize:
        return QSize(128, 128)

    def min_width(self) -> int:
        return 64

    def min_height(self) -> int:
        return 64

    def draw(self,
             configured: bool,
             values: Dict[str, Union[float, int, bool, None]],
             draw_zone_size: QSize,
             painter: QPainter
             ) -> None:

        OUTER_CIRCLE = 1
        INNER_CIRCLE = 0.95
        KNOB = 0.15
        TEXT_DISPLAY_H = 0.3
        TEXT_DISPLAY_W = 0.8
        TEXT_DISPLAY_Y = 0.3
        COLOR_W = 0.07
        TICK_LEN = 0.12
        STROKE = 0.02

        aspect_ratio = draw_zone_size.height() / draw_zone_size.width()
        ref_size = draw_zone_size.width() / 2
        center = QPointF(draw_zone_size.width() / 2, draw_zone_size.height() / 2)
        stroke_w = max(ref_size * STROKE, 1)
        outer_radius = ref_size * OUTER_CIRCLE - stroke_w / 2
        inner_radius = ref_size * INNER_CIRCLE - stroke_w / 2
        knob_radius = ref_size * KNOB
        color_indicator_w = ref_size * COLOR_W
        color_indicator_radius = inner_radius - stroke_w / 2 - color_indicator_w / 2
        textbox_w = ref_size * TEXT_DISPLAY_W
        textbox_h = ref_size * TEXT_DISPLAY_H * aspect_ratio
        textbox_x = center.x() - textbox_w / 2
        textbox_y = center.y() + ref_size * TEXT_DISPLAY_Y * aspect_ratio
        tick_len = ref_size * TICK_LEN
        pointer_length = inner_radius - stroke_w - tick_len / 2

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pen = QPen()
        pen.setWidthF(stroke_w)
        pen.setColor(HMITheme.Color.frame_border())
        painter.setPen(pen)
        painter.setBrush(HMITheme.Color.widget_background())
        painter.drawEllipse(center, outer_radius, outer_radius * aspect_ratio)

        nb_ticks = self._spn_ticks.value()
        if nb_ticks >= 2:
            pen.setColor(HMITheme.Color.text())
            painter.setPen(pen)

            delta_angle = 270 / (nb_ticks - 1)
            tick_p1_radius = inner_radius - stroke_w

            for i in range(nb_ticks):
                angle = 225 - i * delta_angle
                p1 = QPointF(
                    center.x() - tick_p1_radius * math.cos(math.radians(angle)),
                    center.y() - tick_p1_radius * math.sin(math.radians(angle)) * aspect_ratio,
                )
                p2 = QPointF(
                    center.x() - (tick_p1_radius - tick_len) * math.cos(math.radians(angle)),
                    center.y() - (tick_p1_radius - tick_len) * math.sin(math.radians(angle)) * aspect_ratio,
                )

                painter.drawLine(p1, p2)

        pen.setColor(HMITheme.Color.frame_border())
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, inner_radius, inner_radius * aspect_ratio)

        value = values['val']
        val_min = values['min']
        val_max = values['max']

        pen.setColor(HMITheme.Color.pointer_border())
        painter.setPen(pen)
        painter.setBrush(HMITheme.Color.pointer_fill())

        if value is None or val_min is None or val_max is None:
            self._numerical_display.set_val("N/A")
            painter.drawEllipse(center, knob_radius, knob_radius * aspect_ratio)
            return

        self._numerical_display.set_val(value)
        self._numerical_display.setPos(QPointF(textbox_x, textbox_y))
        self._numerical_display.set_size(QSizeF(textbox_w, textbox_h).toSize())
        self._numerical_display.update()

        ratio = (float(value) - float(val_min)) / (float(val_max) - float(val_min))
        ratio = min(max(ratio, 0), 1)
        pointer_angle_deg = (225 - 270 * ratio)

        pointer_tip_y = -pointer_length * math.sin(math.radians(pointer_angle_deg)) * aspect_ratio
        pointer_tip_x = pointer_length * math.cos(math.radians(pointer_angle_deg))

        p1_y = -knob_radius * math.sin(math.radians(pointer_angle_deg + 90)) * aspect_ratio
        p1_x = knob_radius * math.cos(math.radians(pointer_angle_deg + 90))
        p2_y = -knob_radius * math.sin(math.radians(pointer_angle_deg - 90)) * aspect_ratio
        p2_x = knob_radius * math.cos(math.radians(pointer_angle_deg - 90))

        painter.drawPolygon([
            QPointF(p1_x, p1_y) + center,
            QPointF(pointer_tip_x, pointer_tip_y) + center,
            QPointF(p2_x, p2_y) + center,
        ])

        painter.drawEllipse(center, knob_radius, knob_radius * aspect_ratio)

    def get_config_widget(self) -> Optional[QWidget]:
        return self._config_widget
