#    brush_config.py
#        A widget to configure a fill color (QBrush)
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['BrushConfigWidget']

from PySide6.QtWidgets import (QWidget, QFormLayout, QComboBox)
from PySide6.QtGui import QBrush, QColor
from PySide6.QtCore import Signal, QObject, Qt

from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.widgets.color_button import ColorButton

from scrutiny import tools
from scrutiny.tools.typing import *


class BrushConfigStateDict(TypedDict):
    fill_style: int
    color: str


class BrushConfigWidget(QWidget):
    """A widget to edit a QBrush params"""

    class _Signals(QObject):
        changed = Signal()

    _btn_color: ColorButton
    _cmb_style: QComboBox
    _signals: _Signals

    _BRUSH_STYLES: Dict[str, Qt.BrushStyle] = {
        "Fill": Qt.BrushStyle.SolidPattern,
        "None": Qt.BrushStyle.NoBrush,
    }

    @tools.copy_type(QWidget.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._signals = self._Signals()

        self._btn_color = ColorButton(scrutiny_get_theme().palette().text().color())
        self._btn_color.setFixedWidth(60)

        self._cmb_style = QComboBox()
        for label, style in self._BRUSH_STYLES.items():
            self._cmb_style.addItem(label, style)

        form = QFormLayout(self)
        form.addRow("Color:", self._btn_color)
        form.addRow("Fill:", self._cmb_style)

        self._cmb_style.currentIndexChanged.connect(self._signals.changed)
        self._btn_color.signals.changed.connect(self._signals.changed)

    @property
    def signals(self) -> "_Signals":
        return self._signals

# region Getters and Setters

    def get_brush(self) -> QBrush:
        style = cast(Qt.BrushStyle, self._cmb_style.currentData())
        brush = QBrush()
        brush.setColor(self._btn_color.get_color())
        brush.setStyle(style)
        return brush

    def set_brush(self, brush: QBrush) -> None:
        self._btn_color.set_color(brush.color())
        idx = self._cmb_style.findData(brush.style())
        if idx >= 0:
            self._cmb_style.setCurrentIndex(idx)

# endregion

    def get_state_dict(self) -> BrushConfigStateDict:
        brush = self.get_brush()
        return {
            "fill_style": cast(int, brush.style().value),
            "color": brush.color().name(QColor.NameFormat.HexRgb)
        }

    def set_state_dict(self, d: BrushConfigStateDict) -> bool:
        brush = QBrush()
        valid_style = False
        valid_color = False

        if 'fill_style' in d and isinstance(d['fill_style'], int):
            brush.setStyle(Qt.BrushStyle(d['fill_style']))
            valid_style = True

        if 'color' in d:
            color = QColor(d['color'])
            if color.name(QColor.NameFormat.HexRgb) == d['color']:  # Check valid
                brush.setColor(color)
                valid_color = True

        self.set_brush(brush)

        return valid_style and valid_color
