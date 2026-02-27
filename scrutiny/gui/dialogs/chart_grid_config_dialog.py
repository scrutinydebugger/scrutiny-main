#    chart_grid_config_dialog.py
#        A dialog to configure the grid on a ScrutinyChart
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['GridConfiguration', 'GridConfiguration', 'SingleTypeGridConfiguration']

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QWidget, QVBoxLayout, QHBoxLayout,
    QGroupBox, QFormLayout, QSpinBox, QCheckBox,
    QComboBox, QPushButton, QColorDialog
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt
from scrutiny.gui.widgets.base_chart import SingleTypeGridConfiguration, GridConfiguration


from scrutiny.tools.typing import *


class _ColorButton(QWidget):
    _btn: QPushButton
    _color: QColor

    def __init__(self, color: QColor, parent: QWidget) -> None:
        super().__init__(parent)
        self._color = QColor(color)
        self._btn = QPushButton(self)
        self._btn.setMinimumWidth(60)
        self._btn.clicked.connect(self._open_color_dialog)
        self._update_appearance()

    def _open_color_dialog(self) -> None:
        new_color = QColorDialog.getColor(self._color, self, "Select Color")
        if new_color.isValid():
            self._color = new_color
            self._update_appearance()

    def _update_appearance(self) -> None:
        self._btn.setStyleSheet(
            f"background-color: {self._color.name(QColor.NameFormat.HexRgb)}; border: 1px solid gray;"
        )

    def get_color(self) -> QColor:
        """Return a copy of the currently selected color"""
        return QColor(self._color)

    def set_color(self, color: QColor) -> None:
        """Set the current color and update the button appearance"""
        self._color = QColor(color)
        self._update_appearance()


class _SingleTypeGridConfigWidget(QGroupBox):

    _chk_visible: QCheckBox
    """Checkbox to toggle grid visibility"""
    _spn_tick_count: QSpinBox
    """Spinbox for the number of grid major ticks"""
    _btn_color: _ColorButton
    """Color picker button for the grid line color"""
    _cmb_line_style: QComboBox
    """Dropdown to choose between Solid and Dashed line style"""
    _spn_line_width: QSpinBox
    """Spinbox for the grid line width in pixels"""

    def __init__(self, title: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(title, parent)

        self._chk_visible = QCheckBox(self)

        self._spn_tick_count = QSpinBox(self)
        self._spn_tick_count.setMinimum(0)
        self._spn_tick_count.setMaximum(10)

        self._btn_color = _ColorButton(QColor(0, 0, 0), self)

        self._cmb_line_style = QComboBox(self)

        self._cmb_line_style.addItem("Solid", Qt.PenStyle.SolidLine)
        self._cmb_line_style.addItem("Dash", Qt.PenStyle.DashLine)
        self._cmb_line_style.addItem("Dot", Qt.PenStyle.DotLine)

        self._spn_line_width = QSpinBox(self)
        self._spn_line_width.setMinimum(0)
        self._spn_line_width.setMaximum(10)

        form = QFormLayout(self)
        form.addRow("Visible:", self._chk_visible)
        form.addRow("Tick Count:", self._spn_tick_count)
        form.addRow("Line Color:", self._btn_color)
        form.addRow("Line Style:", self._cmb_line_style)
        form.addRow("Line Width:", self._spn_line_width)

        self._chk_visible.checkStateChanged.connect(self._chk_visible_state_changed_slot)

    def _chk_visible_state_changed_slot(self, state: Qt.CheckState) -> None:
        self._update_visual()

    def _update_visual(self) -> None:
        if self._chk_visible.checkState() == Qt.CheckState.Checked:
            self._spn_tick_count.setEnabled(True)
            self._btn_color.setEnabled(True)
            self._cmb_line_style.setEnabled(True)
            self._spn_line_width.setEnabled(True)
            self._spn_tick_count.setMinimum(1)
        else:
            self._spn_tick_count.setEnabled(False)
            self._btn_color.setEnabled(False)
            self._cmb_line_style.setEnabled(False)
            self._spn_line_width.setEnabled(False)
            self._spn_tick_count.setMinimum(0)

    def load_config(self, config: SingleTypeGridConfiguration) -> None:
        """Populate all widgets from a GridConfiguration"""
        if config.tick_count > 0:
            self._chk_visible.setChecked(config.visible)
        else:
            self._chk_visible.setChecked(False)
        self._spn_tick_count.setValue(config.tick_count)
        self._btn_color.set_color(config.color)
        idx = self._cmb_line_style.findData(config.line_style)
        if idx >= 0:
            self._cmb_line_style.setCurrentIndex(idx)
        else:
            self._cmb_line_style.setCurrentIndex(self._cmb_line_style.findData(Qt.PenStyle.SolidLine))

        self._spn_line_width.setValue(config.line_width)

        self._update_visual()

    def read_config(self) -> SingleTypeGridConfiguration:
        """Build a GridConfiguration from the current widget values"""
        line_style = cast(Qt.PenStyle, self._cmb_line_style.currentData())
        assert isinstance(line_style, Qt.PenStyle)

        return SingleTypeGridConfiguration(
            visible=self._chk_visible.isChecked(),
            tick_count=self._spn_tick_count.value(),
            color=self._btn_color.get_color(),
            line_style=line_style,
            line_width=self._spn_line_width.value(),
        )


class GridConfigDialog(QDialog):
    _config: GridConfiguration
    """The confirmed configuration, updated only when the user accepts the dialog"""

    _major_grid_widget: _SingleTypeGridConfigWidget
    """Widget group for the major grid settings"""
    _minor_grid_widget: _SingleTypeGridConfigWidget
    """Widget group for the minor grid settings"""
    _btn_reset: QPushButton
    """Button that resets all widgets to the built-in default values"""
    _buttons: QDialogButtonBox
    """Standard OK / Cancel button box"""

    def __init__(self, config: GridConfiguration, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)

        self._config = config   # Immutable

        self.setWindowTitle("Grid Configuration")
        self.setModal(True)
        self.setWindowFlags(
            Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.Dialog
        )

        # --- Grid groups ---
        self._major_grid_widget = _SingleTypeGridConfigWidget("Major Grid", self)
        self._minor_grid_widget = _SingleTypeGridConfigWidget("Minor Grid", self)

        # --- Button row ---
        self._btn_reset = QPushButton("Reset to Defaults", self)
        self._buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )

        btn_row = QWidget(self)
        btn_row_layout = QHBoxLayout(btn_row)
        btn_row_layout.setContentsMargins(0, 0, 0, 0)
        btn_row_layout.addWidget(self._btn_reset)
        btn_row_layout.addStretch()
        btn_row_layout.addWidget(self._buttons)

        # --- Main layout ---
        main_layout = QVBoxLayout(self)
        config_container = QWidget()
        config_layout = QHBoxLayout(config_container)
        self._major_grid_widget.setMinimumWidth(250)
        self._minor_grid_widget.setMinimumWidth(250)
        config_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        config_layout.setSpacing(50)
        config_layout.addWidget(self._minor_grid_widget)
        config_layout.addWidget(self._major_grid_widget)

        main_layout.addWidget(config_container)
        main_layout.addWidget(btn_row)

        self._buttons.accepted.connect(self._btn_ok_slot)
        self._buttons.rejected.connect(self._btn_cancel_slot)
        self._btn_reset.clicked.connect(self._btn_reset_slot)

        self._load_config_to_ui(config)

    def _load_config_to_ui(self, config: GridConfiguration) -> None:
        """Populate all widgets from *config* without touching ``self._config``"""
        self._major_grid_widget.load_config(config.major)
        self._minor_grid_widget.load_config(config.minor)

    def _read_ui_to_config(self) -> GridConfiguration:
        """Build an AxisConfiguration from the current widget values"""
        return GridConfiguration(
            major=self._major_grid_widget.read_config(),
            minor=self._minor_grid_widget.read_config(),
        )

    def _btn_ok_slot(self) -> None:
        self._config = self._read_ui_to_config()
        self.accept()

    def _btn_cancel_slot(self) -> None:
        self.reject()

    def _btn_reset_slot(self) -> None:
        self.reset_to_default()

    def reset_to_default(self) -> None:
        self._load_config_to_ui(GridConfiguration.make_default())

    def get_config(self) -> GridConfiguration:
        return self._config
