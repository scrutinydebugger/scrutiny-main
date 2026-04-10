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


from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets
from scrutiny import tools
from scrutiny.tools.typing import *

if TYPE_CHECKING:
    from scrutiny.gui.components.locals.hmi.hmi_component import HMIComponent

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory


class TextLabelHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Basics
    _NAME = 'Text Display'
    _ICON = assets.Icons.CSV

    _text_color: QColor

    def __init__(self, hmi_component: "HMIComponent") -> None:
        super().__init__(hmi_component)
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

        painter.setPen(QColor(0, 0x66, 0))
        painter.setBrush(QColor(0, 0x66, 0))
        text_rect = QRect(QPoint(0, 0), draw_zone_size)
        painter.drawRect(text_rect)
        painter.setPen(self._text_color)
        painter.setPen(self._text_color)
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawText(text_rect, text, Qt.AlignmentFlag.AlignLeft)
