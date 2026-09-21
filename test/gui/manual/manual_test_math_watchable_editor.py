#    manual_test_math_watchable_editor.py
#        Manual test for the MathWatchableEditor component
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
from manual_test_base import make_manual_test_app, manual_test_args
app = make_manual_test_app()

from PySide6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton
from scrutiny.gui.components.globals.math_builder.math_watchable_editor import MathWatchableEditor
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.core.fqn_name_pair import FqnNamePair

window = QMainWindow()
central_widget = QWidget()
window.setCentralWidget(central_widget)
layout = QVBoxLayout(central_widget)

editor = MathWatchableEditor()
layout.addWidget(editor)

# --- Buttons ---

btn_layout = QHBoxLayout()

btn_clear = QPushButton("New (Clear)")
btn_get = QPushButton("Get MathWatchable")
btn_load = QPushButton("Load Sample")

btn_layout.addWidget(btn_clear)
btn_layout.addWidget(btn_get)
btn_layout.addWidget(btn_load)
layout.addLayout(btn_layout)


def on_clear():
    editor.clear()
    print("Editor cleared")


def on_get():
    mw = editor.get_if_fully_configured()
    if mw is None:
        print("get_if_fully_configured() returned None (incomplete or invalid)")
    else:
        print(f"Name: {mw.get_name()}")
        print(f"Expr: {mw.get_expr()}")
        print(f"Vars: {mw.get_var_fqn_map()}")
        print(f"Dict: {mw.to_dict()}")


def on_load():
    mw = GUIMathWatchable(name="my_magnitude", expr="sqrt(a^2 + b^2)")
    mw.bind_watchable("a", FqnNamePair(name="speed_x", fqn="var:/sensors/speed_x"))
    mw.bind_watchable("b", FqnNamePair(name="speed_y", fqn="var:/sensors/speed_y"))
    editor.load(mw)
    print(f"Loaded sample: {mw.to_dict()}")


btn_clear.clicked.connect(on_clear)
btn_get.clicked.connect(on_get)
btn_load.clicked.connect(on_load)

window.resize(500, 300)
if manual_test_args.debug_layout:
    window.setStyleSheet("border:1px solid red")
window.show()

sys.exit(app.exec())
