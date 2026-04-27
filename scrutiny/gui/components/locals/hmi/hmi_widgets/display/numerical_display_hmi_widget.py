#    numerical_display_hmi_widget.py
#        An HMI widget that display a numerical value as text. Will select the right font
#        for the given rect
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['NumericalDisplayHMIWidget']

from PySide6.QtGui import QPainter
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget, QGroupBox


from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui import assets
from scrutiny.tools.typing import *

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory
from scrutiny.gui.components.locals.hmi.common.numerical_text_display import NumericalTextDisplay
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme

if TYPE_CHECKING:
    from scrutiny.gui.components.locals.hmi.hmi_component import HMIComponent


class NumericalDisplayHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Display
    _UNIQUE_NAME = 'numerical_display'
    _DISPLAY_NAME = 'Numerical Display'
    _ICON = assets.Icons.HMITextDisplay

    _numerical_display: NumericalTextDisplay
    _config_widget: QWidget

    def __init__(self, hmi_component: "HMIComponent") -> None:
        super().__init__(hmi_component)
        self.declare_value_slot('val', 'Value')

        self._config_widget = QWidget()
        self._numerical_display = NumericalTextDisplay(self)
        self._numerical_display.set_border_width(4)
        config_layout = QVBoxLayout(self._config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        gb = QGroupBox("Formatting")
        gb_layout = QVBoxLayout(gb)
        gb_layout.addWidget(self._numerical_display.get_config_widget())
        config_layout.addWidget(gb)
        self._numerical_display.set_text_color(HMITheme.Color.text())

        self._numerical_display.signals.config_changed.connect(self._config_changed_slot)

    def _config_changed_slot(self) -> None:
        self.update()

    def get_config_widget(self) -> QWidget | None:
        return self._config_widget

    @classmethod
    def default_size(cls) -> QSize:
        return QSize(128, 64)

    def min_height(self) -> int:
        return 32

    def min_width(self) -> int:
        return 64

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
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
