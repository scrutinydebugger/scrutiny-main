#    numerical_text_display.py
#        A graphic item able to display a numerical value in a graphicScene. Offers parameters
#        to control the font size and avoid display glitches
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['BoundedTextDisplay']

from dataclasses import dataclass
from PySide6.QtGui import QPainter, QFont, QFontMetrics, QColor, QPen
from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget, QFormLayout, QLineEdit, QCheckBox, QSpinBox, QGraphicsItem
from PySide6.QtCore import QObject, QRectF, QRect, Signal, QSize, QPoint, Qt

from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny import tools
from scrutiny.gui import assets
from scrutiny.tools.typing import *


class NumericalConfigConstants:
    MINIMUM_DECIMAL = 0
    MINIMUM_INTS = 1
    MAXIMUM_DECIMAL = 6
    MAXIMUM_INTS = 10
    DEFAULT_ENG_NOTATION = True
    DEFAULT_DECIMALS = 1
    DEFAULT_INTS = 6
    DEFAULT_UNIT = ""
    UNIT_MAXLEN = 3


@dataclass(slots=True)
class BoundedTextNumericalConfig:
    units: str = NumericalConfigConstants.DEFAULT_UNIT
    max_ints: int = NumericalConfigConstants.DEFAULT_INTS
    decimals: int = NumericalConfigConstants.DEFAULT_DECIMALS
    eng_notation: bool = NumericalConfigConstants.DEFAULT_ENG_NOTATION

    def get_state(self) -> Dict[str, Any]:
        return {
            'eng': self.eng_notation,
            'decimals': self.decimals,
            'units': self.units,
            'max_int': self.max_ints
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> Self:

        # Engineering Notation
        eng = d.get('eng', NumericalConfigConstants.DEFAULT_ENG_NOTATION)
        if not isinstance(eng, bool):
            eng = NumericalConfigConstants.DEFAULT_ENG_NOTATION

        # Decimals
        decimals = d.get('decimals', NumericalConfigConstants.DEFAULT_DECIMALS)
        if not isinstance(decimals, int):
            decimals = NumericalConfigConstants.DEFAULT_DECIMALS
        if decimals < NumericalConfigConstants.MINIMUM_DECIMAL or decimals > NumericalConfigConstants.MAXIMUM_DECIMAL:
            decimals = NumericalConfigConstants.DEFAULT_DECIMALS

        # Ints
        max_ints = d.get('max_int', NumericalConfigConstants.DEFAULT_INTS)
        if not isinstance(max_ints, int):
            max_ints = NumericalConfigConstants.DEFAULT_INTS
        if max_ints < NumericalConfigConstants.MINIMUM_INTS or max_ints > NumericalConfigConstants.MAXIMUM_INTS:
            max_ints = NumericalConfigConstants.DEFAULT_INTS

        # Units
        units = d.get('units', NumericalConfigConstants.DEFAULT_UNIT)
        if not isinstance(units, str):
            units = NumericalConfigConstants.DEFAULT_UNIT
        if len(units) > NumericalConfigConstants.UNIT_MAXLEN:
            units = NumericalConfigConstants.DEFAULT_UNIT

        return cls(
            units=units,
            max_ints=max_ints,
            decimals=decimals,
            eng_notation=eng
        )


class _NumericalConfigWidget(QWidget):
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
        self.txt_units.setMaxLength(NumericalConfigConstants.UNIT_MAXLEN)
        self.chk_eng_notation = QCheckBox()
        self.spn_decimals = QSpinBox()
        self.spn_decimals.setMinimum(NumericalConfigConstants.MINIMUM_DECIMAL)
        self.spn_decimals.setMaximum(NumericalConfigConstants.MAXIMUM_DECIMAL)
        self.spn_ints = QSpinBox()
        self.spn_ints.setMinimum(NumericalConfigConstants.MINIMUM_INTS)
        self.spn_ints.setMaximum(NumericalConfigConstants.MAXIMUM_INTS)

        layout = QFormLayout(self)
        layout.addRow("Engineering notation", self.chk_eng_notation)
        layout.addRow("Integers", self.spn_ints)
        layout.addRow("Decimals", self.spn_decimals)
        layout.addRow("Units", self.txt_units)

        def _changed_slot(*args: Any, **kwargs: Any) -> None:
            self._update_ui_state()
            self._signals.changed.emit()

        self.chk_eng_notation.checkStateChanged.connect(_changed_slot)
        self.spn_ints.valueChanged.connect(_changed_slot)
        self.spn_decimals.valueChanged.connect(_changed_slot)
        self.txt_units.textEdited.connect(_changed_slot)

        self._update_ui_state()

    @property
    def signals(self) -> _Signals:
        return self._signals

    def load_state(self, d: Dict[str, Any]) -> None:
        # Engineering Notation
        config = BoundedTextNumericalConfig.from_dict(d)
        self.apply_config(config)

    def get_config(self) -> BoundedTextNumericalConfig:
        config = BoundedTextNumericalConfig(
            eng_notation=self.chk_eng_notation.isChecked(),
            decimals=self.spn_decimals.value(),
            max_ints=self.spn_ints.value(),
            units=self.txt_units.text()
        )
        return config

    def apply_config(self, config: BoundedTextNumericalConfig) -> None:
        self.chk_eng_notation.setChecked(config.eng_notation)
        self.spn_decimals.setValue(config.decimals)
        self.spn_ints.setValue(config.max_ints)
        self.txt_units.setText(config.units)

        self._update_ui_state()

    def _update_ui_state(self) -> None:
        if self.chk_eng_notation.isChecked():
            self.spn_ints.setDisabled(True)
        else:
            self.spn_ints.setDisabled(False)


class BoundedTextDisplay(QGraphicsItem):

    class _Signals(QObject):
        config_changed = Signal()

    _config_widget: _NumericalConfigWidget
    _config: BoundedTextNumericalConfig
    _signals: _Signals
    _val: Union[float, int, bool, str]
    _font: QFont
    _text_color: QColor
    _border_color: QColor
    _alignement: Qt.AlignmentFlag
    _size: QSize
    _border_width: int
    _background_color: QColor

    def __init__(self, parent: Optional[QGraphicsItem]) -> None:
        super().__init__(parent)
        self._signals = self._Signals()
        self._config = BoundedTextNumericalConfig()
        self._config_widget = _NumericalConfigWidget()
        self._config_widget.apply_config(self._config)
        self._font = assets.get_font(assets.ScrutinyFont.Monospaced)
        self._alignement = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        self._text_color = HMITheme.Color.text()
        self._border_color = HMITheme.Color.frame_border()
        self._size = QSize()
        self._border_width = 1
        self._background_color = HMITheme.Color.text_display_background()

        self._config_widget.signals.changed.connect(self._config_changed_slot)

# region Public
    @property
    def signals(self) -> _Signals:
        return self._signals

    def _config_changed_slot(self) -> None:
        self._config = self._config_widget.get_config()
        self.update()
        self._signals.config_changed.emit()

    def set_size(self, size: QSize) -> None:
        self._size = size

    def set_border_width(self, width: int) -> None:
        self._border_width = width

    def set_border_color(self, color: QColor) -> None:
        self._border_color = color

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
    @classmethod
    def format_numerical_value(cls, config: BoundedTextNumericalConfig, val: float) -> str:
        if config.eng_notation:
            return tools.format_eng_unit(val, decimal=config.decimals, unit=config.units)

        if config.decimals == 0:
            return str(int(val))

        format_str = f"%0.{config.decimals}f"
        text = (format_str % val) + config.units

        return text

    @classmethod
    def max_char_count(cls, config: BoundedTextNumericalConfig) -> int:
        unit_part = len(config.units)
        if unit_part > 0 and config.eng_notation:
            unit_part += 1  # prefix
        decimal_part = 0
        if config.decimals > 0:
            decimal_part = 1 + config.decimals   # 1 is for dot

        if config.eng_notation:
            return 3 + decimal_part + unit_part + 1     # +1 for sign

        count = config.max_ints + decimal_part + unit_part + 1  # +1 for sign
        return count

    @classmethod
    def apply_font_size(cls, font: QFont, config: BoundedTextNumericalConfig, text: str, rect: QRect) -> None:
        text_len = max(len(text), cls.max_char_count(config))

        font.setPixelSize(max(1, rect.size().height()))
        text_width = QFontMetrics(font).averageCharWidth() * text_len
        if text_width > rect.size().width():
            font.setPixelSize(max(1, int(rect.size().height() * rect.size().width() / text_width)))

# endregion

    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: Optional[QWidget] = None) -> None:
        if isinstance(self._val, str):
            text = self._val
        elif isinstance(self._val, bool):
            text = "1" if self._val else "0"
        else:
            text = self.format_numerical_value(self._config, float(self._val))

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
            pen.setColor(self._border_color)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            painter.drawRect(frame_rect)
        else:
            inner_frame_rect = bounding_rect

        self.apply_font_size(self._font, self._config, text, inner_frame_rect.toRect())
        painter.setFont(self._font)
        painter.setPen(HMITheme.Color.text())
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawText(inner_frame_rect, self._alignement, text)
        # painter.drawRect(inner_frame_rect)
