#    numerical_text_display.py
#        A graphic item able to display a numerical value in a graphicScene. Offers parameters
#        to control the font size and avoid display glitches
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['NumericalTextDisplay']

from PySide6.QtGui import QPainter, QFont, QFontMetrics, QColor, QPen
from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget, QFormLayout, QLineEdit, QCheckBox, QSpinBox, QGraphicsItem
from PySide6.QtCore import QObject, QRectF, QRect, Signal, QSize, QPoint, Qt

from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny import tools
from scrutiny.gui import assets
from scrutiny.tools.typing import *


class _ConfigWidget(QWidget):
    DEFAULT_ENG_NOTATION = True
    DEFAULT_DECIMALS = 1
    DEFAULT_INTS = 6
    DEFAULT_UNIT = ""

    class _Signals(QObject):
        changed = Signal()

    txt_units: QLineEdit
    chk_eng_notation: QCheckBox
    spn_decimals: QSpinBox
    spn_ints: QSpinBox
    _signals: _Signals

    def __init__(self) -> None:
        super().__init__()
        self._signals = self._Signals()

        self.txt_units = QLineEdit()
        self.txt_units.setMaxLength(3)
        self.txt_units.setText(self.DEFAULT_UNIT)
        self.chk_eng_notation = QCheckBox()
        self.chk_eng_notation.setChecked(self.DEFAULT_ENG_NOTATION)
        self.spn_decimals = QSpinBox()
        self.spn_decimals.setMinimum(0)
        self.spn_decimals.setMaximum(6)
        self.spn_decimals.setValue(self.DEFAULT_DECIMALS)
        self.spn_ints = QSpinBox()
        self.spn_ints.setMinimum(1)
        self.spn_ints.setMaximum(10)
        self.spn_ints.setValue(self.DEFAULT_INTS)

        layout = QFormLayout(self)
        layout.addRow("Integers", self.spn_ints)
        layout.addRow("Decimals", self.spn_decimals)
        layout.addRow("Units", self.txt_units)
        layout.addRow("Engineering notation", self.chk_eng_notation)

        def _changed_slot(*args: Any, **kwargs: Any) -> None:
            self._update_state()
            self._signals.changed.emit()

        self.chk_eng_notation.checkStateChanged.connect(_changed_slot)
        self.spn_ints.valueChanged.connect(_changed_slot)
        self.spn_decimals.valueChanged.connect(_changed_slot)
        self.txt_units.textEdited.connect(_changed_slot)

    @property
    def signals(self) -> _Signals:
        return self._signals

    def get_state(self) -> Dict[str, Any]:
        return {
            'eng': self.chk_eng_notation.isChecked(),
            'decimals': self.spn_decimals.value(),
            'units': self.txt_units.text(),
            'max_int': self.spn_ints.value()
        }

    def load_state(self, d: Dict[str, Any]) -> None:
        # Engineering Notation
        eng = d.get('eng', self.DEFAULT_ENG_NOTATION)
        if not isinstance(eng, bool):
            eng = self.DEFAULT_ENG_NOTATION

        # Decimals
        decimals = d.get('decimals', self.DEFAULT_DECIMALS)
        if not isinstance(decimals, int):
            decimals = self.DEFAULT_DECIMALS
        if decimals < self.spn_decimals.minimum() or decimals > self.spn_decimals.maximum():
            decimals = self.DEFAULT_DECIMALS

        # Ints
        ints = d.get('max_int', self.DEFAULT_INTS)
        if not isinstance(ints, int):
            ints = self.DEFAULT_INTS
        if ints < self.spn_ints.minimum() or ints > self.spn_ints.maximum():
            ints = self.DEFAULT_INTS

        # Units
        units = d.get('units', self.DEFAULT_UNIT)
        if not isinstance(units, str):
            units = self.DEFAULT_UNIT
        if len(units) > self.txt_units.maxLength():
            units = self.DEFAULT_UNIT

        # Apply
        self.chk_eng_notation.setChecked(eng)
        self.spn_decimals.setValue(decimals)
        self.spn_ints.setValue(ints)
        self.txt_units.setText(units)

        self._update_state()

    def _update_state(self) -> None:
        if self.chk_eng_notation.isChecked():
            self.spn_ints.setDisabled(True)
        else:
            self.spn_ints.setDisabled(False)


class NumericalTextDisplay(QGraphicsItem):

    class _Signals(QObject):
        config_changed = Signal()

    _config_widget: _ConfigWidget

    _signals: _Signals
    _val: Union[float, int, bool, str]
    _font: QFont
    _text_color: QColor
    _alignement: Qt.AlignmentFlag
    _size: QSize
    _border_width: int
    _background_color: QColor

    def __init__(self, parent: Optional[QGraphicsItem]) -> None:
        super().__init__(parent)
        self._signals = self._Signals()
        self._config_widget = _ConfigWidget()
        self._font = assets.get_font(assets.ScrutinyFont.Monospaced)
        self._alignement = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        self._text_color = QColor()
        self._size = QSize()
        self._border_width = 1
        self._background_color = HMITheme.Color.text_display_background()

        self._config_widget.signals.changed.connect(self._signals.config_changed)
        self._config_widget.signals.changed.connect(self.update)

# region Public
    @property
    def signals(self) -> _Signals:
        return self._signals

    def set_size(self, size: QSize) -> None:
        self._size = size

    def set_border_width(self, width: int) -> None:
        self._border_width = width

    def set_text_color(self, color: QColor) -> None:
        self._text_color = color

    def set_background_color(self, color: QColor) -> None:
        self._background_color = color

    def set_val(self, val: Union[float, int, bool, str]) -> None:
        self._val = val

    def set_alignment(self, alignement: Qt.AlignmentFlag) -> None:
        self._alignement = alignement

    def get_config_widget(self) -> QWidget:
        return self._config_widget

    def boundingRect(self) -> QRectF:
        return QRectF(QPoint(0, 0), self._size)
# endregion

# region Private
    def _format_value(self, val: float) -> str:
        units = self._config_widget.txt_units.text()
        decimals = self._config_widget.spn_decimals.value()
        if self._config_widget.chk_eng_notation.isChecked():
            return tools.format_eng_unit(val, decimal=decimals, unit=units)

        if decimals == 0:
            return str(int(val))

        format_str = f"%0.{decimals}f"
        text = (format_str % val) + units

        return text

    def _max_char_count(self) -> int:
        unit_part = len(self._config_widget.txt_units.text())
        if unit_part > 0 and self._config_widget.chk_eng_notation.isChecked():
            unit_part += 1  # prefix
        decimal_part = 0
        if self._config_widget.spn_decimals.value() > 0:
            decimal_part = 1 + self._config_widget.spn_decimals.value()   # 1 is for dot

        if self._config_widget.chk_eng_notation.isChecked():
            return 3 + decimal_part + unit_part + 1     # +1 for sign

        count = self._config_widget.spn_ints.value() + decimal_part + unit_part + 1  # +1 for sign
        return count

    def _set_font_size(self, text: str, rect: QRect) -> None:
        text_len = max(len(text), self._max_char_count())

        self._font.setPixelSize(max(1, rect.size().height()))
        text_width = QFontMetrics(self._font).averageCharWidth() * text_len
        if text_width > rect.size().width():
            self._font.setPixelSize(max(1, int(rect.size().height() * rect.size().width() / text_width)))

# endregion

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        if isinstance(self._val, str):
            text = self._val
        elif isinstance(self._val, bool):
            text = "1" if self._val else "0"
        else:
            text = self._format_value(float(self._val))

        bounding_rect = self.boundingRect()
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(self._background_color)
        painter.drawRect(bounding_rect)

        if bounding_rect.width() > 2 * self._border_width and bounding_rect.height() > 2 * self._border_width:
            frame_rect = QRectF(
                self._border_width / 2,
                self._border_width / 2,
                bounding_rect.width() - self._border_width,
                bounding_rect.height() - self._border_width
            )
            inner_frame_rect = QRectF(
                self._border_width,
                self._border_width,
                bounding_rect.width() - 2 * self._border_width,
                bounding_rect.height() - 2 * self._border_width
            )
            pen = QPen()
            pen.setWidth(self._border_width)
            pen.setColor(HMITheme.Color.frame_border())
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            painter.drawRect(frame_rect)
        else:
            inner_frame_rect = bounding_rect

        self._set_font_size(text, inner_frame_rect.toRect())
        painter.setFont(self._font)
        painter.setPen(HMITheme.Color.text())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawText(inner_frame_rect, self._alignement, text)
