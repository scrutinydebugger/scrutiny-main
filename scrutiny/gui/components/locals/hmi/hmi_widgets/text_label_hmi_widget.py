#    text_label_hmi_widget.py
#        A HMI widget that displays a value in text form. Font size selected to fill the draw
#        zone.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['TextLabelHMIWidget']

from PySide6.QtGui import QPainter, QColor
from PySide6.QtCore import QSize, QRect, QPoint, Qt

from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny import tools
from scrutiny.tools.typing import *


class TextLabelHMIWidget(BaseHMIWidget):

    _text_color: QColor

    def __init__(self, app_interface: AbstractComponentAppInterface) -> None:
        super().__init__(app_interface)
        self.declare_watchable_slot('val', 'Value', validator=None)
        self._text_color = scrutiny_get_theme().palette().text().color()

    def draw(self,
             configured: bool,
             values: Dict[str, Union[float, int, bool, None]],
             draw_zone_size: QSize,
             painter: QPainter
             ) -> None:

        val = values['val']
        if not configured or val is None:
            text = "N/A"
        else:
            if isinstance(val, float):
                text = str(tools.f2g(val))
            else:
                text = str(val)

        painter.setPen(self._text_color)
        text_rect = QRect(QPoint(0, 0), draw_zone_size)
        painter.drawText(text_rect, text, Qt.AlignmentFlag.AlignLeft)
