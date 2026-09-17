#    manual_test_math_builder_component.py
#        Manual test for the MathBuilderComponent with a VarListComponent on the left
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

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QSplitter, QPushButton, QVBoxLayout
from PySide6.QtCore import Qt
from scrutiny.gui.components.globals.math_builder.math_builder_component import MathBuilderComponent
from scrutiny.gui.components.globals.varlist.varlist_component import VarListComponent
from scrutiny.gui.core.watchable_registry.watchable_registry import WatchableRegistry
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui.component_app_interface import AbstractComponentAppInterface

from scrutiny.sdk import WatchableType, BriefWatchableConfiguration, EmbeddedDataType
from test.gui.fake_server_manager import FakeServerManager


class AppInterface(AbstractComponentAppInterface):
    varlist: VarListComponent

    def reveal_varlist_fqn(self, fqn: str) -> None:
        self.varlist.reveal_fqn(fqn)


window = QMainWindow()
central_widget = QWidget()
window.setCentralWidget(central_widget)

registry = WatchableRegistry()
server_manager = FakeServerManager(registry)
app_interface = AppInterface()
app_interface.server_manager = server_manager
app_interface.watchable_registry = registry

varlist = VarListComponent(main_window=window, instance_name="varlist1", app_interface=app_interface)
varlist.setup()

math_builder = MathBuilderComponent(main_window=window, instance_name="math_builder1", app_interface=app_interface)
math_builder.setup()
math_builder.ready()

# Populate registry with fake data
registry.write_content({
    RegistryNodeType.Variable: {
        '/sensors/speed_x': BriefWatchableConfiguration(WatchableType.Variable, EmbeddedDataType.float32, enum=None),
        '/sensors/speed_y': BriefWatchableConfiguration(WatchableType.Variable, EmbeddedDataType.float32, enum=None),
        '/sensors/speed_z': BriefWatchableConfiguration(WatchableType.Variable, EmbeddedDataType.float32, enum=None),
        '/sensors/temperature': BriefWatchableConfiguration(WatchableType.Variable, EmbeddedDataType.float32, enum=None),
        '/motor/rpm': BriefWatchableConfiguration(WatchableType.Variable, EmbeddedDataType.uint32, enum=None),
        '/motor/torque': BriefWatchableConfiguration(WatchableType.Variable, EmbeddedDataType.float32, enum=None),
        '/control/output': BriefWatchableConfiguration(WatchableType.Variable, EmbeddedDataType.float64, enum=None),
    },
    RegistryNodeType.Alias: {
        '/speed_magnitude': BriefWatchableConfiguration(WatchableType.Alias, EmbeddedDataType.float32, enum=None),
        '/avg_temperature': BriefWatchableConfiguration(WatchableType.Alias, EmbeddedDataType.float32, enum=None),
    },
    RegistryNodeType.RuntimePublishedValue: {
        '/rpv/gain_p': BriefWatchableConfiguration(WatchableType.RuntimePublishedValue, EmbeddedDataType.float32, enum=None),
        '/rpv/gain_i': BriefWatchableConfiguration(WatchableType.RuntimePublishedValue, EmbeddedDataType.float32, enum=None),
        '/rpv/gain_d': BriefWatchableConfiguration(WatchableType.RuntimePublishedValue, EmbeddedDataType.float32, enum=None),
    },
})
varlist.reload_model([RegistryNodeType.Variable, RegistryNodeType.Alias, RegistryNodeType.RuntimePublishedValue])
btn_clear_var = QPushButton("Clear Var")
btn_clear_var.clicked.connect(lambda: registry.clear_content_by_type(RegistryNodeType.Variable))

left_side_widget = QWidget()
left_side_widget_layout = QVBoxLayout(left_side_widget)

left_side_widget_layout.addWidget(varlist)
left_side_widget_layout.addWidget(btn_clear_var)

# Layout: VarList on the left, MathBuilder on the right
splitter = QSplitter(Qt.Orientation.Horizontal)
splitter.addWidget(left_side_widget)
splitter.addWidget(math_builder)
splitter.setStretchFactor(0, 1)
splitter.setStretchFactor(1, 2)

layout = QHBoxLayout(central_widget)
layout.addWidget(splitter)

window.resize(900, 600)
if manual_test_args.debug_layout:
    window.setStyleSheet("border:1px solid red")
window.show()

sys.exit(app.exec())
