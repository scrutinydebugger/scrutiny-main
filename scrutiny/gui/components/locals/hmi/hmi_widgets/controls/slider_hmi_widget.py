__all__ = ['SliderHMIWidget']

import enum
import math

from PySide6.QtGui import QPainter, QPainterPath, QPen, QBrush, QDoubleValidator
from PySide6.QtCore import QSize, Qt, QPointF, QRectF, QSizeF
from PySide6.QtWidgets import QGraphicsSceneMouseEvent, QVBoxLayout, QWidget, QGroupBox, QComboBox, QFormLayout, QLineEdit, QSlider, QSpinBox

from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui.components.locals.hmi.common.serialization import deserialize_combobox_val
from scrutiny.gui.components.locals.hmi.common.hmi_colors import create_color_combobox, HMIColor
from scrutiny.gui.components.locals.hmi.common.text import set_font_size_to_fit_rect
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny.gui import assets
from scrutiny.tools.typing import *
from scrutiny.gui.widgets.validable_line_edit import FloatValidableLineEdit

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory


class _Dims:

    pass


class SliderHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Control
    _UNIQUE_NAME = 'slider'
    _DISPLAY_NAME = 'Slider'
    _ICON = assets.Icons.HMISlider

    _config_widget: QWidget
    _cmb_orientation: QComboBox
    _txt_min_val: FloatValidableLineEdit
    _txt_max_val: FloatValidableLineEdit
    _sld_label_size: QSlider
    _spn_major_ticks: QSpinBox
    _spn_minor_ticks: QSpinBox

    def __init__(self, app: AbstractComponentAppInterface) -> None:
        super().__init__(app)
        self.declare_value_slot('val', 'Value', allow_constant=False)

        self._cmb_orientation = QComboBox()
        self._cmb_orientation.addItem("Horizontal", Qt.Orientation.Horizontal)
        self._cmb_orientation.addItem("Vertical", Qt.Orientation.Vertical)
        self._cmb_orientation.setCurrentIndex(self._cmb_orientation.findData(Qt.Orientation.Horizontal))

        self._txt_min_val = FloatValidableLineEdit(hard_validator=QDoubleValidator())
        self._txt_min_val.set_float_value(0.0)

        self._txt_max_val = FloatValidableLineEdit(hard_validator=QDoubleValidator())
        self._txt_max_val.set_float_value(100.0)

        self._sld_label_size = QSlider(Qt.Orientation.Horizontal)
        self._sld_label_size.setMinimum(0)
        self._sld_label_size.setMaximum(100)
        self._sld_label_size.setValue(50)
        self._sld_label_size.setTickInterval(5)

        self._spn_major_ticks = QSpinBox()
        self._spn_major_ticks.setMinimum(0)
        self._spn_major_ticks.setMaximum(20)
        self._spn_major_ticks.setValue(5)

        self._spn_minor_ticks = QSpinBox()
        self._spn_minor_ticks.setMinimum(0)
        self._spn_minor_ticks.setMaximum(12)
        self._spn_minor_ticks.setValue(3)

        self._config_widget = QWidget()
        gb_config = QGroupBox("Configuration")
        layout = QVBoxLayout(self._config_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(gb_config)

        gb_config_layout = QFormLayout(gb_config)
        gb_config_layout.addRow("Orientation", self._cmb_orientation)
        gb_config_layout.addRow("Minimum", self._txt_min_val)
        gb_config_layout.addRow("Maximum", self._txt_max_val)
        gb_config_layout.addRow("Label Size", self._sld_label_size)
        gb_config_layout.addRow("Major Ticks", self._spn_major_ticks)
        gb_config_layout.addRow("Minor Ticks", self._spn_minor_ticks)

        self._cmb_orientation.currentIndexChanged.connect(self._config_changed_slot)
        self._txt_min_val.textChanged.connect(self._config_changed_slot)
        self._txt_max_val.textChanged.connect(self._config_changed_slot)
        self._sld_label_size.valueChanged.connect(self._config_changed_slot)
        self._spn_major_ticks.valueChanged.connect(self._config_changed_slot)
        self._spn_minor_ticks.valueChanged.connect(self._config_changed_slot)

    def destroy(self) -> None:
        self._cmb_orientation.currentIndexChanged.disconnect()
        self._txt_min_val.textChanged.disconnect()
        self._txt_max_val.textChanged.disconnect()
        self._sld_label_size.valueChanged.disconnect()
        self._spn_major_ticks.valueChanged.disconnect()
        self._spn_minor_ticks.valueChanged.disconnect()
        return super().destroy()

    def _config_changed_slot(self) -> None:
        self.update()

    def _write_val(self, val: bool) -> None:
        self.write_value_slot('val', val)

# region Getters and Setters

    def get_orientation(self) -> Qt.Orientation:
        return cast(Qt.Orientation, self._cmb_orientation.currentData())

    def set_orientation(self, orientation: Qt.Orientation) -> None:
        index = self._cmb_orientation.findData(orientation)
        if index >= 0:
            self._cmb_orientation.setCurrentIndex(index)

    def set_min_val(self, val: float) -> None:
        self._txt_min_val.set_float_value(val)

    def set_max_val(self, val: float) -> None:
        self._txt_max_val.set_float_value(val)

    def set_label_size_percent(self, size: int) -> None:
        self._sld_label_size.setValue(size)

    def set_major_ticks(self, ticks: int) -> None:
        self._spn_major_ticks.setValue(ticks)

    def set_minor_ticks(self, ticks: int) -> None:
        self._spn_minor_ticks.setValue(ticks)

    def get_min_val(self) -> Optional[float]:
        return self._txt_min_val.get_float_value()

    def get_max_val(self) -> Optional[float]:
        return self._txt_max_val.get_float_value()

    def get_label_size_percent(self) -> int:
        return self._sld_label_size.value()

    def get_major_ticks(self) -> int:
        return self._spn_major_ticks.value()

    def get_minor_ticks(self) -> int:
        return self._spn_minor_ticks.value()

# endregion

# region Override

    @classmethod
    def default_size(cls) -> QSize:
        return QSize(64, 32)

    def min_height(self) -> int:
        return 32

    def min_width(self) -> int:
        return 32

    def get_config_widget(self) -> QWidget:
        return self._config_widget

    def mouseMoveEvent(self, event: QGraphicsSceneMouseEvent) -> None:
        return super().mouseMoveEvent(event)

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             edit_mode: bool,
             painter: QPainter
             ) -> None:

        pass

    def get_implementation_config_dict(self) -> Dict[str, Any]:
        min_val = self._txt_min_val.get_float_value()
        max_val = self._txt_max_val.get_float_value()
        return {
            'orientation': cast(Qt.Orientation, self._cmb_orientation.currentData()).value,
            'min_val': min_val if min_val is not None else 0.0,
            'max_val': max_val if max_val is not None else 100.0,
            'label_size_percent': self._sld_label_size.value(),
            'major_ticks': self._spn_major_ticks.value(),
            'minor_ticks': self._spn_minor_ticks.value(),
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        valid_orientation = False
        valid_min_val = False
        valid_max_val = False
        valid_label_size_percent = False
        valid_major_ticks = False
        valid_minor_ticks = False

        if 'orientation' in d and isinstance(d['orientation'], int):
            valid_orientation = deserialize_combobox_val(d['orientation'], Qt.Orientation, self._cmb_orientation)

        if 'min_val' in d and isinstance(d['min_val'], (int, float)):
            self._txt_min_val.set_float_value(float(d['min_val']))
            valid_min_val = True

        if 'max_val' in d and isinstance(d['max_val'], (int, float)):
            self._txt_max_val.set_float_value(float(d['max_val']))
            valid_max_val = True

        if 'label_size_percent' in d and isinstance(d['label_size_percent'], int):
            self._sld_label_size.setValue(d['label_size_percent'])
            valid_label_size_percent = (d['label_size_percent'] == self._sld_label_size.value())

        if 'major_ticks' in d and isinstance(d['major_ticks'], int):
            self._spn_major_ticks.setValue(d['major_ticks'])
            valid_major_ticks = (d['major_ticks'] == self._spn_major_ticks.value())

        if 'minor_ticks' in d and isinstance(d['minor_ticks'], int):
            self._spn_minor_ticks.setValue(d['minor_ticks'])
            valid_minor_ticks = (d['minor_ticks'] == self._spn_minor_ticks.value())

        if not valid_orientation:
            self._logger.warning('Invalid orientation value')
        if not valid_min_val:
            self._logger.warning('Invalid minimum value')
        if not valid_max_val:
            self._logger.warning('Invalid maximum value')
        if not valid_label_size_percent:
            self._logger.warning('Invalid label size percentage')
        if not valid_major_ticks:
            self._logger.warning('Invalid major ticks value')
        if not valid_minor_ticks:
            self._logger.warning('Invalid minor ticks value')

        return (
            valid_orientation
            and valid_min_val
            and valid_max_val
            and valid_label_size_percent
            and valid_major_ticks
            and valid_minor_ticks
        )


# endregion
