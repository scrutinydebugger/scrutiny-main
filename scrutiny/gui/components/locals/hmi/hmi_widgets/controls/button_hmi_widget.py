#    button_hmi_widget.py
#        An HMI widget acting as a push button. Write a boolean value to a watchable. The
#        button can be momentary or toggle
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['ButtonHMIWidget']

import enum
import math

from PySide6.QtGui import QPainter, QPainterPath, QPen, QBrush
from PySide6.QtCore import QSize, Qt, QPointF, QRectF, QSizeF
from PySide6.QtWidgets import QGraphicsSceneMouseEvent, QVBoxLayout, QWidget, QGroupBox, QComboBox, QFormLayout, QLineEdit

from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui.components.locals.hmi.common.serialization import deserialize_combobox_val
from scrutiny.gui.components.locals.hmi.common.hmi_colors import create_color_combobox, HMIColor
from scrutiny.gui.components.locals.hmi.common.text import set_font_size_to_fit_rect
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny.gui import assets
from scrutiny.tools.typing import *

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory


class _Dims:
    EDGE_WIDTH = 0.05
    EDGE_WIDTH_MAX_PX = 3
    PERSPECTIVE_WIDTH = 0.075
    PERSPECTIVE_WIDTH_MAX_PX = 6
    RADIUS_PX = 3
    ROUND_CORNER_DELTA = RADIUS_PX * (1 - math.cos(math.pi / 4))
    TEXT_MARGIN_RATIO = 0.1
    TEXT_MARGIN_MAX_PX = 10


class ButtonType(enum.Enum):
    MOMENTARY = 1
    TOGGLE = 2


class ButtonHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Control
    _UNIQUE_NAME = 'button'
    _DISPLAY_NAME = 'Button'
    _ICON = assets.Icons.HMIButton

    _cmb_button_type: QComboBox
    _config_widget: QWidget

    _cmb_color_active: QComboBox
    _cmb_color_inactive: QComboBox
    _txt_label_active: QLineEdit
    _txt_label_inactive: QLineEdit

    _is_pressed: bool
    _text_pen: QPen

    def __init__(self, app: AbstractComponentAppInterface) -> None:
        super().__init__(app)
        self.declare_value_slot('val', 'Value', allow_constant=False)
        self._is_pressed = False
        self._text_pen = QPen()
        self._text_pen.setColor(HMITheme.Color.text())

        self._config_widget = QWidget()
        self._cmb_button_type = QComboBox()

        self._cmb_color_active = create_color_combobox()
        self._cmb_color_inactive = create_color_combobox()
        self._txt_label_active = QLineEdit()
        self._txt_label_inactive = QLineEdit()

        self._cmb_button_type.addItem("Momentary", ButtonType.MOMENTARY)
        self._cmb_button_type.addItem("Toggle", ButtonType.TOGGLE)

        config_layout = QVBoxLayout(self._config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        gb_config = QGroupBox("Configuration")
        gb_config_layout = QFormLayout(gb_config)
        gb_config_layout.addRow("Type", self._cmb_button_type)

        gb_active = QGroupBox("Active")
        gb_active_layout = QFormLayout(gb_active)
        gb_active_layout.addRow("Label", self._txt_label_active)
        gb_active_layout.addRow("Color", self._cmb_color_active)
        gb_inactive = QGroupBox("Inactive")
        gb_inactive_layout = QFormLayout(gb_inactive)
        gb_inactive_layout.addRow("Label", self._txt_label_inactive)
        gb_inactive_layout.addRow("Color", self._cmb_color_inactive)

        config_layout.addWidget(gb_config)
        config_layout.addWidget(gb_active)
        config_layout.addWidget(gb_inactive)

        self._cmb_button_type.setCurrentIndex(self._cmb_button_type.findData(ButtonType.MOMENTARY))
        self._txt_label_active.setText("ON")
        self._cmb_color_active.setCurrentIndex(self._cmb_color_active.findData(HMIColor.GOOD))
        self._txt_label_inactive.setText("OFF")
        self._cmb_color_inactive.setCurrentIndex(self._cmb_color_inactive.findData(HMIColor.INACTIVE))

        self._cmb_button_type.currentIndexChanged.connect(self._config_changed_slot)
        self._cmb_color_active.currentIndexChanged.connect(self._config_changed_slot)
        self._cmb_color_inactive.currentIndexChanged.connect(self._config_changed_slot)
        self._txt_label_active.textChanged.connect(self._config_changed_slot)
        self._txt_label_inactive.textChanged.connect(self._config_changed_slot)

    def destroy(self) -> None:
        self._cmb_button_type.currentIndexChanged.disconnect()
        self._cmb_color_active.currentIndexChanged.disconnect()
        self._cmb_color_inactive.currentIndexChanged.disconnect()
        self._txt_label_active.textChanged.disconnect()
        self._txt_label_inactive.textChanged.disconnect()

        return super().destroy()

    def _config_changed_slot(self) -> None:
        self.update()

    def _write_val(self, val: bool) -> None:
        # There will be (almost) no visual glitches during the duration of the write.
        # The BaseHMIWidget has a mechanism to override the draw value while the write is in progress
        self.write_value_slot('val', val)

# region Getters and Setters

    def get_button_type(self) -> ButtonType:
        return cast(ButtonType, self._cmb_button_type.currentData())

    def set_button_type(self, btn_type: ButtonType) -> None:
        index = self._cmb_button_type.findData(btn_type)
        if index >= 0:
            self._cmb_button_type.setCurrentIndex(index)

    def get_label_active(self) -> str:
        return self._txt_label_active.text()

    def set_label_active(self, label: str) -> None:
        self._txt_label_active.setText(label)

    def get_color_active(self) -> HMIColor:
        return cast(HMIColor, self._cmb_color_active.currentData())

    def set_color_active(self, color: HMIColor) -> None:
        index = self._cmb_color_active.findData(color)
        if index >= 0:
            self._cmb_color_active.setCurrentIndex(index)

    def get_label_inactive(self) -> str:
        return self._txt_label_inactive.text()

    def set_label_inactive(self, label: str) -> None:
        self._txt_label_inactive.setText(label)

    def get_color_inactive(self) -> HMIColor:
        return cast(HMIColor, self._cmb_color_inactive.currentData())

    def set_color_inactive(self, color: HMIColor) -> None:
        index = self._cmb_color_inactive.findData(color)
        if index >= 0:
            self._cmb_color_inactive.setCurrentIndex(index)

# endregion

# region Override

    @classmethod
    def default_size(cls) -> QSize:
        return QSize(48, 48)

    def min_height(self) -> int:
        return 16

    def min_width(self) -> int:
        return 16

    def get_config_widget(self) -> QWidget:
        return self._config_widget

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        print("move")
        return super().mouseMoveEvent(event)

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             edit_mode: bool,
             painter: QPainter
             ) -> None:

        is_valid = (values['val'] is not None)
        is_active = False
        if is_valid:
            is_active = bool(values['val'])

        bounding_rect = self.boundingRect()
        border_width = min(min(bounding_rect.width(), bounding_rect.height()) * _Dims.EDGE_WIDTH, _Dims.EDGE_WIDTH_MAX_PX)

        border_pen = QPen()
        border_pen.setWidthF(border_width)
        border_pen.setColor(HMITheme.Color.frame_border())

        brush = QBrush()
        brush.setStyle(Qt.BrushStyle.SolidPattern)

        if not is_valid:
            text = ""
            brush.setColor(HMIColor.INACTIVE.to_qcolor())
        else:
            if is_active:
                brush.setColor(cast(HMIColor, self._cmb_color_active.currentData()).to_qcolor())
                text = self._txt_label_active.text()
            else:
                brush.setColor(cast(HMIColor, self._cmb_color_inactive.currentData()).to_qcolor())
                text = self._txt_label_inactive.text()

        painter.setPen(border_pen)
        painter.setBrush(brush)

        perspective_delta = min(min(bounding_rect.width(), bounding_rect.height()) * _Dims.PERSPECTIVE_WIDTH, _Dims.PERSPECTIVE_WIDTH_MAX_PX)
        text_margin_v = min((bounding_rect.height() - border_width) * _Dims.TEXT_MARGIN_RATIO, _Dims.TEXT_MARGIN_MAX_PX)
        text_margin_h = min((bounding_rect.width() - border_width) * _Dims.TEXT_MARGIN_RATIO, _Dims.TEXT_MARGIN_MAX_PX)
        rect_size = QSizeF(bounding_rect.width() - perspective_delta - border_width, bounding_rect.height() - border_width - perspective_delta)

        half_border_width = border_width / 2
        bottom_rect = QRectF(
            QPointF(half_border_width, half_border_width + perspective_delta),
            rect_size
        )

        top_rect = QRectF(
            QPointF(half_border_width + perspective_delta, half_border_width),
            rect_size
        )

        if self._is_pressed:
            painter.drawRoundedRect(bottom_rect, _Dims.RADIUS_PX, _Dims.RADIUS_PX)
            text_rect = QRectF(
                bottom_rect.topLeft() + QPointF(text_margin_h, text_margin_v),
                bottom_rect.size() - QSizeF(2 * text_margin_h, 2 * text_margin_v)
            )

            painter.setPen(self._text_pen)
        else:
            painter.drawRoundedRect(bottom_rect, _Dims.RADIUS_PX, _Dims.RADIUS_PX)
            p1 = QPointF(half_border_width + _Dims.ROUND_CORNER_DELTA, half_border_width + perspective_delta + _Dims.ROUND_CORNER_DELTA)
            p2 = QPointF(half_border_width + perspective_delta + _Dims.ROUND_CORNER_DELTA, half_border_width + _Dims.ROUND_CORNER_DELTA)
            delta_bl = QPointF(0, rect_size.height() - 2 * _Dims.ROUND_CORNER_DELTA)
            delta_br = QPointF(rect_size.width() - 2 * _Dims.ROUND_CORNER_DELTA, rect_size.height() - 2 * _Dims.ROUND_CORNER_DELTA)
            painter.drawLine(p1, p2)
            painter.drawLine(p1 + delta_bl, p2 + delta_bl)
            painter.drawLine(p1 + delta_br, p2 + delta_br)
            painter.drawRoundedRect(top_rect, _Dims.RADIUS_PX, _Dims.RADIUS_PX)

            text_rect = QRectF(
                top_rect.topLeft() + QPointF(text_margin_h, text_margin_v),
                top_rect.size() - QSizeF(2 * text_margin_h, 2 * text_margin_v)
            )

        font = painter.font()
        set_font_size_to_fit_rect(font, text, text_rect)
        painter.setFont(font)
        painter.setPen(self._text_pen)
        painter.drawText(text_rect, text, Qt.AlignmentFlag.AlignCenter)

    def get_implementation_config_dict(self) -> Dict[str, Any]:
        return {
            'btn_type': cast(ButtonType, self._cmb_button_type.currentData()).value,
            'label_active': self._txt_label_active.text(),
            'color_active': cast(HMIColor, self._cmb_color_active.currentData()).value,
            'label_inactive': self._txt_label_inactive.text(),
            'color_inactive': cast(HMIColor, self._cmb_color_inactive.currentData()).value,
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        valid_button_type = False
        valid_label_active = False
        valid_color_active = False
        valid_label_inactive = False
        valid_color_inactive = False

        if 'btn_type' in d and isinstance(d['btn_type'], int):
            valid_button_type = deserialize_combobox_val(d['btn_type'], ButtonType, self._cmb_button_type)

        if 'label_active' in d and isinstance(d['label_active'], str):
            self._txt_label_active.setText(d['label_active'])
            valid_label_active = True

        if 'color_active' in d and isinstance(d['color_active'], str):
            valid_color_active = deserialize_combobox_val(d['color_active'], HMIColor, self._cmb_color_active)

        if 'label_inactive' in d and isinstance(d['label_inactive'], str):
            self._txt_label_inactive.setText(d['label_inactive'])
            valid_label_inactive = True

        if 'color_inactive' in d and isinstance(d['color_inactive'], str):
            valid_color_inactive = deserialize_combobox_val(d['color_inactive'], HMIColor, self._cmb_color_inactive)

        if not valid_button_type:
            self._logger.warning("Invalid button type")
        if not valid_label_active:
            self._logger.warning("Invalid active label")
        if not valid_color_active:
            self._logger.warning("Invalid active color")
        if not valid_label_inactive:
            self._logger.warning("Invalid inactive label")
        if not valid_color_inactive:
            self._logger.warning("Invalid inactive color")

        return (
            valid_button_type
            and valid_label_active
            and valid_color_active
            and valid_label_inactive
            and valid_color_inactive
        )

    def left_mouse_down(self, pos: QPointF) -> Qt.CursorShape:
        self._is_pressed = True
        if self.get_button_type() == ButtonType.MOMENTARY:
            self._write_val(True)
        elif self.get_button_type() == ButtonType.TOGGLE:
            last_val = self.get_vslot_val_by_name('val')
            if last_val is not None:
                new_val = not bool(last_val)
                self._write_val(new_val)
        else:
            raise NotImplementedError("Unknown button type")    # pragma: no cover

        self.update()
        return Qt.CursorShape.PointingHandCursor

    def left_mouse_up(self, pos: Optional[QPointF]) -> Qt.CursorShape:
        if self.get_button_type() == ButtonType.MOMENTARY:
            self._write_val(False)
        elif self.get_button_type() == ButtonType.TOGGLE:
            pass
        else:
            raise NotImplementedError("Unknown button type")    # pragma: no cover
        self._is_pressed = False
        self.update()
        return Qt.CursorShape.PointingHandCursor

    def mouse_move(self, pos: QPointF) -> Qt.CursorShape:
        return Qt.CursorShape.PointingHandCursor

# endregion
