#    text_label_hmi_widget.py
#        A graphical only HMI widget that display static text
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['TextLabel']

from PySide6.QtGui import QPainter, QPen, QBrush, QFontMetrics
from PySide6.QtCore import QSizeF, Qt, QRectF, QPointF
from PySide6.QtWidgets import QVBoxLayout, QWidget, QGroupBox, QLineEdit


from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory
from scrutiny.gui.components.locals.hmi.common.pen_config import PenConfigWidget
from scrutiny.gui.components.locals.hmi.common.brush_config import BrushConfigWidget
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny.gui.widgets.color_button import ColorButton

from scrutiny.gui import assets
from scrutiny.tools.typing import *

if TYPE_CHECKING:
    from scrutiny.gui.components.locals.hmi.hmi_component import HMIComponent


class TextLabel(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Graphic
    _NAME = 'Label'
    _ICON = assets.Icons.HMILabel

    _config_widget: QWidget
    _border_pen_config: PenConfigWidget
    _fill_brush_config: BrushConfigWidget
    _txt_content: QLineEdit
    _font_color_picker: ColorButton

    def __init__(self, hmi_component: "HMIComponent") -> None:
        super().__init__(hmi_component)

        self._config_widget = QWidget()
        self._font_color_picker = ColorButton(HMITheme.Color.text())
        self._border_pen_config = PenConfigWidget()
        self._fill_brush_config = BrushConfigWidget()
        self._txt_content = QLineEdit()
        self._txt_content.setText("New label")

        layout = QVBoxLayout(self._config_widget)

        gb_border = QGroupBox("Border")
        gb_fill = QGroupBox("Fill")

        gb_border_layout = QVBoxLayout(gb_border)
        gb_fill_layout = QVBoxLayout(gb_fill)

        default_pen = QPen()
        default_pen.setStyle(Qt.PenStyle.NoPen)
        default_pen.setWidthF(1)
        default_pen.setColor(HMITheme.Color.frame_border())
        self._border_pen_config.set_pen(default_pen)

        default_brush = QBrush()
        default_brush.setStyle(Qt.BrushStyle.NoBrush)
        default_brush.setColor(HMITheme.Color.workzone_background())
        self._fill_brush_config.set_brush(default_brush)

        gb_border_layout.addWidget(self._border_pen_config)
        gb_fill_layout.addWidget(self._fill_brush_config)

        layout.addWidget(self._txt_content)
        layout.addWidget(gb_border)
        layout.addWidget(gb_fill)

        self._font_color_picker.signals.changed.connect(self._update)
        self._border_pen_config.signals.changed.connect(self._update)
        self._fill_brush_config.signals.changed.connect(self._update)
        self._txt_content.textChanged.connect(self._update)

    def _update(self, *args: Any, **kwargs: Any) -> None:
        self.update()

    def get_config_widget(self) -> QWidget | None:
        return self._config_widget

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             painter: QPainter
             ) -> None:

        pen = self._border_pen_config.get_pen()
        painter.setPen(pen)
        painter.setBrush(self._fill_brush_config.get_brush())
        bounding_rect = self.boundingRect()
        draw_rect = QRectF(
            QPointF(pen.widthF() / 2, pen.widthF() / 2),
            QSizeF(bounding_rect.width() - pen.widthF(), bounding_rect.height() - pen.widthF())
        )

        painter.drawRect(draw_rect)

        pen = QPen()
        pen.setColor(self._font_color_picker.get_color())
        painter.setPen(pen)
        font = painter.font()
        text = self._txt_content.text()

        font.setPixelSize(max(1, int(draw_rect.size().height())))
        text_width = QFontMetrics(font).averageCharWidth() * len(text)
        if text_width > draw_rect.size().width():
            font.setPixelSize(max(1, int(draw_rect.size().height() * draw_rect.size().width() / text_width)))

        # apply_font_size uses average char size. It might not be exact.
        # Decrease the size until we fit on one line
        while font.pixelSize() > 1:
            previous_size = font.pixelSize()
            required_width = QFontMetrics(font).size(0, text)
            if required_width.width() <= draw_rect.width():
                break

            font.setPixelSize(previous_size - 1)
            if not font.pixelSize() < previous_size:
                self._logger.critical("Failed to reduce the font size. Report this error please.")
                break
        painter.setFont(font)
        painter.drawText(draw_rect, text, Qt.AlignmentFlag.AlignCenter)
