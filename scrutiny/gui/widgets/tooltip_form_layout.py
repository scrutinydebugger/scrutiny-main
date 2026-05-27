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
