
from PySide6.QtWidgets import (QDialog, QDialogButtonBox, QWidget, QVBoxLayout, QHBoxLayout, QFormLayout)
from PySide6.QtCore import Qt
from PySide6.QtGui import QDoubleValidator
from PySide6.QtCharts import QValueAxis
from scrutiny.gui.widgets.validable_line_edit import FloatValidableLineEdit
from scrutiny.gui.widgets.feedback_label import FeedbackLabel

from scrutiny.tools.typing import *


class ChartRangeEditDialog(QDialog):
    _value_axis: QValueAxis
    """The ValueAxis we're working on"""
    _buttons: QDialogButtonBox
    """Standard OK / Cancel button box"""
    _txt_min: FloatValidableLineEdit
    """Line edit for the minimum value"""
    _txt_max: FloatValidableLineEdit
    """Line edit for the maximum value"""
    _feedback_label: FeedbackLabel
    """A label to display errors"""

    def __init__(self, value_axis: QValueAxis, parent: QWidget) -> None:
        super().__init__(parent)

        self._value_axis = value_axis
        self._feedback_label = FeedbackLabel(self)

        self.setWindowTitle(f"Axis: {value_axis.titleText()}")
        self.setModal(True)

        # --- Inputs ---
        self._txt_min = FloatValidableLineEdit(self, hard_validator=QDoubleValidator())
        self._txt_max = FloatValidableLineEdit(self, hard_validator=QDoubleValidator())

        form_widget = QWidget(self)
        form = QFormLayout(form_widget)
        form.setAlignment(Qt.AlignmentFlag.AlignLeft)
        form.addRow("Max:", self._txt_max)
        form.addRow("Min:", self._txt_min)

        self._txt_max.setMaximumWidth(self._txt_max.sizeHint().width())
        self._txt_min.setMaximumWidth(self._txt_min.sizeHint().width())

        # --- Button row ---
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self
        )

        btn_row = QWidget(self)
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.addWidget(self._buttons)

        # --- Main layout ---
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(form_widget)
        main_layout.addWidget(self._feedback_label)
        main_layout.addWidget(btn_row)

        self.setTabOrder(self._txt_max, self._txt_min)
        self.setTabOrder(self._txt_min, self._buttons)

        self._buttons.accepted.connect(self._btn_ok_slot)
        self._buttons.rejected.connect(self._btn_cancel_slot)

        self.load_ui_from_axis()
        self._txt_max.selectAll()

    def load_ui_from_axis(self) -> None:
        self._txt_min.set_float_value(self._value_axis.min())
        self._txt_max.set_float_value(self._value_axis.max())

    def _validate(self) -> bool:
        min_valid = self._txt_min.validate_expect_valid()
        max_valid = self._txt_max.validate_expect_valid()

        if not min_valid or not max_valid:
            self._feedback_label.set_error("Invalid values")
            return False

        minval = self.get_min()
        maxval = self.get_max()
        # Validator above allows use to assert not None
        assert minval is not None
        assert maxval is not None
        if minval >= maxval:
            self._feedback_label.set_error("Min must be smaller than Max")
            return False

        self._feedback_label.clear()
        return True

    def _btn_ok_slot(self) -> None:
        if self._validate():
            minval = self.get_min()
            maxval = self.get_max()

            assert minval is not None
            assert maxval is not None

            self._value_axis.setRange(minval, maxval)

            self.accept()

    def _btn_cancel_slot(self) -> None:
        self.reject()

    def get_min(self) -> Optional[float]:
        """Return the validated minimum value, or None if the field is invalid."""
        return self._txt_min.get_float_value()

    def get_max(self) -> Optional[float]:
        """Return the validated maximum value, or None if the field is invalid."""
        return self._txt_max.get_float_value()
