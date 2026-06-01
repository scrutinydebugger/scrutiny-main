#    vertical_scroll_area.py
#        A ScrollArea that only scroll vertically, resize the underlying widget horizontally.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import QScrollArea
from PySide6.QtCore import Qt


class VerticalScrollArea(QScrollArea):
    """Scrolls only vertically. Child width tracks the viewport width, and
    heightForWidth() is called on resize so layouts recompute correctly."""

    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)  # Qt resizes widget width to viewport width first
        widget = self.widget()
        if widget is not None:
            w = self.viewport().width()
            widget.setMaximumWidth(w)
            if widget.hasHeightForWidth():
                widget.setMinimumHeight(widget.heightForWidth(w))
