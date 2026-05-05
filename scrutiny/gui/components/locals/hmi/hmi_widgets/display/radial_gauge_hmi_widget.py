#    radial_gauge_hmi_widget.py
#        An HMI widget that display a value with a gauge that goes from a minimum to a maximum
#        value. Like a speedometer
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['RadialGaugeHMIWidget', 'ColorSpan', 'NumberFormattingConfig']

import math
import enum

from PySide6.QtGui import QPainter, QPen
from PySide6.QtCore import QSize, Qt, QPointF, QRectF, QSizeF
from PySide6.QtWidgets import (QStyleOptionGraphicsItem, QWidget, QFormLayout, QComboBox,
                               QSpinBox, QGroupBox, QVBoxLayout, QGraphicsItem)

from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny.gui.components.locals.hmi.common.numerical_text_display import NumericalTextDisplay, NumberFormattingConfig, NumericalTextDisplayStateDict
from scrutiny.gui.components.locals.hmi.common.color_span_editor import ColorSpanEditor, ColorSpanListStateDict, ColorSpan
from scrutiny.gui.components.locals.hmi.common.gauge import GaugeOverflowBehavior
from scrutiny.gui import assets
from scrutiny import tools
from scrutiny.tools.typing import *


class _Dims:
    """Those are relative dimensions used to draw the gauge."""
    OUTER_CIRCLE = 1
    INNER_CIRCLE = 0.97
    KNOB = 0.12
    TEXT_DISPLAY_H = 0.25
    TEXT_DISPLAY_W = TEXT_DISPLAY_H * 3.2
    TEXT_DISPLAY_Y = 0.575
    COLOR_W = 0.05
    MAJOR_TICK_LEN = 0.12
    MINOR_TICK_LEN = 0.04
    STROKE = 0.02
    POINTER_LEN = 0.9
    TICK_LABEL_W = 0.30
    TICK_LABEL_H = 0.12


class _GaugePointer(QGraphicsItem):
    """The needle of the gauge"""
    _angle: float
    """Angle in degree, relative to a standard cartesian plane"""
    _valid: bool
    """a validity flag. Don't draw the pointer when not valid"""

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
        knob_radius = ref_size * _Dims.KNOB
        center = QPointF(bounding_rect.width() / 2, bounding_rect.height() / 2)
        aspect_ratio = bounding_rect.height() / bounding_rect.width()

        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen()
        pen.setColor(HMITheme.Color.pointer_border())
        pen.setWidthF(max(ref_size * _Dims.STROKE, 1))
        painter.setPen(pen)
        painter.setBrush(HMITheme.Color.pointer_fill())

        if self._valid:
            pointer_length = ref_size * _Dims.POINTER_LEN
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


class RadialGaugeHMIWidget(BaseHMIWidget):
    """A HMI widget that draw a gauge with a pointer (needle) that rotate from left to right according to a value, a min and a max"""

    _CATEGORY = LibraryCategory.Display
    _UNIQUE_NAME = 'radial_gauge'
    _DISPLAY_NAME = 'Radial Gauge'
    _ICON = assets.Icons.HMIRadialGauge

    _pointer: _GaugePointer
    """The needle that rotates. Drawn as a sub graphical item"""

    # Config
    _config_widget: QWidget
    """the widget given to the HMI Component"""
    _numerical_display: NumericalTextDisplay
    """The text display in the bottom-center of the gauge"""
    _cmb_overflow_behavior: QComboBox
    """A combo box to select the overflow behavior"""
    _spn_major_ticks: QSpinBox
    """A spinbox to select how many major ticks we have"""
    _spn_minor_ticks: QSpinBox
    """A spinbox to select how many minor ticks we have"""
    _color_span_editor: ColorSpanEditor
    """A widget to define region highlighted in colors. Region are defined by a percentage from 0 to 100 and an associated color."""

    # State variables
    _minval: Optional[float]
    """The last minimum we have received (it's not a constant)"""
    _maxval: Optional[float]
    """The last maximum we have received (it's not a constant)"""

    def __init__(self, app: AbstractComponentAppInterface) -> None:
        super().__init__(app)
        self.declare_value_slot('val', 'Value', require_redraw=False, value_update_callback=self._process_new_val)
        self.declare_value_slot('min', 'Minimum')
        self.declare_value_slot('max', 'Maximum')

        self._minval = None
        self._maxval = None

        self._numerical_display = NumericalTextDisplay(self)
        self._numerical_display.set_background_color(HMITheme.Color.workzone_background())  # Effect of hole
        self._numerical_display.set_border_width(4)  # Padding. Use same color as background to male the inner border invisible
        self._numerical_display.set_border_color(HMITheme.Color.workzone_background())
        self._pointer = _GaugePointer(self)
        self._pointer.setPos(0, 0)

        self._cmb_overflow_behavior = QComboBox()
        self._cmb_overflow_behavior.addItem("Clip", GaugeOverflowBehavior.CLIP)
        self._cmb_overflow_behavior.addItem("Show Invalid", GaugeOverflowBehavior.SHOW_NA)

        self._spn_major_ticks = QSpinBox()
        self._spn_major_ticks.setMinimum(0)
        self._spn_major_ticks.setMaximum(15)
        self._spn_major_ticks.setValue(7)

        self._spn_minor_ticks = QSpinBox()
        self._spn_minor_ticks.setMinimum(0)
        self._spn_minor_ticks.setMaximum(12)
        self._spn_minor_ticks.setValue(3)

        self._color_span_editor = ColorSpanEditor()
        self._color_span_editor.set_max_span(6)

        self._config_widget = QWidget()
        gb_text_display = QGroupBox("Text Display")
        gb_ticks_display = QGroupBox("Ticks")
        gb_colors = QGroupBox("Colors")
        layout = QVBoxLayout(self._config_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(gb_ticks_display)
        layout.addWidget(gb_text_display)
        layout.addWidget(gb_colors)

        gb_ticks_display_layout = QFormLayout(gb_ticks_display)
        gb_ticks_display_layout.addRow("Overflow", self._cmb_overflow_behavior)
        gb_ticks_display_layout.addRow("Major Ticks", self._spn_major_ticks)
        gb_ticks_display_layout.addRow("Minor Ticks", self._spn_minor_ticks)

        gb_text_display_layout = QFormLayout(gb_text_display)
        gb_text_display_layout.addWidget(self._numerical_display.get_number_format_config_widget())

        gb_colors_layout = QVBoxLayout(gb_colors)
        gb_colors_layout.addWidget(self._color_span_editor)

        self._cmb_overflow_behavior.currentIndexChanged.connect(self._config_changed_slot)
        self._spn_major_ticks.valueChanged.connect(self._config_changed_slot)
        self._spn_minor_ticks.valueChanged.connect(self._config_changed_slot)
        self._numerical_display.signals.config_changed.connect(self._config_changed_slot)
        self._color_span_editor.signals.row_added.connect(self._config_changed_slot)
        self._color_span_editor.signals.row_removed.connect(self._config_changed_slot)
        self._color_span_editor.signals.row_changed.connect(self._config_changed_slot)

    def _config_changed_slot(self) -> None:
        self.update()

    def _get_pointer_angle(self, val: Optional[Union[bool, int, float]]) -> Optional[float]:
        """Tells what angle should the pointer be given an input value. ``None`` if no value to display"""
        if val is None or self._minval is None or self._maxval is None:
            return None

        denom = self._maxval - self._minval
        if denom <= 0:
            return None
        ratio = (float(val) - float(self._minval)) / denom
        overflow_behavior = cast(GaugeOverflowBehavior, self._cmb_overflow_behavior.currentData())
        if ratio < 0 or ratio > 1:
            if overflow_behavior == GaugeOverflowBehavior.SHOW_NA:
                return None
            else:
                ratio = min(max(ratio, 0), 1)
        return (225 - 270 * ratio)

    def _process_new_val(self, val: Optional[Union[bool, int, float]]) -> None:
        """Update the value of the gauge by setting the pointer and the text display"""
        if val is None:
            self._numerical_display.set_val("N/A")
            self._numerical_display.set_alignment(Qt.AlignmentFlag.AlignCenter)
        else:
            self._numerical_display.set_val(val)
            self._numerical_display.set_alignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        pointer_angle = self._get_pointer_angle(val)
        if pointer_angle is None:
            self._pointer.set_valid(False)
        else:
            self._pointer.set_angle(pointer_angle)
            self._pointer.set_valid(True)

        self._numerical_display.update()
        self._pointer.update()


# region Getter & Setters

    def set_number_formatting_config(self, config: NumberFormattingConfig) -> None:
        self._numerical_display.set_number_formatting_config(config)

    def set_overflow_behavior(self, behavior: GaugeOverflowBehavior) -> None:
        index = self._cmb_overflow_behavior.findData(behavior)
        if index >= 0:
            self._cmb_overflow_behavior.setCurrentIndex(index)

    def set_minor_ticks(self, ticks: int) -> None:
        self._spn_minor_ticks.setValue(ticks)

    def set_major_ticks(self, ticks: int) -> None:
        self._spn_major_ticks.setValue(ticks)

    def set_color_spans(self, spans: List[ColorSpan]) -> None:
        self._color_span_editor.set_from_spans_object(spans)

    def get_number_formatting_config(self) -> NumberFormattingConfig:
        return self._numerical_display.get_number_formatting_config()

    def get_overflow_behavior(self) -> GaugeOverflowBehavior:
        return cast(GaugeOverflowBehavior, self._cmb_overflow_behavior.currentData())

    def get_minor_ticks(self) -> int:
        return self._spn_minor_ticks.value()

    def get_major_ticks(self) -> int:
        return self._spn_major_ticks.value()

    def get_color_spans(self) -> List[ColorSpan]:
        return self._color_span_editor.get_span_objects()

# endregion

# region Override

    @classmethod
    def default_size(cls) -> QSize:
        return QSize(128, 128)

    def min_width(self) -> int:
        return 64

    def min_height(self) -> int:
        return 64

    def destroy(self) -> None:
        self._cmb_overflow_behavior.currentIndexChanged.disconnect()
        self._spn_major_ticks.valueChanged.disconnect()
        self._spn_minor_ticks.valueChanged.disconnect()
        self._numerical_display.signals.config_changed.disconnect()
        self._color_span_editor.signals.row_added.disconnect()
        self._color_span_editor.signals.row_removed.disconnect()
        self._color_span_editor.signals.row_changed.disconnect()

        super().destroy()

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             edit_mode: bool,
             painter: QPainter
             ) -> None:

        # Draw is only invoked when a value changes. But here, we want to avoid
        # redrawing the background of the gauge when only the value changes.

        self._minval = values['min']
        self._maxval = values['max']

        bounding_rect = self.boundingRect()
        # Start by computing the dimensions
        aspect_ratio = bounding_rect.height() / bounding_rect.width()
        ref_size = bounding_rect.width() / 2
        center = QPointF(bounding_rect.width() / 2, bounding_rect.height() / 2)
        stroke_w = max(ref_size * _Dims.STROKE, 1)
        outer_radius = ref_size * _Dims.OUTER_CIRCLE - stroke_w / 2
        inner_radius = ref_size * _Dims.INNER_CIRCLE - stroke_w / 2
        textbox_w = ref_size * _Dims.TEXT_DISPLAY_W
        textbox_h = ref_size * _Dims.TEXT_DISPLAY_H * aspect_ratio
        textbox_x = center.x() - textbox_w / 2
        textbox_y = center.y() + ref_size * _Dims.TEXT_DISPLAY_Y * aspect_ratio
        major_tick_len = ref_size * _Dims.MAJOR_TICK_LEN
        minor_tick_len = ref_size * _Dims.MINOR_TICK_LEN
        color_indicator_w = ref_size * _Dims.COLOR_W
        color_indicator_radius = inner_radius * 0.98 - minor_tick_len - stroke_w / 2 - color_indicator_w / 2

        pen = QPen()
        pen.setWidthF(1)
        pen.setColor(HMITheme.Color.select_frame_border())
        painter.setPen(pen)
        painter.setBrush(HMITheme.Color.widget_background())

        # Draw the contour
        painter.drawEllipse(center, outer_radius, outer_radius * aspect_ratio)

        # Draw color spans
        color_spans = self._color_span_editor.get_span_objects()
        for span in color_spans:
            start = min(max(span.start / 100, 0), 1)
            stop = min(max(span.stop / 100, 0), 1)

            angle_stop = 225 - stop * 270
            angle_len = (stop - start) * 270

            pen = QPen()
            color = span.color.to_qcolor()
            pen.setColor(color)
            pen.setWidthF(color_indicator_w)
            pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            painter.setPen(pen)
            rect = QRectF(
                QPointF(ref_size - color_indicator_radius, (ref_size - color_indicator_radius) * aspect_ratio),
                QSizeF(color_indicator_radius * 2, color_indicator_radius * 2 * aspect_ratio))
            painter.drawArc(rect, int(angle_stop * 16), int(angle_len * 16))    # CCW

        # The we draw the tick marks
        major_ticks_pen = QPen()
        major_ticks_pen.setColor(HMITheme.Color.major_ticks())
        major_ticks_pen.setWidthF(stroke_w)

        major_ticks_label_pen = QPen()
        major_ticks_label_pen.setColor(HMITheme.Color.text())

        minor_ticks_pen = QPen()
        minor_ticks_pen.setColor(HMITheme.Color.minor_ticks())

        nb_major_ticks = self._spn_major_ticks.value()
        nb_minor_ticks = self._spn_minor_ticks.value()
        numerical_config = NumberFormattingConfig(units="", decimals=1, eng_notation=True)
        monospace_font = assets.get_font(assets.ScrutinyFont.Monospaced)

        # Draw major ticks
        if nb_major_ticks >= 2:
            # Precompute common values
            delta_angle = 270 / (nb_major_ticks - 1)
            tick_p1_radius = inner_radius - stroke_w
            tick_p2_radius = tick_p1_radius - major_tick_len
            tick_label_size = QSizeF(ref_size * _Dims.TICK_LABEL_W, ref_size * _Dims.TICK_LABEL_H * aspect_ratio)
            tick_label_half_size = QSizeF(tick_label_size.width() / 2, tick_label_size.height() / 2)
            tick_label_longest_diagonal = math.sqrt((tick_label_size.height() / 2)**2 + (tick_label_size.width() / 2)**2)

            for i in range(nb_major_ticks):
                angle = 225 - i * delta_angle
                angle_rad = math.radians(angle)
                cos_angle = math.cos(angle_rad)
                sin_angle = math.sin(angle_rad)
                painter.setPen(major_ticks_pen)

                tick_p1 = QPointF(
                    center.x() + tick_p1_radius * cos_angle,
                    center.y() - tick_p1_radius * sin_angle * aspect_ratio,
                )
                tick_p2 = QPointF(
                    center.x() + tick_p2_radius * cos_angle,
                    center.y() - tick_p2_radius * sin_angle * aspect_ratio,
                )

                painter.drawLine(tick_p1, tick_p2)

                # Write the major tick label
                if self._minval is not None and self._maxval is not None and self._maxval > self._minval:
                    label_radius = max(tick_p2_radius - 2, tick_p2_radius * 0.98)
                    label_intersect_point = QPointF(
                        center.x() + label_radius * cos_angle,
                        center.y() - label_radius * sin_angle * aspect_ratio,
                    )

                    intersect_x_unclipped = tick_label_longest_diagonal * cos_angle
                    intersect_y_unclipped = -tick_label_longest_diagonal * sin_angle
                    intersect_x = max(min(intersect_x_unclipped, tick_label_half_size.width()), -tick_label_half_size.width())
                    intersect_y = max(min(intersect_y_unclipped, tick_label_half_size.height()), -tick_label_half_size.height())

                    tick_val = self._minval + i * ((self._maxval - self._minval) / (nb_major_ticks - 1))
                    tick_text = NumericalTextDisplay.format_numerical_value(numerical_config, tick_val)
                    text_align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter

                    tick_label_pos = label_intersect_point - \
                        QPointF(tick_label_half_size.width() + intersect_x, tick_label_half_size.height() +
                                intersect_y)    # Double inversion on Y. cancel out
                    tick_label_rect = QRectF(tick_label_pos, tick_label_size)
                    NumericalTextDisplay.apply_font_size(monospace_font, numerical_config, tick_text, tick_label_rect)
                    painter.setFont(monospace_font)
                    painter.setPen(major_ticks_label_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawText(tick_label_rect, tick_text, text_align)

                # Draw minor ticks
                if nb_minor_ticks > 0 and i < nb_major_ticks - 1:
                    painter.setPen(minor_ticks_pen)
                    for j in range(nb_minor_ticks):
                        minor_angle = angle - (j + 1) * delta_angle / (nb_minor_ticks + 1)
                        minor_angle_rad = math.radians(minor_angle)
                        cos_minor_angle = math.cos(minor_angle_rad)
                        sin_minor_angle = math.sin(minor_angle_rad)

                        tick_p1 = QPointF(
                            center.x() + tick_p1_radius * cos_minor_angle,
                            center.y() - tick_p1_radius * sin_minor_angle * aspect_ratio,
                        )
                        tick_p2 = QPointF(
                            center.x() + (tick_p1_radius - minor_tick_len) * cos_minor_angle,
                            center.y() - (tick_p1_radius - minor_tick_len) * sin_minor_angle * aspect_ratio,
                        )
                        painter.drawLine(tick_p1, tick_p2)

        pen = QPen()
        pen.setColor(HMITheme.Color.frame_border())
        pen.setWidthF(stroke_w)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        # Draw a 2nd circle to give a depth effect and make a smooth transition between the tick marks and the edge
        painter.drawEllipse(center, inner_radius, inner_radius * aspect_ratio)

        self._numerical_display.setPos(QPointF(textbox_x, textbox_y))
        self._numerical_display.set_size(QSizeF(textbox_w, textbox_h).toSize())

        self._process_new_val(values['val'])

    def get_config_widget(self) -> Optional[QWidget]:
        return self._config_widget

    def get_implementation_config_dict(self) -> Dict[str, Any]:
        return {
            'display': self._numerical_display.get_state_dict(),
            'overflow': cast(GaugeOverflowBehavior, self._cmb_overflow_behavior.currentData()).value,
            'minor_tick': self._spn_minor_ticks.value(),
            'major_tick': self._spn_major_ticks.value(),
            'colors': self._color_span_editor.get_state_dict()
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        valid_display = False
        valid_overflow = False
        valid_minor_tick = False
        valid_major_tick = False
        valid_colors = False

        if 'display' in d and isinstance(d['display'], dict):
            valid_display = self._numerical_display.set_state_dict(cast(NumericalTextDisplayStateDict, d['display']))

        if 'overflow' in d and isinstance(d['overflow'], int):
            with tools.SuppressException(Exception):
                behavior = GaugeOverflowBehavior(d['overflow'])
                index = self._cmb_overflow_behavior.findData(behavior)
                if index >= 0:
                    self._cmb_overflow_behavior.setCurrentIndex(index)
                    valid_overflow = True

        if 'minor_tick' in d and isinstance(d['minor_tick'], int):
            self._spn_minor_ticks.setValue(d['minor_tick'])
            if d['minor_tick'] == self._spn_minor_ticks.value():
                valid_minor_tick = True

        if 'major_tick' in d and isinstance(d['major_tick'], int):
            self._spn_major_ticks.setValue(d['major_tick'])
            if d['major_tick'] == self._spn_major_ticks.value():
                valid_major_tick = True

        if 'colors' in d and isinstance(d['colors'], dict):
            valid_colors = self._color_span_editor.set_state_dict(cast(ColorSpanListStateDict, d['colors']))

        if not valid_display:
            self._logger.warning('Invalid numerical display configuration')
        if not valid_overflow:
            self._logger.warning('Invalid overflow behavior')
        if not valid_minor_tick:
            self._logger.warning('Invalid minor tick value')
        if not valid_major_tick:
            self._logger.warning('Invalid major tick value')
        if not valid_colors:
            self._logger.warning('Invalid color spans')

        return (
            valid_display
            and valid_overflow
            and valid_minor_tick
            and valid_major_tick
            and valid_colors
        )
# endregion
