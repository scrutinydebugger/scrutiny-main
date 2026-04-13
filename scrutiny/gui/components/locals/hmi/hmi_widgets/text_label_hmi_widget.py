#    text_label_hmi_widget.py
#        A HMI widget that displays a value in text form. Font size selected to fill the draw
#        zone.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['TextLabelHMIWidget']

from PySide6.QtGui import QPainter
from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QVBoxLayout, QWidget


from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets
from scrutiny.tools.typing import *

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory
from scrutiny.gui.components.locals.hmi.common.numerical_text_display import NumericalTextDisplay

if TYPE_CHECKING:
    from scrutiny.gui.components.locals.hmi.hmi_component import HMIComponent


class TextLabelHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Basics
    _NAME = 'Text Display'
    _ICON = assets.Icons.CSV

    _MARGIN = 4

    _numerical_display: NumericalTextDisplay
    _config_widget: QWidget

    def __init__(self, hmi_component: "HMIComponent") -> None:
        super().__init__(hmi_component)
        self.declare_value_slot('val', 'Value')
        self._text_color = scrutiny_get_theme().palette().text().color()

        self._config_widget = QWidget()
        self._numerical_display = NumericalTextDisplay(self)
        layout = QVBoxLayout(self._config_widget)
        layout.addWidget(self._numerical_display.get_config_widget())
        self._numerical_display.set_text_color(scrutiny_get_theme().palette().text().color())
        self._numerical_display.set_alignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)

        self._numerical_display.signals.config_changed.connect(self.update)

    def get_config_widget(self) -> QWidget | None:
        return self._config_widget

    def draw(self,
             configured: bool,
             values: Dict[str, Union[float, int, bool, None]],
             draw_zone_size: QSize,
             painter: QPainter
             ) -> None:

        val = None
        if configured:
            val = values['val']
        val_or_text: Union[str, bool, int, float] = "N/A"
        if val is not None:
            val_or_text = val

        self._numerical_display.set_size(draw_zone_size)
        self._numerical_display.set_val(val_or_text)
        self._numerical_display.update()
