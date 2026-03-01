#    chart_range_edit_dialog.py
#        A dialog to edit a chart axis range
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from dataclasses import dataclass
import functools
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QWidget, QGroupBox,
                               QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtCharts import QValueAxis
from scrutiny.gui.widgets.validable_line_edit import FloatValidableLineEdit
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

from scrutiny.tools.typing import *

@dataclass(init=False)
class AxisEditData:
    axis: QValueAxis
    txt_min:FloatValidableLineEdit
    txt_max:FloatValidableLineEdit
    btn_apply:QPushButton
    btn_reset:QPushButton
    initial_min:float
    initial_max:float


    def __init__(self, axis:QValueAxis, parent:QWidget) -> None:
        self.axis = axis
        self.txt_min = FloatValidableLineEdit(parent, hard_validator=QDoubleValidator())
        self.txt_max = FloatValidableLineEdit(parent, hard_validator=QDoubleValidator())
        self.btn_apply = QPushButton("Apply", parent)
        self.btn_reset = QPushButton("Reset", parent)
        self.initial_min = axis.min()
        self.initial_max = axis.max()

class ChartRangeEditDialog(QDialog):
    _axes_edit_data:List[AxisEditData]
    """Data about every axes given to the constructor"""
    _buttons: QDialogButtonBox
    """Standard OK / Cancel button box"""
    _feedback_label: FeedbackLabel
    """A label to display errors"""

    def __init__(self, xaxis: QValueAxis, axes:List[QValueAxis], parent: QWidget) -> None:
        super().__init__(parent)

        self._feedback_label = FeedbackLabel(self)

        self.setWindowTitle(f"Axes range")
        self.setModal(True)

        self._axes_edit_data = []
        self._axes_edit_data.append(AxisEditData(xaxis, self))
        for axis in axes:
            self._axes_edit_data.append(AxisEditData(axis, self))

        scroll_area = QScrollArea(self)
        edit_zone = QWidget()
        edit_zone_layout = QVBoxLayout(edit_zone)
        edit_zone_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll_area.setWidget(edit_zone)
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        for axis_data in self._axes_edit_data:
            prefix = ''
            if axis_data.axis.orientation() == Qt.Orientation.Horizontal:
                prefix = 'X: '
            elif axis_data.axis.orientation() == Qt.Orientation.Vertical:
                prefix = 'Y: '

            gb_title = f'{prefix}{axis_data.axis.titleText()}'
            gb = QGroupBox(gb_title, self)
            gb_layout = QHBoxLayout(gb)
            gb_layout.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
            gb_layout.addWidget(axis_data.txt_min)
            gb_layout.addWidget(axis_data.txt_max)
            gb_layout.addWidget(axis_data.btn_apply)
            gb_layout.addWidget(axis_data.btn_reset)

            axis_data.btn_reset.clicked.connect(functools.partial(self._reset_slot, axis_data))
            axis_data.btn_apply.clicked.connect(functools.partial(self._apply_slot, axis_data))
            axis_data.txt_max.textChanged.connect(functools.partial(self._text_changed_slot, axis_data))
            axis_data.txt_min.textChanged.connect(functools.partial(self._text_changed_slot, axis_data))

            edit_zone_layout.addWidget(gb)

            axis_data.txt_max.setMaximumWidth(axis_data.txt_max.sizeHint().width())
            axis_data.txt_min.setMaximumWidth(axis_data.txt_min.sizeHint().width())
            axis_data.btn_apply.setMaximumWidth(axis_data.btn_apply.sizeHint().width())
            axis_data.btn_reset.setMaximumWidth(axis_data.btn_reset.sizeHint().width())

            self._update_btn_state(axis_data)

        # --- Main layout ---
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll_area)
        main_layout.addWidget(self._feedback_label)

        self.load_ui_from_axis()

    def load_ui_from_axis(self) -> None:
        for axis_data in self._axes_edit_data:
            axis_data.txt_min.set_float_value(axis_data.axis.min())
            axis_data.txt_max.set_float_value(axis_data.axis.max())

    def _text_changed_slot(self, axis_data:AxisEditData, text:str) -> None:
        self._update_btn_state(axis_data)

    def _update_btn_state(self, axis_data:AxisEditData) -> None:
        minval = axis_data.txt_min.get_float_value()
        maxval = axis_data.txt_max.get_float_value()

        if minval is None or maxval is None:
            axis_data.btn_apply.setDisabled(True)
            axis_data.btn_reset.setDisabled(False)
            return

        diff_from_axis = minval != axis_data.axis.min() or maxval != axis_data.axis.max()
        diff_from_initial = minval != axis_data.initial_min or maxval != axis_data.initial_max
        axis_data.btn_apply.setEnabled(diff_from_axis)
        axis_data.btn_reset.setEnabled(diff_from_initial)


    def _reset_slot(self, axis_data:AxisEditData) -> None:
        axis_data.txt_min.set_float_value(axis_data.initial_min)
        axis_data.txt_max.set_float_value(axis_data.initial_max)
        axis_data.axis.setRange(axis_data.initial_min, axis_data.initial_max)
        self._update_btn_state(axis_data)

    def _apply_slot(self, axis_data:AxisEditData) -> None:
        axis_name = axis_data.axis.titleText()
        valid_min = axis_data.txt_min.validate_expect_valid()
        valid_max = axis_data.txt_max.validate_expect_valid()

        if not valid_min or not valid_max:
            self._feedback_label.set_error(f"{axis_name}: Invalid value")
            return

        minval = axis_data.txt_min.get_float_value()
        maxval = axis_data.txt_max.get_float_value()

        assert minval is not None
        assert maxval is not None

        if minval >= maxval:
            self._feedback_label.set_error(f"{axis_name}: Min must be smaller than max")
            return

        axis_data.axis.setRange(minval, maxval)
        self._feedback_label.clear()
        self._update_btn_state(axis_data)
