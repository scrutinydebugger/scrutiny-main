#    manual_test_chart_range_edit_dialog.py
#        A manual test suite for the ChartRangeEditDialog
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

if __name__ != '__main__':
    raise RuntimeError("This script is expected to run from the command line")

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

import logging
from PySide6.QtWidgets import QMainWindow, QPushButton, QWidget, QVBoxLayout, QDialog
from scrutiny.gui.widgets.chart_range_edit_dialog import ChartRangeEditDialog
from scrutiny.gui.widgets.base_chart import ScrutinyValueAxisWithMinMax

DATASERIES_MIN = -100.5
DATASERIES_MAX = 200.75

window = QMainWindow()
central_widget = QWidget()
btn_show = QPushButton("Show ChartRangeEditDialog")
window.setCentralWidget(central_widget)
layout = QVBoxLayout(central_widget)
layout.addWidget(btn_show)

axis = ScrutinyValueAxisWithMinMax()
axis.set_maxval(DATASERIES_MAX)
axis.set_minval(DATASERIES_MIN)
axis.autoset_range()


def show_dialog() -> None:
    dialog = ChartRangeEditDialog(axis, window)
    result = dialog.exec()
    if result == QDialog.DialogCode.Accepted:
        logging.info(f"Accepted - min={dialog.get_min()}, max={dialog.get_max()}")
    else:
        logging.info("Cancelled")


btn_show.clicked.connect(show_dialog)
window.show()

sys.exit(app.exec())
