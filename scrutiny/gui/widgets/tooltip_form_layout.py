#    tooltip_form_layout.py
#        An extension of the QFormLayout that can easily add tooltips on the label
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from PySide6.QtWidgets import QFormLayout, QWidget, QLabel
from PySide6.QtCore import Qt

from scrutiny.tools.typing import *


class TooltipFormLayout(QFormLayout):
    def add_row_tooltip(self, txt: str, widget: QWidget, tooltip: Optional[str] = None) -> None:
        label = QLabel(txt)
        if tooltip is not None:
            label.setToolTip(tooltip)
            label.setCursor(Qt.CursorShape.WhatsThisCursor)
        self.addRow(label, widget)
