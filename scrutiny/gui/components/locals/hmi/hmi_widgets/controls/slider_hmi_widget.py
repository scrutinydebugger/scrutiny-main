#    slider_hmi_widget.py
#        A slider that can write a float value by moving a cursor from min to max. Can be
#        horizontal or vertical.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['SliderHMIWidget']

from PySide6.QtGui import QPainter, QPen, QBrush, QDoubleValidator, QFontMetrics
from PySide6.QtCore import QSize, Qt, QPointF, QRectF, QSizeF
from PySide6.QtWidgets import QStyleOptionGraphicsItem, QVBoxLayout, QWidget, QGroupBox, QComboBox, QFormLayout, QSlider, QSpinBox, QGraphicsItem

from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui.components.locals.hmi.common.serialization import deserialize_combobox_val
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny.gui.components.locals.hmi.common.numerical_text_display import (
    NumberFormattingConfig, NumericalTextDisplay, NumberFormattingConfigWidget)
from scrutiny.gui import assets
from scrutiny.tools.typing import *
from scrutiny.gui.widgets.validable_line_edit import FloatValidableLineEdit


class _Dims:
    CURSOR_MIN_W_PX = 16
    TEXT_LABEL_MARGIN_PX = 3
    MAJOR_TICK_LEN_RATIO = 0.05
    MAJOR_TICK_MAX_LEN_PX = 20
    SLIDE_ZONE_MIN_W_RATIO = 0.1
    CURSOR_W_RATIO = 0.2
    CURSOR_H_RATIO_TO_CURSOR_W = 0.3
    CURSOR_H_MAX_PX = 15
    BORDER_MAX_PX = 5
    CURSOR_BORDER_MAX_PX = 3
    BORDER_RATIO = 0.03
    MAJOR_TICK_MAX_THICKNESS_PX = 4


class SliderCursor(QGraphicsItem):
    """The sliding cursor. Only this should be redrawn in display mode"""

    _size: QSizeF
    """Cursor rectangle size"""
    _border_size: float
    """Pen border size"""
    _cursor_pen: QPen
    """Pen used to draw the cursor"""
    _cursor_brush: QBrush
    """Brush used to draw the cursor"""
    _enabled: bool
    """Enable flag to show/hide the cursor"""

    def __init__(self, parent: QGraphicsItem) -> None:
        super().__init__(parent)
        self._size = QSizeF(0, 0)
        self._border_size = 0

        self._cursor_pen = QPen()
        self._cursor_pen.setWidthF(self._border_size)
        self._cursor_pen.setColor(HMITheme.Color.pointer_border())
        self._cursor_brush = QBrush()
        self._cursor_brush.setColor(HMITheme.Color.pointer_fill())
        self._cursor_brush.setStyle(Qt.BrushStyle.SolidPattern)
        self._enabled = True

    def set_size(self, size: QSizeF) -> None:
        self._size = size

    def set_border_size(self, border_size: float) -> None:
        self._border_size = border_size

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        self.setVisible(self._enabled)

    def get_size(self) -> QSizeF:
        return self._size

    def get_border_size(self) -> float:
        return self._border_size

    def is_enabled(self) -> bool:
        return self._enabled

    def boundingRect(self) -> QRectF:
        return QRectF(QPointF(0, 0), self._size)

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        if not self._enabled:
            return
        self._cursor_pen.setWidthF(self._border_size)
        painter.setPen(self._cursor_pen)
        painter.setBrush(self._cursor_brush)

        rect = QRectF(
            QPointF(self._border_size / 2, self._border_size / 2),
            QSizeF(self._size.width() - self._border_size, self._size.height() - self._border_size)
        )

        painter.drawRect(rect)


class SliderHMIWidget(BaseHMIWidget):

    _UNIQUE_NAME = 'slider'
    _DISPLAY_NAME = 'Slider'
    _ICON = assets.Icons.HMISlider

    _config_widget: QWidget
    """Container widget holding all configuration controls"""
    _cmb_orientation: QComboBox
    """Dropdown to select horizontal or vertical orientation"""
    _txt_min_val: FloatValidableLineEdit
    """Text input for the minimum value of the slider range"""
    _txt_max_val: FloatValidableLineEdit
    """Text input for the maximum value of the slider range"""
    _sld_label_size: QSlider
    """Slider to control the size of tick labels"""
    _spn_major_ticks: QSpinBox
    """Spin box to set the number of major tick marks"""
    _spn_minor_ticks: QSpinBox
    """Spin box to set the number of minor tick marks between major ticks"""
    _label_format_config_widget: NumberFormattingConfigWidget
    """A widget to configure the label numerical formatting"""
    _edit_border_pen: QPen
    """Pen used to draw the border of the slider in edit mode"""
    _cursor: SliderCursor
    """The draggable cursor element on the slider track"""

    _slide_zone_rect: Optional[QRectF]
    """Bounding rectangle of the slider track area, None until first paint"""
    _dragging_val: Optional[float]
    """The value being dragged to, None when not actively dragging"""
    _last_val_received: Optional[Union[float, int, bool]]
    """Last value received used to prevent redraw when not necessary"""

    _slide_zone_pen: QPen
    _slide_zone_brush: QBrush
    _major_tick_pen: QPen
    _minor_tick_pen: QPen

    def __init__(self, app: AbstractComponentAppInterface) -> None:
        super().__init__(app)
        self.declare_value_slot('val', 'Value', allow_constant=False, require_redraw=False, value_update_callback=self._value_update_callback)
        self._slide_zone_rect = None
        self._dragging_val = None
        self._cursor = SliderCursor(self)
        self._cursor.set_enabled(False)
        self._last_val_received = None

        self._cmb_orientation = QComboBox()
        self._cmb_orientation.addItem("Horizontal", Qt.Orientation.Horizontal)
        self._cmb_orientation.addItem("Vertical", Qt.Orientation.Vertical)
        self._cmb_orientation.setCurrentIndex(self._cmb_orientation.findData(Qt.Orientation.Horizontal))

        self._txt_min_val = FloatValidableLineEdit(hard_validator=QDoubleValidator())
        self._txt_max_val = FloatValidableLineEdit(hard_validator=QDoubleValidator())

        self._sld_label_size = QSlider(Qt.Orientation.Horizontal)
        self._sld_label_size.setMinimum(0)
        self._sld_label_size.setMaximum(100)
        self._sld_label_size.setTickInterval(5)

        self._spn_major_ticks = QSpinBox()
        self._spn_major_ticks.setMinimum(0)
        self._spn_major_ticks.setMaximum(20)

        self._spn_minor_ticks = QSpinBox()
        self._spn_minor_ticks.setMinimum(0)
        self._spn_minor_ticks.setMaximum(12)

        self._label_format_config_widget = NumberFormattingConfigWidget()
        self._label_format_config_widget.apply_config(NumberFormattingConfig(decimals=1, eng_notation=True))

        self._config_widget = QWidget()
        gb_config = QGroupBox("Configuration")
        gb_label = QGroupBox("Labels")
        layout = QVBoxLayout(self._config_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(gb_config)
        layout.addWidget(gb_label)

        gb_config_layout = QFormLayout(gb_config)
        gb_config_layout.addRow("Orientation", self._cmb_orientation)
        gb_config_layout.addRow("Minimum", self._txt_min_val)
        gb_config_layout.addRow("Maximum", self._txt_max_val)
        gb_config_layout.addRow("Label Size", self._sld_label_size)
        gb_config_layout.addRow("Major Ticks", self._spn_major_ticks)
        gb_config_layout.addRow("Minor Ticks", self._spn_minor_ticks)

        gb_label_layout = QVBoxLayout(gb_label)
        gb_label_layout.addWidget(self._label_format_config_widget)

        self._cmb_orientation.setCurrentIndex(self._cmb_orientation.findData(Qt.Orientation.Vertical))
        self._txt_min_val.setText("")
        self._txt_max_val.setText("")
        self._sld_label_size.setValue(50)
        self._spn_major_ticks.setValue(5)
        self._spn_minor_ticks.setValue(3)

        self._edit_border_pen = QPen()
        self._edit_border_pen.setWidthF(1)
        self._edit_border_pen.setStyle(Qt.PenStyle.DotLine)
        self._edit_border_pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        self._edit_border_pen.setColor(HMITheme.Color.select_frame_border())

        self._slide_zone_pen = QPen()
        self._slide_zone_pen.setWidthF(0)
        self._slide_zone_pen.setColor(HMITheme.Color.frame_border())

        self._slide_zone_brush = QBrush()
        self._slide_zone_brush.setColor(HMITheme.Color.widget_background())
        self._slide_zone_brush.setStyle(Qt.BrushStyle.SolidPattern)

        self._major_tick_pen = QPen()
        self._major_tick_pen.setWidthF(0)
        self._major_tick_pen.setColor(HMITheme.Color.frame_border())

        self._minor_tick_pen = QPen()
        self._minor_tick_pen.setWidthF(1)
        self._minor_tick_pen.setColor(HMITheme.Color.frame_border())

        self._cmb_orientation.currentIndexChanged.connect(self._config_changed_slot)
        self._txt_min_val.textChanged.connect(self._config_changed_slot)
        self._txt_max_val.textChanged.connect(self._config_changed_slot)
        self._sld_label_size.valueChanged.connect(self._config_changed_slot)
        self._spn_major_ticks.valueChanged.connect(self._config_changed_slot)
        self._spn_minor_ticks.valueChanged.connect(self._config_changed_slot)
        self._label_format_config_widget.signals.changed.connect(self._config_changed_slot)

    def destroy(self) -> None:
        self._cmb_orientation.currentIndexChanged.disconnect()
        self._txt_min_val.textChanged.disconnect()
        self._txt_max_val.textChanged.disconnect()
        self._sld_label_size.valueChanged.disconnect()
        self._spn_major_ticks.valueChanged.disconnect()
        self._spn_minor_ticks.valueChanged.disconnect()
        self._label_format_config_widget.signals.changed.disconnect()
        return super().destroy()

    def _config_changed_slot(self) -> None:
        self.update()

    def _val_from_pos(self, pos: QPointF) -> Optional[float]:
        """Compute the value to write based on the position of the cursor"""
        min_val = self._txt_min_val.get_float_value()
        max_val = self._txt_max_val.get_float_value()

        if min_val is None or max_val is None:
            return None

        if self._slide_zone_rect is None:
            return None

        if self._slide_zone_rect.height() == 0 or self._slide_zone_rect.width() == 0:
            return None

        orientation = self.get_orientation()
        if orientation == Qt.Orientation.Vertical:
            yval = min(self._slide_zone_rect.bottom(), max(self._slide_zone_rect.top(), pos.y()))
            ratio = (yval - self._slide_zone_rect.top()) / self._slide_zone_rect.height()
            return (max_val - min_val) * (1 - ratio) + min_val    # 1-ratio because y0 is at the top and minval is at bottom
        elif orientation == Qt.Orientation.Horizontal:
            xval = min(self._slide_zone_rect.right(), max(self._slide_zone_rect.left(), pos.x()))
            ratio = (xval - self._slide_zone_rect.left()) / self._slide_zone_rect.width()
            return (max_val - min_val) * ratio + min_val

        raise NotImplementedError("Unknown orientation")

    def _get_val_ratio(self, val: Optional[Union[float, int, bool]]) -> Optional[float]:
        """Compute the value ratio representing the cursor position in the min/max range"""
        ratio: Optional[float] = None
        min_val = self._txt_min_val.get_float_value()
        max_val = self._txt_max_val.get_float_value()
        if min_val is not None and max_val is not None and val is not None and max_val > min_val:
            if self._dragging_val is not None:
                val = self._dragging_val
            ratio = min(1, max(0, (val - min_val) / (max_val - min_val)))
        return ratio

    def _get_vertical_cursor_y(self, ratio: float) -> float:
        """Get the Y position of the cursor for vertical slider"""
        assert self._slide_zone_rect is not None
        return self._slide_zone_rect.top() + self._slide_zone_rect.height() * (1 - ratio) - self._cursor.get_size().height() / 2

    def _get_horizontal_cursor_x(self, ratio: float) -> float:
        """Get the X position of the cursor for horizontal slider"""
        assert self._slide_zone_rect is not None
        return self._slide_zone_rect.left() + self._slide_zone_rect.width() * ratio - self._cursor.get_size().width() / 2

    def _value_update_callback(self, val: Optional[Union[float, int, bool]]) -> None:
        """Called when a new value is received"""
        if val == self._last_val_received and type(val) == type(self._last_val_received):
            return

        self._last_val_received = val
        ratio = self._get_val_ratio(val)
        if self._slide_zone_rect is None or ratio is None:
            self._cursor.set_enabled(False)
            self._cursor.update()
            return

        self._cursor.set_enabled(True)

        orientation = cast(Qt.Orientation, self._cmb_orientation.currentData())
        if orientation == Qt.Orientation.Vertical:
            cursor_y = self._get_vertical_cursor_y(ratio)
            self._cursor.setPos(QPointF(self._cursor.pos().x(), cursor_y))
        elif orientation == Qt.Orientation.Horizontal:
            cursor_x = self._get_horizontal_cursor_x(ratio)
            self._cursor.setPos(QPointF(cursor_x, self._cursor.pos().y()))
        else:
            raise NotImplementedError("Unknown orientation")
        self._cursor.update()

    def get_cursor_rect(self) -> QRectF:
        return QRectF(self._cursor.pos(), self._cursor.get_size())

    def get_slidezone_rect(self) -> Optional[QRectF]:
        return self._slide_zone_rect

# region Getters and Setters

    def get_orientation(self) -> Qt.Orientation:
        return cast(Qt.Orientation, self._cmb_orientation.currentData())

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        index = self._cmb_orientation.findData(orientation)
        if index >= 0:
            self._cmb_orientation.setCurrentIndex(index)

    def set_min_val(self, val: float) -> None:
        self._txt_min_val.set_float_value(val)

    def set_max_val(self, val: float) -> None:
        self._txt_max_val.set_float_value(val)

    def set_label_size_percent(self, size: int) -> None:
        self._sld_label_size.setValue(size)

    def set_major_ticks(self, ticks: int) -> None:
        self._spn_major_ticks.setValue(ticks)

    def set_minor_ticks(self, ticks: int) -> None:
        self._spn_minor_ticks.setValue(ticks)

    def get_min_val(self) -> Optional[float]:
        return self._txt_min_val.get_float_value()

    def get_max_val(self) -> Optional[float]:
        return self._txt_max_val.get_float_value()

    def get_label_size_percent(self) -> int:
        return self._sld_label_size.value()

    def get_major_ticks(self) -> int:
        return self._spn_major_ticks.value()

    def get_minor_ticks(self) -> int:
        return self._spn_minor_ticks.value()

# endregion

# region Override

    @classmethod
    def default_size(cls) -> QSize:
        return QSize(32, 128)

    def min_height(self) -> int:
        return 32

    def min_width(self) -> int:
        return 32

    def get_config_widget(self) -> QWidget:
        return self._config_widget

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             edit_mode: bool,
             painter: QPainter
             ) -> None:
        monospace_font = assets.get_font(assets.ScrutinyFont.Monospaced)
        orientation = cast(Qt.Orientation, self._cmb_orientation.currentData())
        bounding_rect = self.boundingRect()
        border_size = min(_Dims.BORDER_RATIO * min(bounding_rect.width(), bounding_rect.height()), _Dims.BORDER_MAX_PX)
        cursor_border_size = min(border_size, _Dims.CURSOR_BORDER_MAX_PX)

        self._slide_zone_pen.setWidthF(border_size)
        self._major_tick_pen.setWidthF(min(border_size, _Dims.MAJOR_TICK_MAX_THICKNESS_PX))

        min_val = self._txt_min_val.get_float_value()
        max_val = self._txt_max_val.get_float_value()

        major_ticks = self._spn_major_ticks.value()
        minor_ticks = self._spn_minor_ticks.value()
        label_config = self._label_format_config_widget.get_config()
        label_size_ratio = float(self._sld_label_size.value()) / 100.0

        ratio = self._get_val_ratio(values['val'])

        if orientation == Qt.Orientation.Vertical:
            label_height = float(0)
            if major_ticks >= 2:
                label_height = label_size_ratio * bounding_rect.height() / float(major_ticks)

            cursor_x = float(0)
            cursor_w = bounding_rect.width() * _Dims.CURSOR_W_RATIO
            slide_zone_w = bounding_rect.width() * _Dims.SLIDE_ZONE_MIN_W_RATIO
            slide_zone_x = cursor_w / 2 - slide_zone_w / 2
            slide_zone_y = border_size / 2 + label_height / 2
            slide_zone_h = bounding_rect.height() - 2 * slide_zone_y
            cursor_h = min(cursor_w * _Dims.CURSOR_H_RATIO_TO_CURSOR_W, _Dims.CURSOR_H_MAX_PX)

            if major_ticks >= 2:
                major_tick_w = max(slide_zone_w * _Dims.MAJOR_TICK_LEN_RATIO, 2 * border_size)
                minor_tick_w = major_tick_w / 2
                major_tick_x1 = slide_zone_x + slide_zone_w + border_size / 2
                major_tick_x2 = major_tick_x1 + major_tick_w
                minor_tick_x1 = major_tick_x1
                minor_tick_x2 = minor_tick_x1 + minor_tick_w
                delta_major_tick = slide_zone_h / (major_ticks - 1)
                label_x = max(major_tick_x2, cursor_w) + _Dims.TEXT_LABEL_MARGIN_PX
                label_width = max(bounding_rect.right() - label_x, 0)

                for i in range(major_ticks):
                    painter.setPen(self._major_tick_pen)
                    major_tick_y = slide_zone_y + i * delta_major_tick
                    painter.drawLine(QPointF(major_tick_x1, major_tick_y), QPointF(major_tick_x2, major_tick_y))

                    if minor_ticks > 0 and i < major_ticks - 1:
                        painter.setPen(self._minor_tick_pen)
                        for j in range(minor_ticks):
                            minor_tick_y = major_tick_y + (j + 1) * delta_major_tick / (minor_ticks + 1)
                            painter.drawLine(QPointF(minor_tick_x1, minor_tick_y), QPointF(minor_tick_x2, minor_tick_y))

                    label_topleft_y = major_tick_y - label_height / 2
                    tick_label_rect = QRectF(
                        QPointF(label_x, label_topleft_y),
                        QSizeF(label_width, label_height)
                    )

                    if edit_mode:
                        painter.setPen(self._edit_border_pen)
                        painter.drawRect(tick_label_rect)

                    if max_val is not None and min_val is not None:
                        value_range = max_val - min_val
                        delta_val = value_range / (major_ticks - 1)
                        tick_val = max_val - delta_val * i
                        tick_text = NumericalTextDisplay.format_numerical_value(label_config, tick_val)
                        text_align = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                        NumericalTextDisplay.apply_font_size(monospace_font, label_config, tick_text, tick_label_rect)
                        painter.setFont(monospace_font)
                        painter.setPen(HMITheme.Color.text())
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawText(tick_label_rect, tick_text, text_align)

            painter.setPen(self._slide_zone_pen)
            painter.setBrush(self._slide_zone_brush)

            self._slide_zone_rect = QRectF(
                QPointF(slide_zone_x, slide_zone_y),
                QSizeF(slide_zone_w, slide_zone_h))
            painter.drawRect(self._slide_zone_rect)

            self._cursor.set_border_size(cursor_border_size)
            self._cursor.set_size(QSizeF(cursor_w, cursor_h))   # Need to be set before _get_vertical_cursor_y()
            if ratio is not None:
                cursor_y = self._get_vertical_cursor_y(ratio)
                self._cursor.setPos(QPointF(cursor_x, cursor_y))
                self._cursor.set_enabled(True)
            else:
                self._cursor.set_enabled(False)
            self._cursor.update()

        elif orientation == Qt.Orientation.Horizontal:
            # Horizontal slider drawing is tricky because labels grow horizontally
            # We use the cursor height as a base.
            # Estimate cursor length based on label max label width, then make sure cursor has minimum size,
            # then recompute the label height and position of everything

            label_width = float(0)
            major_tick_h = float(0)
            minor_tick_h = float(0)
            label_height = float(0)
            label_margin = float(0)

            cursor_y = float(0)

            if major_ticks >= 2:    # Has labels
                # Compute ideal label height to take all the width. May be too big, we will fix later.
                label_width = label_size_ratio * bounding_rect.width() / float(major_ticks)
                monospace_font.setPixelSize(12)
                single_char_rect = QFontMetrics(monospace_font).boundingRect("a")
                font_h2w_ratio = float(single_char_rect.height()) / single_char_rect.width()

                label_max_char = NumericalTextDisplay.max_char_count(label_config)
                label_height = label_width / label_max_char * font_h2w_ratio
                major_tick_h = min(bounding_rect.height() * _Dims.MAJOR_TICK_LEN_RATIO, _Dims.MAJOR_TICK_MAX_LEN_PX)
                minor_tick_h = major_tick_h / 2
                label_margin = _Dims.TEXT_LABEL_MARGIN_PX

            # If label height is too big, cursor will be too small. Make sure the cursor is visible then fix label heights
            cursor_h = (bounding_rect.height() - label_height - minor_tick_h - label_margin)
            cursor_h = max(cursor_h, _Dims.CURSOR_MIN_W_PX)
            cursor_w = min(cursor_h * _Dims.CURSOR_H_RATIO_TO_CURSOR_W, _Dims.CURSOR_H_MAX_PX)
            label_height = min(label_height, bounding_rect.height() - cursor_h - major_tick_h - label_margin)

            # We have cursor and label height. We can compute the position of everything now.
            slide_zone_h = cursor_h * _Dims.SLIDE_ZONE_MIN_W_RATIO / _Dims.CURSOR_W_RATIO
            slide_zone_y = cursor_h / 2 - slide_zone_h / 2
            slide_zone_x = max(border_size / 2 + label_width / 2, cursor_w / 2 + border_size / 2)
            slide_zone_w = bounding_rect.width() - 2 * slide_zone_x

            if major_ticks >= 2:    # We have labels and ticks
                major_tick_y1 = slide_zone_y + slide_zone_h + border_size / 2
                major_tick_y2 = major_tick_y1 + major_tick_h
                minor_tick_y1 = major_tick_y1
                minor_tick_y2 = minor_tick_y1 + minor_tick_h
                delta_major_tick = slide_zone_w / (major_ticks - 1)
                label_y = max(major_tick_y2, cursor_h + cursor_border_size) + _Dims.TEXT_LABEL_MARGIN_PX
                label_max_height = max(bounding_rect.bottom() - label_y, 0)
                label_height = min(label_height, label_max_height)

                for i in range(major_ticks):
                    painter.setPen(self._major_tick_pen)
                    major_tick_x = slide_zone_x + i * delta_major_tick
                    painter.drawLine(QPointF(major_tick_x, major_tick_y1), QPointF(major_tick_x, major_tick_y2))

                    if minor_ticks > 0 and i < major_ticks - 1:
                        painter.setPen(self._minor_tick_pen)
                        for j in range(minor_ticks):
                            minor_tick_x = major_tick_x + (j + 1) * delta_major_tick / (minor_ticks + 1)
                            painter.drawLine(QPointF(minor_tick_x, minor_tick_y1), QPointF(minor_tick_x, minor_tick_y2))

                    label_topleft_x = major_tick_x - label_width / 2

                    tick_label_rect = QRectF(
                        QPointF(label_topleft_x, label_y),
                        QSizeF(label_width, label_height)
                    )

                    if edit_mode:
                        painter.setPen(self._edit_border_pen)
                        painter.drawRect(tick_label_rect)

                    if max_val is not None and min_val is not None:
                        value_range = max_val - min_val
                        delta_val = value_range / (major_ticks - 1)
                        tick_val = min_val + delta_val * i
                        tick_text = NumericalTextDisplay.format_numerical_value(label_config, tick_val)
                        text_align = Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter
                        NumericalTextDisplay.apply_font_size(monospace_font, label_config, tick_text, tick_label_rect)
                        painter.setFont(monospace_font)
                        painter.setPen(HMITheme.Color.text())
                        painter.setBrush(Qt.BrushStyle.NoBrush)
                        painter.drawText(tick_label_rect, tick_text, text_align)

            painter.setPen(self._slide_zone_pen)
            painter.setBrush(self._slide_zone_brush)

            self._slide_zone_rect = QRectF(
                QPointF(slide_zone_x, slide_zone_y),
                QSizeF(slide_zone_w, slide_zone_h))
            painter.drawRect(self._slide_zone_rect)

            self._cursor.set_border_size(cursor_border_size)
            self._cursor.set_size(QSizeF(cursor_w, cursor_h))
            if ratio is not None:
                cursor_x = self._get_horizontal_cursor_x(ratio)
                self._cursor.setPos(QPointF(cursor_x, cursor_y))
                self._cursor.set_enabled(True)
            else:
                self._cursor.set_enabled(False)
            self._cursor.update()

    def left_mouse_down(self, pos: QPointF) -> Qt.CursorShape:
        if not self._cursor.is_enabled():
            return Qt.CursorShape.ArrowCursor

        cursor_rect = QRectF(self._cursor.pos(), self._cursor.get_size())
        if not cursor_rect.contains(pos):
            return Qt.CursorShape.ArrowCursor

        self._dragging_val = self._val_from_pos(pos)
        orientation = self.get_orientation()
        if orientation == Qt.Orientation.Horizontal:
            return Qt.CursorShape.SizeHorCursor
        elif orientation == Qt.Orientation.Vertical:
            return Qt.CursorShape.SizeVerCursor
        else:
            raise NotImplementedError("Unknown orientation")

    def left_mouse_up(self, pos: QPointF | None) -> Qt.CursorShape:
        self._dragging_val = None
        return Qt.CursorShape.ArrowCursor

    def mouse_move(self, pos: QPointF) -> Qt.CursorShape:
        orientation = self.get_orientation()
        if orientation == Qt.Orientation.Horizontal:
            resize_cursor = Qt.CursorShape.SizeHorCursor
        elif orientation == Qt.Orientation.Vertical:
            resize_cursor = Qt.CursorShape.SizeVerCursor
        else:
            raise NotImplementedError("Unknown orientation")

        if self._dragging_val is None:
            if not self._cursor.is_enabled():
                return Qt.CursorShape.ArrowCursor
            cursor_rect = QRectF(self._cursor.pos(), self._cursor.get_size())
            if not cursor_rect.contains(pos):
                return Qt.CursorShape.ArrowCursor

            return resize_cursor
        else:
            v = self._val_from_pos(pos)
            if v is not None:
                self._dragging_val = v
                self.write_value_slot('val', v)
            return resize_cursor

    def get_implementation_config_dict(self) -> Dict[str, Any]:
        min_val = self._txt_min_val.get_float_value()
        max_val = self._txt_max_val.get_float_value()
        return {
            'orientation': cast(Qt.Orientation, self._cmb_orientation.currentData()).value,
            'min_val': min_val if min_val is not None else 0.0,
            'max_val': max_val if max_val is not None else 100.0,
            'label_size_percent': self._sld_label_size.value(),
            'major_ticks': self._spn_major_ticks.value(),
            'minor_ticks': self._spn_minor_ticks.value(),
            'label_config': self._label_format_config_widget.get_config().to_dict()
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        valid_orientation = False
        valid_min_val = False
        valid_max_val = False
        valid_label_size_percent = False
        valid_major_ticks = False
        valid_minor_ticks = False
        valid_label_config = False

        key = 'orientation'
        if key in d and isinstance(d[key], int):
            valid_orientation = deserialize_combobox_val(d[key], Qt.Orientation, self._cmb_orientation)

        key = 'min_val'
        if key in d and isinstance(d[key], (int, float)):
            self._txt_min_val.set_float_value(float(d[key]))
            valid_min_val = True

        key = 'max_val'
        if key in d and isinstance(d[key], (int, float)):
            self._txt_max_val.set_float_value(float(d[key]))
            valid_max_val = True

        key = 'label_size_percent'
        if key in d and isinstance(d[key], int):
            self._sld_label_size.setValue(d[key])
            valid_label_size_percent = (d[key] == self._sld_label_size.value())

        key = 'major_ticks'
        if key in d and isinstance(d[key], int):
            self._spn_major_ticks.setValue(d[key])
            valid_major_ticks = (d[key] == self._spn_major_ticks.value())

        key = 'minor_ticks'
        if key in d and isinstance(d[key], int):
            self._spn_minor_ticks.setValue(d[key])
            valid_minor_ticks = (d[key] == self._spn_minor_ticks.value())

        key = 'label_config'
        if key in d and isinstance(d[key], dict):
            label_config, valid_label_config = NumberFormattingConfig.from_dict(d[key])
            self._label_format_config_widget.apply_config(label_config)

        if not valid_orientation:
            self._logger.warning('Invalid orientation value')
        if not valid_min_val:
            self._logger.warning('Invalid minimum value')
        if not valid_max_val:
            self._logger.warning('Invalid maximum value')
        if not valid_label_size_percent:
            self._logger.warning('Invalid label size percentage')
        if not valid_major_ticks:
            self._logger.warning('Invalid major ticks value')
        if not valid_minor_ticks:
            self._logger.warning('Invalid minor ticks value')
        if not valid_label_config:
            self._logger.warning('Invalid label configuration')

        return (
            valid_orientation
            and valid_min_val
            and valid_max_val
            and valid_label_size_percent
            and valid_major_ticks
            and valid_minor_ticks
            and valid_label_config
        )


# endregion
