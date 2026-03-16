#    fake_server_manager.py
#        A stubbed Server MAnager for unit test purpose
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2024 Scrutiny Debugger

import logging
from PySide6.QtCore import Signal, QObject, QTimer
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.core.server_manager import ServerConfig
from test.gui.fake_sdk_client import StubbedWatchableHandle, FakeSDKClient
from scrutiny import sdk
from uuid import uuid4
from datetime import datetime
from scrutiny.sdk.listeners import ValueUpdate, ValueStatus
import random

from scrutiny.tools.typing import *

enum_rpv_a_c = sdk.EmbeddedEnum("EnumAC", {'aaa': 0, 'bbb': 1, 'ccc': 2})

DUMMY_DATASET_RPV = {
    '/rpv/rpv.a/rpv.a.a': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpv.a/rpv.a.b': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpv.a/rpv.a.c': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.uint32, enum=enum_rpv_a_c),
    '/rpv/rpv.b/rpv.b.a': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpv.b/rpv.b.b': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/rpv/rpv.b/rpv.b.c': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.RuntimePublishedValue, datatype=sdk.EmbeddedDataType.float32, enum=None),
}

DUMMY_DATASET_ALIAS = {
    '/alias/alias.a/alias.a.a': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias.a/alias.a.b': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias.a/alias.a.c': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias.b/alias.b.a': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias.b/alias.b.b': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/alias/alias.b/alias.b.c': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Alias, datatype=sdk.EmbeddedDataType.float32, enum=None),
}

DUMMY_DATASET_VAR = {
    '/var/var.a/var.a.a': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var.a/var.a.b': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var.a/var.a.c': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var.b/var.b.a': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var.b/var.b.b': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
    '/var/var.b/var.b.c': sdk.BriefWatchableConfiguration(watchable_type=sdk.WatchableType.Variable, datatype=sdk.EmbeddedDataType.float32, enum=None),
}


class FakeServerManager:
    class _Signals(QObject):    # QObject required for signals to work
        """Signals offered to the outside world"""
        started = Signal()
        starting = Signal()
        stopping = Signal()
        stopped = Signal()
        server_connected = Signal()
        server_disconnected = Signal()
        device_ready = Signal()
        device_disconnected = Signal()
        datalogging_state_changed = Signal()
        sfd_loaded = Signal()
        sfd_unloaded = Signal()
        registry_changed = Signal()
        status_received = Signal()

    _started: bool
    _server_connected: bool
    _device_connected: bool
    _sfd_loaded: bool

    _client: FakeSDKClient
    _handles: Dict[str, StubbedWatchableHandle]
    _broadcast_timer: QTimer
    _registrations: Dict[Union[str, int], Set[StubbedWatchableHandle]]

    def __init__(self, watchable_registry: WatchableRegistry):
        self._signals = self._Signals()
        self._registry = watchable_registry

        self._started = False
        self._server_connected = False
        self._device_connected = False
        self._sfd_loaded = False
        self._logger = logging.getLogger(self.__class__.__name__)
        self._broadcast_timer = QTimer()
        self._broadcast_timer.setInterval(300)
        self._broadcast_timer.timeout.connect(self._broadcast_timer_slot)
        self._handles = {}

        self._client = FakeSDKClient()

        for dataset in [DUMMY_DATASET_RPV, DUMMY_DATASET_VAR, DUMMY_DATASET_ALIAS]:
            for path, config in dataset.items():
                server_id = uuid4().hex
                handle = StubbedWatchableHandle(path, config.watchable_type, config.datatype, config.enum, server_id)
                self._handles[path] = handle
        self._broadcast_timer.start()

    @property
    def signals(self) -> _Signals:
        """The events exposed to the application"""
        return self._signals

    @property
    def registry(self) -> WatchableRegistry:
        """The watchable registry containing a definition of all the watchables available on the server"""
        return self._registry

    def start(self, config: ServerConfig) -> None:
        self._signals.starting.emit()
        self._started = True
        self._signals.started.emit()
        self._signals.server_connected.emit()

        if self.registry.clear():
            self._signals.registry_changed.emit()

    def stop(self) -> None:
        self._signals.stopping.emit()
        self._started = False
        self._signals.stopped.emit()

        if self.registry.clear():
            self._signals.registry_changed.emit()

    def simulate_server_connect(self):
        if not self._started:
            return
        need_signal = not self._server_connected
        self._server_connected = True
        if need_signal:
            self._signals.server_connected.emit()

        if self.registry.clear():
            self._signals.registry_changed.emit()

        if self._device_connected:
            self.simulate_device_ready()
        if self._sfd_loaded:
            self.simulate_sfd_loaded()

    def simulate_server_disconnected(self):
        if not self._started:
            return
        need_signal = self._server_connected
        self._server_connected = False
        if need_signal:
            self._signals.server_disconnected.emit()

        if self.registry.clear():
            self._signals.registry_changed.emit()

    def is_running(self) -> bool:
        return self._started

    def simulate_device_ready(self) -> None:
        if not self._server_connected:
            return
        self._device_connected = True
        self._signals.device_ready.emit()
        self.registry.clear_content_by_type(sdk.WatchableType.RuntimePublishedValue)
        self.registry.write_content({
            sdk.WatchableType.RuntimePublishedValue: DUMMY_DATASET_RPV
        })
        for path, config in DUMMY_DATASET_RPV.items():
            handle = self._handles[path]
            self._registry.assign_serverid_to_node(config.watchable_type, path, handle.server_id)
        self._signals.registry_changed.emit()

    def simulate_device_disconnect(self) -> None:
        if not self._server_connected:
            return
        self._device_connected = False
        self._signals.device_disconnected.emit()
        self.registry.clear_content_by_type(sdk.WatchableType.RuntimePublishedValue)
        self._signals.registry_changed.emit()

    def simulate_sfd_loaded(self) -> None:
        if not self._server_connected:
            return
        self._sfd_loaded = True
        self._signals.sfd_loaded.emit()
        self.registry.clear_content_by_type(sdk.WatchableType.Alias)
        self.registry.clear_content_by_type(sdk.WatchableType.Variable)
        self.registry.write_content({
            sdk.WatchableType.Variable: DUMMY_DATASET_VAR,
            sdk.WatchableType.Alias: DUMMY_DATASET_ALIAS,
        })

        self._signals.registry_changed.emit()

    def simulate_sfd_unloaded(self) -> None:
        if not self._server_connected:
            return
        self._sfd_loaded = False
        self._signals.sfd_unloaded.emit()
        self.registry.clear_content_by_type(sdk.WatchableType.Alias)
        self.registry.clear_content_by_type(sdk.WatchableType.Variable)
        self._signals.registry_changed.emit()

    def get_server_state(self) -> sdk.ServerState:
        if self._server_connected:
            return sdk.ServerState.Connected

        return sdk.ServerState.Disconnected

    def get_server_info(self) -> Optional[sdk.ServerInfo]:
        if not self._started:
            return None

        if not self._server_connected:
            return None

        datalogging = None
        device_comm_state = sdk.DeviceCommState.Disconnected
        device_session_id = None
        if self._device_connected:
            datalogging = sdk.DataloggingInfo(completion_ratio=0, state=sdk.DataloggingState.Standby)
            device_comm_state = sdk.DeviceCommState.ConnectedReady
            device_session_id = 'aaa'

        sfd_firmware_id = None
        if self._sfd_loaded:
            sfd_firmware_id = 'bbb'

        info = sdk.ServerInfo(
            device_link=sdk.DeviceLinkInfo(
                type=sdk.DeviceLinkType.NONE,
                config=sdk.NoneLinkConfig(),
                operational=True,
                demo_mode=False
            ),
            datalogging=datalogging,
            device_comm_state=device_comm_state,
            device_session_id=device_session_id,
            sfd_firmware_id=sfd_firmware_id
        )

        return info

    def qt_write_watchable_value(self, fqn: str, value: Union[str, int, float, bool], callback: Callable[[Optional[Exception]], None]) -> None:
        pass

    def _broadcast_timer_slot(self) -> None:
        updates: List[updates] = []
        for handle in self._handles.values():
            value = random.randint(0, 100)
            status = ValueStatus.Valid
            if handle.server_path == '/rpv/rpv.a/rpv.a.a':
                status = ValueStatus.NullPtrDereferenced
                value = None
            elif handle.server_path == '/rpv/rpv.b/rpv.b.a':
                continue

            update = ValueUpdate(handle, value, status, datetime.now())
            updates.append(update)
        self._registry.broadcast_value_updates_to_watchers(updates)
