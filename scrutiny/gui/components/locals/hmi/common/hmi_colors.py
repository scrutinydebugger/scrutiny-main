#    hmi_colors.py
#        Colors defined by their role in the HMI dashboard
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import enum
from PySide6.QtWidgets import QComboBox
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtCore import QSize

from scrutiny.gui.components.locals.hmi.hmi_theme import HMITheme
from scrutiny.tools.typing import *


class HMIColor(enum.Enum):
    """A set of predefined color"""

    GOOD = "good"
    WARNING = "warning"
    DANGER = "danger"
    HIGHLIGHT = "highlight"
    INACTIVE = "inactive"

    def to_qcolor(self) -> QColor:
        _map = {
            HMIColor.GOOD: QColor(HMITheme.Color.green_good()),
            HMIColor.WARNING: QColor(HMITheme.Color.yellow_warning()),
            HMIColor.DANGER: QColor(HMITheme.Color.red_danger()),
            HMIColor.HIGHLIGHT: QColor(HMITheme.Color.blue_highlight()),
            HMIColor.INACTIVE: QColor(HMITheme.Color.gray_inactive()),
        }
        if self in _map:
            return _map[self]

        raise NotImplementedError(f"Unknown color {self}")

    def to_str(self) -> str:
        return self.value

    @classmethod
    def from_str(cls, v: str) -> Self:
        return cls(v)


def create_color_combobox() -> QComboBox:
    combobox = QComboBox()
    icon_size = QSize(combobox.sizeHint().height(), combobox.sizeHint().height())
    for color, text in [
        (HMIColor.GOOD, "Good"),
        (HMIColor.WARNING, "Warning"),
        (HMIColor.DANGER, "Danger"),
        (HMIColor.HIGHLIGHT, "Highlight"),
        (HMIColor.INACTIVE, "Inactive")
    ]:
        icon = QPixmap(icon_size)
        icon.fill(color.to_qcolor())
        combobox.addItem(icon, text, color)
    return combobox
