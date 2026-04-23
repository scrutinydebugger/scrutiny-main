__all__ = ['PenConfigWidget']

from PySide6.QtWidgets import (QWidget, QFormLayout, QDoubleSpinBox, QComboBox)
from PySide6.QtGui import QPen
from PySide6.QtCore import Signal, QObject, Qt

from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.widgets.color_button import ColorButton

from scrutiny import tools
from scrutiny.tools.typing import *


class PenConfigWidget(QWidget):

    class _Signals(QObject):
        changed = Signal()

    _spn_width: QDoubleSpinBox
    _btn_color: ColorButton
    _cmb_style: QComboBox
    _signals: _Signals

    _PEN_STYLES: "List[Tuple[str, Qt.PenStyle]]" = [
        ("Solid", Qt.PenStyle.SolidLine),
        ("Dash", Qt.PenStyle.DashLine),
        ("Dot", Qt.PenStyle.DotLine),
        ("Dash Dot", Qt.PenStyle.DashDotLine),
        ("Dash Dot Dot", Qt.PenStyle.DashDotDotLine),
        ("None", Qt.PenStyle.NoPen),
    ]

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
        for label, style in self._PEN_STYLES:
            self._cmb_style.addItem(label, style)

        form = QFormLayout(self)
        form.addRow("Width:", self._spn_width)
        form.addRow("Color:", self._btn_color)
        form.addRow("Style:", self._cmb_style)

        self._btn_color.setMaximumWidth(self._btn_color.sizeHint().width())
        self._cmb_style.setMaximumWidth(self._cmb_style.sizeHint().width())
        self._spn_width.setMaximumWidth(self._spn_width.sizeHint().width())

        self._spn_width.valueChanged.connect(self._signals.changed)
        self._cmb_style.currentIndexChanged.connect(self._signals.changed)
        self._btn_color.signals.changed.connect(self._signals.changed)

    @property
    def signals(self) -> "_Signals":
        return self._signals

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
