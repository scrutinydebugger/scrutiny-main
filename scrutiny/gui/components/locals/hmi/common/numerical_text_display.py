#    numerical_text_display.py
#        A graphic item able to display a numerical value in a graphicScene. Offers parameters
#        to control the font size and avoid display glitches
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['NumericalTextDisplay', 'NumberFormattingConfig']

from dataclasses import dataclass
import logging
from PySide6.QtGui import QPainter, QFont, QFontMetrics, QColor, QPen
from PySide6.QtWidgets import QStyleOptionGraphicsItem, QWidget, QFormLayout, QLineEdit, QCheckBox, QSpinBox, QGraphicsItem
from PySide6.QtCore import QObject, QRectF, Signal, QSize, QPoint, Qt

from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny import tools
from scrutiny.gui import assets
from scrutiny.tools.typing import *


class NumberFormattingConfigDict(TypedDict):
    """A Dict version of ``NumberFormattingConfig`` for serialization"""
    units: str
    max_ints: int
    decimals: int
    eng: bool


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
class NumberFormattingConfig:
    """A configuration to be given to the NumericalTextDisplay that contains the formatting parameters"""

    units: str = NumericalConfigConstants.DEFAULT_UNIT
    """A suffix to be printed after the number"""
    max_ints: int = NumericalConfigConstants.DEFAULT_INTS
    """Number of integral digits. Only used when not using engineering notation"""
    decimals: int = NumericalConfigConstants.DEFAULT_DECIMALS
    """Number of decimal digits"""
    eng_notation: bool = NumericalConfigConstants.DEFAULT_ENG_NOTATION
    """Engineering notation enabled when ``True``. Limit the number of integral digits to 3."""

    def to_dict(self) -> NumberFormattingConfigDict:
        return {
            'eng': self.eng_notation,
            'decimals': self.decimals,
            'units': self.units,
            'max_ints': self.max_ints
        }

    @classmethod
    def from_dict(cls, d: NumberFormattingConfigDict) -> Self:
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
        max_ints = d.get('max_ints', NumericalConfigConstants.DEFAULT_INTS)
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


class _NumberFormattingConfigWidget(QWidget):
    """A widget to visually edit a NumberFormattingConfig"""
    class _Signals(QObject):
        changed = Signal()

    txt_units: QLineEdit
    """Units suffix"""
    chk_eng_notation: QCheckBox
    """Engineering notation checkbox"""
    spn_decimals: QSpinBox
    """Number of decimal digits"""
    spn_ints: QSpinBox
    """Number of integral digits (only used when eng notation is ``False``)"""
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
        layout.addRow("Eng. notation", self.chk_eng_notation)
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

    def get_config(self) -> NumberFormattingConfig:
        """Build a config from the widget content"""
        config = NumberFormattingConfig(
            eng_notation=self.chk_eng_notation.isChecked(),
            decimals=self.spn_decimals.value(),
            max_ints=self.spn_ints.value(),
            units=self.txt_units.text()
        )
        return config

    def apply_config(self, config: NumberFormattingConfig) -> None:
        """Reload a configuration and update the widget content"""
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


class NumericalTextDisplayStateDict(TypedDict):
    """A serializable dict that represent the NumericalTextDisplay state"""
    number_format: NumberFormattingConfigDict
    """The number formatting parameters"""
    alignment: int
    """QT Alignment flag"""
    text_color: str
    """The text color in #hexrgb format"""
    border_color: str
    """Border color in #hexrgb format"""
    border_width: float
    """Border width"""
    background_color: str
    """Background color in #hexrgb format"""


class NumericalTextDisplay(QGraphicsItem):

    class _Signals(QObject):
        config_changed = Signal()

    _number_format_config_widget: _NumberFormattingConfigWidget
    """The widget that edits the NumberFormattingConfig"""
    _number_format_config: NumberFormattingConfig
    """The presently loaded number formatting config"""
    _val: Union[float, int, bool, str]
    """The value presently displayed"""
    _font: QFont
    """The font used. Expected to be monospaced"""
    _text_color: QColor
    """Text color"""
    _border_color: QColor
    """Border color"""
    _alignment: Qt.AlignmentFlag
    """QT Alignment flag"""
    _size: QSize
    """Size of the rectangle to print in. Used for font size selection"""
    _border_width: float
    """Border width"""
    _background_color: QColor
    """Background Color"""
    _logger: logging.Logger
    _signals: _Signals

    def __init__(self, parent: Optional[QGraphicsItem]) -> None:
        super().__init__(parent)
        self._signals = self._Signals()
        self._number_format_config = NumberFormattingConfig()
        self._number_format_config_widget = _NumberFormattingConfigWidget()
        self._number_format_config_widget.apply_config(self._number_format_config)
        self._font = assets.get_font(assets.ScrutinyFont.Monospaced)
        self._alignment = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        self._text_color = HMITheme.Color.text()
        self._border_color = HMITheme.Color.frame_border()
        self._size = QSize()
        self._border_width = 1
        self._background_color = HMITheme.Color.text_display_background()
        self._logger = logging.getLogger(self.__class__.__name__)
        self._val = ""

        self._number_format_config_widget.signals.changed.connect(self._number_format_config_changed_slot)

    @property
    def signals(self) -> _Signals:
        return self._signals

    def _number_format_config_changed_slot(self) -> None:
        self._number_format_config = self._number_format_config_widget.get_config()
        self._signals.config_changed.emit()

# region Public API
    def set_size(self, size: QSize) -> None:
        self._size = size

    def set_border_width(self, width: float) -> None:
        self._border_width = width

    def set_border_color(self, color: QColor) -> None:
        self._border_color = color

    def set_text_color(self, color: QColor) -> None:
        self._text_color = color

    def set_background_color(self, color: QColor) -> None:
        self._background_color = color

    def set_val(self, val: Union[float, int, bool, str]) -> None:
        self._val = val

    def set_alignment(self, alignment: Qt.AlignmentFlag) -> None:
        self._alignment = alignment

    def set_number_formatting_config(self, config: NumberFormattingConfig) -> None:
        self._number_format_config = config
        self._number_format_config_widget.apply_config(config)

    def get_size(self) -> QSize:
        return self._size

    def get_border_width(self) -> float:
        return self._border_width

    def get_border_color(self) -> QColor:
        return self._border_color

    def get_text_color(self) -> QColor:
        return self._text_color

    def get_background_color(self) -> QColor:
        return self._background_color

    def get_val(self) -> Union[float, int, bool, str]:
        return self._val

    def get_alignment(self) -> Qt.AlignmentFlag:
        return self._alignment

    def get_number_format_config_widget(self) -> QWidget:
        return self._number_format_config_widget

    def get_number_formatting_config(self) -> NumberFormattingConfig:
        return self._number_format_config

    def boundingRect(self) -> QRectF:
        return QRectF(QPoint(0, 0), self._size)

    def get_state_dict(self) -> NumericalTextDisplayStateDict:
        return {
            'number_format': self._number_format_config.to_dict(),
            'alignment': self._alignment.value,
            'text_color': self._text_color.name(QColor.NameFormat.HexRgb),
            'border_color': self._border_color.name(QColor.NameFormat.HexRgb),
            'border_width': self._border_width,
            'background_color': self._background_color.name(QColor.NameFormat.HexRgb),
        }

    def set_state_dict(self, d: NumericalTextDisplayStateDict) -> bool:
        valid_number_format = False
        valid_alignment = False
        valid_text_color = False
        valid_border_width = False
        valid_border_color = False
        valid_background_color = False

        if 'number_format' in d and isinstance(d['number_format'], dict):
            self._number_format_config = NumberFormattingConfig.from_dict(d['number_format'])
            self._number_format_config_widget.apply_config(self._number_format_config)
            valid_number_format = True

        if 'alignment' in d and isinstance(d['alignment'], int):
            self._alignment = Qt.AlignmentFlag(d['alignment'])
            valid_alignment = True

        if 'text_color' in d and isinstance(d['text_color'], str):
            color = QColor(d['text_color'])
            if color.name(QColor.NameFormat.HexRgb) == d['text_color']:
                self._text_color = color
                valid_text_color = True

        if 'border_color' in d and isinstance(d['border_color'], str):
            color = QColor(d['border_color'])
            if color.name(QColor.NameFormat.HexRgb) == d['border_color']:
                self._border_color = color
                valid_border_color = True

        if 'border_width' in d and isinstance(d['border_width'], (float, int)):
            self._border_width = float(d['border_width'])
            valid_border_width = True

        if 'background_color' in d and isinstance(d['background_color'], str):
            color = QColor(d['background_color'])
            if color.name(QColor.NameFormat.HexRgb) == d['background_color']:
                self._background_color = color
                valid_background_color = True

        if not valid_number_format:
            self._logger.warning('Invalid number formatting configuration ')
        if not valid_alignment:
            self._logger.warning('Invalid alignment')
        if not valid_text_color:
            self._logger.warning('Invalid text color')
        if not valid_border_width:
            self._logger.warning('Invalid border width')
        if not valid_border_color:
            self._logger.warning('Invalid border color')
        if not valid_background_color:
            self._logger.warning('Invalid background color')

        self._process_change()

        return (
            valid_number_format
            and valid_alignment
            and valid_text_color
            and valid_border_width
            and valid_border_color
            and valid_background_color
        )

    @classmethod
    def format_numerical_value(cls, config: NumberFormattingConfig, val: float) -> str:
        """Take a float number and return a string following the parameters in the given configuration"""
        if config.eng_notation:
            return tools.format_eng_unit(val, decimal=config.decimals, unit=config.units)

        if config.decimals == 0:
            return str(int(val)) + config.units

        format_str = f"%0.{config.decimals}f"
        text = (format_str % val) + config.units

        return text

    @classmethod
    def max_char_count(cls, config: NumberFormattingConfig) -> int:
        """Return the maximum characters a configuration may generate"""
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
    def apply_font_size(cls, font: QFont, config: NumberFormattingConfig, text: str, rect: QRectF) -> None:
        """Set the font size on a font to fit a text in a rectangle, following the formatting configuration.
        Assumes a monospaced font."""
        text_len = max(len(text), cls.max_char_count(config))

        font.setPixelSize(max(1, int(rect.size().height())))
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
            text = self.format_numerical_value(self._number_format_config, float(self._val))

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
            pen.setWidthF(self._border_width)
            pen.setColor(self._border_color)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            painter.drawRect(frame_rect)
        else:
            inner_frame_rect = bounding_rect

        self.apply_font_size(self._font, self._number_format_config, text, inner_frame_rect)
        painter.setFont(self._font)
        painter.setPen(self._text_color)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawText(inner_frame_rect, self._alignment, text)
