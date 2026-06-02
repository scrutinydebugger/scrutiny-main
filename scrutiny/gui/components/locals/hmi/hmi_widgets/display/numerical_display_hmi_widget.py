#    numerical_display_hmi_widget.py
#        An HMI widget that display a numerical value as text. Will select the right font
#        for the given rect
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['NumericalDisplayHMIWidget', 'NumberFormattingConfig', 'NumericalTextDisplayStateDict']

from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget, QGroupBox

from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui import assets
from scrutiny.tools.typing import *

from scrutiny.gui.components.locals.hmi.common.numerical_text_display import (
    NumericalTextDisplay, NumericalTextDisplayStateDict, NumberFormattingConfig
)
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme


class NumericalDisplayHMIWidget(BaseHMIWidget):

    _UNIQUE_NAME = 'numerical_display'
    _DISPLAY_NAME = 'Numerical Display'
    _ICON = assets.Icons.HMITextDisplay

    _numerical_display: NumericalTextDisplay
    _config_widget: QWidget

    def __init__(self, app: AbstractComponentAppInterface) -> None:
        super().__init__(app)
        self.declare_value_slot('val', 'Value', tooltip="The value to display as a number")

        self._config_widget = QWidget()
        self._numerical_display = NumericalTextDisplay(self)
        self._numerical_display.set_border_width(4)
        config_layout = QVBoxLayout(self._config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        gb = QGroupBox("Formatting")
        gb_layout = QVBoxLayout(gb)
        gb_layout.addWidget(self._numerical_display.get_number_format_config_widget())
        config_layout.addWidget(gb)
        self._numerical_display.set_text_color(HMITheme.Color.text())

        self._numerical_display.signals.config_changed.connect(self._config_changed_slot)

    def _config_changed_slot(self) -> None:
        self.update()
        self.invalidate_save()

# region Getters and Setters
    def set_border_width(self, width: float) -> None:
        self._numerical_display.set_border_width(width)

    def set_border_color(self, color: QColor) -> None:
        self._numerical_display.set_border_color(color)

    def set_text_color(self, color: QColor) -> None:
        self._numerical_display.set_text_color(color)

    def set_background_color(self, color: QColor) -> None:
        self._numerical_display.set_background_color(color)

    def set_val(self, val: Union[float, int, bool, str]) -> None:
        self._numerical_display.set_val(val)

    def set_alignment(self, alignment: Qt.AlignmentFlag) -> None:
        self._numerical_display.set_alignment(alignment)

    def set_number_formatting_config(self, config: NumberFormattingConfig) -> None:
        self._numerical_display.set_number_formatting_config(config)

    def get_border_width(self) -> float:
        return self._numerical_display.get_border_width()

    def get_border_color(self) -> QColor:
        return self._numerical_display.get_border_color()

    def get_text_color(self) -> QColor:
        return self._numerical_display.get_text_color()

    def get_background_color(self) -> QColor:
        return self._numerical_display.get_background_color()

    def get_val(self) -> Union[float, int, bool, str]:
        return self._numerical_display.get_val()

    def get_alignment(self) -> Qt.AlignmentFlag:
        return self._numerical_display.get_alignment()

    def get_number_formatting_config(self) -> NumberFormattingConfig:
        return self._numerical_display.get_number_formatting_config()
# endregion

# region Override

    @classmethod
    def default_size(cls) -> QSize:
        return QSize(128, 64)

    def min_height(self) -> int:
        return 32

    def min_width(self) -> int:
        return 64

    def get_config_widget(self) -> QWidget:
        return self._config_widget

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             edit_mode: bool,
             painter: QPainter
             ) -> None:
        val = values['val']

        if val is None:
            self._numerical_display.set_val("N/A")
            self._numerical_display.set_alignment(Qt.AlignmentFlag.AlignCenter)
        else:
            self._numerical_display.set_val(val)
            self._numerical_display.set_alignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight)

        self._numerical_display.set_size(self.boundingRect().size().toSize())
        self._numerical_display.update()

    def get_implementation_config_dict(self) -> Dict[str, Any]:
        return {
            'display': self._numerical_display.get_state_dict()
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        valid_display = False
        if 'display' in d and isinstance(d['display'], dict):
            valid_display = self._numerical_display.set_state_dict(cast(NumericalTextDisplayStateDict, d['display']))

        if not valid_display:
            self._logger.warning("Invalid numerical display configuration")

        return valid_display

# endregion
