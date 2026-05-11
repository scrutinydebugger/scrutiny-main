
__all__ = ['ButtonHMIWidget']

import enum

from PySide6.QtGui import QPainter, QPen, QRadialGradient, QBrush, QColor
from PySide6.QtCore import QSize, Qt, QPointF
from PySide6.QtWidgets import QGraphicsSceneMouseEvent, QVBoxLayout, QWidget, QGroupBox, QComboBox, QFormLayout, QLineEdit

from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui.components.locals.hmi.common.serialization import deserialize_combobox_val
from scrutiny.gui import assets
from scrutiny.tools.typing import *

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory
from scrutiny import tools

class ButtonType(enum.Enum):
    MOMENTARY=1
    TOGGLE=2

class ButtonHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Control
    _UNIQUE_NAME = 'button'
    _DISPLAY_NAME = 'Button'
    _ICON = assets.Icons.HMIColorIndicator

    _cmb_button_type: QComboBox
    _config_widget: QWidget

    _is_pressed:bool

    def __init__(self, app: AbstractComponentAppInterface) -> None:
        super().__init__(app)
        self.declare_value_slot('val', 'Value')
        self._is_pressed = False

        self._config_widget = QWidget()
        self._cmb_button_type = QComboBox()

        self._cmb_button_type.addItem("Momentary", ButtonType.MOMENTARY)
        self._cmb_button_type.addItem("Toggle", ButtonType.TOGGLE)

        config_layout = QVBoxLayout(self._config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        gb = QGroupBox("Configuration")
        gb_layout = QFormLayout(gb)
        gb_layout.addRow("Type", self._cmb_button_type)

        config_layout.addWidget(gb)

        self._cmb_button_type.currentIndexChanged.connect(self._config_changed_slot)

    def destroy(self) -> None:
        self._cmb_button_type.currentIndexChanged.disconnect()

        return super().destroy()

    def _config_changed_slot(self) -> None:
        self.update()

    def _blink_timer_slot(self) -> None:
        self._blink_enable_flag = not self._blink_enable_flag
        self.update()

# region Getters and Setters

    def get_button_type(self) -> ButtonType:
        return cast(ButtonType, self._cmb_button_type.currentData())

    def set_button_type(self, btn_type: ButtonType) -> None:
        index = self._cmb_button_type.findData(btn_type)
        if index >= 0:
            self._cmb_button_type.setCurrentIndex(index)

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

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             edit_mode: bool,
             painter: QPainter
             ) -> None:

        if values['val'] is None:
            painter.setBrush(QColor("gray"))
        else:
            v = bool(values['val'])
            if self._is_pressed:
                painter.setBrush(QColor("green"))
            else:
                painter.setBrush(QColor("red"))
        painter.drawEllipse(self.boundingRect())


    def get_implementation_config_dict(self) -> Dict[str, Any]:
        return {
            'btn_type': cast(ButtonType, self._cmb_button_type.currentData()).value,
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        valid_button_type = False

        if 'btn_type' in d and isinstance(d['btn_type'], int):
            valid_button_type = deserialize_combobox_val(d['btn_type'], ButtonType, self._cmb_button_type)

        if not valid_button_type:
            self._logger.warning("Invalid button type")

        return (
            valid_button_type
        )

    def left_mouse_down(self, pos:QPointF) -> None:
        print(f"left_mouse_down : {pos}")
        self._is_pressed = True
        self.update()

    def left_mouse_up(self, pos:Optional[QPointF]) -> None:
        print(f"left_mouse_up : {pos}")
        self._is_pressed = False
        self.update()


# endregion
