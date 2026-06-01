#    tooltip_form_layout.py
#        An extension of the QFormLayout that can easily add tooltips on the label
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from PySide6.QtWidgets import QFormLayout, QWidget, QLabel

from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.tools.typing import *


class TooltipFormLayout(QFormLayout):
    def add_row_tooltip(self, txt: str, widget: QWidget, tooltip: Optional[str] = None) -> None:
        label = QLabel(txt)
        if tooltip is not None:
            label.setToolTip(tooltip)
            label.setCursor(scrutiny_get_theme().tooltip_cursor())
        self.addRow(label, widget)
