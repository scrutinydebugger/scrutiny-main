
__all__ = ['LinearGaugeHMIWidget', 'ColorSpan', 'NumberFormattingConfig']

import math
import enum

from PySide6.QtGui import QPainter, QPen
from PySide6.QtCore import QSize, Qt, QPointF, QRectF, QSizeF
from PySide6.QtWidgets import (QSlider, QWidget, QFormLayout, QComboBox,
                               QSpinBox, QGroupBox, QVBoxLayout, QCheckBox)

from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny.gui.components.locals.hmi.common.numerical_text_display import NumberFormattingConfig, NumericalTextDisplay, NumberFormattingConfigWidget
from scrutiny.gui.components.locals.hmi.common.color_span_editor import ColorSpanEditor, ColorSpanListStateDict, ColorSpan
from scrutiny.gui.components.locals.hmi.common.gauge import GaugeOverflowBehavior
from scrutiny.gui import assets
from scrutiny import tools
from scrutiny.tools.typing import *


class _Dims:
    """Those are relative dimensions used to draw the gauge."""
    BORDER_WIDTH = 0.02
    GAUGE_MIN_WIDTH = 0.2
    GAUGE_MAX_WIDTH = 0.8
    COLOR_BAR_WIDTH_GAUGE_RATIO = 0.15
    COLOR_BAR_OFFSET_GAUGE_RATIO = 0.35
    MAJOR_TICK_LEN_GAUGE_RATIO = 0.6
    MINOR_TICK_LEN_GAUGE_RATIO = 0.25
    FILL_COLOR_WIDTH_GAUGE_RATIO = 0.
    LABEL_WIDTH = 0.35
    CURSOR_HEIGHT = 0.05
    CURSOR_WIDTH = 0.1
    TEXT_LABEL_MARGIN_PX = 5


class LinearGaugeHMIWidget(BaseHMIWidget):
    """A HMI widget that draw a gauge with a pointer (needle) that rotate from left to right according to a value, a min and a max"""

    _CATEGORY = LibraryCategory.Display
    _UNIQUE_NAME = 'linear_gauge'
    _DISPLAY_NAME = 'Linear Gauge'
    _ICON = assets.Icons.HMILinearGauge

    # Config
    _config_widget: QWidget
    """the widget given to the HMI Component"""
    _cmb_overflow_behavior: QComboBox
    """A combo box to select the overflow behavior"""
    _chk_inverted_axis: QCheckBox
    """A checkbox to invert t"""
    _spn_major_ticks: QSpinBox
    """A spinbox to select how many major ticks we have"""
    _spn_minor_ticks: QSpinBox
    """A spinbox to select how many minor ticks we have"""
    _color_span_editor: ColorSpanEditor
    """A widget to define region highlighted in colors. Region are defined by a percentage from 0 to 100 and an associated color."""
    _sld_gauge_width: QSlider
    _sld_text_size: QSlider
    _label_format_config_widget: NumberFormattingConfigWidget

    # State variables
    _minval: Optional[float]
    """The last minimum we have received (it's not a constant)"""
    _maxval: Optional[float]
    """The last maximum we have received (it's not a constant)"""

    def __init__(self, app: AbstractComponentAppInterface) -> None:
        super().__init__(app)
        self.declare_value_slot('val', 'Value')
        self.declare_value_slot('min', 'Minimum')
        self.declare_value_slot('max', 'Maximum')
        self.declare_value_slot('zero', 'Zero Point')

        self._minval = None
        self._maxval = None

        self._cmb_overflow_behavior = QComboBox()
        self._cmb_overflow_behavior.addItem("Clip", GaugeOverflowBehavior.CLIP)
        self._cmb_overflow_behavior.addItem("Show Invalid", GaugeOverflowBehavior.SHOW_NA)

        self._chk_inverted_axis = QCheckBox()

        self._spn_major_ticks = QSpinBox()
        self._spn_major_ticks.setMinimum(0)
        self._spn_major_ticks.setMaximum(15)
        self._spn_major_ticks.setValue(7)

        self._spn_minor_ticks = QSpinBox()
        self._spn_minor_ticks.setMinimum(0)
        self._spn_minor_ticks.setMaximum(12)
        self._spn_minor_ticks.setValue(3)

        self._sld_gauge_width = QSlider(Qt.Orientation.Horizontal)
        self._sld_gauge_width.setMinimum(0)
        self._sld_gauge_width.setMaximum(100)
        self._sld_gauge_width.setValue(50)
        self._sld_gauge_width.setTickInterval(5)

        self._sld_text_size = QSlider(Qt.Orientation.Horizontal)
        self._sld_text_size.setMinimum(10)
        self._sld_text_size.setMaximum(100)
        self._sld_text_size.setValue(50)
        self._sld_text_size.setTickInterval(5)

        self._color_span_editor = ColorSpanEditor()
        self._color_span_editor.set_max_span(6)

        self._label_format_config_widget = NumberFormattingConfigWidget()
        self._label_format_config_widget.apply_config(NumberFormattingConfig(decimals=1, eng_notation=True))

        self._config_widget = QWidget()
        gb_behavior = QGroupBox("Behavior")
        gb_rendering = QGroupBox("Rendering")
        gb_label = QGroupBox("Labels")
        gb_colors = QGroupBox("Colors")
        layout = QVBoxLayout(self._config_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(gb_behavior)
        layout.addWidget(gb_rendering)
        layout.addWidget(gb_label)
        layout.addWidget(gb_colors)

        gb_behavior_layout = QFormLayout(gb_behavior)
        gb_behavior_layout.addRow("Overflow", self._cmb_overflow_behavior)
        gb_behavior_layout.addRow("Inverted", self._chk_inverted_axis)

        gb_rendering_layout = QFormLayout(gb_rendering)
        gb_rendering_layout.addRow("Gauge Width", self._sld_gauge_width)
        gb_rendering_layout.addRow("Text Size", self._sld_text_size)
        gb_rendering_layout.addRow("Major Ticks", self._spn_major_ticks)
        gb_rendering_layout.addRow("Minor Ticks", self._spn_minor_ticks)

        gb_label_layout = QVBoxLayout(gb_label)
        gb_label_layout.addWidget(self._label_format_config_widget)

        gb_colors_layout = QVBoxLayout(gb_colors)
        gb_colors_layout.addWidget(self._color_span_editor)

        self._cmb_overflow_behavior.currentIndexChanged.connect(self._config_changed_slot)
        self._chk_inverted_axis.checkStateChanged.connect(self._config_changed_slot)
        self._spn_major_ticks.valueChanged.connect(self._config_changed_slot)
        self._spn_minor_ticks.valueChanged.connect(self._config_changed_slot)
        self._color_span_editor.signals.row_added.connect(self._config_changed_slot)
        self._color_span_editor.signals.row_removed.connect(self._config_changed_slot)
        self._color_span_editor.signals.row_changed.connect(self._config_changed_slot)
        self._sld_gauge_width.valueChanged.connect(self._config_changed_slot)
        self._sld_text_size.valueChanged.connect(self._config_changed_slot)
        self._label_format_config_widget.signals.changed.connect(self._config_changed_slot)

    def _config_changed_slot(self, *args: Any, **kwargs: Any) -> None:
        self.update()


# region Getter & Setters

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

    def set_label_format_config(self, config: NumberFormattingConfig) -> None:
        self._label_format_config_widget.apply_config(config)

    def set_inverted_axis(self, inverted: bool) -> None:
        self._chk_inverted_axis.setChecked(inverted)

    def set_gauge_width_percent(self, width: int) -> None:
        self._sld_gauge_width.setValue(width)

    def set_text_size_percent(self, size: int) -> None:
        self._sld_text_size.setValue(size)

    def get_overflow_behavior(self) -> GaugeOverflowBehavior:
        return cast(GaugeOverflowBehavior, self._cmb_overflow_behavior.currentData())

    def get_minor_ticks(self) -> int:
        return self._spn_minor_ticks.value()

    def get_major_ticks(self) -> int:
        return self._spn_major_ticks.value()

    def get_color_spans(self) -> List[ColorSpan]:
        return self._color_span_editor.get_span_objects()

    def get_label_format_config(self) -> NumberFormattingConfig:
        return self._label_format_config_widget.get_config()

    def get_inverted_axis(self) -> bool:
        return self._chk_inverted_axis.isChecked()

    def get_gauge_width_percent(self) -> int:
        return self._sld_gauge_width.value()

    def get_text_size_percent(self) -> int:
        return self._sld_text_size.value()

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
        self._chk_inverted_axis.checkStateChanged.disconnect()
        self._spn_major_ticks.valueChanged.disconnect()
        self._spn_minor_ticks.valueChanged.disconnect()
        self._color_span_editor.signals.row_added.disconnect()
        self._color_span_editor.signals.row_removed.disconnect()
        self._color_span_editor.signals.row_changed.disconnect()
        self._sld_gauge_width.valueChanged.disconnect()
        self._sld_text_size.valueChanged.disconnect()
        self._label_format_config_widget.signals.changed.disconnect()

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
        ref_width = bounding_rect.width()
        border_width = min(max(_Dims.BORDER_WIDTH * ref_width, 1), 5)
        half_border_width = border_width / 2

        major_ticks_pen = QPen()
        major_ticks_pen.setColor(HMITheme.Color.major_ticks())
        major_ticks_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        major_ticks_pen.setWidthF(border_width)

        major_ticks_label_pen = QPen()
        major_ticks_label_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        major_ticks_label_pen.setColor(HMITheme.Color.text())

        minor_ticks_pen = QPen()
        minor_ticks_pen.setColor(HMITheme.Color.minor_ticks())

        edit_border_pen = QPen()
        edit_border_pen.setWidthF(1)
        edit_border_pen.setStyle(Qt.PenStyle.DotLine)
        edit_border_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        edit_border_pen.setColor(HMITheme.Color.select_frame_border())

        nb_major_ticks = self._spn_major_ticks.value()
        nb_minor_ticks = self._spn_minor_ticks.value()
        numerical_config = self._label_format_config_widget.get_config()
        monospace_font = assets.get_font(assets.ScrutinyFont.Monospaced)

        pen = QPen()
        pen.setWidthF(border_width)
        pen.setColor(HMITheme.Color.frame_border())
        painter.setPen(pen)

        painter.setBrush(HMITheme.Color.widget_background())
        gauge_width_ratio = (_Dims.GAUGE_MAX_WIDTH - _Dims.GAUGE_MIN_WIDTH) * self._sld_gauge_width.value() / 100 + _Dims.GAUGE_MIN_WIDTH
        gauge_width = ref_width * gauge_width_ratio - border_width

        gauge_height = bounding_rect.height() - border_width
        gauge_padding = float(0)
        if nb_major_ticks >= 2:
            label_height = self._sld_text_size.value() / 100 * bounding_rect.height() / nb_major_ticks
            gauge_padding = label_height / 2
            gauge_height -= 2 * gauge_padding

        gauge_rect = QRectF(
            QPointF(half_border_width + _Dims.CURSOR_WIDTH * ref_width, gauge_padding),
            QSizeF(gauge_width, gauge_height)
        )
        gauge_inner_rect = QRectF(
            gauge_rect.topLeft() + QPointF(half_border_width, half_border_width),
            gauge_rect.size() - QSizeF(border_width, border_width)
        )
        painter.drawRect(gauge_rect)

        val = values['val']
        if val is not None and self._minval is not None and self._maxval is not None:
            overflow_behavior = cast(GaugeOverflowBehavior, self._cmb_overflow_behavior.currentData())
            clipped = False
            if val < self._minval or val > self._maxval:
                if overflow_behavior == GaugeOverflowBehavior.CLIP:
                    val = min(max(val, self._minval), self._maxval)
                    clipped = True
                elif overflow_behavior == GaugeOverflowBehavior.SHOW_NA:
                    val = None

            if val is not None:
                ratio = (val - self._minval) / (self._maxval - self._minval)
                if self._chk_inverted_axis.isChecked():
                    cursor_y = ratio * gauge_rect.height() + gauge_rect.top()
                else:
                    cursor_y = gauge_rect.bottom() - ratio * gauge_rect.height()

                cursor_x = _Dims.CURSOR_WIDTH * ref_width
                cursor_height = _Dims.CURSOR_HEIGHT * gauge_height
                p1 = QPointF(cursor_x, cursor_y)
                p2 = QPointF(0, cursor_y + cursor_height / 2)
                p3 = QPointF(0, cursor_y - cursor_height / 2)
                color = HMITheme.Color.pointer_fill()
                if clipped:
                    color = HMITheme.Color.red_danger()
                painter.setBrush(color)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.drawPolygon([p1, p2, p3], Qt.FillRule.WindingFill)

                zero_val = values['zero']
                if zero_val is not None and zero_val >= self._minval and zero_val <= self._maxval:
                    zero_ratio = (zero_val - self._minval) / (self._maxval - self._minval)
                    if self._chk_inverted_axis.isChecked():
                        fill_start_y = zero_ratio * gauge_inner_rect.height() + gauge_inner_rect.top()
                    else:
                        fill_start_y = gauge_inner_rect.bottom() - zero_ratio * gauge_inner_rect.height()

                    cursor_y_inside = min(max(cursor_y, gauge_inner_rect.top()), gauge_inner_rect.bottom())
                    top_y = min(fill_start_y, cursor_y_inside)
                    height = max(0, abs(cursor_y_inside - fill_start_y))
                    fill_rect = QRectF(
                        QPointF(gauge_rect.left() + half_border_width, top_y),
                        QSizeF(gauge_inner_rect.width() * _Dims.FILL_COLOR_WIDTH_GAUGE_RATIO, height)
                    )

                    painter.setBrush(HMITheme.Color.blue_highlight())
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.drawRect(fill_rect)

                # Draw Line
                p1 = QPointF(cursor_x + border_width, cursor_y)
                p2 = QPointF(p1.x() + gauge_inner_rect.width(), cursor_y)
                pen = QPen()
                pen.setColor(HMITheme.Color.pointer_border())
                pen.setWidthF(1)
                painter.setPen(pen)
                painter.drawLine(p1, p2)

        color_span_pen = QPen()
        color_span_pen.setWidthF(gauge_inner_rect.width() * _Dims.COLOR_BAR_WIDTH_GAUGE_RATIO)
        color_span_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        color_spans = self._color_span_editor.get_span_objects()
        for span in color_spans:
            start = min(max(span.start / 100, 0), 1)
            stop = min(max(span.stop / 100, 0), 1)

            color_span_pen.setColor(span.color.to_qcolor())
            painter.setPen(color_span_pen)
            if self._chk_inverted_axis.isChecked():
                color_bar_y1 = gauge_inner_rect.top() + start * gauge_inner_rect.height()
                color_bar_y2 = gauge_inner_rect.top() + stop * gauge_inner_rect.height()
            else:
                color_bar_y1 = gauge_inner_rect.bottom() - start * gauge_inner_rect.height()
                color_bar_y2 = gauge_inner_rect.bottom() - stop * gauge_inner_rect.height()
            color_bar_x = gauge_inner_rect.right() - gauge_inner_rect.width() * _Dims.COLOR_BAR_OFFSET_GAUGE_RATIO

            painter.drawLine(QPointF(color_bar_x, color_bar_y1), QPointF(color_bar_x, color_bar_y2))

        painter.setBrush(Qt.BrushStyle.NoBrush)
        if nb_major_ticks >= 2:
            major_tick_x1 = gauge_inner_rect.right()
            major_tick_x2 = major_tick_x1 - gauge_inner_rect.width() * _Dims.MAJOR_TICK_LEN_GAUGE_RATIO
            minor_tick_x1 = gauge_inner_rect.right()
            minor_tick_x2 = minor_tick_x1 - gauge_inner_rect.width() * _Dims.MINOR_TICK_LEN_GAUGE_RATIO
            delta_major_tick = gauge_rect.height() / (nb_major_ticks - 1)
            label_width = max((bounding_rect.right() - gauge_rect.right() - _Dims.TEXT_LABEL_MARGIN_PX) - half_border_width, 0)
            label_x = gauge_rect.right() + half_border_width + _Dims.TEXT_LABEL_MARGIN_PX

            for i in range(nb_major_ticks):
                major_tick_y = gauge_rect.top() + i * delta_major_tick
                painter.setPen(major_ticks_pen)
                if i not in (0, nb_major_ticks - 1):
                    painter.drawLine(QPointF(major_tick_x1, major_tick_y), QPointF(major_tick_x2, major_tick_y))
                label_topleft_y = major_tick_y - label_height / 2
                tick_label_rect = QRectF(
                    QPointF(label_x, label_topleft_y),
                    QSizeF(label_width, label_height)
                )
                if edit_mode:
                    painter.setPen(edit_border_pen)
                    painter.drawRect(tick_label_rect)

                if self._maxval is not None and self._minval is not None:
                    value_range = self._maxval - self._minval
                    delta_val = value_range / (nb_major_ticks - 1)
                    if self._chk_inverted_axis.isChecked():
                        tick_val = self._minval + delta_val * i
                    else:
                        tick_val = self._maxval - delta_val * i
                    tick_text = NumericalTextDisplay.format_numerical_value(numerical_config, tick_val)
                    text_align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                    NumericalTextDisplay.apply_font_size(monospace_font, numerical_config, tick_text, tick_label_rect)
                    painter.setFont(monospace_font)
                    painter.setPen(major_ticks_label_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawText(tick_label_rect, tick_text, text_align)

                if nb_minor_ticks > 0 and i < nb_major_ticks - 1:
                    painter.setPen(minor_ticks_pen)
                    for j in range(nb_minor_ticks):
                        minor_tick_y = major_tick_y + (j + 1) * delta_major_tick / (nb_minor_ticks + 1)
                        painter.drawLine(QPointF(minor_tick_x1, minor_tick_y), QPointF(minor_tick_x2, minor_tick_y))

    def get_config_widget(self) -> Optional[QWidget]:
        return self._config_widget

    def get_implementation_config_dict(self) -> Dict[str, Any]:
        return {
            'overflow': cast(GaugeOverflowBehavior, self._cmb_overflow_behavior.currentData()).value,
            'minor_tick': self._spn_minor_ticks.value(),
            'major_tick': self._spn_major_ticks.value(),
            'colors': self._color_span_editor.get_state_dict(),
            'inverted_axis': self._chk_inverted_axis.isChecked(),
            'gauge_width_percent': self._sld_gauge_width.value(),
            'text_size_percent': self._sld_text_size.value(),
            'label_format_config': self._label_format_config_widget.get_config().to_dict()
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        valid_overflow = False
        valid_minor_tick = False
        valid_major_tick = False
        valid_colors = False
        valid_inverted_axis = False
        valid_gauge_width_percent = False
        valid_text_size_percent = False
        valid_label_format_config = False

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

        if 'inverted_axis' in d and isinstance(d['inverted_axis'], bool):
            self._chk_inverted_axis.setChecked(d['inverted_axis'])
            valid_inverted_axis = True

        if 'gauge_width_percent' in d and isinstance(d['gauge_width_percent'], int):
            self._sld_gauge_width.setValue(d['gauge_width_percent'])
            valid_gauge_width_percent = (d['gauge_width_percent'] == self._sld_gauge_width.value())

        if 'text_size_percent' in d and isinstance(d['text_size_percent'], int):
            self._sld_text_size.setValue(d['text_size_percent'])
            valid_text_size_percent = (d['text_size_percent'] == self._sld_text_size.value())

        if 'label_format_config' in d and isinstance(d['label_format_config'], dict):
            config, valid_label_format_config = NumberFormattingConfig.from_dict(d['label_format_config'])
            self._label_format_config_widget.apply_config(config)

        if not valid_overflow:
            self._logger.warning('Invalid overflow behavior')
        if not valid_minor_tick:
            self._logger.warning('Invalid minor tick value')
        if not valid_major_tick:
            self._logger.warning('Invalid major tick value')
        if not valid_colors:
            self._logger.warning('Invalid color spans')

        if not valid_inverted_axis:
            self._logger.warning("Invalid inverted_axis")
        if not valid_gauge_width_percent:
            self._logger.warning("Invalid gauge width percentage")
        if not valid_text_size_percent:
            self._logger.warning("Invalid text size percentage")
        if not valid_label_format_config:
            self._logger.warning("Invalid label configuration")

        return (
            valid_overflow
            and valid_minor_tick
            and valid_major_tick
            and valid_colors
        )
# endregion
