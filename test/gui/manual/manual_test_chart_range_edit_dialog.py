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
from scrutiny.gui.dialogs.chart_range_edit_dialog import ChartRangeEditDialog
from scrutiny.gui.widgets.base_chart import ScrutinyValueAxisWithMinMax


window = QMainWindow()
central_widget = QWidget()
btn_show = QPushButton("Show ChartRangeEditDialog")
window.setCentralWidget(central_widget)
layout = QVBoxLayout(central_widget)
layout.addWidget(btn_show)

axis1 = ScrutinyValueAxisWithMinMax()
axis2 = ScrutinyValueAxisWithMinMax()
axis3 = ScrutinyValueAxisWithMinMax()
axis1.setRange(-1, 1)
axis2.setRange(-2, 2)
axis3.setRange(-3, 3)
axis1.setTitleText("Axis1")
axis2.setTitleText("Axis2")
axis3.setTitleText("Axis3")


def show_dialog() -> None:
    dialog = ChartRangeEditDialog(axis1, [axis2, axis3], window)
    dialog.show()

    def display():
        logging.info("Axis1: [%g - %g]" % (axis1.min(), axis1.max()))
        logging.info("Axis2: [%g - %g]" % (axis2.min(), axis2.max()))
        logging.info("Axis3: [%g - %g]" % (axis3.min(), axis3.max()))
    dialog.finished.connect(display)


btn_show.clicked.connect(show_dialog)
window.show()

sys.exit(app.exec())
