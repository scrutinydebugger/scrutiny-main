
__all__ = ['LinearGaugeHMIWidget', 'ColorSpan', 'NumberFormattingConfig']

import math
import enum

from PySide6.QtGui import QPainter, QPen
from PySide6.QtCore import QSize, Qt, QPointF, QRectF, QSizeF
from PySide6.QtWidgets import (QStyleOptionGraphicsItem, QWidget, QFormLayout, QComboBox,
                               QSpinBox, QGroupBox, QVBoxLayout, QGraphicsItem, QCheckBox)

from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny.gui.components.locals.hmi.common.numerical_text_display import NumericalTextDisplay, NumberFormattingConfig, NumericalTextDisplayStateDict
from scrutiny.gui.components.locals.hmi.common.color_span_editor import ColorSpanEditor, ColorSpanListStateDict, ColorSpan
from scrutiny.gui.components.locals.hmi.common.gauge import GaugeOverflowBehavior
from scrutiny.gui import assets
from scrutiny import tools
from scrutiny.tools.typing import *

class LinearGaugeOrientation(enum.Enum):
    VERTICAL = 1
    HORIZONTAL = 2

class _Dims:
    """Those are relative dimensions used to draw the gauge."""
    COLOR_W = 0.05
    MAJOR_TICK_LEN = 0.12
    MINOR_TICK_LEN = 0.04
    TICK_LABEL_W = 0.30
    TICK_LABEL_H = 0.12

class LinearGaugeHMIWidget(BaseHMIWidget):
    """A HMI widget that draw a gauge with a pointer (needle) that rotate from left to right according to a value, a min and a max"""

    _CATEGORY = LibraryCategory.Display
    _UNIQUE_NAME = 'linear_gauge'
    _DISPLAY_NAME = 'Linear Gauge'
    _ICON = assets.Icons.HMILinearGauge

    # Config
    _config_widget: QWidget
    """the widget given to the HMI Component"""
    _cmb_overflow_behavior: QComboBox
    """A combo box to select the overflow behavior"""
    _cmb_orientation: QComboBox
    """A combo box to select the orientation of the gauge (vertical/horizontal)"""
    _chk_inverted_axis:QCheckBox
    """A checkbox to invert t"""
    _spn_major_ticks: QSpinBox
    """A spinbox to select how many major ticks we have"""
    _spn_minor_ticks: QSpinBox
    """A spinbox to select how many minor ticks we have"""
    _color_span_editor: ColorSpanEditor
    """A widget to define region highlighted in colors. Region are defined by a percentage from 0 to 100 and an associated color."""

    # State variables
    _minval: Optional[float]
    """The last minimum we have received (it's not a constant)"""
    _maxval: Optional[float]
    """The last maximum we have received (it's not a constant)"""

    def __init__(self, app: AbstractComponentAppInterface) -> None:
        super().__init__(app)
        self.declare_value_slot('val', 'Value')
        self.declare_value_slot('min', 'Minimum')
        self.declare_value_slot('max', 'Maximum')

        self._minval = None
        self._maxval = None

        self._cmb_overflow_behavior = QComboBox()
        self._cmb_overflow_behavior.addItem("Clip", GaugeOverflowBehavior.CLIP)
        self._cmb_overflow_behavior.addItem("Show Invalid", GaugeOverflowBehavior.SHOW_NA)

        self._cmb_orientation = QComboBox()
        self._cmb_orientation.addItem("Vertical", LinearGaugeOrientation.VERTICAL)
        self._cmb_orientation.addItem("Horizontal", LinearGaugeOrientation.HORIZONTAL)

        self._chk_inverted_axis = QCheckBox()

        self._spn_major_ticks = QSpinBox()
        self._spn_major_ticks.setMinimum(0)
        self._spn_major_ticks.setMaximum(15)
        self._spn_major_ticks.setValue(7)

        self._spn_minor_ticks = QSpinBox()
        self._spn_minor_ticks.setMinimum(0)
        self._spn_minor_ticks.setMaximum(12)
        self._spn_minor_ticks.setValue(3)

        self._color_span_editor = ColorSpanEditor()
        self._color_span_editor.set_max_span(6)

        self._config_widget = QWidget()
        gb_ticks_display = QGroupBox("Ticks")
        gb_colors = QGroupBox("Colors")
        layout = QVBoxLayout(self._config_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(gb_ticks_display)
        layout.addWidget(gb_colors)

        gb_ticks_display_layout = QFormLayout(gb_ticks_display)
        gb_ticks_display_layout.addRow("Overflow", self._cmb_overflow_behavior)
        gb_ticks_display_layout.addRow("Major Ticks", self._spn_major_ticks)
        gb_ticks_display_layout.addRow("Minor Ticks", self._spn_minor_ticks)
        gb_ticks_display_layout.addRow("Invert axis", self._chk_inverted_axis)

        gb_colors_layout = QVBoxLayout(gb_colors)
        gb_colors_layout.addWidget(self._color_span_editor)

        self._cmb_overflow_behavior.currentIndexChanged.connect(self._config_changed_slot)
        self._cmb_orientation.currentIndexChanged.connect(self._config_changed_slot)
        self._chk_inverted_axis.checkStateChanged.connect(self._config_changed_slot)
        self._spn_major_ticks.valueChanged.connect(self._config_changed_slot)
        self._spn_minor_ticks.valueChanged.connect(self._config_changed_slot)
        self._color_span_editor.signals.row_added.connect(self._config_changed_slot)
        self._color_span_editor.signals.row_removed.connect(self._config_changed_slot)
        self._color_span_editor.signals.row_changed.connect(self._config_changed_slot)

    def _config_changed_slot(self, *args:Any, **kwargs:Any) -> None:
        self.update()


# region Getter & Setters

    def set_overflow_behavior(self, behavior: GaugeOverflowBehavior) -> None:
        index = self._cmb_overflow_behavior.findData(behavior)
        if index >= 0:
            self._cmb_overflow_behavior.setCurrentIndex(index)

    def set_minor_ticks(self, ticks: int) -> None:
        self._spn_minor_ticks.setValue(ticks)

    def set_major_ticks(self, ticks: int) -> None:
        self._spn_major_ticks.setValue(ticks)

    def set_color_spans(self, spans: List[ColorSpan]) -> None:
        self._color_span_editor.set_from_spans_object(spans)

    def get_overflow_behavior(self) -> GaugeOverflowBehavior:
        return cast(GaugeOverflowBehavior, self._cmb_overflow_behavior.currentData())

    def get_minor_ticks(self) -> int:
        return self._spn_minor_ticks.value()

    def get_major_ticks(self) -> int:
        return self._spn_major_ticks.value()

    def get_color_spans(self) -> List[ColorSpan]:
        return self._color_span_editor.get_span_objects()

# endregion

# region Override

    @classmethod
    def default_size(cls) -> QSize:
        return QSize(128, 128)

    def min_width(self) -> int:
        return 64

    def min_height(self) -> int:
        return 64

    def destroy(self) -> None:
        self._cmb_overflow_behavior.currentIndexChanged.disconnect()
        self._cmb_orientation.currentIndexChanged.disconnect()
        self._chk_inverted_axis.checkStateChanged.disconnect()
        self._spn_major_ticks.valueChanged.disconnect()
        self._spn_minor_ticks.valueChanged.disconnect()
        self._color_span_editor.signals.row_added.disconnect()
        self._color_span_editor.signals.row_removed.disconnect()
        self._color_span_editor.signals.row_changed.disconnect()

        super().destroy()

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             painter: QPainter
             ) -> None:

        # Draw is only invoked when a value changes. But here, we want to avoid
        # redrawing the background of the gauge when only the value changes.

        self._minval = values['min']
        self._maxval = values['max']

        bounding_rect = self.boundingRect()
        # Start by computing the dimensions
        aspect_ratio = bounding_rect.height() / bounding_rect.width()
        ref_size = bounding_rect.width() / 2





    def get_config_widget(self) -> Optional[QWidget]:
        return self._config_widget

    def get_implementation_config_dict(self) -> Dict[str, Any]:
        return {
            'overflow': cast(GaugeOverflowBehavior, self._cmb_overflow_behavior.currentData()).value,
            'minor_tick': self._spn_minor_ticks.value(),
            'major_tick': self._spn_major_ticks.value(),
            'colors': self._color_span_editor.get_state_dict()
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        valid_overflow = False
        valid_minor_tick = False
        valid_major_tick = False
        valid_colors = False

        if 'overflow' in d and isinstance(d['overflow'], int):
            with tools.SuppressException(Exception):
                behavior = GaugeOverflowBehavior(d['overflow'])
                index = self._cmb_overflow_behavior.findData(behavior)
                if index >= 0:
                    self._cmb_overflow_behavior.setCurrentIndex(index)
                    valid_overflow = True

        if 'minor_tick' in d and isinstance(d['minor_tick'], int):
            self._spn_minor_ticks.setValue(d['minor_tick'])
            if d['minor_tick'] == self._spn_minor_ticks.value():
                valid_minor_tick = True

        if 'major_tick' in d and isinstance(d['major_tick'], int):
            self._spn_major_ticks.setValue(d['major_tick'])
            if d['major_tick'] == self._spn_major_ticks.value():
                valid_major_tick = True

        if 'colors' in d and isinstance(d['colors'], dict):
            valid_colors = self._color_span_editor.set_state_dict(cast(ColorSpanListStateDict, d['colors']))


        if not valid_overflow:
            self._logger.warning('Invalid overflow behavior')
        if not valid_minor_tick:
            self._logger.warning('Invalid minor tick value')
        if not valid_major_tick:
            self._logger.warning('Invalid major tick value')
        if not valid_colors:
            self._logger.warning('Invalid color spans')

        return (
            valid_overflow
            and valid_minor_tick
            and valid_major_tick
            and valid_colors
        )
# endregion
