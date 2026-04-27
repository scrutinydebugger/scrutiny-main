#    line_hmi_widget.py
#        A graphical only HMI widget that draws a line
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['LineHMIWidget']

from PySide6.QtGui import QPainter
from PySide6.QtCore import Qt, QPointF
from PySide6.QtWidgets import QVBoxLayout, QWidget, QComboBox


from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui import assets
from scrutiny.tools.typing import *

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory
from scrutiny.gui.components.locals.hmi.common.pen_config import PenConfigWidget

if TYPE_CHECKING:
    from scrutiny.gui.components.locals.hmi.hmi_component import HMIComponent


class LineHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Graphic
    _UNIQUE_NAME = 'line'
    _DISPLAY_NAME = 'Line'
    _ICON = assets.Icons.HMILine

    _config_widget: QWidget
    _cmb_direction: QComboBox
    _pen_config: PenConfigWidget

    def __init__(self, hmi_component: "HMIComponent") -> None:
        super().__init__(hmi_component)

        self._config_widget = QWidget()
        self._pen_config = PenConfigWidget()
        self._pen_config.set_width(5)

        layout = QVBoxLayout(self._config_widget)
        self._cmb_direction = QComboBox()
        self._cmb_direction.addItem("Vertical", Qt.Orientation.Vertical)
        self._cmb_direction.addItem("Horizontal", Qt.Orientation.Horizontal)
        self._cmb_direction.setCurrentIndex(self._cmb_direction.findData(Qt.Orientation.Horizontal))

        layout.addWidget(self._pen_config)
        layout.addWidget(self._cmb_direction)

        self._pen_config.signals.changed.connect(self._update)
        self._cmb_direction.currentIndexChanged.connect(self._update)

    def _update(self, *args: Any, **kwargs: Any) -> None:
        self.update()

    def get_config_widget(self) -> QWidget | None:
        return self._config_widget

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             painter: QPainter
             ) -> None:
        orientation = cast(Qt.Orientation, self._cmb_direction.currentData())
        bounding_rect = self.boundingRect()
        pen = self._pen_config.get_pen()
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        if orientation == Qt.Orientation.Horizontal:
            line_w = min(pen.widthF(), bounding_rect.width())
            pen.setWidthF(line_w)
            p1 = QPointF(0, bounding_rect.height() / 2)
            p2 = QPointF(bounding_rect.width(), bounding_rect.height() / 2)
        elif orientation == Qt.Orientation.Vertical:
            line_h = min(pen.widthF(), bounding_rect.height())
            pen.setWidthF(line_h)
            p1 = QPointF(bounding_rect.width() / 2, 0)
            p2 = QPointF(bounding_rect.width() / 2, bounding_rect.height())
        else:
            raise NotImplementedError("Unknown orientation")

        painter.setPen(pen)
        painter.drawLine(p1, p2)
