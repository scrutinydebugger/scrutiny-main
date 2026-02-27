
if __name__ != '__main__':
    raise RuntimeError("This script is expected to run from the command line")

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

import logging
from PySide6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget
from PySide6.QtGui import QColor
from scrutiny.gui.dialogs.chart_grid_config_dialog import (
    GridConfigDialog, GridConfiguration
)
from PySide6.QtCore import Qt


default_config = GridConfiguration.make_default()
print(default_config)

window = QMainWindow()
window.setGeometry(200, 200, 300, 150)
central = QWidget()
layout = QVBoxLayout(central)


def open_dialog() -> None:
    dlg = GridConfigDialog(default_config, window)
    if dlg.exec() == GridConfigDialog.DialogCode.Accepted:
        result = dlg.get_config()
        logging.info(f"Config accepted:")
        logging.info(f"  Major grid: visible={result.major.visible}, "
                     f"ticks={result.major.tick_count}, "
                     f"color={result.major.color.name(QColor.NameFormat.HexRgb)}, "
                     f"style={result.major.line_style.name}, "
                     f"width={result.major.line_width}")
        logging.info(f"  Minor grid: visible={result.minor.visible}, "
                     f"ticks={result.minor.tick_count}, "
                     f"color={result.minor.color.name(QColor.NameFormat.HexRgb)}, "
                     f"style={result.minor.line_style.name}, "
                     f"width={result.minor.line_width}")
    else:
        logging.info("Dialog cancelled")


btn = QPushButton("Open Axis Config Dialog")
btn.clicked.connect(open_dialog)
layout.addWidget(btn)

window.setCentralWidget(central)
window.show()

sys.exit(app.exec())
