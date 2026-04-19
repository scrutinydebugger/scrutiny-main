__all__ = ['ScrutinyQMenu']


from PySide6.QtWidgets import QMenu
from PySide6.QtGui import QAction

from scrutiny import tools
from scrutiny.tools.typing import *


class ScrutinyQMenu(QMenu):

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
