#    scrutiny_qmenu.py
#        An extension of the QMenu used for right click menus. Has a method to destroy cleanly
#        the menu and avoid memmory leaks with closures
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['ScrutinyQMenu']


from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction
from PySide6.QtCore import QPoint

from scrutiny import tools
from scrutiny.tools.typing import *


class ScrutinyQMenu(QMenu):

    def exec_at_first_and_disconnect(self, pos: QPoint) -> None:
        actions = self.actions()
        at: Optional[QAction] = None
        if len(actions) > 0:
            pos += QPoint(0, self.actionGeometry(actions[0]).height())
            at = actions[0]
        self.exec_and_disconnect_triggered(pos, at)

    @tools.copy_type(QMenu.exec)
    def exec_and_disconnect_triggered(self, *args: Any, **kwargs: Any) -> None:
        self.exec(*args, **kwargs)
        self.disconnect_all_triggered_signals()

    def disconnect_all_triggered_signals(self) -> None:
        self.apply_to_action_recursive(lambda action: action.triggered.disconnect())

    def apply_to_action_recursive(self, callback: Callable[[QAction], Any]) -> None:
        ScrutinyQMenu._apply_to_action_recursive(self, callback)

    @staticmethod
    def _apply_to_action_recursive(menu: QMenu, callback: Callable[[QAction], Any]) -> None:
        for action in menu.actions():
            submenu = action.menu()
            callback(action)
            if isinstance(submenu, QMenu):
                ScrutinyQMenu._apply_to_action_recursive(submenu, callback)
