#    line_hmi_widget.py
#        A graphical only HMI widget that draws a line
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['LineHMIWidget']

from PySide6.QtGui import QPainter, QPen
from PySide6.QtCore import Qt, QPointF, QRectF, QSizeF
from PySide6.QtWidgets import QVBoxLayout, QWidget, QComboBox


from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui import assets
from scrutiny.tools.typing import *

from scrutiny.gui.components.locals.hmi.common.pen_config import PenConfigWidget, PenConfigStateDict
from scrutiny.gui.components.locals.hmi.common.hit_zones import RectHitZone


class LineHMIWidget(BaseHMIWidget):

    _UNIQUE_NAME = 'line'
    _DISPLAY_NAME = 'Line'
    _ICON = assets.Icons.HMILine

    _config_widget: QWidget
    _cmb_orientation: QComboBox
    _pen_config: PenConfigWidget

    def __init__(self, app: AbstractComponentAppInterface) -> None:
        super().__init__(app)
        self._config_widget = QWidget()
        self._pen_config = PenConfigWidget()
        self._pen_config.set_width(5)

        layout = QVBoxLayout(self._config_widget)
        self._cmb_orientation = QComboBox()
        self._cmb_orientation.addItem("Vertical", Qt.Orientation.Vertical)
        self._cmb_orientation.addItem("Horizontal", Qt.Orientation.Horizontal)
        self._cmb_orientation.setCurrentIndex(self._cmb_orientation.findData(Qt.Orientation.Horizontal))

        layout.addWidget(self._pen_config)
        layout.addWidget(self._cmb_orientation)

        self._pen_config.signals.changed.connect(self._update)
        self._cmb_orientation.currentIndexChanged.connect(self._update)

    def _update(self, *args: Any, **kwargs: Any) -> None:
        self.update()

# region Getters and Setters
    def set_border_pen(self, pen: QPen) -> None:
        self._pen_config.set_pen(pen)

    def get_border_pen(self) -> QPen:
        return self._pen_config.get_pen()

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        index = self._cmb_orientation.findData(orientation)
        if index >= 0:
            self._cmb_orientation.setCurrentIndex(index)

    def get_orientation(self) -> Qt.Orientation:
        return cast(Qt.Orientation, self._cmb_orientation.currentData())

# endregion

# region Override
    def get_config_widget(self) -> Optional[QWidget]:
        return self._config_widget

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             edit_mode: bool,
             painter: QPainter
             ) -> None:
        orientation = cast(Qt.Orientation, self._cmb_orientation.currentData())
        bounding_rect = self.boundingRect()
        pen = self._pen_config.get_pen()
        pen.setCapStyle(Qt.PenCapStyle.FlatCap)
        if orientation == Qt.Orientation.Horizontal:
            line_w = min(pen.widthF(), bounding_rect.width())
            pen.setWidthF(line_w)
            p1 = QPointF(0, bounding_rect.height() / 2)
            p2 = QPointF(bounding_rect.width(), bounding_rect.height() / 2)
            hit_zone = RectHitZone(QRectF(
                QPointF(p1.x(), p1.y() - line_w / 2),
                QSizeF(bounding_rect.width(), line_w),
            ))
        elif orientation == Qt.Orientation.Vertical:
            line_h = min(pen.widthF(), bounding_rect.height())
            pen.setWidthF(line_h)
            p1 = QPointF(bounding_rect.width() / 2, 0)
            p2 = QPointF(bounding_rect.width() / 2, bounding_rect.height())

            hit_zone = RectHitZone(QRectF(
                QPointF(p1.x() - line_h / 2, p1.y()),
                QSizeF(line_h, bounding_rect.height()),
            ))

        else:
            raise NotImplementedError("Unknown orientation")

        self._set_hit_zone(hit_zone)

        painter.setPen(pen)
        painter.drawLine(p1, p2)

    def get_implementation_config_dict(self) -> Dict[str, Any]:
        return {
            'border': self._pen_config.get_state_dict(),
            'orientation': cast(Qt.Orientation, self._cmb_orientation.currentData()).value
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        border_valid = False
        orientation_valid = False

        if 'border' in d and isinstance(d['border'], dict):
            border_valid = self._pen_config.set_state_dict(cast(PenConfigStateDict, d['border']))

        if 'orientation' in d and isinstance(d['orientation'], int):
            index = self._cmb_orientation.findData(Qt.Orientation(d['orientation']))
            if index >= 0:
                self._cmb_orientation.setCurrentIndex(index)
                orientation_valid = True

        if not border_valid:
            self._logger.warning(f"Invalid border settings for HMI Widget: {self.get_display_name()}")

        if not orientation_valid:
            self._logger.warning(f"Invalid orientation for HMI Widget: {self.get_display_name()}")

        return orientation_valid and border_valid
# endregion
