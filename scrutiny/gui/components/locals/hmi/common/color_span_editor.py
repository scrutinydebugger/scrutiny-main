__all__ = ['ColorSpanEditor', 'ColorSpan', 'SpanColor']

import enum
from dataclasses import dataclass

from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QVBoxLayout, QDoubleSpinBox,
                               QComboBox, QToolButton, QLabel, QPushButton)
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtCore import Signal, QObject, Qt, QSize

from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme

from scrutiny import tools
from scrutiny.tools.typing import *


class SpanColor(enum.Enum):
    GOOD = "good"
    WARNING = "warning"
    DANGER = "danger"

    def to_qcolor(self) -> QColor:
        _map = {
            SpanColor.GOOD: HMITheme.Color.green_good(),
            SpanColor.WARNING: HMITheme.Color.yellow_warning(),
            SpanColor.DANGER: HMITheme.Color.red_danger()
        }
        if self in _map:
            return _map[self]

        raise NotImplementedError(f"Unknown color {self}")

    def to_str(self) -> str:
        return self.value

    @classmethod
    def from_str(cls, v: str) -> Self:
        return cls(v)


@dataclass(slots=True)
class ColorSpan:
    min_val: float
    max_val: float
    color: SpanColor


class _SpanRow(QWidget):
    """A single row: [start] to [stop] [color] [remove]"""

    class _Signals(QObject):
        remove_requested = Signal()
        row_changed = Signal()

    _spn_start: QDoubleSpinBox
    _spn_stop: QDoubleSpinBox
    _cmb_color: QComboBox
    _btn_remove: QToolButton

    _signals: _Signals

    @tools.copy_type(QWidget.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self._signals = self._Signals()

        self._spn_start = QDoubleSpinBox(minimum=0, maximum=100, value=0)
        self._spn_start.setMaximumWidth(self._spn_start.sizeHint().width() + 15)
        self._spn_start.setSuffix("%")
        self._spn_start.setSingleStep(0.1)
        self._spn_start.setDecimals(1)
        self._spn_stop = QDoubleSpinBox(minimum=0, maximum=100, value=100)
        self._spn_stop.setMaximumWidth(self._spn_stop.sizeHint().width() + 15)
        self._spn_stop.setSuffix("%")
        self._spn_stop.setSingleStep(0.1)
        self._spn_stop.setDecimals(1)

        self._cmb_color = QComboBox()
        icon_size = QSize(self._cmb_color.height(), self._cmb_color.height())
        good_icon = QPixmap(icon_size)
        good_icon.fill(SpanColor.GOOD.to_qcolor())
        warning_icon = QPixmap(icon_size)
        warning_icon.fill(SpanColor.WARNING.to_qcolor())
        danger_icon = QPixmap(icon_size)
        danger_icon.fill(SpanColor.DANGER.to_qcolor())

        self._cmb_color.addItem(good_icon, "Good", SpanColor.GOOD)
        self._cmb_color.addItem(warning_icon, "Warning", SpanColor.WARNING)
        self._cmb_color.addItem(danger_icon, "Danger", SpanColor.DANGER)

        self._btn_remove = QToolButton()
        self._btn_remove.setIcon(scrutiny_get_theme().load_tiny_icon(assets.Icons.RedX))
        self._btn_remove.setText("Remove")
        self._btn_remove.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self._btn_remove.clicked.connect(self._signals.remove_requested)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        line1 = QWidget()
        line1_layout = QHBoxLayout(line1)
        line1_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        line1_layout.setContentsMargins(0, 0, 0, 0)
        line1_layout.addWidget(self._spn_start)
        line1_layout.addWidget(QLabel(" to "))
        line1_layout.addWidget(self._spn_stop)

        line2 = QWidget()
        line2_layout = QHBoxLayout(line2)
        line2_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        line2_layout.setContentsMargins(0, 0, 0, 0)
        line2_layout.addWidget(QLabel("Color:"))
        line2_layout.addWidget(self._cmb_color)
        line2_layout.addWidget(self._btn_remove)

        layout.addWidget(line1)
        layout.addWidget(line2)

        self._spn_start.valueChanged.connect(self._value_changed_slot)
        self._spn_stop.valueChanged.connect(self._value_changed_slot)

        self._spn_start.valueChanged.connect(self._signals.row_changed)
        self._spn_stop.valueChanged.connect(self._signals.row_changed)
        self._cmb_color.currentIndexChanged.connect(self._signals.row_changed)

    @property
    def signals(self) -> _Signals:
        return self._signals

    def _value_changed_slot(self, v: int) -> None:
        self.update_minmax()

    def update_minmax(self) -> None:
        self._spn_stop.setMinimum(self._spn_start.value())
        self._spn_start.setMaximum(self._spn_stop.value())

    def get_span_object(self) -> ColorSpan:
        start = self._spn_start.value()
        stop = self._spn_stop.value()
        color = cast(SpanColor, self._cmb_color.currentData())
        return ColorSpan(min_val=min(start, stop), max_val=max(start, stop), color=color)

    def set_from_span_object(self, span: ColorSpan) -> None:
        self._spn_start.setValue(span.min_val)
        self._spn_stop.setValue(span.max_val)
        index = self._cmb_color.findData(span.color)
        if index >= 0:
            self._cmb_color.setCurrentIndex(index)


class ColorSpanEditor(QWidget):

    class _Signals(QObject):
        row_added = Signal()
        row_removed = Signal()
        row_changed = Signal()

    _max_spans: int
    _rows: List[_SpanRow]
    _rows_layout: QVBoxLayout
    _btn_add: QPushButton

    _signals: _Signals

    def __init__(self) -> None:
        super().__init__()

        self._signals = self._Signals()

        self._rows = []
        self._max_spans = 6
        self._rows_layout = QVBoxLayout()
        self._rows_layout.setContentsMargins(0, 0, 0, 0)

        self._btn_add = QPushButton("Add color")
        self._btn_add.setMaximumWidth(self._btn_add.sizeHint().width())
        self._btn_add.clicked.connect(lambda: self._add_row())

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self._btn_add)
        main_layout.addLayout(self._rows_layout)
        main_layout.addStretch()

    @property
    def signals(self) -> _Signals:
        return self._signals

    def set_max_span(self, v: int) -> None:
        if v < 1:
            raise ValueError("Cannot set a number of span smaller than 1")
        self._max_spans = v

    def _add_row(self, span: Optional[ColorSpan] = None) -> None:
        if len(self._rows) >= self._max_spans:
            return

        row = _SpanRow(self)
        if span is not None:
            row.set_from_span_object(span)
        row.signals.remove_requested.connect(lambda: self._remove_row(row))
        row.signals.row_changed.connect(self._signals.row_changed)

        self._rows.append(row)
        self._rows_layout.addWidget(row)
        self._update_add_button()

        self._signals.row_added.emit()

    def _remove_row(self, row: _SpanRow) -> None:
        if row in self._rows:
            self._rows.remove(row)
            self._rows_layout.removeWidget(row)
            row.signals.remove_requested.disconnect()
            row.signals.row_changed.disconnect()
            row.deleteLater()
        self._update_add_button()
        self._signals.row_removed.emit()

    def _update_add_button(self) -> None:
        self._btn_add.setEnabled(len(self._rows) < self._max_spans)

    def get_span_objects(self) -> List[ColorSpan]:
        return [row.get_span_object() for row in self._rows]

    def set_from_spans_object(self, spans: "List[ColorSpan]") -> None:
        self.clear()
        for span in spans[:self._max_spans]:
            self._add_row(span)

    def clear(self) -> None:
        for row in list(self._rows):
            self._remove_row(row)
