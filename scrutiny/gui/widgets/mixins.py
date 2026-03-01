#    mixins.py
#        Some mixins to use across the GUI to keep it consistent
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['qmenu_add_copy_path_action']

from PySide6.QtWidgets import QApplication, QMenu
from PySide6.QtGui import QAction

from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets

from scrutiny.tools.typing import *


def qmenu_add_copy_path_action(menu: QMenu, paths: Iterable[str]) -> QAction:
    def _action_slot() -> None:
        QApplication.clipboard().setText('\n'.join(paths))

    action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.Copy), "Copy path")
    action.triggered.connect(_action_slot)
    return action
