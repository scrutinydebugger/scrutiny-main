#    manual_test_graph_axis.py
#        A dummy app to test the graph axis tree widget
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

if __name__ != '__main__':
    raise RuntimeError("This script is expected to run from the command line")

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout

from scrutiny.gui.components.globals.varlist.varlist_component import VarListComponent
from scrutiny.gui.components.locals.watch.watch_component import WatchComponent
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.widgets.graph_signal_tree import GraphSignalTree
from scrutiny.gui.component_app_interface import AbstractComponentAppInterface

from test.gui.fake_server_manager import FakeServerManager, ServerConfig


class DummyAppInterface(AbstractComponentAppInterface):
    varlist: VarListComponent

    def reveal_varlist_fqn(self, fqn: str) -> None:
        self.varlist.reveal_fqn(fqn)


window = QMainWindow()
central_widget = QWidget()
window.setCentralWidget(central_widget)

registry = WatchableRegistry()
server_manager = FakeServerManager(registry)
server_manager.start(ServerConfig('localhost', 1234))
server_manager.simulate_server_connect()
server_manager.simulate_sfd_loaded()
server_manager.simulate_device_ready()

app_interface = DummyAppInterface()
app_interface.server_manager = server_manager
app_interface.watchable_registry = registry

varlist = VarListComponent(main_window=window, instance_name="varlist1", app_interface=app_interface)
watch1 = WatchComponent(main_window=window, instance_name="watch1", app_interface=app_interface)
graph_axes_zone = GraphSignalTree(window, registry, has_value_col=True)

app_interface.varlist = varlist

varlist.setup()
watch1.setup()

layout = QHBoxLayout(central_widget)
layout.addWidget(varlist)
layout.addWidget(watch1)
layout.addWidget(graph_axes_zone)

window.show()

sys.exit(app.exec())
