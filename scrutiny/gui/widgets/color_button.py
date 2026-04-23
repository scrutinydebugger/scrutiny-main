from PySide6.QtWidgets import (QWidget, QHBoxLayout, QPushButton, QColorDialog)
from PySide6.QtGui import QColor
from PySide6.QtCore import QSize, Qt, Signal, QObject

from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.tools.typing import *


class ColorButton(QWidget):

    class _Signals(QObject):
        changed = Signal()

    color_changed: Signal = Signal(QColor)

    _btn: QPushButton
    _color: QColor
    _signals: _Signals

    def __init__(self, color: QColor) -> None:
        super().__init__()
        self._signals = self._Signals()
        self._color = QColor(color)
        self._btn = QPushButton()
        self._btn.clicked.connect(self._open_color_dialog)
        layout = QHBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self._btn, stretch=1)
        self._update_appearance()

    @property
    def signals(self) -> "_Signals":
        return self._signals

    def _open_color_dialog(self) -> None:
        new_color = QColorDialog.getColor(self._color, self, "Select Color")
        if new_color.isValid():
            self.set_color(new_color)

    def _update_appearance(self) -> None:
        border_color = scrutiny_get_theme().palette().text().color()
        stylesheet = f"background-color: {self._color.name(QColor.NameFormat.HexRgb)};"
        stylesheet += f"border: 1px solid {border_color.name(QColor.NameFormat.HexRgb)};"
        self._btn.setStyleSheet(stylesheet)

    def get_color(self) -> QColor:
        return QColor(self._color)

    def set_color(self, color: QColor, emit: bool = False) -> None:
        self._color = QColor(color)
        self._update_appearance()
        if emit:
            self._signals.changed.emit(QColor(self._color))

    def sizeHint(self) -> QSize:
        size_hint = super().sizeHint()
        size_hint.setWidth(max(size_hint.width(), 60))
        return size_hint
