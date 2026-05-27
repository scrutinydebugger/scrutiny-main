#    text_label_hmi_widget.py
#        A graphical only HMI widget that display static text
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['TextLabelHMIWidget']

from PySide6.QtGui import QPainter, QPen, QBrush, QColor
from PySide6.QtCore import QSizeF, Qt, QRectF, QPointF
from PySide6.QtWidgets import QVBoxLayout, QWidget, QGroupBox, QLineEdit

from scrutiny.gui.widgets.tooltip_form_layout import TooltipFormLayout
from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui.components.locals.hmi.common.pen_config import PenConfigWidget, PenConfigStateDict
from scrutiny.gui.components.locals.hmi.common.brush_config import BrushConfigWidget, BrushConfigStateDict
from scrutiny.gui.components.locals.hmi.common.text import set_font_size_to_fit_rect
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny.gui.widgets.color_button import ColorButton

from scrutiny.gui import assets
from scrutiny.tools.typing import *


class TextLabelHMIWidget(BaseHMIWidget):

    _UNIQUE_NAME = 'label'
    _DISPLAY_NAME = 'Label'
    _ICON = assets.Icons.HMILabel

    _config_widget: QWidget
    _border_pen_config: PenConfigWidget
    _fill_brush_config: BrushConfigWidget
    _txt_content: QLineEdit
    _font_color_button: ColorButton

    def __init__(self, app: AbstractComponentAppInterface) -> None:
        super().__init__(app)

        self._config_widget = QWidget()
        self._font_color_button = ColorButton(HMITheme.Color.text())
        self._font_color_button.setFixedWidth(60)
        self._border_pen_config = PenConfigWidget()
        self._fill_brush_config = BrushConfigWidget()
        self._txt_content = QLineEdit()
        self._txt_content.setText("New label")

        layout = QVBoxLayout(self._config_widget)

        gb_text = QGroupBox("Text")
        gb_border = QGroupBox("Border")
        gb_fill = QGroupBox("Fill")

        gb_text_layout = TooltipFormLayout(gb_text)
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

        gb_text_layout.add_row_tooltip("Text", self._txt_content, "Text to display")
        gb_text_layout.add_row_tooltip("Font color", self._font_color_button, "Text color")

        gb_border_layout.addWidget(self._border_pen_config)
        gb_fill_layout.addWidget(self._fill_brush_config)

        layout.addWidget(gb_text)
        layout.addWidget(gb_border)
        layout.addWidget(gb_fill)

        self._font_color_button.signals.changed.connect(self._update)
        self._border_pen_config.signals.changed.connect(self._update)
        self._fill_brush_config.signals.changed.connect(self._update)
        self._txt_content.textChanged.connect(self._update)

    def _update(self, *args: Any, **kwargs: Any) -> None:
        self.update()

# region Getters and Setters
    def set_border_pen(self, pen: QPen) -> None:
        self._border_pen_config.set_pen(pen)

    def get_border_pen(self) -> QPen:
        return self._border_pen_config.get_pen()

    def set_fill_brush(self, brush: QBrush) -> None:
        self._fill_brush_config.set_brush(brush)

    def get_fill_brush(self) -> QBrush:
        return self._fill_brush_config.get_brush()

    def get_font_color(self) -> QColor:
        return self._font_color_button.get_color()

    def set_font_color(self, color: QColor) -> None:
        self._font_color_button.set_color(color)

    def get_text(self) -> str:
        return self._txt_content.text()

    def set_text(self, txt: str) -> None:
        self._txt_content.setText(txt)
# endregion

# region Override
    def get_config_widget(self) -> Optional[QWidget]:
        return self._config_widget

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             edit_mode: bool,
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
        pen.setColor(self._font_color_button.get_color())
        painter.setPen(pen)
        font = painter.font()
        text = self._txt_content.text()
        set_font_size_to_fit_rect(font, text, draw_rect)
        painter.setFont(font)
        painter.drawText(draw_rect, text, Qt.AlignmentFlag.AlignCenter)

    def get_implementation_config_dict(self) -> Dict[str, Any]:
        return {
            'border': self._border_pen_config.get_state_dict(),
            'fill': self._fill_brush_config.get_state_dict(),
            'text': self._txt_content.text(),
            'font_color': self._font_color_button.get_color().name(QColor.NameFormat.HexRgb)
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        border_valid = False
        fill_valid = False
        text_valid = False
        font_color_valid = False

        if 'border' in d and isinstance(d['border'], dict):
            border_valid = self._border_pen_config.set_state_dict(cast(PenConfigStateDict, d['border']))

        if 'fill' in d and isinstance(d['fill'], dict):
            fill_valid = self._fill_brush_config.set_state_dict(cast(BrushConfigStateDict, d['fill']))

        if 'text' in d and isinstance(d['text'], str):
            self._txt_content.setText(d['text'])
            text_valid = True

        if 'font_color' in d and isinstance(d['font_color'], str):
            color = QColor(d['font_color'])
            if color.name(QColor.NameFormat.HexRgb) == d['font_color']:  # Check valid
                self._font_color_button.set_color(color)
                font_color_valid = True

        if not border_valid:
            self._logger.warning(f"Invalid border settings for HMI Widget: {self.get_display_name()}")

        if not fill_valid:
            self._logger.warning(f"Invalid fill settings for HMI Widget: {self.get_display_name()}")

        if not text_valid:
            self._logger.warning(f"Invalid text content for HMI Widget: {self.get_display_name()}")

        if not font_color_valid:
            self._logger.warning(f"Invalid color for HMI Widget: {self.get_display_name()}")

        return fill_valid and border_valid and text_valid and font_color_valid
# endregion
