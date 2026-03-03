#    chart_range_edit_dialog.py
#        A dialog to configure a chart axes range
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from dataclasses import dataclass
import functools
import math
from PySide6.QtWidgets import (QDialog, QWidget, QGroupBox, QLabel,
                               QVBoxLayout, QHBoxLayout, QScrollArea, QPushButton)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtCharts import QValueAxis
from scrutiny.gui.widgets.validable_line_edit import FloatValidableLineEdit
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny import tools

from scrutiny.tools.typing import *


@dataclass(init=False)
class AxisEditData:
    """Each axis has a row with those widgets"""
    axis: QValueAxis
    """The graph axis object"""
    txt_min: FloatValidableLineEdit
    """Min textbox"""
    txt_max: FloatValidableLineEdit
    """Max textbox"""
    btn_apply: QPushButton
    """Apply button"""
    btn_reset: QPushButton
    """Reset button"""
    initial_min: float
    """Axis min when the dialog was created"""
    initial_max: float
    """Axis max when the dialog was created"""

    def __init__(self, axis: QValueAxis, parent: QWidget) -> None:
        self.axis = axis
        self.txt_min = FloatValidableLineEdit(parent, hard_validator=QDoubleValidator())
        self.txt_max = FloatValidableLineEdit(parent, hard_validator=QDoubleValidator())
        self.btn_apply = QPushButton("Apply", parent)
        self.btn_reset = QPushButton("Reset", parent)
        self.initial_min = tools.f2g(axis.min())
        self.initial_max = tools.f2g(axis.max())


class ChartRangeEditDialog(QDialog):
    _axes_edit_data: List[AxisEditData]
    """Data about every axes given to the constructor"""
    _btn_close: QPushButton
    """Close button"""
    _btn_apply_all: QPushButton
    """Apply All button"""
    _feedback_label: FeedbackLabel
    """A label to display errors"""

    def __init__(self, xaxis: QValueAxis, axes: Sequence[QValueAxis], parent: QWidget) -> None:
        super().__init__(parent)

        self._feedback_label = FeedbackLabel(self)
        self._btn_close = QPushButton("Close", parent=self)
        self._btn_apply_all = QPushButton("Apply All", parent=self)

        self.setWindowTitle(f"Axes range")
        self.setModal(True)

        self._axes_edit_data = []
        self._axes_edit_data.append(AxisEditData(xaxis, self))
        for axis in axes:
            self._axes_edit_data.append(AxisEditData(axis, self))

        scroll_area = QScrollArea(self)
        edit_zone = QWidget()
        edit_zone_layout = QVBoxLayout(edit_zone)
        edit_zone_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)

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

            min_container = QWidget()
            minlabel = QLabel("Min:")
            min_container_layout = QHBoxLayout(min_container)
            min_container_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            min_container_layout.addWidget(minlabel)
            min_container_layout.addWidget(axis_data.txt_min)
            minlabel.setMaximumWidth(minlabel.sizeHint().width())
            min_container.setMaximumWidth(min_container.sizeHint().width())
            gb_layout.addWidget(min_container)

            max_container = QWidget()
            maxlabel = QLabel("Max:")
            max_container_layout = QHBoxLayout(max_container)
            max_container_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            max_container_layout.addWidget(maxlabel)
            max_container_layout.addWidget(axis_data.txt_max)
            maxlabel.setMaximumWidth(minlabel.sizeHint().width())
            max_container.setMaximumWidth(max_container.sizeHint().width())
            gb_layout.addWidget(max_container)

            gb_layout.addWidget(axis_data.btn_apply)
            gb_layout.addWidget(axis_data.btn_reset)

            axis_data.btn_reset.clicked.connect(functools.partial(self._reset_slot, axis_data))
            axis_data.btn_apply.clicked.connect(functools.partial(self._apply_single_slot, axis_data))
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

        btn_container = QWidget()
        btn_layout = QHBoxLayout(btn_container)
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        btn_layout.addWidget(self._btn_close)
        btn_layout.addWidget(self._btn_apply_all)
        main_layout.addWidget(btn_container)

        self._btn_apply_all.clicked.connect(self._apply_all_slot)
        self._btn_close.clicked.connect(self.close)

        self.load_ui_from_axis()

    def load_ui_from_axis(self) -> None:
        for axis_data in self._axes_edit_data:
            axis_data.txt_min.set_float_value(axis_data.axis.min())  # Apply f2g
            axis_data.txt_max.set_float_value(axis_data.axis.max())  # Apply f2g

    def _text_changed_slot(self, axis_data: AxisEditData, text: str) -> None:
        self._update_btn_state(axis_data)

    def _update_btn_state(self, axis_data: AxisEditData) -> None:
        """Enable/disable buttons based on axes values.
        Apply is enabled if the value changed.
        Reset is enabled if the value written is different from initial
        """
        minval = axis_data.txt_min.get_float_value()
        maxval = axis_data.txt_max.get_float_value()

        if minval is None or maxval is None:
            axis_data.btn_apply.setDisabled(True)
            axis_data.btn_reset.setDisabled(False)
            return

        axis_min = tools.f2g(axis_data.axis.min())
        axis_max = tools.f2g(axis_data.axis.max())
        diff_from_axis = not math.isclose(minval, axis_min) or not math.isclose(maxval, axis_max)
        diff_from_initial = not math.isclose(minval, axis_data.initial_min) or not math.isclose(maxval, axis_data.initial_max)

        axis_data.btn_apply.setEnabled(diff_from_axis)
        axis_data.btn_reset.setEnabled(diff_from_initial)

    def _reset_slot(self, axis_data: AxisEditData) -> None:
        """Reset button click"""
        axis_data.txt_min.set_float_value(axis_data.initial_min)
        axis_data.txt_max.set_float_value(axis_data.initial_max)
        axis_data.axis.setRange(axis_data.initial_min, axis_data.initial_max)
        self._update_btn_state(axis_data)

    def _apply_single_slot(self, axis_data: AxisEditData) -> None:
        """Apply button (for a single axis)"""
        self._validate_apply_axis(axis_data)

    def _apply_all_slot(self) -> None:
        """Apply all button"""
        all_fine = True
        for axis_data in self._axes_edit_data:
            applied = self._validate_apply_axis(axis_data)
            all_fine = all_fine and applied
            if not applied:
                break

        if all_fine:
            self.close()

    def _validate_apply_axis(self, axis_data: AxisEditData) -> bool:
        """Check that values for an axis in the textboxes are valid and apply if they are """
        axis_name = axis_data.axis.titleText()
        valid_min = axis_data.txt_min.validate_expect_valid()
        valid_max = axis_data.txt_max.validate_expect_valid()

        if not valid_min or not valid_max:
            self._feedback_label.set_error(f"{axis_name}: Invalid value")
            return False

        minval = axis_data.txt_min.get_float_value()
        maxval = axis_data.txt_max.get_float_value()

        assert minval is not None
        assert maxval is not None

        # Keep significant digits
        minval = tools.f2g(minval)
        maxval = tools.f2g(maxval)

        axis_data.txt_min.set_float_value(minval)
        axis_data.txt_max.set_float_value(maxval)

        if minval >= maxval:
            self._feedback_label.set_error(f"{axis_name}: Min must be smaller than max")
            return False

        axis_data.axis.setRange(minval, maxval)
        self._feedback_label.clear()
        self._update_btn_state(axis_data)
        return True
