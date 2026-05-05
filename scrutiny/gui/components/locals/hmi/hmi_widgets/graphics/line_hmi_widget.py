#    line_hmi_widget.py
#        A graphical only HMI widget that draws a line
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['LineHMIWidget']

from PySide6.QtGui import QPainter, QPen
from PySide6.QtCore import Qt, QPointF
from PySide6.QtWidgets import QVBoxLayout, QWidget, QComboBox


from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui import assets
from scrutiny.tools.typing import *

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory
from scrutiny.gui.components.locals.hmi.common.pen_config import PenConfigWidget, PenConfigStateDict


class LineHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Graphic
    _UNIQUE_NAME = 'line'
    _DISPLAY_NAME = 'Line'
    _ICON = assets.Icons.HMILine

    _config_widget: QWidget
    _cmb_direction: QComboBox
    _pen_config: PenConfigWidget

    def __init__(self, app: AbstractComponentAppInterface) -> None:
        super().__init__(app)

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

# region Getters and Setters
    def set_border_pen(self, pen: QPen) -> None:
        self._pen_config.set_pen(pen)

    def get_border_pen(self) -> QPen:
        return self._pen_config.get_pen()
# endregion

# region Override
    def get_config_widget(self) -> Optional[QWidget]:
        return self._config_widget

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             edit_mode: bool,
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

    def get_implementation_config_dict(self) -> Dict[str, Any]:
        return {
            'border': self._pen_config.get_state_dict(),
            'direction': cast(Qt.Orientation, self._cmb_direction.currentData()).value
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        border_valid = False
        direction_valid = False

        if 'border' in d and isinstance(d['border'], dict):
            border_valid = self._pen_config.set_state_dict(cast(PenConfigStateDict, d['border']))

        if 'direction' in d and isinstance(d['direction'], int):
            index = self._cmb_direction.findData(Qt.Orientation(d['direction']))
            if index >= 0:
                self._cmb_direction.setCurrentIndex(index)
                direction_valid = True

        if not border_valid:
            self._logger.warning(f"Invalid border settings for HMI Widget: {self.get_display_name()}")

        if not direction_valid:
            self._logger.warning(f"Invalid direction for HMI Widget: {self.get_display_name()}")

        return direction_valid and border_valid
# endregion
