#    manual_test_varlist_watch_components.py
#        A test file that can be invoked manually to check on the varlist/watch widget
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2024 Scrutiny Debugger

if __name__ != '__main__':
    raise RuntimeError("This script is expected to run from the command line")

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from manual_test_base import make_manual_test_app
app = make_manual_test_app()

from PySide6.QtWidgets import QMainWindow, QLabel, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QFormLayout
from scrutiny.gui.components.globals.varlist.varlist_component import VarListComponent
from scrutiny.gui.components.locals.watch.watch_component import WatchComponent
from scrutiny.gui.components.globals.math_builder.math_builder_component import MathBuilderComponent
from scrutiny.gui.core.watchable_registry.watchable_registry import WatchableRegistry
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.core.fqn_name_pair import FqnNamePair
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from test.gui.fake_server_manager import FakeServerManager, ServerConfig
from scrutiny.tools.typing import *

window = QMainWindow()
central_widget = QWidget()
window.setCentralWidget(central_widget)

registry = WatchableRegistry()
server_manager = FakeServerManager(registry)

vlayout = QVBoxLayout(central_widget)

btn_start = QPushButton("Start")
btn_stop = QPushButton("Stop")
btn_connect = QPushButton("Connect server")
btn_disconnect = QPushButton("Disconnect server")
btn_device_ready = QPushButton("Connect Device")
btn_device_gone = QPushButton("Disconnect Device")
btn_load_sfd = QPushButton("Load Sfd")
btn_unload_sfd = QPushButton("Unload SFD")
btn_load_math = QPushButton("Load Math Elements")
btn_unload_math = QPushButton("Unload Math Elements")


button_container = QWidget()
component_container = QWidget()
status_container = QWidget()
vlayout.addWidget(button_container)
vlayout.addWidget(component_container)
vlayout.addWidget(status_container)

button_layout = QHBoxLayout(button_container)


def add_per_group(widgets: List[QWidget]):
    container = QWidget()
    layout = QVBoxLayout(container)
    for widget in widgets:
        layout.addWidget(widget)
    button_layout.addWidget(container)


add_per_group([QLabel("Server Manager"), btn_start, btn_stop])
add_per_group([QLabel("Server Connection"), btn_connect, btn_disconnect])
add_per_group([QLabel("Device Connection"), btn_device_ready, btn_device_gone])
add_per_group([QLabel("Firmware Description"), btn_load_sfd, btn_unload_sfd])
add_per_group([QLabel("Math Elements"), btn_load_math, btn_unload_math])


class AppInterface(AbstractComponentAppInterface):
    # Enable global features without dashboard

    varlist: VarListComponent

    def reveal_varlist_fqn(self, fqn: str) -> None:
        self.varlist.reveal_fqn(fqn)


component_layout = QHBoxLayout(component_container)

app_interface = AppInterface()
app_interface.server_manager = server_manager
app_interface.watchable_registry = registry

varlist = VarListComponent(main_window=window, instance_name="varlist1", app_interface=app_interface)
watch1 = WatchComponent(main_window=window, instance_name="watch1", app_interface=app_interface)
watch2 = WatchComponent(main_window=window, instance_name="watch2", app_interface=app_interface)
math_builder = MathBuilderComponent(main_window=window, instance_name="math_builder1", app_interface=app_interface)

app_interface.varlist = varlist

varlist.setup()
watch1.setup()
watch2.setup()
math_builder.setup()

component_layout.addWidget(varlist)
component_layout.addWidget(watch1)
component_layout.addWidget(watch2)
component_layout.addWidget(math_builder)

status_layout = QFormLayout(status_container)
running_label = QLabel("")
server_connected_label = QLabel("")
device_connected_label = QLabel("")
sfd_loaded_label = QLabel("")

status_layout.addRow("Manager state: ", running_label)
status_layout.addRow("Server: ", server_connected_label)
status_layout.addRow("Device: ", device_connected_label)
status_layout.addRow("SFD: ", sfd_loaded_label)

window.show()


def update_ui():
    btn_start.setEnabled(not server_manager.is_running())
    btn_stop.setEnabled(server_manager.is_running())
    server_connected = server_manager.get_server_info() is not None
    math_loaded = len(list(registry.get_all_math_watchables())) > 0
    btn_load_math.setEnabled(not math_loaded)
    btn_unload_math.setEnabled(math_loaded)
    if server_manager.is_running():
        btn_connect.setEnabled(not server_connected)
        btn_disconnect.setEnabled(server_connected)
        if server_connected:
            btn_device_ready.setEnabled(not server_manager._device_connected)
            btn_device_gone.setEnabled(server_manager._device_connected)
            btn_load_sfd.setEnabled(not server_manager._sfd_loaded)
            btn_unload_sfd.setEnabled(server_manager._sfd_loaded)
        else:
            btn_device_ready.setEnabled(False)
            btn_device_gone.setEnabled(False)
            btn_load_sfd.setEnabled(False)
            btn_unload_sfd.setEnabled(False)
    else:
        btn_connect.setEnabled(False)
        btn_disconnect.setEnabled(False)
        btn_device_ready.setEnabled(False)
        btn_device_gone.setEnabled(False)
        btn_load_sfd.setEnabled(False)
        btn_unload_sfd.setEnabled(False)

    running_label.setText("Running" if server_manager.is_running() else "Stopped")
    server_connected_label.setText("Connected" if server_connected else "Disconnected")
    device_connected_label.setText("Connected" if server_manager._device_connected else "Disconnected")
    sfd_loaded_label.setText("Loaded" if server_manager._sfd_loaded else "Unloaded")


def btn_start_slot():
    server_manager.start(ServerConfig(hostname='localhost', port=12345))
    update_ui()


def btn_stop_slot():
    server_manager.stop()
    update_ui()


def btn_connect_slot():
    server_manager.simulate_server_connect()
    update_ui()


def btn_disconnect_slot():
    server_manager.simulate_server_disconnected()
    update_ui()


def btn_device_ready_slot():
    server_manager.simulate_device_ready()
    update_ui()


def btn_device_gone_slot():
    server_manager.simulate_device_disconnect()
    update_ui()


def btn_load_sfd_slot():
    server_manager.simulate_sfd_loaded()
    update_ui()


def btn_unload_sfd_slot():
    server_manager.simulate_sfd_unloaded()
    update_ui()


def _make_math_watchables() -> List[GUIMathWatchable]:
    # Single var dependency: 2*x
    math_var = GUIMathWatchable("math_single_var", "2*x")
    math_var.bind_watchable("x", FqnNamePair(name="var.a.a", fqn="var:/var/var.a/var.a.a"))

    # Single alias dependency: sqrt(x)
    math_alias = GUIMathWatchable("math_single_alias", "sqrt(x)")
    math_alias.bind_watchable("x", FqnNamePair(name="alias.a.a", fqn="alias:/alias/alias.a/alias.a.a"))

    # Single rpv dependency: x + 1
    math_rpv = GUIMathWatchable("math_single_rpv", "x + 1")
    math_rpv.bind_watchable("x", FqnNamePair(name="rpv.a.b", fqn="rpv:/rpv/rpv.a/rpv.a.b"))

    # Mixed: sqrt(a^2 + b^2 + c^2) — one var, one alias, one rpv
    math_mixed = GUIMathWatchable("math_mixed_3vars", "sqrt(a^2 + b^2 + c^2)")
    math_mixed.bind_watchable("a", FqnNamePair(name="var.a.a", fqn="var:/var/var.a/var.a.a"))
    math_mixed.bind_watchable("b", FqnNamePair(name="alias.a.a", fqn="alias:/alias/alias.a/alias.a.a"))
    math_mixed.bind_watchable("c", FqnNamePair(name="rpv.a.b", fqn="rpv:/rpv/rpv.a/rpv.a.b"))

    return [math_var, math_alias, math_rpv, math_mixed]


def btn_load_math_slot():
    registry.add_math_watchables(_make_math_watchables())


def btn_unload_math_slot():
    registry.clear_content_by_type(RegistryNodeType.Math)


btn_start.clicked.connect(btn_start_slot)
btn_stop.clicked.connect(btn_stop_slot)
btn_connect.clicked.connect(btn_connect_slot)
btn_disconnect.clicked.connect(btn_disconnect_slot)
btn_device_ready.clicked.connect(btn_device_ready_slot)
btn_device_gone.clicked.connect(btn_device_gone_slot)
btn_load_sfd.clicked.connect(btn_load_sfd_slot)
btn_unload_sfd.clicked.connect(btn_unload_sfd_slot)
btn_load_math.clicked.connect(btn_load_math_slot)
btn_unload_math.clicked.connect(btn_unload_math_slot)
registry.signals.content_changed.connect(lambda _: update_ui())

update_ui()


sys.exit(app.exec())
