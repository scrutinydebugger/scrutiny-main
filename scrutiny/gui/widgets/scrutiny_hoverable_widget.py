#    scrutiny_hoverable_widget.py
#        A widget that can be hovered and style according to the stylesheets
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['ScrutinyHoverableWidget']

from PySide6.QtWidgets import QFrame


class ScrutinyHoverableWidget(QFrame):
    pass  # Handled in stylesheet. QFrame works, not Widget.
