#    pen_config.py
#        A widget to configure a border color (QPen)
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['PenConfigWidget']

from PySide6.QtWidgets import QWidget, QDoubleSpinBox, QComboBox
from PySide6.QtGui import QPen, QColor
from PySide6.QtCore import Signal, QObject, Qt

from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.widgets.color_button import ColorButton
from scrutiny.gui.widgets.tooltip_form_layout import TooltipFormLayout

from scrutiny import tools
from scrutiny.tools.typing import *


class PenConfigStateDict(TypedDict):
    style: int
    width: float
    color: str


class PenConfigWidget(QWidget):

    class _Signals(QObject):
        changed = Signal()

    _spn_width: QDoubleSpinBox
    _btn_color: ColorButton
    _cmb_style: QComboBox
    _signals: _Signals

    _PEN_STYLES: Dict[str, Qt.PenStyle] = {
        "Solid": Qt.PenStyle.SolidLine,
        "Dash": Qt.PenStyle.DashLine,
        "Dot": Qt.PenStyle.DotLine,
        "Dash Dot": Qt.PenStyle.DashDotLine,
        "Dash Dot Dot": Qt.PenStyle.DashDotDotLine,
        "None": Qt.PenStyle.NoPen
    }

    @tools.copy_type(QWidget.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._signals = self._Signals()

        self._spn_width = QDoubleSpinBox()
        self._spn_width.setMinimum(0.0)
        self._spn_width.setMaximum(10.0)
        self._spn_width.setSingleStep(0.5)
        self._spn_width.setDecimals(1)
        self._spn_width.setValue(1.0)

        self._btn_color = ColorButton(scrutiny_get_theme().palette().text().color())

        self._cmb_style = QComboBox()
        for label, style in self._PEN_STYLES.items():
            self._cmb_style.addItem(label, style)

        form = TooltipFormLayout(self)
        form.add_row_tooltip("Width:", self._spn_width, "Border width in px")
        form.add_row_tooltip("Color:", self._btn_color, "Border color")
        form.add_row_tooltip("Style:", self._cmb_style, "Border style")

        self._btn_color.setMaximumWidth(self._btn_color.sizeHint().width())
        self._cmb_style.setMaximumWidth(self._cmb_style.sizeHint().width())
        self._spn_width.setMaximumWidth(self._spn_width.sizeHint().width())

        self._spn_width.valueChanged.connect(self._signals.changed)
        self._cmb_style.currentIndexChanged.connect(self._signals.changed)
        self._btn_color.signals.changed.connect(self._signals.changed)

    @property
    def signals(self) -> "_Signals":
        return self._signals

# region Getters & Setters

    def get_pen(self) -> QPen:
        style = cast(Qt.PenStyle, self._cmb_style.currentData())
        pen = QPen()
        pen.setWidthF(self._spn_width.value())
        pen.setColor(self._btn_color.get_color())
        pen.setStyle(style)
        return pen

    def set_pen(self, pen: QPen) -> None:
        self._spn_width.setValue(pen.widthF())
        self._btn_color.set_color(pen.color())
        idx = self._cmb_style.findData(pen.style())
        if idx >= 0:
            self._cmb_style.setCurrentIndex(idx)

    def set_width(self, v: float) -> None:
        pen = self.get_pen()
        pen.setWidthF(v)
        self.set_pen(pen)

# endregion

    def get_state_dict(self) -> PenConfigStateDict:
        pen = self.get_pen()
        return {
            "style": cast(int, pen.style().value),
            "width": pen.widthF(),
            "color": pen.color().name(QColor.NameFormat.HexRgb)
        }

    def set_state_dict(self, d: PenConfigStateDict) -> bool:
        pen = QPen()
        valid_style = False
        valid_color = False
        valid_width = False
        if 'style' in d and isinstance(d['style'], int):
            pen.setStyle(Qt.PenStyle(d['style']))   # Value is validated by QT
            valid_style = True

        if 'color' in d:
            color = QColor(d['color'])
            if color.name(QColor.NameFormat.HexRgb) == d['color']:  # Check valid
                pen.setColor(color)
                valid_color = True

        if 'width' in d and isinstance(d["width"], (float, int)) and d["width"] >= 0:
            pen.setWidthF(d["width"])
            valid_width = True

        self.set_pen(pen)

        return valid_style and valid_color and valid_width
