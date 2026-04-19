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
from PySide6.QtWidgets import (QStyleOptionGraphicsItem, QWidget, QFormLayout, QComboBox, QLineEdit, QSpinBox, QGroupBox, QVBoxLayout, QGraphicsItem)

from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny.gui.components.locals.hmi.common.numerical_text_display import NumericalTextDisplay
from scrutiny.gui import assets
from scrutiny import tools
from scrutiny.tools.typing import *

if TYPE_CHECKING:
    from scrutiny.gui.components.locals.hmi.hmi_component import HMIComponent

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory


class Dims:
    OUTER_CIRCLE = 1
    INNER_CIRCLE = 0.97
    KNOB = 0.12
    TEXT_DISPLAY_H = 0.25
    TEXT_DISPLAY_W = 0.8
    TEXT_DISPLAY_Y = 0.35
    COLOR_W = 0.07
    MAJOR_TICK_LEN = 0.12
    MINOR_TICK_LEN = 0.04
    STROKE = 0.02
    POINTER_LEN = 0.9


class OverflowBehavior(enum.Enum):
    CLIP = enum.auto()
    SHOW_NA = enum.auto()


class GaugePointer(QGraphicsItem):

    _angle: float
    _valid: bool

    @tools.copy_type(QGraphicsItem.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._angle = 0
        self._valid = True

    def set_angle(self, angle: float) -> None:
        self._angle = angle

    def set_valid(self, valid: bool) -> None:
        self._valid = valid

    def boundingRect(self) -> QRectF:
        return self.parentItem().boundingRect()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        bounding_rect = self.boundingRect()
        ref_size = bounding_rect.width() / 2
        knob_radius = ref_size * Dims.KNOB
        center = QPointF(bounding_rect.width() / 2, bounding_rect.height() / 2)
        aspect_ratio = bounding_rect.height() / bounding_rect.width()

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pen = QPen()
        pen.setColor(HMITheme.Color.pointer_border())
        pen.setWidthF(max(ref_size * Dims.STROKE, 1))
        painter.setPen(pen)
        painter.setBrush(HMITheme.Color.pointer_fill())

        if self._valid:
            pointer_length = ref_size * Dims.POINTER_LEN
            pointer_angle_rad = math.radians(self._angle)

            pointer_tip_y = -pointer_length * math.sin(pointer_angle_rad) * aspect_ratio
            pointer_tip_x = pointer_length * math.cos(pointer_angle_rad)

            base_half_width = knob_radius / 2
            p1_angle_rad = math.radians(self._angle + 90)
            p2_angle_rad = math.radians(self._angle - 90)
            p1_y = -base_half_width * math.sin(p1_angle_rad) * aspect_ratio
            p1_x = base_half_width * math.cos(p1_angle_rad)
            p2_y = -base_half_width * math.sin(p2_angle_rad) * aspect_ratio
            p2_x = base_half_width * math.cos(p2_angle_rad)

            painter.drawPolygon([
                QPointF(p1_x, p1_y) + center,
                QPointF(pointer_tip_x, pointer_tip_y) + center,
                QPointF(p2_x, p2_y) + center,
            ])

        painter.drawEllipse(center, knob_radius, knob_radius * aspect_ratio)


class GaugeHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Display
    _NAME = 'Gauge'
    _ICON = assets.Icons.HMIGauge

    _config_widget: QWidget
    _numerical_display: NumericalTextDisplay
    _pointer: GaugePointer
    _cmb_overflow_behavior: QComboBox
    _spn_major_ticks: QSpinBox
    _spn_minor_ticks: QSpinBox
    _txt_name: QLineEdit

    _minval: Optional[float]
    _maxval: Optional[float]

    def __init__(self, hmi_component: "HMIComponent") -> None:
        super().__init__(hmi_component)
        self.declare_value_slot('val', 'Value', require_redraw=False, value_update_callback=self._process_new_val)
        self.declare_value_slot('min', 'Minimum')
        self.declare_value_slot('max', 'Maximum')

        self._minval = None
        self._maxval = None

        self._numerical_display = NumericalTextDisplay(self)
        self._pointer = GaugePointer(self)
        self._pointer.setPos(0, 0)

        self._cmb_overflow_behavior = QComboBox()
        self._cmb_overflow_behavior.addItem("Clip", OverflowBehavior.CLIP)
        self._cmb_overflow_behavior.addItem("Show Invalid", OverflowBehavior.SHOW_NA)

        self._spn_major_ticks = QSpinBox()
        self._spn_major_ticks.setMinimum(0)
        self._spn_major_ticks.setMaximum(12)
        self._spn_major_ticks.setValue(6)

        self._spn_minor_ticks = QSpinBox()
        self._spn_minor_ticks.setMinimum(0)
        self._spn_minor_ticks.setMaximum(12)
        self._spn_minor_ticks.setValue(2)

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
        gb_dial_display_layout.addRow("Major Ticks", self._spn_major_ticks)
        gb_dial_display_layout.addRow("Minor Ticks", self._spn_minor_ticks)

        gb_text_display_layout = QFormLayout(gb_text_display)
        gb_text_display_layout.addWidget(self._numerical_display.get_config_widget())

        self._cmb_overflow_behavior.currentIndexChanged.connect(self._config_changed_slot)
        self._spn_major_ticks.valueChanged.connect(self._config_changed_slot)
        self._spn_minor_ticks.valueChanged.connect(self._config_changed_slot)
        self._txt_name.textChanged.connect(self._config_changed_slot)
        self._numerical_display.signals.config_changed.connect(self._config_changed_slot)

        # Make sure we do not redraw the full gauge when the needle or the text is updated.
        self.setCacheMode(self.CacheMode.ItemCoordinateCache)

    def destroy(self) -> None:
        self._cmb_overflow_behavior.currentIndexChanged.disconnect()
        self._spn_major_ticks.valueChanged.disconnect()
        self._spn_minor_ticks.valueChanged.disconnect()
        self._txt_name.textChanged.disconnect()
        self._numerical_display.signals.config_changed.disconnect()

        super().destroy()

    def _config_changed_slot(self) -> None:
        self.update()

    def _get_pointer_angle(self, val: Optional[Union[bool, int, float]]) -> Optional[float]:
        if val is None or self._minval is None or self._maxval is None:
            return None

        denom = self._maxval - self._minval
        if denom <= 0:
            return None
        ratio = (float(val) - float(self._minval)) / denom
        ratio = min(max(ratio, 0), 1)
        return (225 - 270 * ratio)

    def _process_new_val(self, val: Optional[Union[bool, int, float]]) -> None:
        if val is None:
            self._numerical_display.set_val("N/A")
        else:
            self._numerical_display.set_val(val)

        pointer_angle = self._get_pointer_angle(val)
        if pointer_angle is None:
            self._pointer.set_valid(False)
        else:
            self._pointer.set_angle(pointer_angle)
            self._pointer.set_valid(True)

        self._numerical_display.update()
        self._pointer.update()

    @classmethod
    def default_size(cls) -> QSize:
        return QSize(128, 128)

    def min_width(self) -> int:
        return 64

    def min_height(self) -> int:
        return 64

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             painter: QPainter
             ) -> None:
        bounding_rect = self.boundingRect()
        aspect_ratio = bounding_rect.height() / bounding_rect.width()
        ref_size = bounding_rect.width() / 2
        center = QPointF(bounding_rect.width() / 2, bounding_rect.height() / 2)
        stroke_w = max(ref_size * Dims.STROKE, 1)
        outer_radius = ref_size * Dims.OUTER_CIRCLE - stroke_w / 2
        inner_radius = ref_size * Dims.INNER_CIRCLE - stroke_w / 2
        color_indicator_w = ref_size * Dims.COLOR_W
        color_indicator_radius = inner_radius - stroke_w / 2 - color_indicator_w / 2
        textbox_w = ref_size * Dims.TEXT_DISPLAY_W
        textbox_h = ref_size * Dims.TEXT_DISPLAY_H * aspect_ratio
        textbox_x = center.x() - textbox_w / 2
        textbox_y = center.y() + ref_size * Dims.TEXT_DISPLAY_Y * aspect_ratio
        major_tick_len = ref_size * Dims.MAJOR_TICK_LEN
        minor_tick_len = ref_size * Dims.MINOR_TICK_LEN

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        pen = QPen()
        pen.setWidthF(1)
        pen.setColor(HMITheme.Color.select_frame_border())
        painter.setPen(pen)
        painter.setBrush(HMITheme.Color.widget_background())
        painter.drawEllipse(center, outer_radius, outer_radius * aspect_ratio)

        pen.setColor(HMITheme.Color.frame_border())
        pen.setWidthF(stroke_w)
        painter.setPen(pen)
        nb_major_ticks = self._spn_major_ticks.value()
        nb_minor_ticks = self._spn_minor_ticks.value()
        if nb_major_ticks >= 2:
            delta_angle = 270 / (nb_major_ticks - 1)
            tick_p1_radius = inner_radius - stroke_w

            for i in range(nb_major_ticks):
                angle = 225 - i * delta_angle
                angle_rad = math.radians(angle)
                p1 = QPointF(
                    center.x() - tick_p1_radius * math.cos(angle_rad),
                    center.y() - tick_p1_radius * math.sin(angle_rad) * aspect_ratio,
                )
                p2 = QPointF(
                    center.x() - (tick_p1_radius - major_tick_len) * math.cos(angle_rad),
                    center.y() - (tick_p1_radius - major_tick_len) * math.sin(angle_rad) * aspect_ratio,
                )

                painter.drawLine(p1, p2)

                if nb_minor_ticks > 0 and i < nb_major_ticks - 1:
                    for j in range(nb_minor_ticks):
                        minor_angle = angle - (j + 1) * delta_angle / (nb_minor_ticks + 1)
                        minor_angle_rad = math.radians(minor_angle)

                        p1 = QPointF(
                            center.x() - tick_p1_radius * math.cos(minor_angle_rad),
                            center.y() - tick_p1_radius * math.sin(minor_angle_rad) * aspect_ratio,
                        )
                        p2 = QPointF(
                            center.x() - (tick_p1_radius - minor_tick_len) * math.cos(minor_angle_rad),
                            center.y() - (tick_p1_radius - minor_tick_len) * math.sin(minor_angle_rad) * aspect_ratio,
                        )
                        painter.drawLine(p1, p2)

        pen.setColor(HMITheme.Color.frame_border())
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(center, inner_radius, inner_radius * aspect_ratio)

        self._numerical_display.setPos(QPointF(textbox_x, textbox_y))
        self._numerical_display.set_size(QSizeF(textbox_w, textbox_h).toSize())

        self._minval = values['min']
        self._maxval = values['max']
        self._process_new_val(values['val'])

    def get_config_widget(self) -> Optional[QWidget]:
        return self._config_widget
