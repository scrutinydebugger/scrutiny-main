#    color_indicator_hmi_widget.py
#        A HMI widget that simply turn a circle ON or OFF with customizable colors based on
#        a condition.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['ColorIndicatorHMIWidget', 'RelationalOperator', 'ActiveBehavior']

import enum

from PySide6.QtGui import QPainter, QPen, QRadialGradient, QBrush, QColor
from PySide6.QtCore import QSize, Qt, QPointF, QTimer
from PySide6.QtWidgets import QVBoxLayout, QWidget, QGroupBox, QComboBox, QFormLayout

from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.components.locals.hmi.hmi_widgets.base_hmi_widget import BaseHMIWidget, WatchableValueType
from scrutiny.gui.components.locals.hmi.common.hmi_colors import HMIColor, create_color_combobox
from scrutiny.gui import assets
from scrutiny.tools.typing import *

from scrutiny.gui.components.locals.hmi.hmi_library_category import LibraryCategory
from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny import tools


class _Dims:
    """Those are relative dimensions used to draw the gauge."""
    RADIUS = 1
    BORDER_W = 0.05


class RelationalOperator(enum.Enum):
    # Keep those indices values for future compatibility.
    # Those are written in the dashboard file.
    GE = 1
    GEQ = 2
    LE = 3
    LEQ = 4
    EQ = 5
    NEQ = 6


class ActiveBehavior(enum.Enum):
    Steady = 1
    BlinkSlow = 2
    BlinkFast = 3


_BLINK_SLOW_INTERVAL_MS = 1000
_BLINK_FAST_INTERVAL_MS = 400


class ColorIndicatorHMIWidget(BaseHMIWidget):

    _CATEGORY = LibraryCategory.Display
    _UNIQUE_NAME = 'color_indicator'
    _DISPLAY_NAME = 'Color Indicator'
    _ICON = assets.Icons.HMIColorIndicator

    _cmb_color_on: QComboBox
    _cmb_color_off: QComboBox
    _cmb_operator: QComboBox
    _cmb_active_behavior: QComboBox
    _tmr_blink: QTimer
    _blink_enable_flag: bool
    _last_condition_eval_result: bool
    _config_widget: QWidget

    def __init__(self, app: AbstractComponentAppInterface) -> None:
        super().__init__(app)
        self.declare_value_slot('operand1', 'Operand 1')
        self.declare_value_slot('operand2', 'Operand 2')

        self._config_widget = QWidget()

        self._cmb_color_on = create_color_combobox()
        self._cmb_color_off = create_color_combobox()
        self._cmb_operator = QComboBox()
        self._cmb_active_behavior = QComboBox()
        self._tmr_blink = QTimer()
        self._blink_enable_flag = False
        self._last_condition_eval_result = False

        self._cmb_operator.addItem("=", RelationalOperator.EQ)
        self._cmb_operator.addItem("!=", RelationalOperator.NEQ)
        self._cmb_operator.addItem(">", RelationalOperator.GE)
        self._cmb_operator.addItem(">=", RelationalOperator.GEQ)
        self._cmb_operator.addItem("<", RelationalOperator.LE)
        self._cmb_operator.addItem("<=", RelationalOperator.LEQ)

        self._cmb_active_behavior.addItem("Steady", ActiveBehavior.Steady)
        self._cmb_active_behavior.addItem("Blink Slow", ActiveBehavior.BlinkSlow)
        self._cmb_active_behavior.addItem("Blink Fast", ActiveBehavior.BlinkFast)

        config_layout = QVBoxLayout(self._config_widget)
        config_layout.setContentsMargins(0, 0, 0, 0)
        gb = QGroupBox("Configuration")
        gb_layout = QFormLayout(gb)
        gb_layout.addRow("Condition", self._cmb_operator)
        gb_layout.addRow("ON color", self._cmb_color_on)
        gb_layout.addRow("OFF color", self._cmb_color_off)
        gb_layout.addRow("Active Behavior", self._cmb_active_behavior)
        config_layout.addWidget(gb)

        self._cmb_operator.setCurrentIndex(self._cmb_operator.findData(RelationalOperator.NEQ))
        self._cmb_color_on.setCurrentIndex(self._cmb_color_on.findData(HMIColor.GOOD))
        self._cmb_color_off.setCurrentIndex(self._cmb_color_off.findData(HMIColor.INACTIVE))
        self._cmb_active_behavior.setCurrentIndex(self._cmb_active_behavior.findData(ActiveBehavior.Steady))

        self.configure_vslot_constant('operand2', "0")

        self._cmb_operator.currentIndexChanged.connect(self._config_changed_slot)
        self._cmb_color_on.currentIndexChanged.connect(self._config_changed_slot)
        self._cmb_color_off.currentIndexChanged.connect(self._config_changed_slot)
        self._cmb_active_behavior.currentIndexChanged.connect(self._active_behavior_changed)
        self._tmr_blink.timeout.connect(self._blink_timer_slot)

    def destroy(self) -> None:
        self._tmr_blink.stop()
        self._cmb_operator.currentIndexChanged.disconnect()
        self._cmb_color_on.currentIndexChanged.disconnect()
        self._cmb_color_off.currentIndexChanged.disconnect()
        self._cmb_active_behavior.currentIndexChanged.disconnect()
        self._tmr_blink.timeout.disconnect()

        return super().destroy()

    def _config_changed_slot(self) -> None:
        self.update()

    def _active_behavior_changed(self) -> None:
        self._blink_enable_flag = True
        behavior = cast(ActiveBehavior, self._cmb_active_behavior.currentData())
        if behavior == ActiveBehavior.Steady:
            self._tmr_blink.stop()
        elif behavior == ActiveBehavior.BlinkSlow:
            self._tmr_blink.setInterval(_BLINK_SLOW_INTERVAL_MS)
            self._tmr_blink.start()
        elif behavior == ActiveBehavior.BlinkFast:
            self._tmr_blink.setInterval(_BLINK_FAST_INTERVAL_MS)
            self._tmr_blink.start()
        else:
            raise NotImplementedError("Unknown active behavior")

        self.update()

    def _eval_condition(self, condition: RelationalOperator, v1: Optional[WatchableValueType], v2: Optional[WatchableValueType]) -> bool:
        if v1 is None or v2 is None:
            return False

        # Python type handling already ahs the behavior we need. nothing to do other than casting.
        if condition == RelationalOperator.NEQ:
            return v1 != v1.__class__(v2)
        elif condition == RelationalOperator.EQ:
            return v1 == v1.__class__(v2)
        elif condition == RelationalOperator.GE:
            return v1 > v1.__class__(v2)
        elif condition == RelationalOperator.GEQ:
            return v1 >= v1.__class__(v2)
        elif condition == RelationalOperator.LE:
            return v1 < v1.__class__(v2)
        elif condition == RelationalOperator.LEQ:
            return v1 <= v1.__class__(v2)

        raise NotImplementedError("Unknown condition")

    @staticmethod
    def _load_combobox(val: Any, dtype: Type[Any], cmbbox: QComboBox) -> bool:
        with tools.SuppressException(Exception):
            index = cmbbox.findData(dtype(val))
            if index != -1:
                cmbbox.setCurrentIndex(index)
                return True

        return False

    def _blink_timer_slot(self) -> None:
        self._blink_enable_flag = not self._blink_enable_flag
        self.update()

# region Getters and Setters

    def get_on_color(self) -> HMIColor:
        return cast(HMIColor, self._cmb_color_on.currentData())

    def set_on_color(self, color: HMIColor) -> None:
        index = self._cmb_color_on.findData(color)
        if index >= 0:
            self._cmb_color_on.setCurrentIndex(index)

    def get_off_color(self) -> HMIColor:
        return cast(HMIColor, self._cmb_color_off.currentData())

    def set_off_color(self, color: HMIColor) -> None:
        index = self._cmb_color_off.findData(color)
        if index >= 0:
            self._cmb_color_off.setCurrentIndex(index)

    def get_operator(self) -> RelationalOperator:
        return cast(RelationalOperator, self._cmb_operator.currentData())

    def set_operator(self, operator: RelationalOperator) -> None:
        index = self._cmb_operator.findData(operator)
        if index >= 0:
            self._cmb_operator.setCurrentIndex(index)

    def get_active_behavior(self) -> ActiveBehavior:
        return cast(ActiveBehavior, self._cmb_active_behavior.currentData())

    def set_active_behavior(self, behavior: ActiveBehavior) -> None:
        index = self._cmb_active_behavior.findData(behavior)
        if index >= 0:
            self._cmb_active_behavior.setCurrentIndex(index)

# endregion

# region Override

    @classmethod
    def default_size(cls) -> QSize:
        return QSize(48, 48)

    def min_height(self) -> int:
        return 16

    def min_width(self) -> int:
        return 16

    def get_config_widget(self) -> QWidget:
        return self._config_widget

    def draw(self,
             values: Dict[str, Optional[WatchableValueType]],
             painter: QPainter
             ) -> None:
        op1 = values['operand1']
        op2 = values['operand2']
        bounding_rect = self.boundingRect()
        ref_width = bounding_rect.width() / 2
        aspect_ratio = bounding_rect.height() / bounding_rect.width()
        radius = (_Dims.RADIUS - _Dims.BORDER_W / 2) * ref_width
        inner_radius = (_Dims.RADIUS - _Dims.BORDER_W) * ref_width
        border_width = _Dims.BORDER_W * ref_width
        center = QPointF(bounding_rect.width() / 2, bounding_rect.height() / 2)

        result = self._eval_condition(self._cmb_operator.currentData(), op1, op2)
        if result and not self._last_condition_eval_result:
            self._blink_enable_flag = True  # Make sure we start a "true" event on with a display of ON state
            if self._tmr_blink.isActive():
                self._tmr_blink.stop()
                self._tmr_blink.start()

        self._last_condition_eval_result = result
        if result and self._blink_enable_flag:
            color = cast(HMIColor, self._cmb_color_on.currentData()).to_qcolor()
        else:
            color = cast(HMIColor, self._cmb_color_off.currentData()).to_qcolor()

        painter.setBrush(color)
        pen = QPen()
        pen.setWidthF(border_width)
        pen.setColor(HMITheme.Color.frame_border())
        painter.setPen(pen)
        painter.drawEllipse(center, radius, radius * aspect_ratio)

        painter.setPen(Qt.PenStyle.NoPen)
        gradient = QRadialGradient(center, radius)
        gradient.setColorAt(0, QColor("#33ffffff"))  # 33 is alpha channel
        gradient.setColorAt(1, QColor("#33000000"))
        painter.setBrush(QBrush(gradient))
        painter.drawEllipse(center, inner_radius, inner_radius * aspect_ratio)

    def get_implementation_config_dict(self) -> Dict[str, Any]:
        return {
            'operator': cast(RelationalOperator, self._cmb_operator.currentData()).value,
            'off_color': cast(HMIColor, self._cmb_color_off.currentData()).value,
            'on_color': cast(HMIColor, self._cmb_color_on.currentData()).value,
            'active_behavior': cast(ActiveBehavior, self._cmb_active_behavior.currentData()).value,
        }

    def apply_implementation_config_dict(self, d: Dict[str, Any]) -> bool:
        valid_operator = False
        valid_on_color = False
        valid_off_color = False
        valid_active_behavior = False

        if 'operator' in d and isinstance(d['operator'], int):
            valid_operator = self._load_combobox(d['operator'], RelationalOperator, self._cmb_operator)

        if 'off_color' in d and isinstance(d['off_color'], str):
            valid_off_color = self._load_combobox(d['off_color'], HMIColor, self._cmb_color_off)

        if 'on_color' in d and isinstance(d['on_color'], str):
            valid_on_color = self._load_combobox(d['on_color'], HMIColor, self._cmb_color_on)

        if 'active_behavior' in d and isinstance(d['active_behavior'], int):
            valid_active_behavior = self._load_combobox(d['active_behavior'], ActiveBehavior, self._cmb_active_behavior)

        if not valid_operator:
            self._logger.warning("Invalid condition operator")
        if not valid_on_color:
            self._logger.warning("Invalid ON color")
        if not valid_off_color:
            self._logger.warning("Invalid OFF color")
        if not valid_active_behavior:
            self._logger.warning("Invalid active behavior")

        return (
            valid_operator
            and valid_on_color
            and valid_off_color
            and valid_active_behavior
        )

# endregion
