#    chart_mixins.py
#        Mixin functions related to charts that are shared across components. They exhibit
#        similar chart features
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from PySide6.QtWidgets import QWidget, QMenu
from PySide6.QtGui import QAction
from scrutiny.gui.dialogs.chart_grid_config_dialog import GridConfigDialog
from scrutiny.gui.widgets.base_chart import ScrutinyChart
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets
from scrutiny.tools.typing import *


def add_grid_config_action(chart: ScrutinyChart, menu: QMenu, parent: Optional[QWidget] = None) -> QAction:
    def slot() -> None:
        config = chart.get_grid_config()
        dialog = GridConfigDialog(config, parent=parent)
        if dialog.exec() == GridConfigDialog.DialogCode.Accepted:
            chart.set_grid_config(dialog.get_config())

    action = menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.Grid), "Grid settings")
    action.triggered.connect(slot)
    return action
