#    server_manager.py
#        Object that handles the communication with the server and inform the rest of the
#        GUI about what's happening on the other side of the socket. Based on the SDK ScrutinyClient
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2024 Scrutiny Debugger

__all__ = ['ServerManager', 'ServerConfig', 'ValueUpdate']

from scrutiny import sdk
import threading
import time
import logging
import enum
from copy import copy
from dataclasses import dataclass

from PySide6.QtCore import Signal, QObject

from scrutiny.core.logging import DUMPDATA_LOGLEVEL
from scrutiny.sdk.listeners import BaseListener, ValueUpdate
from scrutiny.sdk.watchable_handle import WatchableHandle
from scrutiny.sdk.client import ScrutinyClient, WatchableListDownloadRequest
from scrutiny.gui.core.watchable_registry import WatchableRegistry, GlobalWatchCallbackData
from scrutiny.gui.core.user_messages_manager import UserMessagesManager
from scrutiny.gui.core.server_manager.qt_buffered_listener import QtBufferedListener
from scrutiny.gui.core.server_manager.client_task_reactor import ClientTaskReactor
from scrutiny.gui.core.threads import QT_THREAD_NAME, SERVER_MANAGER_THREAD_NAME
from scrutiny.gui.tools.invoker import invoke_in_qt_thread_synchronized, invoke_later

from scrutiny import tools
from scrutiny.tools.thread_enforcer import thread_func, enforce_thread
from scrutiny.tools.typing import *
from scrutiny.gui.app_settings import app_settings

USER_MSG_ID_CONNECT_FAILED = "connect_failed"


@dataclass(slots=True)
class ServerConfig:
    hostname: str
    port: int


class ServerManager:
    """Runs a thread for the synchronous SDK and emit QT events when something interesting happens"""

    @dataclass(frozen=True, slots=True)
    class Statistics:
        listener: BaseListener.Statistics
        client: ScrutinyClient.Statistics
        watchable_registry: WatchableRegistry.Statistics
        status_update_received: int
        listener_to_gui_qsize: int
        listener_event_rate: float

    class WatchableRegistrationState(enum.Enum):
        SUBSCRIBING = enum.auto()
        SUBSCRIBED = enum.auto()
        UNSUBSCRIBING = enum.auto()
        UNSUBSCRIBED = enum.auto()

        def is_transition_state(self) -> bool:
            return self in cast(List[ServerManager.WatchableRegistrationState], [self.SUBSCRIBING, self.UNSUBSCRIBING])

    class WatchableRegistrationAction(enum.Enum):
        NONE = enum.auto()
        SUBSCRIBE = enum.auto()
        UNSUBSCRIBE = enum.auto()

    @dataclass(slots=True)
    class WatchableRegistrationStatus:
        active_state: "ServerManager.WatchableRegistrationState"
        pending_action: "ServerManager.WatchableRegistrationAction"
        last_requested_rate: Optional[float]
        pending_update_rate: Optional[float]

    class ThreadState:
        """Data used by the server thread used to detect changes and emit events"""
        runtime_watchables_download_request: Optional[WatchableListDownloadRequest]
        sfd_watchables_download_request: Optional[WatchableListDownloadRequest]
        connect_timestamp_mono: Optional[float]
        last_server_state: sdk.ServerState

        def __init__(self) -> None:
            self.runtime_watchables_download_request = None
            self.sfd_watchables_download_request = None
            self.connect_timestamp_mono = None

            self.clear()

        def clear(self) -> None:
            self.connect_timestamp_mono = None
            self.last_server_state = sdk.ServerState.Disconnected
            self.clear_download_requests()

        def clear_download_requests(self) -> None:
            # RPV request
            req = self.runtime_watchables_download_request  # Get a reference atomically
            if req is not None:
                req.cancel()
            self.runtime_watchables_download_request = None

            # Alias/Var request
            req = self.sfd_watchables_download_request
            if req is not None:
                req.cancel()
            self.sfd_watchables_download_request = None

    class _InternalSignals(QObject):
        thread_exit_signal = Signal()

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
        device_info_availability_changed = Signal()
        loaded_sfd_availability_changed = Signal()
        datalogging_storage_updated = Signal(sdk.DataloggingListChangeType, str)  # type, reference_id

    RECONNECT_DELAY = 1
    VAR_FACTORY_MAX_WATCHABLE: int
    VAR_FACTORY_MAX_TOTAL_GENERATED_VAR: int
    SERVER_THROTTLING_RATE: int

    _client: ScrutinyClient
    """The SDK client object that talks with the server"""
    _thread: Optional[threading.Thread]
    """The thread that runs the synchronous client"""
    _registry: WatchableRegistry
    """The watchable registry that holds the list of available watchables, downloaded from the server"""

    _thread_stop_event: threading.Event
    """Event used to stop the thread"""
    _signals: _Signals
    """The signals"""
    _internal_signals: _InternalSignals
    """Some signals used internally, mainly for synchronization"""
    _allow_auto_reconnect: bool
    """Flag indicating if the thread should try to reconnect the client if disconnected"""
    _logger: logging.Logger
    """Logger"""
    _thread_state: ThreadState
    """Data used by the thread to detect state changes"""

    _stop_pending: bool
    """Indicate if a stop is in progress. ``True`` between calls to stop() and emission of ``stopped`` signal"""
    _client_task_reactor: ClientTaskReactor
    """A reactor that can pipeline blocking requests to the server"""
    _listener: QtBufferedListener
    """A custom listener that passes the data from the SDK client thread to the QT GUI thread"""
    _status_update_received: int
    """Counter that tells how many status update we received"""

    _registration_status_store: Dict[sdk.WatchableType, Dict[str, WatchableRegistrationStatus]]
    """A dictionary that maps server paths to a subscription status. Used to deal with request for subscription happening while another is not complete."""

    _unit_test: bool
    """Enable some internal instrumentation for unit testing"""
    _qt_watch_unwatch_ui_callback_call_count: int
    """For unit testing. Used for synchronization of threads"""
    _exit_in_progress: bool
    """Flag set by the main window informing that the application is exiting. Cancel callbacks"""

    _device_info: Optional[sdk.DeviceInfo]
    """Contains all the info about the actually connected device. ``None`` if not available"""
    _loaded_sfd: Optional[sdk.SFDInfo]
    """Contains all the info about the actually loaded Scrutiny Firmware Description. ``None`` if not available"""

    _partial_watchable_downloaded_data: Dict[sdk.WatchableType, Dict[str, sdk.BriefWatchableConfiguration]]

    def __init__(self, watchable_registry: WatchableRegistry, client: Optional[ScrutinyClient] = None) -> None:
        super().__init__()  # Required for signals to work
        self._logger = logging.getLogger(self.__class__.__name__)

        if client is None:
            self._client = ScrutinyClient()
        else:
            self._client = client   # Mainly useful for unit testing
        self._client.listen_events(ScrutinyClient.Events.LISTEN_ALL)
        self._signals = self._Signals()
        self._internal_signals = self._InternalSignals()

        self._thread = None
        self._thread_stop_event = threading.Event()
        self._allow_auto_reconnect = False

        self._thread_state = self.ThreadState()
        self._registry = watchable_registry
        self._partial_watchable_downloaded_data = {
            sdk.WatchableType.Variable: {},
            sdk.WatchableType.Alias: {},
            sdk.WatchableType.RuntimePublishedValue: {}
        }

        self._internal_signals.thread_exit_signal.connect(self._qt_thread_join_thread_and_emit_stopped)
        self._stop_pending = False
        self._client_task_reactor = ClientTaskReactor(self._client, nb_thread=16, queue_max_size=100)
        self._registry.register_global_watch_callback(self._qt_registry_watch_callback, self._qt_registry_unwatch_callback)

        self._listener = QtBufferedListener()
        self._client.register_listener(self._listener)
        self._listener.signals.data_received.connect(self._qt_value_update_received)

        self._status_update_received = 0

        def inc_status_update_count() -> None:
            self._status_update_received += 1
        self._signals.status_received.connect(inc_status_update_count)

        # Registration logic
        self._registration_status_store = {
            sdk.WatchableType.Variable: {},
            sdk.WatchableType.Alias: {},
            sdk.WatchableType.RuntimePublishedValue: {}
        }

        def clear_rpv_registration_status() -> None:
            self._registration_status_store[sdk.WatchableType.RuntimePublishedValue].clear()

        def clear_var_alias_registration_status() -> None:
            self._registration_status_store[sdk.WatchableType.Variable].clear()
            self._registration_status_store[sdk.WatchableType.Alias].clear()

        def clear_all_registration_status() -> None:
            for k in self._registration_status_store:
                self._registration_status_store[k].clear()

        self._signals.device_disconnected.connect(clear_rpv_registration_status)
        self._signals.sfd_unloaded.connect(clear_var_alias_registration_status)
        self._signals.server_connected.connect(clear_all_registration_status)
        self._signals.server_disconnected.connect(clear_all_registration_status)

        self._unit_test = False
        self._qt_watch_unwatch_ui_callback_call_count = 0
        self._exit_in_progress = False

        self._device_info = None
        self._loaded_sfd = None

        # Logging logic
        if self._logger.isEnabledFor(DUMPDATA_LOGLEVEL):    # pragma: no cover
            self._signals.server_connected.connect(lambda: self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: server_connected"))
            self._signals.server_disconnected.connect(lambda: self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: server_disconnected"))
            self._signals.device_ready.connect(lambda: self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: device_ready"))
            self._signals.device_disconnected.connect(lambda: self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: device_disconnected"))
            self._signals.sfd_loaded.connect(lambda: self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: sfd_loaded"))
            self._signals.sfd_unloaded.connect(lambda: self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: sfd_unloaded"))
            self._signals.registry_changed.connect(lambda: self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: registry_changed"))
            self._signals.datalogging_state_changed.connect(lambda: self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: datalogging_state_changed"))
            self._signals.status_received.connect(lambda: self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: status_received"))
            self._signals.device_info_availability_changed.connect(lambda: self._logger.log(
                DUMPDATA_LOGLEVEL, "+Signal: device_info_availability_changed"))
            self._signals.loaded_sfd_availability_changed.connect(lambda: self._logger.log(
                DUMPDATA_LOGLEVEL, "+Signal: loaded_sfd_availability_changed"))
            self._signals.datalogging_storage_updated.connect(lambda: self._logger.log(DUMPDATA_LOGLEVEL, "+Signal: datalogging_storage_updated"))

        # These internal slots are used to download the device info and SFD details when they are ready
        self._signals.sfd_loaded.connect(self._sfd_loaded_callback)
        self._signals.sfd_unloaded.connect(self._sfd_unloaded_callback)
        self._signals.device_ready.connect(self._device_ready_callback)
        self._signals.device_disconnected.connect(self._device_disconnected_callback)
        self._signals.server_disconnected.connect(self._server_disconnected_callback)
        self._signals.server_connected.connect(self._server_connected_callback)

        self.SERVER_THROTTLING_RATE = app_settings().SCRUTINY_GUI_SERVER_THROTTLING_RATE
        self.VAR_FACTORY_MAX_WATCHABLE = app_settings().SCRUTINY_GUI_MAX_GENERATED_VAR_PER_ELEMENT
        self.VAR_FACTORY_MAX_TOTAL_GENERATED_VAR = app_settings().SCRUTINY_GUI_MAX_TOTAL_GENERATED_VAR

    # region Private - internal thread

    @thread_func(SERVER_MANAGER_THREAD_NAME)
    def _thread_func(self, config: ServerConfig) -> None:
        """Thread that monitors state change on the server side"""
        # Is the server thread
        self._logger.debug("Server manager thread running")
        self._thread_state.clear()

        self._thread_clear_client_events()

        try:
            self._listener.start()
            while not self._thread_stop_event.is_set():
                if self._client.server_state == sdk.ServerState.Disconnected:
                    self._thread_handle_reconnect(config)

                server_state = self._client.server_state
                if server_state == sdk.ServerState.Error:
                    invoke_in_qt_thread_synchronized(self.stop)
                    break
                self._thread_process_client_events()
                self._thread_handle_download_watchable_logic()

                self._thread_state.last_server_state = server_state

        except Exception as e:  # pragma: no cover
            if not self._exit_in_progress:
                str_level = logging.CRITICAL
                traceback_level = logging.INFO
            else:
                str_level = logging.DEBUG
                traceback_level = logging.DEBUG
            tools.log_exception(self._logger, e, "Error in server manager thread", str_level=str_level, traceback_level=traceback_level)
        finally:
            self._client.disconnect()
            was_connected = self._thread_state.last_server_state == sdk.ServerState.Connected
            if was_connected:
                with tools.SuppressException(RuntimeError):  # May fail if the window is deleted before this thread exits
                    self._signals.server_disconnected.emit()

            # Empty the event queue
            self._thread_clear_client_events()

        self._thread_state.clear()
        self._listener.stop()
        self._listener.unsubscribe_all()

        # Ensure the server thread has the time to notice the changes and emit all signals
        t = time.perf_counter()
        timeout = 1
        while self._client.server_state != sdk.ServerState.Disconnected and time.perf_counter() - t < timeout:
            time.sleep(0.01)

        self._logger.debug("Server Manager thread exiting")
        with tools.SuppressException(RuntimeError):  # May fail if the window is deleted before this thread exits
            self._internal_signals.thread_exit_signal.emit()

    def _thread_clear_client_events(self) -> None:
        # Called from internal thread
        while self._client.has_event_pending():
            self._client.read_event(timeout=0)

    def _thread_handle_reconnect(self, config: ServerConfig) -> None:
        # Called from internal thread
        if self._allow_auto_reconnect and not self._stop_pending:
            # timer to prevent going crazy on function call
            if self._thread_state.connect_timestamp_mono is None or time.monotonic() - self._thread_state.connect_timestamp_mono > self.RECONNECT_DELAY:
                try:
                    self._logger.debug("Connecting client")
                    self._thread_state.connect_timestamp_mono = time.monotonic()
                    self._client.connect(config.hostname, config.port, wait_status=False)
                    UserMessagesManager.instance().clear_message_thread_safe(USER_MSG_ID_CONNECT_FAILED)
                except sdk.exceptions.ConnectionError as e:
                    if not self.is_stopping():
                        UserMessagesManager.instance().register_message_thread_safe(USER_MSG_ID_CONNECT_FAILED, str(e), 5)

    def _thread_process_client_events(self) -> None:
        # Called from internal thread
        while True:
            event = self._client.read_event(timeout=0.2)
            if event is None:
                return

            self._logger.log(DUMPDATA_LOGLEVEL, f"+Event: {event}")
            if isinstance(event, ScrutinyClient.Events.ConnectedEvent):
                changed = invoke_in_qt_thread_synchronized(self._registry.clear, timeout=2)
                self._signals.server_connected.emit()
                if changed:
                    self.signals.registry_changed.emit()
                self._allow_auto_reconnect = False    # Ensure we do not try to reconnect until the disconnect event is processed
            elif isinstance(event, ScrutinyClient.Events.DisconnectedEvent):
                changed = invoke_in_qt_thread_synchronized(self._registry.clear, timeout=2)
                if changed:
                    self.signals.registry_changed.emit()
                self._signals.server_disconnected.emit()
                self._allow_auto_reconnect = True  # Full cycle completed. We allow reconnecting
            elif isinstance(event, ScrutinyClient.Events.DeviceReadyEvent):
                self._thread_event_device_ready()
            elif isinstance(event, ScrutinyClient.Events.DeviceGoneEvent):
                self._thread_event_device_disconnected()
            elif isinstance(event, ScrutinyClient.Events.SFDLoadedEvent):
                self._thread_event_sfd_loaded()
            elif isinstance(event, ScrutinyClient.Events.SFDUnLoadedEvent):
                self._thread_event_sfd_unloaded()
            elif isinstance(event, ScrutinyClient.Events.DataloggingStateChanged):
                if not self._exit_in_progress:
                    self._signals.datalogging_state_changed.emit()
            elif isinstance(event, ScrutinyClient.Events.StatusUpdateEvent):
                if not self._exit_in_progress:
                    self._signals.status_received.emit()
            elif isinstance(event, ScrutinyClient.Events.DataloggingListChanged):
                if not self._exit_in_progress:
                    self._signals.datalogging_storage_updated.emit(event.change_type, event.acquisition_reference_id)
            else:
                self._logger.error(f"Unsupported event type : {event.__class__.__name__}")

    def _thread_handle_download_watchable_logic(self) -> None:
        # Called from internal thread
        if self._thread_state.runtime_watchables_download_request is not None:
            if self._thread_state.runtime_watchables_download_request.completed:
                # Download is finished
                # Data is already inside the registry. Added from the callback
                self._logger.debug("Download of watchable list is complete. Group : runtime")
                if self._thread_state.runtime_watchables_download_request.is_success:
                    data = self._thread_state.runtime_watchables_download_request.get()
                    content = {
                        sdk.WatchableType.RuntimePublishedValue: data.rpv
                    }
                    invoke_in_qt_thread_synchronized(lambda: self._registry.write_content(content), timeout=5)
                    self._signals.registry_changed.emit()
                else:
                    invoke_in_qt_thread_synchronized(lambda: self._registry.clear_content_by_type(
                        [sdk.WatchableType.RuntimePublishedValue]), timeout=3)
                self._thread_state.runtime_watchables_download_request = None   # Clear the request.
            else:
                pass  # Downloading

        if self._thread_state.sfd_watchables_download_request is not None:
            if self._thread_state.sfd_watchables_download_request.completed:
                # Download complete
                # Data is already inside the registry. Added from the callback
                self._logger.debug("Download of watchable list is complete. Group : SFD")
                if self._thread_state.sfd_watchables_download_request.is_success:
                    data = self._thread_state.sfd_watchables_download_request.get()
                    generated_var = self._make_var_watchable_from_factories(data.var_factory)
                    data.var.update(generated_var)
                    content = {
                        sdk.WatchableType.Variable: data.var,
                        sdk.WatchableType.Alias: data.alias,
                    }
                    invoke_in_qt_thread_synchronized(lambda: self._registry.write_content(content), timeout=5)
                    self._signals.registry_changed.emit()
                else:
                    invoke_in_qt_thread_synchronized(lambda: self._registry.clear_content_by_type(
                        [sdk.WatchableType.Alias, sdk.WatchableType.Variable]), timeout=3)
                self._thread_state.sfd_watchables_download_request = None   # Clear the request.
            else:
                pass    # Downloading

    def _thread_event_device_ready(self) -> None:
        """To be called once when a device connects"""
        self._logger.debug("Detected device ready")
        req = self._thread_state.runtime_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()

        self._thread_state.runtime_watchables_download_request = self._client.download_watchable_list([sdk.WatchableType.RuntimePublishedValue])
        if not self._exit_in_progress:
            self._signals.device_ready.emit()

    def _thread_event_sfd_loaded(self) -> None:
        """To be called once when a SFD is loaded"""
        self._logger.debug("Detected SFD loaded")
        req = self._thread_state.sfd_watchables_download_request    # Get the ref atomically
        if req is not None:
            req.cancel()
        self._thread_state.sfd_watchables_download_request = self._client.download_watchable_list(
            [sdk.WatchableType.Variable, sdk.WatchableType.Alias])
        if not self._exit_in_progress:
            self.signals.sfd_loaded.emit()

    def _thread_event_sfd_unloaded(self) -> None:
        """To be called once when a SFD is unloaded"""
        self._logger.debug("Detected SFD unloaded")
        req = self._thread_state.sfd_watchables_download_request    # Get the ref atomically
        if req is not None and not req.completed:
            req.cancel()
        self._thread_state.sfd_watchables_download_request = None
        self._thread_clear_registry_synchronized([sdk.WatchableType.Alias, sdk.WatchableType.Variable])
        if not self._exit_in_progress:
            self.signals.sfd_unloaded.emit()

    def _thread_event_device_disconnected(self) -> None:
        """To be called once when a device disconnect"""
        self._logger.debug("Detected device disconnected")
        req = self._thread_state.runtime_watchables_download_request    # Get the ref atomically
        if req is not None and not req.completed:
            req.cancel()
        self._thread_state.runtime_watchables_download_request = None
        self._thread_clear_registry_synchronized([sdk.WatchableType.RuntimePublishedValue])
        if not self._exit_in_progress:
            self.signals.device_disconnected.emit()

    def _thread_clear_registry_synchronized(self, type_list: List[sdk.WatchableType]) -> None:
        @dataclass(slots=True)
        class Context:
            had_data: bool = False

        ctx = Context()

        def clear_func() -> None:
            for wt in type_list:
                had_data = self._registry.clear_content_by_type(wt)
                ctx.had_data = ctx.had_data or had_data
        if self._logger.isEnabledFor(logging.DEBUG):    # pragma: no cover
            self._logger.debug("Clearing registry for types: %s" % ([x.name for x in type_list]))
        invoke_in_qt_thread_synchronized(clear_func, timeout=2)
        if self._logger.isEnabledFor(logging.DEBUG):    # pragma: no cover
            self._logger.debug("Cleared registry for types: %s" % ([x.name for x in type_list]))
        if ctx.had_data:
            self._signals.registry_changed.emit()

    def _make_var_watchable_from_factories(self, var_factories: Dict[str, sdk.VariableFactoryInterface]) -> Dict[str, sdk.BriefWatchableConfiguration]:
        """Take the variable factories received from the server and generate all the var watchables from them.
        Might drop some of them to avoid bloating the registry with large buffers
        """
        outdict: Dict[str, sdk.BriefWatchableConfiguration] = {}
        var_factories_filt: List[sdk.VariableFactoryInterface] = []
        # Start by removing var factory that generate too many elements
        for access_path, factory in var_factories.items():
            path_count = factory.count_possible_paths()
            if path_count <= self.VAR_FACTORY_MAX_WATCHABLE:
                var_factories_filt.append(factory)
            else:
                if self._logger.isEnabledFor(logging.DEBUG):
                    self._logger.debug(
                        f"Ignoring variable factory \"{access_path}\" because it would generate too many watchables ({path_count}). Max={self.VAR_FACTORY_MAX_WATCHABLE}")

        # Then successively remove factories to keep the number of generated watchables below a threshold
        # Remove from biggest to smallest
        var_factories_filt.sort(key=lambda x: x.count_possible_paths(), reverse=True)
        total_element = sum([x.count_possible_paths() for x in var_factories_filt])
        to_remove = max(total_element - self.VAR_FACTORY_MAX_TOTAL_GENERATED_VAR, 0)
        removed = 0
        while removed < to_remove and len(var_factories_filt) > 0:
            if self._logger.isEnabledFor(logging.DEBUG):
                self._logger.debug(
                    f"Ignoring variable factory \"{var_factories_filt[0].access_path}\" because to avoid generating too much variables")
            removed += var_factories_filt[0].count_possible_paths()
            del var_factories_filt[0]

        # Create a dict for the output
        for factory in var_factories_filt:
            for path, definition in factory.iterate_possible_paths():
                outdict[path] = definition

        return outdict

    # endregion

    # region Private QT side methods

    def _request_update_rate_change(self, handle: WatchableHandle, update_rate: Optional[float]) -> None:
        def _ephemerous_thread_change(client: ScrutinyClient) -> Optional[float]:
            return handle.change_update_rate(update_rate)

        def _qt_thread_callback(effective_rate: Optional[float], error: Optional[Exception]) -> None:
            if error is not None:
                tools.log_exception(self._logger, error, "Failed to change the update rate")
            # Nothing else to do. We don't try to recover from a failure.

        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(f"Changing update rate of {handle.server_path} to {update_rate}")
        self.schedule_client_request(_ephemerous_thread_change, _qt_thread_callback)

    def _qt_update_registration_from_watchable_handle(self,
                                                      registration_status: WatchableRegistrationStatus,
                                                      handle: Optional[WatchableHandle]) -> None:
        """Internal function that update the registration status based on the real state of the SDK client watch handle."""
        # Update state based on SDK client
        if handle is not None:
            if handle.is_dead:
                registration_status.active_state = self.WatchableRegistrationState.UNSUBSCRIBED
                registration_status.last_requested_rate = None
            else:
                registration_status.active_state = self.WatchableRegistrationState.SUBSCRIBED
                registration_status.last_requested_rate = handle.requested_update_rate
        else:
            registration_status.active_state = self.WatchableRegistrationState.UNSUBSCRIBED
            registration_status.last_requested_rate = None

    def _qt_watch_unwatch_ui_callback(self,
                                      attempted_action: WatchableRegistrationAction,
                                      watchable_type: sdk.WatchableType,
                                      server_path: str,
                                      registration_status: WatchableRegistrationStatus,
                                      error: Optional[Exception]) -> None:
        if error is not None:
            if attempted_action == self.WatchableRegistrationAction.SUBSCRIBE:
                tools.log_exception(self._logger, error, f"Failed to watch {server_path}")
            elif attempted_action == self.WatchableRegistrationAction.UNSUBSCRIBE:
                tools.log_exception(self._logger, error, f"Failed to unwatch {server_path}")
            else:
                raise NotImplementedError("Unsupported attempted action")

        # Update state based on SDK client
        client_handle = self._client.try_get_existing_watch_handle(server_path)
        self._qt_update_registration_from_watchable_handle(registration_status, client_handle)

        # We tried to subscribe and succeeded . Inform the listener
        if (attempted_action == self.WatchableRegistrationAction.SUBSCRIBE
                and registration_status.active_state == self.WatchableRegistrationState.SUBSCRIBED):
            assert client_handle is not None
            self._registry.assign_serverid_to_node(client_handle.type, server_path, client_handle.server_id)
            self._listener.subscribe(client_handle)
        self._listener.prune_subscriptions()    # Delete dead handles

        # We tried to unsubscribe, succeeded and nothing else to do. Cleanup
        if (registration_status.active_state == self.WatchableRegistrationState.UNSUBSCRIBED
                and registration_status.pending_action == self.WatchableRegistrationAction.NONE):
            if server_path in self._registration_status_store[watchable_type]:
                del self._registration_status_store[watchable_type][server_path]    # Save some memory.
            self._registry.clear_serverid_from_node(watchable_type, server_path)
        else:
            if registration_status.pending_action == self.WatchableRegistrationAction.SUBSCRIBE:
                self._qt_maybe_request_watch(watchable_type, server_path, registration_status.pending_update_rate)
            elif registration_status.pending_action == self.WatchableRegistrationAction.UNSUBSCRIBE:
                self._qt_maybe_request_unwatch(watchable_type, server_path)

        if self._unit_test:
            self._qt_watch_unwatch_ui_callback_call_count += 1

    @enforce_thread(QT_THREAD_NAME)
    def _qt_maybe_request_watch(self, watchable_type: sdk.WatchableType, server_path: str, update_rate: Optional[float]) -> None:
        """Will request the server for a watch subscription if not already done or working on it."""
        if not server_path in self._registration_status_store[watchable_type]:
            self._registration_status_store[watchable_type][server_path] = self.WatchableRegistrationStatus(
                active_state=self.WatchableRegistrationState.UNSUBSCRIBED,
                pending_action=self.WatchableRegistrationAction.NONE,
                last_requested_rate=None,
                pending_update_rate=None
            )
        registration_status = self._registration_status_store[watchable_type][server_path]

        # Update state based on SDK client
        if not registration_status.active_state.is_transition_state():
            client_handle = self._client.try_get_existing_watch_handle(server_path)
            self._qt_update_registration_from_watchable_handle(registration_status, client_handle)

        # Decide what to do based on active state and pending action
        if registration_status.active_state in (self.WatchableRegistrationState.SUBSCRIBED, self.WatchableRegistrationState.SUBSCRIBING):
            # Nothing to do. Ensure we do nothing
            registration_status.pending_action = self.WatchableRegistrationAction.NONE

            if update_rate != registration_status.last_requested_rate:
                client_handle = self._client.try_get_existing_watch_handle(server_path)
                if client_handle is not None:
                    self._request_update_rate_change(client_handle, update_rate)
                    registration_status.last_requested_rate = update_rate
                else:
                    registration_status.pending_action = self.WatchableRegistrationAction.SUBSCRIBE
                    registration_status.pending_update_rate = update_rate

        elif registration_status.active_state == self.WatchableRegistrationState.UNSUBSCRIBING:
            # enqueue. Next callback will pick this up
            registration_status.pending_action = self.WatchableRegistrationAction.SUBSCRIBE
            registration_status.pending_update_rate = update_rate

        elif registration_status.active_state == self.WatchableRegistrationState.UNSUBSCRIBED:
            # Proceed with subscription
            registration_status.pending_action = self.WatchableRegistrationAction.NONE
            registration_status.pending_update_rate = None
            registration_status.active_state = self.WatchableRegistrationState.SUBSCRIBING

            def func(client: ScrutinyClient) -> Optional[Exception]:
                try:
                    client.watch(server_path, update_rate=update_rate)
                except sdk.exceptions.ScrutinySDKException as e:
                    return e   # Exception others than SDKException are not normal.
                return None

            def ui_callback(expected_error: Optional[Exception], unexpected_error: Optional[Exception]) -> None:
                if unexpected_error is not None:
                    tools.log_exception(self._logger, unexpected_error, str_level=logging.CRITICAL)    # Not supposed to happen
                else:
                    self._qt_watch_unwatch_ui_callback(
                        attempted_action=self.WatchableRegistrationAction.SUBSCRIBE,
                        watchable_type=watchable_type,
                        server_path=server_path,
                        registration_status=registration_status,
                        error=expected_error)

            self.schedule_client_request(func, ui_callback)
            registration_status.last_requested_rate = update_rate
        else:   # pragma: no cover
            raise NotImplementedError(f"Unsupported state: {registration_status.active_state}")

    @enforce_thread(QT_THREAD_NAME)
    def _qt_maybe_request_unwatch(self, watchable_type: sdk.WatchableType, server_path: str) -> None:
        """Will request the server to unsubscribe to a watchif not already done or working on it."""
        if not server_path in self._registration_status_store[watchable_type]:
            self._registration_status_store[watchable_type][server_path] = self.WatchableRegistrationStatus(
                active_state=self.WatchableRegistrationState.UNSUBSCRIBED,
                pending_action=self.WatchableRegistrationAction.NONE,
                pending_update_rate=None,
                last_requested_rate=None
            )
        registration_status = self._registration_status_store[watchable_type][server_path]

        # Update state based on SDK client
        if not registration_status.active_state.is_transition_state():  # Handle is subscribed or unsubscribed. no intermediate state
            client_handle = self._client.try_get_existing_watch_handle(server_path)
            self._qt_update_registration_from_watchable_handle(registration_status, client_handle)

        if registration_status.active_state in [self.WatchableRegistrationState.UNSUBSCRIBED, self.WatchableRegistrationState.UNSUBSCRIBING]:
            # Nothing to do. Ensure we do nothing
            registration_status.pending_action = self.WatchableRegistrationAction.NONE
        elif registration_status.active_state == self.WatchableRegistrationState.SUBSCRIBING:
            # enqueue. Next callback will pick this up
            registration_status.pending_action = self.WatchableRegistrationAction.UNSUBSCRIBE
        elif registration_status.active_state == self.WatchableRegistrationState.SUBSCRIBED:
            # Proceed with unsubscription
            registration_status.pending_action = self.WatchableRegistrationAction.NONE
            registration_status.active_state = self.WatchableRegistrationState.UNSUBSCRIBING

            def func(client: ScrutinyClient) -> Optional[Exception]:
                try:
                    client.unwatch(server_path)
                except sdk.exceptions.ScrutinySDKException as e:
                    return e   # Exception others than SDKException are not normal.
                return None

            def ui_callback(expected_error: Optional[Exception], unexpected_error: Optional[Exception]) -> None:
                if unexpected_error is not None:
                    tools.log_exception(self._logger, unexpected_error, str_level=logging.CRITICAL)    # Not supposed to happen
                else:
                    self._qt_watch_unwatch_ui_callback(
                        attempted_action=self.WatchableRegistrationAction.UNSUBSCRIBE,
                        watchable_type=watchable_type,
                        server_path=server_path,
                        registration_status=registration_status,
                        error=expected_error)

            self.schedule_client_request(func, ui_callback)
        else:   # pragma: no cover
            raise NotImplementedError(f"Unsupported state: {registration_status.active_state}")

    @enforce_thread(QT_THREAD_NAME)
    def _qt_registry_watch_callback(self, data: GlobalWatchCallbackData) -> None:
        """Called when a gui component register a watcher on the registry"""
        # Runs from QT thread
        if data.watcher_count is not None and data.watcher_count > 0:
            self._qt_maybe_request_watch(data.watchable_config.watchable_type, data.server_path, data.highest_update_rate)

    @enforce_thread(QT_THREAD_NAME)
    def _qt_registry_unwatch_callback(self, data: GlobalWatchCallbackData) -> None:
        """Called when a gui component unregister a watcher on the registry"""
        # Runs from QT thread
        if data.watcher_count is not None and data.watcher_count == 0:
            self._qt_maybe_request_unwatch(data.watchable_config.watchable_type, data.server_path)
        else:
            handle = self._client.try_get_existing_watch_handle(data.server_path)
            if handle is not None:
                # Slow down the update rate if necessary
                if data.highest_update_rate != handle.requested_update_rate:
                    self._request_update_rate_change(handle, data.highest_update_rate)

    def _qt_value_update_received(self) -> None:
        # Called in the QT thread when a value update is received by the listener (the client)
        aggregated_updates: List[ValueUpdate] = []
        while not self._listener.to_gui_thread_queue.empty():
            update_list = self._listener.to_gui_thread_queue.get_nowait()
            aggregated_updates.extend(update_list)

        self._registry.broadcast_value_updates_to_watchers(aggregated_updates)
        self._listener.ready_for_next_update()

    @enforce_thread(QT_THREAD_NAME)
    def _qt_thread_join_thread_and_emit_stopped(self) -> None:
        """Called when the stop process is completed. Triggered by the internal thread, executed in the QT thread"""
        if self._thread is not None:    # Should always be true
            self._thread.join(0.5)    # Should be already dead if that signal came in. Wil join instantly
            if self._thread.is_alive():
                self._logger.error("Failed to stop the internal thread")
            else:
                self._logger.debug("Server manager stopped")
        self._thread = None
        self._stop_pending = False
        self.signals.stopped.emit()

    @enforce_thread(QT_THREAD_NAME)
    def _set_loaded_sfd(self, sfd: Optional[sdk.SFDInfo]) -> None:
        need_event = (sfd != self._loaded_sfd)
        self._loaded_sfd = sfd
        if need_event:
            invoke_later(lambda: self._signals.loaded_sfd_availability_changed.emit())

    @enforce_thread(QT_THREAD_NAME)
    def _set_device_info(self, device_info: Optional[sdk.DeviceInfo]) -> None:
        need_event = (device_info != self._device_info)
        self._device_info = device_info
        if need_event:
            invoke_later(lambda: self._signals.device_info_availability_changed.emit())

    @enforce_thread(QT_THREAD_NAME)
    def _sfd_loaded_callback(self) -> None:
        # Called in the UI thread when we emit the signal : sfd_loaded.
        # Use to download the SFD data
        info = self.get_server_info()
        if info is not None:
            if info.sfd_firmware_id is not None:
                sfd_firmware_id = info.sfd_firmware_id

                def func(client: ScrutinyClient) -> Tuple[str, Optional[sdk.SFDInfo]]:
                    loaded_sfd = client.get_loaded_sfd()
                    return sfd_firmware_id, loaded_sfd

                self.schedule_client_request(func, self._receive_loaded_sfd_info)

    @enforce_thread(QT_THREAD_NAME)
    def _sfd_unloaded_callback(self) -> None:
        # Called when the server manager emit the signal : sfd_unloaded
        self._set_loaded_sfd(None)

    @enforce_thread(QT_THREAD_NAME)
    def _device_ready_callback(self) -> None:
        # Called when the server manager emit the signal : device_connected
        info = self.get_server_info()
        if info is not None:
            if info.device_session_id is not None:
                session_id = info.device_session_id

                def func(client: ScrutinyClient) -> Tuple[str, Optional[sdk.DeviceInfo]]:
                    device_info = client.get_device_info()
                    return session_id, device_info

                self.schedule_client_request(func, self._receive_device_info)

    @enforce_thread(QT_THREAD_NAME)
    def _device_disconnected_callback(self) -> None:
        # Called when the server manager emit the signal : device_disconnected
        self._set_device_info(None)

    @enforce_thread(QT_THREAD_NAME)
    def _receive_device_info(self, retval: Optional[Any], error: Optional[Exception]) -> None:
        # Called when client.get_device_info() completes
        valid = False
        device_info: Optional[sdk.DeviceInfo] = None
        if retval is not None:
            server_info = self.get_server_info()
            if server_info is not None:
                if server_info.device_session_id is not None:
                    session_id, device_info = cast(Tuple[str, sdk.DeviceInfo], retval)
                    if server_info.device_session_id == session_id:  # Is unchanged since request is initiated
                        valid = True
        else:
            if error is not None:
                self._logger.error(f"Failed to download the device information: {error}")

        if valid:
            assert device_info is not None
            self._set_device_info(device_info)
            self._device_info = device_info
        else:
            self._set_device_info(None)

    @enforce_thread(QT_THREAD_NAME)
    def _receive_loaded_sfd_info(self, retval: Optional[Any], error: Optional[Exception]) -> None:
        # Called when client.get_loaded_sfd() completes.
        valid = False
        loaded_sfd: Optional[sdk.SFDInfo] = None
        if retval is not None:  # Success
            server_info = self.get_server_info()
            if server_info is not None:
                if server_info.sfd_firmware_id is not None:
                    sfd_firmware_id, loaded_sfd = cast(Tuple[str, sdk.SFDInfo], retval)
                    if server_info.sfd_firmware_id == sfd_firmware_id:  # Is unchanged since request is initiated
                        valid = True
        else:
            if error is not None:
                self._logger.error(f"Failed to download the SFD details: {error}")
                tools.log_exception(self._logger, error)

        if valid:
            assert loaded_sfd is not None
            self._set_loaded_sfd(loaded_sfd)
        else:
            self._set_loaded_sfd(None)

    def _server_disconnected_callback(self) -> None:
        self._set_device_info(None)
        self._set_loaded_sfd(None)

    def _server_connected_callback(self) -> None:
        self._request_throttling()

    def _request_throttling(self) -> None:
        def _emphemerous_thread_set_throttling(client: ScrutinyClient) -> int:
            rate = self.SERVER_THROTTLING_RATE
            client.set_server_throttling(rate)
            return rate

        def _ui_thread_response(requested_rate: int, error: Optional[Exception]) -> None:
            if error is not None:
                tools.log_exception(self._logger, error, "Failed to configure server throttling")
            else:
                self._logger.info(f"Server throttling configured to {requested_rate} updates/sec")

        self.schedule_client_request(
            user_func=_emphemerous_thread_set_throttling,
            ui_thread_callback=_ui_thread_response
        )

    # endregion

    # region Public - Fully thread safe

    def schedule_client_request(self,
                                user_func: Callable[[ScrutinyClient], Any],
                                ui_thread_callback: Callable[[Any, Optional[Exception]], None]
                                ) -> None:
        """Runs a client request in a separate thread and calls a callback in the UI thread when done."""
        # Thread safe. Can be called from any thread
        self._client_task_reactor.put_task(user_func, ui_thread_callback)

    def get_server_state(self) -> sdk.ServerState:
        # Called from QT thread + Server thread. atomic
        return self._client.server_state

    def get_server_info(self) -> Optional[sdk.ServerInfo]:
        # Called from QT thread + Server thread. atomic
        try:
            return self._client.get_latest_server_status()
        except sdk.exceptions.ScrutinySDKException:
            return None

    def get_device_info(self) -> Optional[sdk.DeviceInfo]:
        return copy(self._device_info)

    def get_loaded_sfd(self) -> Optional[sdk.SFDInfo]:
        return copy(self._loaded_sfd)

    @property
    def signals(self) -> _Signals:
        """The events exposed to the application"""
        return self._signals
    # endregion

    # region Public -  QT side methods

    @enforce_thread(QT_THREAD_NAME)
    def qt_write_watchable_value(self, fqn: str, value: Union[str, int, float, bool], callback: Callable[[Optional[Exception]], None]) -> None:
        """Request the server manager to write the value of a node in the registry identified by its Fully Qualified Name.
        Must be called from QT thread

        :param fqn: The Fully Qualified Name of the watchable
        :param callback: A callback to call on completion. If the single parameter is None, completed successfully, otherwise will be the exception raised

        """
        server_id = self._registry.get_server_id_fqn(fqn)
        if server_id is None:
            raise Exception(f"Item {fqn} is not in the registry. Cannot write its value")

        def threaded_func(client: ScrutinyClient) -> None:
            handle = client.try_get_existing_watch_handle_by_server_id(server_id)
            if handle is None:
                raise Exception(f"Item {fqn} is not being watched. Cannot write its value")

            handle.value = value    # String parsing is done by the server

        def ui_callback(_: None, exception: Optional[Exception]) -> None:
            callback(exception)

        self.schedule_client_request(threaded_func, ui_callback)

    def get_stats(self) -> Statistics:
        """Return some internal metrics for diagnostic"""
        return self.Statistics(
            listener=self._listener.get_stats(),
            client=self._client.get_local_stats(),
            watchable_registry=self._registry.get_stats(),
            listener_to_gui_qsize=self._listener.gui_qsize,
            listener_event_rate=self._listener.effective_event_rate,
            status_update_received=self._status_update_received
        )

    def reset_stats(self) -> None:
        self._listener.reset_stats()
        self._client.reset_local_stats()
        self._status_update_received = 0

    @enforce_thread(QT_THREAD_NAME)
    def exit(self) -> None:
        self.stop()
        self._exit_in_progress = True

    @enforce_thread(QT_THREAD_NAME)
    def start(self, config: ServerConfig) -> None:
        # Called from the QT thread
        """Makes the server manager try to connect and monitor server state changes
        Will auto-reconnect on disconnection
        """
        self._logger.debug("ServerManager.start() called")
        if self.is_running():
            raise RuntimeError("Already running")   # Temporary hard check for debug

        if self._stop_pending:
            raise RuntimeError("Stop pending")  # Temporary hard check for debug

        self._logger.debug("Starting server manager")
        self._set_device_info(None)
        self._set_loaded_sfd(None)
        self.signals.starting.emit()
        self._allow_auto_reconnect = True
        self._thread_stop_event.clear()
        self._client_task_reactor.start()
        self._thread = threading.Thread(target=self._thread_func, args=[config], daemon=True)
        self._listener.reset_stats()
        self._thread.start()
        self._logger.debug("Server manager started")
        self.signals.started.emit()

    @enforce_thread(QT_THREAD_NAME)
    def stop(self) -> None:
        """Stops the server manager. Will disconnect it from the server and clear all internal data"""
        # Called from the QT thread
        self._logger.debug("ServerManager.stop() called")
        if self._stop_pending:
            self._logger.debug("Stop already pending. Cannot stop")
            return

        if not self.is_running():
            self._logger.debug("Server manager is not running. Cannot stop")
            return

        self._logger.debug("Stopping server manager")
        self._listener.emit_allowed = False
        UserMessagesManager.instance().clear_message(USER_MSG_ID_CONNECT_FAILED)
        self._stop_pending = True
        self._set_device_info(None)
        self._set_loaded_sfd(None)
        self.signals.stopping.emit()

        # Will cause the thread to exit and emit thread_exit_signal that triggers _qt_thread_join_thread_and_emit_stopped in the UI thread
        self._thread_stop_event.set()
        self._client.close_socket()   # Will cancel any pending request in the other thread
        self._client_task_reactor.stop()
        self._logger.debug("Stop initiated")

    def is_running(self) -> bool:
        """Returns ``True`` if the server manager is started and fully working."""
        return self._thread is not None and self._thread.is_alive() and not self._stop_pending

    def is_stopping(self) -> bool:
        """Returns ``True`` if ``stop()`` has been called but the internal thread has not yet exited."""
        return self._stop_pending

    # endregion
