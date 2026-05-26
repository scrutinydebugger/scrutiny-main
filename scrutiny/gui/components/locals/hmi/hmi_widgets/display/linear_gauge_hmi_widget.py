#    linear_gauge_hmi_widget.py
#        An HMI widget that display a value with a linear gauge that goes from a minimum to
#        a maximum value. Like a progress bar
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['LinearGaugeHMIWidget']

from PySide6.QtGui import QPainter, QPen, QColor, QBrush
from PySide6.QtCore import QSize, Qt, QPointF, QRectF, QSizeF
from PySide6.QtWidgets import (QSlider, QStyleOptionGraphicsItem, QWidget, QFormLayout, QComboBox, QGraphicsItem,
                               QSpinBox, QGroupBox, QVBoxLayout, QCheckBox)

from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny.gui.components.locals.hmi.common.numerical_text_display import (
    NumberFormattingConfig, NumericalTextDisplay, NumberFormattingConfigWidget, NumberFormattingConfigDict)
from scrutiny.gui.components.locals.hmi.common.color_span_editor import ColorSpanEditor, ColorSpanListStateDict, ColorSpan
from scrutiny.gui.components.locals.hmi.common.gauge import GaugeOverflowBehavior
from scrutiny.gui.components.locals.hmi.common.serialization import deserialize_combobox_val
from scrutiny.gui import assets
from scrutiny import tools
from scrutiny.tools.typing import *


class _Dims:
    """Those are dimensions (mostly relatives) used to draw the gauge."""
    BORDER_WIDTH = 0.02
    GAUGE_MIN_WIDTH = 0.2
    GAUGE_MAX_WIDTH = 0.8
    COLOR_BAR_WIDTH_GAUGE_RATIO = 0.10
    MAJOR_TICK_LEN_GAUGE_RATIO = 0.6
    MINOR_TICK_LEN_GAUGE_RATIO = 0.25
    FILL_COLOR_WIDTH_GAUGE_RATIO = 1
    CURSOR_WIDTH_GAUGE_RATIO = 0.20
    CURSOR_WIDTH_MAX_PX = 32
    TEXT_LABEL_MARGIN_PX = 5


# region FillRect GraphicItem
class _LinearGaugeFillRect(QGraphicsItem):
    """The graphic item that draw the gauge fill.
    Must be in a different GraphicItem to be updated without redrawing everything"""

    _fill_rect: Optional[QRectF]
    """Rect to fill with fill color. Do not draw if ``None``"""
    _fill_color: QColor
    """Fill color (blue)"""
    _background_rect: QRectF
    """Rect to fill with widget background color"""

    @tools.copy_type(QGraphicsItem.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._fill_rect = None
        self._background_rect = QRectF()
        self._fill_color = QColor()

    def set_fill_rect(self, r: Optional[QRectF]) -> None:
        self._fill_rect = r

    def set_background_rect(self, r: QRectF) -> None:
        self._background_rect = r

    def set_fill_color(self, color: QColor) -> None:
        self._fill_color = color

    def boundingRect(self) -> QRectF:
        return self.parentItem().boundingRect()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(HMITheme.Color.widget_background())
        painter.drawRect(self._background_rect)
        if self._fill_rect is not None:
            painter.setBrush(self._fill_color)
            painter.drawRect(self._fill_rect)

# endregion

# region LinearGauge GraphicItem


class _LinearGauge(QGraphicsItem):
    """The graphic item that does not change for value update.
    Gets redrawn only if dimensions changes. Draw the gauge border, ticks & labels"""

    # Measurements given by the parent graphics items
    _minval: Optional[float]
    _maxval: Optional[float]
    _label_numerical_config: NumberFormattingConfig
    _border_width: float
    _label_height: float
    _gauge_width: float
    _cursor_size: QSizeF
    _nb_major_ticks: int
    _nb_minor_ticks: int
    _inverted_axis: bool
    _edit_mode: bool
    _color_spans: List[ColorSpan]
    _gauge_rect: QRectF

    @tools.copy_type(QGraphicsItem.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # Init values
        self._minval = None
        self._maxval = None
        self._label_numerical_config = NumberFormattingConfig()
        self._border_width = 0
        self._label_height = 0
        self._gauge_width = 0
        self._cursor_size = QSizeF(0, 0)
        self._nb_major_ticks = 0
        self._nb_minor_ticks = 0
        self._inverted_axis = False
        self._edit_mode = False
        self._color_spans = []
        self._gauge_rect = QRectF()

        # Precompute values reused often
        self._major_ticks_pen = QPen()
        self._major_ticks_pen.setColor(HMITheme.Color.major_ticks())
        self._major_ticks_pen.setCapStyle(Qt.PenCapStyle.FlatCap)

        self._major_ticks_label_pen = QPen()
        self._major_ticks_label_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        self._major_ticks_label_pen.setColor(HMITheme.Color.text())

        self._minor_ticks_pen = QPen()
        self._minor_ticks_pen.setColor(HMITheme.Color.minor_ticks())

        self._edit_border_pen = QPen()
        self._edit_border_pen.setWidthF(1)
        self._edit_border_pen.setStyle(Qt.PenStyle.DotLine)
        self._edit_border_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        self._edit_border_pen.setColor(HMITheme.Color.select_frame_border())

        # Bulk of optimization here.
        # When a new value arrives, we redraw only the pointer and the fill.
        # The rest of the gauge is cached and does not need a redraw
        self.setCacheMode(self.CacheMode.ItemCoordinateCache)

# region Getters & Setters
    def set_minmax(self, minval: Optional[float], maxval: Optional[float]) -> None:
        self._minval = minval
        self._maxval = maxval

    def set_label_numerical_config(self, label_numerical_config: NumberFormattingConfig) -> None:
        self._label_numerical_config = label_numerical_config

    def set_border_width(self, width: float) -> None:
        self._border_width = width
        self._recompute_gauge_rect()

    def set_label_height(self, label_height: float) -> None:
        self._label_height = label_height
        self._recompute_gauge_rect()

    def set_gauge_width(self, gauge_width: float) -> None:
        self._gauge_width = gauge_width
        self._recompute_gauge_rect()

    def set_cursor_size(self, cursor_size: QSizeF) -> None:
        self._cursor_size = cursor_size
        self._recompute_gauge_rect()

    def set_major_ticks(self, val: int) -> None:
        self._nb_major_ticks = val
        self._recompute_gauge_rect()

    def set_minor_ticks(self, val: int) -> None:
        self._nb_minor_ticks = val

    def set_inverted_axis(self, val: bool) -> None:
        self._inverted_axis = val

    def set_edit_mode(self, val: bool) -> None:
        self._edit_mode = val

    def get_border_width(self) -> float:
        return self._border_width

    def get_inverted_axis(self) -> bool:
        return self._inverted_axis

    def set_color_spans(self, color_spans: List[ColorSpan]) -> None:
        self._color_spans = color_spans

    def get_color_spans(self) -> List[ColorSpan]:
        return self._color_spans

    def set_gauge_rect(self, gauge_rect: QRectF) -> None:
        self._gauge_rect = gauge_rect

    def get_gauge_rect(self) -> QRectF:
        return self._gauge_rect

    def get_inner_rect(self) -> QRectF:
        return QRectF(
            self._gauge_rect.topLeft() + QPointF(self._border_width / 2, self._border_width / 2),
            QSizeF(self._gauge_rect.width() - self._border_width, self._gauge_rect.height() - self._border_width)
        )

# endregion

    def _recompute_gauge_rect(self) -> None:
        bounding_rect = self.boundingRect()
        gauge_height = bounding_rect.height() - self._border_width
        gauge_padding = float(0)
        if self._nb_major_ticks >= 2:
            gauge_padding = max(self._label_height / 2, gauge_padding)
        gauge_padding = max(gauge_padding, self._cursor_size.height() / 2)
        gauge_height -= 2 * gauge_padding

        self._gauge_rect = QRectF(
            QPointF(0, gauge_padding),
            QSizeF(self._gauge_width, gauge_height)
        )

    def boundingRect(self) -> QRectF:
        return self.parentItem().boundingRect()

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        bounding_rect = self.boundingRect()
        monospace_font = assets.get_font(assets.ScrutinyFont.Monospaced)
        half_border_width = self._border_width / 2
        inner_rect = self.get_inner_rect()

        # Draw the gauge frame (filling comes from another graphic element with different z value)
        pen = QPen()
        pen.setWidthF(self._border_width)
        pen.setColor(HMITheme.Color.frame_border())
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self._gauge_rect)

        # Draw the color bars if any
        if len(self._color_spans) > 0:
            color_span_pen = QPen()
            color_bar_w = inner_rect.width() * _Dims.COLOR_BAR_WIDTH_GAUGE_RATIO
            color_span_pen.setWidthF(color_bar_w)
            color_span_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
            for span in self._color_spans:
                start = min(max(span.start / 100, 0), 1)
                stop = min(max(span.stop / 100, 0), 1)

                color_span_pen.setColor(span.color.to_qcolor())
                painter.setPen(color_span_pen)
                if self._inverted_axis:
                    color_bar_y1 = inner_rect.top() + start * inner_rect.height()
                    color_bar_y2 = inner_rect.top() + stop * inner_rect.height()
                else:
                    color_bar_y1 = inner_rect.bottom() - start * inner_rect.height()
                    color_bar_y2 = inner_rect.bottom() - stop * inner_rect.height()
                color_bar_x = inner_rect.right() - color_bar_w / 2

                painter.drawLine(QPointF(color_bar_x, color_bar_y1), QPointF(color_bar_x, color_bar_y2))

        # Draw the ticks and labels if any
        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self._nb_major_ticks >= 2:
            major_tick_x1 = inner_rect.right()
            major_tick_x2 = major_tick_x1 - inner_rect.width() * _Dims.MAJOR_TICK_LEN_GAUGE_RATIO
            minor_tick_x1 = inner_rect.right()
            minor_tick_x2 = minor_tick_x1 - inner_rect.width() * _Dims.MINOR_TICK_LEN_GAUGE_RATIO
            delta_major_tick = self._gauge_rect.height() / (self._nb_major_ticks - 1)
            label_x = self._gauge_rect.width() + half_border_width + self._cursor_size.width() + _Dims.TEXT_LABEL_MARGIN_PX
            label_width = max(bounding_rect.right() - label_x, 0)

            for i in range(self._nb_major_ticks):
                major_tick_y = self._gauge_rect.top() + i * delta_major_tick
                if self._border_width > 0:
                    self._major_ticks_pen.setWidthF(self._border_width)
                    painter.setPen(self._major_ticks_pen)
                else:
                    painter.setPen(Qt.PenStyle.NoPen)
                if i not in (0, self._nb_major_ticks - 1):
                    painter.drawLine(QPointF(major_tick_x1, major_tick_y), QPointF(major_tick_x2, major_tick_y))
                label_topleft_y = major_tick_y - self._label_height / 2
                tick_label_rect = QRectF(
                    QPointF(label_x, label_topleft_y),
                    QSizeF(label_width, self._label_height)
                )

                if self._edit_mode:
                    painter.setPen(self._edit_border_pen)
                    painter.drawRect(tick_label_rect)

                if self._maxval is not None and self._minval is not None:
                    value_range = self._maxval - self._minval
                    delta_val = value_range / (self._nb_major_ticks - 1)
                    if self._inverted_axis:
                        tick_val = self._minval + delta_val * i
                    else:
                        tick_val = self._maxval - delta_val * i
                    tick_text = NumericalTextDisplay.format_numerical_value(self._label_numerical_config, tick_val)
                    text_align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                    NumericalTextDisplay.apply_font_size(monospace_font, self._label_numerical_config, tick_text, tick_label_rect)
                    painter.setFont(monospace_font)
                    painter.setPen(self._major_ticks_label_pen)
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawText(tick_label_rect, tick_text, text_align)

                # Minor ticks
                if self._nb_minor_ticks > 0 and i < self._nb_major_ticks - 1:
                    painter.setPen(self._minor_ticks_pen)
                    for j in range(self._nb_minor_ticks):
                        minor_tick_y = major_tick_y + (j + 1) * delta_major_tick / (self._nb_minor_ticks + 1)
                        painter.drawLine(QPointF(minor_tick_x1, minor_tick_y), QPointF(minor_tick_x2, minor_tick_y))

# endregion

# region Cursor GraphicItem


class _LinearGaugeCursor(QGraphicsItem):
    """The cursor on the right of the gauge (little triangle).
    In a separate GraphicItem to be updated without redrawing everything"""

    _size: QSizeF
    """Size of bounding box"""
    _pen: QPen
    """Pen for border"""
    _brush: QBrush
    """Brush for fill"""

    @tools.copy_type(QGraphicsItem.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._size = QSizeF()
        self._pen = QPen()
        self._pen.setWidthF(1)
        self._pen.setColor(HMITheme.Color.pointer_border())
        self._brush = QBrush()
        self._brush.setColor(HMITheme.Color.pointer_fill())
        self._brush.setStyle(Qt.BrushStyle.SolidPattern)

        self.setCacheMode(self.CacheMode.ItemCoordinateCache)

    def set_size(self, size: QSizeF) -> None:
        self.prepareGeometryChange()
        self._size = size

    def get_size(self) -> QSizeF:
        return self._size

    def set_fill_color(self, color: QColor) -> None:
        self._brush.setColor(color)

    def boundingRect(self) -> QRectF:
        return QRectF(QPointF(0, 0), self._size)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setPen(self._pen)
        painter.setBrush(self._brush)
        p1 = QPointF(0, self._size.height() / 2)
        p2 = QPointF(self._size.width(), 0)
        p3 = QPointF(self._size.width(), self._size.height())

        painter.drawPolygon([p1, p2, p3], Qt.FillRule.WindingFill)

# endregion

# region HMI Widget


class LinearGaugeHMIWidget(BaseHMIWidget):
    """A HMI widget that draws a linear gauge that shows a small cursor that slide along that gauge.
    Can optionally fill the gauge to look like a progressbar"""

    _UNIQUE_NAME = 'linear_gauge'
    _DISPLAY_NAME = 'Linear Gauge'
    _ICON = assets.Icons.HMILinearGauge

    # Config
    _config_widget: QWidget
    """the widget given to the HMI Component"""
    _cmb_overflow_behavior: QComboBox
    """A combo box to select the overflow behavior"""
    _chk_inverted_axis: QCheckBox
    """A checkbox to invert the axis"""
    _spn_major_ticks: QSpinBox
    """A spinbox to select how many major ticks we have"""
    _spn_minor_ticks: QSpinBox
    """A spinbox to select how many minor ticks we have"""
    _color_span_editor: ColorSpanEditor
    """A widget to define region highlighted in colors. Region are defined by a percentage from 0 to 100 and an associated color."""
    _sld_gauge_width: QSlider
    """A slider to change the width ratio between the gauge and the label"""
    _sld_label_size: QSlider
    """A slider to control the label size"""
    _label_format_config_widget: NumberFormattingConfigWidget
    """A widget to configure the label numerical formatting"""
    _fill_rect: _LinearGaugeFillRect
    """The graphic item that fills the gauge, shown behind"""
    _cursor: _LinearGaugeCursor
    """The graphic item that draws the cursor, shown on top of the gauge"""
    _gauge: _LinearGauge
    """The main gauge graphic item. Drawn with transparent background"""

    # State variables
    _minval: Optional[float]
    """The last minimum we have received (it's not a constant)"""
    _maxval: Optional[float]
    """The last maximum we have received (it's not a constant)"""
    _zero_point: Optional[float]
    """The point from where to start filling the gauge with a fill color."""
    _last_val: Optional[Union[int, float, bool]]
    """Last value received. Used to avoid unnecessary redraw"""

    def __init__(self, app: AbstractComponentAppInterface) -> None:
        super().__init__(app)
        self.declare_value_slot('val', 'Value', require_redraw=False, value_update_callback=self._value_update_callback)
        self.declare_value_slot('min', 'Minimum')
        self.declare_value_slot('max', 'Maximum')
        self.declare_value_slot('zero', 'Zero Point')

        self._minval = None
        self._maxval = None
        self._zero_point = None
        self._last_val = None

        self._fill_rect = _LinearGaugeFillRect(self)
        self._cursor = _LinearGaugeCursor(self)
        self._gauge = _LinearGauge(self)
        self._fill_rect.setZValue(0)
        self._gauge.setZValue(1)
        self._cursor.setZValue(2)

        fill_color = QColor(HMITheme.Color.blue_highlight())
        fill_color.setAlphaF(0.7)
        self._fill_rect.set_fill_color(fill_color)

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

        self._sld_label_size = QSlider(Qt.Orientation.Horizontal)
        self._sld_label_size.setMinimum(10)
        self._sld_label_size.setMaximum(100)
        self._sld_label_size.setValue(50)
        self._sld_label_size.setTickInterval(5)

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
        gb_rendering_layout.addRow("Label Size", self._sld_label_size)
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
        self._sld_label_size.valueChanged.connect(self._config_changed_slot)
        self._label_format_config_widget.signals.changed.connect(self._config_changed_slot)

    def _config_changed_slot(self, *args: Any, **kwargs: Any) -> None:
        self.update()

    def _value_update_callback(self, val: Optional[Union[bool, int, float]]) -> None:
        if tools.strict_eq(val, self._last_val):
            return
        self._process_new_val(val)

    def _process_new_val(self, val: Optional[Union[bool, int, float]]) -> None:
        self._last_val = val

        gauge_rect = self._gauge.get_gauge_rect()
        gauge_inner_rect = self._gauge.get_inner_rect()
        self._fill_rect.set_background_rect(gauge_rect)  # zvalue behind gauge
        self._cursor.setVisible(False)
        self._fill_rect.set_fill_rect(None)
        border_width = self._gauge.get_border_width()
        if val is not None and self._minval is not None and self._maxval is not None:
            overflow_behavior = cast(GaugeOverflowBehavior, self._cmb_overflow_behavior.currentData())
            clipped = False
            if val < self._minval or val > self._maxval:
                if overflow_behavior == GaugeOverflowBehavior.CLIP:
                    val = min(max(val, self._minval), self._maxval)
                    clipped = True
                elif overflow_behavior == GaugeOverflowBehavior.SHOW_NA:
                    val = None
            minmax_range = self._maxval - self._minval
            if val is not None and minmax_range > 0:
                ratio = (val - self._minval) / minmax_range
                if self._chk_inverted_axis.isChecked():
                    cursor_tip_y = ratio * gauge_rect.height() + gauge_rect.top()
                else:
                    cursor_tip_y = gauge_rect.bottom() - ratio * gauge_rect.height()

                cursor_x = gauge_rect.right() + border_width / 2
                self._cursor.setPos(cursor_x, cursor_tip_y - self._cursor.get_size().height() / 2)
                if clipped:
                    self._cursor.set_fill_color(HMITheme.Color.red_danger())
                else:
                    self._cursor.set_fill_color(HMITheme.Color.pointer_fill())
                self._cursor.setVisible(True)

                if self._zero_point is not None and self._zero_point >= self._minval and self._zero_point <= self._maxval:
                    zero_ratio = (self._zero_point - self._minval) / (self._maxval - self._minval)
                    if self._chk_inverted_axis.isChecked():
                        fill_start_y = zero_ratio * gauge_inner_rect.height() + gauge_inner_rect.top()
                    else:
                        fill_start_y = gauge_inner_rect.bottom() - zero_ratio * gauge_inner_rect.height()

                    cursor_y_inside = min(max(cursor_tip_y, gauge_inner_rect.top()), gauge_inner_rect.bottom())
                    top_y = min(fill_start_y, cursor_y_inside)
                    height = max(0, abs(cursor_y_inside - fill_start_y))
                    fill_rect = QRectF(
                        QPointF(gauge_rect.left() + border_width / 2, top_y),
                        QSizeF(gauge_inner_rect.width() * _Dims.FILL_COLOR_WIDTH_GAUGE_RATIO, height)
                    )

                    self._fill_rect.set_fill_rect(fill_rect)

        self._fill_rect.update()
        self._cursor.update()

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

    def set_label_size_percent(self, size: int) -> None:
        self._sld_label_size.setValue(size)

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

    def get_label_size_percent(self) -> int:
        return self._sld_label_size.value()

# endregion

# region Override

    @classmethod
    def default_size(cls) -> QSize:
        return QSize(64, 128)

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
        self._sld_label_size.valueChanged.disconnect()
        self._label_format_config_widget.signals.changed.disconnect()

        super().destroy()

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             edit_mode: bool,
             painter: QPainter
             ) -> None:
        # Draw does not do the drawing directly because we need to stack elements
        # in this order : fill color, gauge, cursor. So we used sub elements.
        self._minval = values['min']    # Used by process_new_val
        self._maxval = values['max']
        self._gauge.set_minmax(values['min'], values['max'])
        self._zero_point = values['zero']

        bounding_rect = self.boundingRect()
        # Start by computing the dimensions
        ref_width = bounding_rect.width()
        border_width = min(max(_Dims.BORDER_WIDTH * ref_width, 1), 5)
        gauge_width_ratio = (_Dims.GAUGE_MAX_WIDTH - _Dims.GAUGE_MIN_WIDTH) * self._sld_gauge_width.value() / 100 + _Dims.GAUGE_MIN_WIDTH
        gauge_width = ref_width * gauge_width_ratio

        label_height = float(0)
        if self._spn_major_ticks.value() >= 2:
            label_height = float(self._sld_label_size.value()) / 100.0 * bounding_rect.height() / float(self._spn_major_ticks.value())

        cursor_size = min(_Dims.CURSOR_WIDTH_MAX_PX, _Dims.CURSOR_WIDTH_GAUGE_RATIO * gauge_width)
        self._cursor.set_size(QSizeF(cursor_size, cursor_size))   # square

        self._gauge.set_edit_mode(edit_mode)
        self._gauge.set_cursor_size(self._cursor.get_size())
        self._gauge.set_gauge_width(gauge_width)
        self._gauge.set_label_height(label_height)
        self._gauge.set_major_ticks(self._spn_major_ticks.value())
        self._gauge.set_minor_ticks(self._spn_minor_ticks.value())
        self._gauge.set_border_width(border_width)
        self._gauge.set_label_numerical_config(self._label_format_config_widget.get_config())
        self._gauge.set_inverted_axis(self._chk_inverted_axis.isChecked())
        self._gauge.set_color_spans(self._color_span_editor.get_span_objects())

        self._process_new_val(values['val'])

        self._gauge.update()
        # Cursor and fill_rect are updated in process_new_val on purpose.

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
            'label_size_percent': self._sld_label_size.value(),
            'label_format_config': self._label_format_config_widget.get_config().to_dict()
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        valid_overflow = False
        valid_minor_tick = False
        valid_major_tick = False
        valid_colors = False
        valid_inverted_axis = False
        valid_gauge_width_percent = False
        valid_label_size_percent = False
        valid_label_format_config = False

        if 'overflow' in d and isinstance(d['overflow'], int):
            valid_overflow = deserialize_combobox_val(d['overflow'], GaugeOverflowBehavior, self._cmb_overflow_behavior)

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

        if 'label_size_percent' in d and isinstance(d['label_size_percent'], int):
            self._sld_label_size.setValue(d['label_size_percent'])
            valid_label_size_percent = (d['label_size_percent'] == self._sld_label_size.value())

        if 'label_format_config' in d and isinstance(d['label_format_config'], dict):
            config, valid_label_format_config = NumberFormattingConfig.from_dict(cast(NumberFormattingConfigDict, d['label_format_config']))
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
        if not valid_label_size_percent:
            self._logger.warning("Invalid label size percentage")
        if not valid_label_format_config:
            self._logger.warning("Invalid label configuration")

        return (
            valid_overflow
            and valid_minor_tick
            and valid_major_tick
            and valid_colors
            and valid_inverted_axis
            and valid_gauge_width_percent
            and valid_label_size_percent
            and valid_label_format_config
        )
# endregion
# endregion
