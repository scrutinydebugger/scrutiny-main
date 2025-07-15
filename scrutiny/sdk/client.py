#    client.py
#        A client that can talk with the Scrutiny server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2023 Scrutiny Debugger

__all__ = ['Client']


import scrutiny.sdk
import scrutiny.sdk.datalogging
from scrutiny.sdk.pending_request import PendingRequest
from scrutiny.tools import validation
sdk = scrutiny.sdk
from scrutiny.sdk import _api_parser as api_parser
from scrutiny.sdk.definitions import *
from scrutiny.sdk.watchable_handle import WatchableHandle
from scrutiny.sdk import listeners
from scrutiny.core.basic_types import *
from scrutiny.tools.timer import Timer
from scrutiny.sdk.write_request import WriteRequest
from scrutiny.server.api import typing as api_typing
from scrutiny.server.api import API
from scrutiny.server.api.tcp_client_handler import TCPClientHandler
from scrutiny.tools.stream_datagrams import StreamMaker, StreamParser
from scrutiny.tools.profiling import VariableRateExponentialAverager
from scrutiny import tools
from scrutiny.tools.timebase import RelativeTimebase
import selectors

import logging
from scrutiny.core.logging import DUMPDATA_LOGLEVEL
import traceback
import threading
import socket
import json
import time
import enum
from dataclasses import dataclass
from base64 import b64encode
import queue
import types
from datetime import datetime

from scrutiny.tools.typing import *


class CallbackState(enum.Enum):
    Pending = enum.auto()
    OK = enum.auto()
    TimedOut = enum.auto()
    Cancelled = enum.auto()
    ServerError = enum.auto()
    CallbackError = enum.auto()
    SimulatedError = enum.auto()


ApiResponseCallback = Callable[[CallbackState, Optional[api_typing.S2CMessage]], None]
WatchableListType = Dict[WatchableType, Dict[str, WatchableConfiguration]]

T = TypeVar('T')


class ApiResponseFuture:
    _state: CallbackState
    _reqid: int
    _processed_event: threading.Event
    _error: Optional[Exception]
    _default_wait_timeout: float

    def __init__(self, reqid: int, default_wait_timeout: float) -> None:
        self._state = CallbackState.Pending
        self._reqid = reqid
        self._processed_event = threading.Event()
        self._error = None
        self._default_wait_timeout = default_wait_timeout

    def _wt_mark_completed(self, new_state: CallbackState, error: Optional[Exception] = None) -> None:
        # No need for lock here. The state will change once.
        # But be careful, this will be called by the sdk thread, not the user thread
        self._error = error
        self._state = new_state
        self._processed_event.set()

    def wait(self, timeout: Optional[float] = None) -> None:
        # This will be called by the user thread
        if timeout is None:
            timeout = self._default_wait_timeout
        self._processed_event.wait(timeout)

    @property
    def state(self) -> CallbackState:
        return self._state

    @property
    def error(self) -> Optional[Exception]:
        return self._error

    @property
    def error_str(self) -> str:
        if self._error is not None:
            return str(self._error)
        elif self._state == CallbackState.Pending:
            return 'Not processed yet'
        elif self._state == CallbackState.Cancelled:
            return 'Cancelled'
        elif self._state == CallbackState.TimedOut:
            return 'Timed out'
        return ''


class CallbackStorageEntry:
    """Represent an entry in the registry of all active requests"""
    _reqid: int
    _callback: ApiResponseCallback
    _future: ApiResponseFuture
    _creation_timestamp_monotonic: float
    _timeout: float

    def __init__(self, reqid: int, callback: ApiResponseCallback, future: ApiResponseFuture, timeout: float):
        self._reqid = reqid
        self._callback = callback
        self._future = future
        self._creation_timestamp_monotonic = time.monotonic()
        self._timeout = timeout


@dataclass
class PendingAPIBatchWrite:
    update_dict: Dict[int, WriteRequest]
    confirmation: api_parser.WriteConfirmation
    creation_perf_timestamp: float
    timeout: float


class BatchWriteContext:
    client: "ScrutinyClient"
    timeout: float
    requests: List[WriteRequest]

    def __init__(self, client: "ScrutinyClient", timeout: float) -> None:
        self.client = client
        self.timeout = timeout
        self.requests = []

    def __enter__(self) -> "BatchWriteContext":
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[types.TracebackType]) -> Literal[False]:
        if exc_type is None:
            self.client._flush_batch_write(self)
            try:
                self.client._wait_write_batch_complete(self)
            finally:
                self.client._end_batch()
        self.client._end_batch()
        return False


class FlushPoint:
    pass


@dataclass(init=False)
class WatchableListDownloadRequest(PendingRequest):
    """Represents a pending watchable download request. It can be used to wait for completion or cancel the request.

    :param client: A reference to the client object
    :param request_id:  The request ID of the initiating request
    :param new_data_callback: A callback to process the segmented data as it comes in. Called from the internal thread.     
    """
    _request_id: int
    _watchable_list: WatchableListType
    _new_data_callback: Optional[Callable[[Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]], bool], None]]

    def __init__(self,
                 client: "ScrutinyClient",
                 request_id: int,
                 new_data_callback: Optional[Callable[[Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]], bool], None]] = None
                 ) -> None:
        self._request_id = request_id
        self._watchable_list = {
            WatchableType.Variable: {},
            WatchableType.Alias: {},
            WatchableType.RuntimePublishedValue: {}
        }
        self._new_data_callback = new_data_callback

        super().__init__(client)

    def _add_data(self, data: Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]], done: bool) -> None:
        if self._new_data_callback is not None:
            self._new_data_callback(data, done)
        else:
            # User has no callback to process it. Let's buffer the response for him
            for watchable_type in WatchableType.all():
                if watchable_type in data:
                    self._watchable_list[watchable_type].update(data[watchable_type])

    def cancel(self) -> None:
        """Informs the client that this request can be canceled.
         Subsequent server response will be ignored and this request will be marked as completed, but failed.

        :raise TimeoutException: If the client fails to cancel the request. Should never happen
        :raise OperationFailure: If called on a completed request
        """
        self._client._cancel_download_watchable_list_request(self._request_id)
        try:
            self.wait_for_completion(2)     # Expect to throw when the client mark us as fail.
        except sdk.exceptions.OperationFailure:
            pass

    def get(self) -> WatchableListType:
        """
        Returns the definition of all the watchables obtained through this request, classified by type.

        :raise InvalidValueError: If the data is not available yet (if the request did not completed successfully)

        :return: A dictionary of dictionary containing the definition of each watchable entry that matched the filters. `foo[type][display_path] = <definition>`
        """
        if self._new_data_callback is not None:
            raise sdk.exceptions.InvalidValueError("The watchable list is not stored when a callback is provided to process the partial responses.")
        if not self.completed:
            raise sdk.exceptions.InvalidValueError("Watchable list is not finished downloading")
        if not self.is_success:
            raise sdk.exceptions.InvalidValueError("Watchable list failed to download fully")

        return self._watchable_list


class DataRateMeasurements:
    rx_data_rate: VariableRateExponentialAverager
    tx_data_rate: VariableRateExponentialAverager
    rx_message_rate: VariableRateExponentialAverager
    tx_message_rate: VariableRateExponentialAverager

    def __init__(self) -> None:
        self.rx_data_rate = VariableRateExponentialAverager(time_estimation_window=0.1, tau=0.5, near_zero=1)
        self.tx_data_rate = VariableRateExponentialAverager(time_estimation_window=0.1, tau=0.5, near_zero=1)
        self.rx_message_rate = VariableRateExponentialAverager(time_estimation_window=0.1, tau=0.5, near_zero=0.1)
        self.tx_message_rate = VariableRateExponentialAverager(time_estimation_window=0.1, tau=0.5, near_zero=0.1)

    def update(self) -> None:
        self.rx_data_rate.update()
        self.tx_data_rate.update()
        self.rx_message_rate.update()
        self.tx_message_rate.update()

    def enable(self) -> None:
        self.rx_data_rate.enable()
        self.tx_data_rate.enable()
        self.rx_message_rate.enable()
        self.tx_message_rate.enable()

    def disable(self) -> None:
        self.rx_data_rate.disable()
        self.tx_data_rate.disable()
        self.rx_message_rate.disable()
        self.tx_message_rate.disable()

    def reset(self) -> None:
        self.rx_data_rate.reset()
        self.tx_data_rate.reset()
        self.rx_message_rate.reset()
        self.tx_message_rate.reset()


class ScrutinyClient:
    RxMessageCallback = Callable[["ScrutinyClient", object], None]
    _UPDATE_SERVER_STATUS_INTERVAL = 2
    _MAX_WRITE_REQUEST_BATCH_SIZE = 500
    _MEMORY_READ_DATA_LIFETIME = 30
    _MEMORY_WRITE_DATA_LIFETIME = 30
    _DOWNLOAD_WATCHABLE_LIST_LIFETIME = 30

    @dataclass(frozen=True)
    class Statistics:
        """Performance metrics given by the client useful for diagnostic and debugging"""

        rx_data_rate: float
        """Returns the approximated data input rate coming from the server in Bytes/sec"""
        rx_message_rate: float
        """Returns the approximated message input rate coming from the server in msg/sec"""
        tx_data_rate: float
        """Returns the approximated data output rate sent to the server in Bytes/sec"""
        tx_message_rate: float
        """Returns the approximated message output rate sent to the server in msg/sec"""

    class Events:
        @dataclass(frozen=True)
        class ConnectedEvent:
            """Triggered when the client connects to a Scrutiny server"""
            _filter_flag = 0x01
            host: str
            """The server hostname"""
            port: int
            """The server port"""

            def msg(self) -> str:
                return f"Connected to a Scrutiny server at {self.host}:{self.port}"

        @dataclass(frozen=True)
        class DisconnectedEvent:
            """Triggered when the client disconnects from a Scrutiny server"""
            _filter_flag = 0x02
            host: str
            """The server hostname"""
            port: int
            """The server port"""

            def msg(self) -> str:
                return f"Disconnected from server at {self.host}:{self.port}"

        @dataclass(frozen=True)
        class DeviceReadyEvent:
            """Triggered when the server establish a communication with a device and the handshake phase is completed"""
            _filter_flag = 0x04
            session_id: str
            """A unique ID assigned to the communication session. This ID will change if the same device disconnects and reconnects."""

            def msg(self) -> str:
                return f"A new device is connected and ready. Session ID: {self.session_id} "

        @dataclass(frozen=True)
        class DeviceGoneEvent:
            """Triggered when the the communication between the server and a device stops"""
            _filter_flag = 0x08
            session_id: str
            """The unique ID assigned to the communication session."""

            def msg(self) -> str:
                return f"Device is gone. Last session ID: {self.session_id}"

        @dataclass(frozen=True)
        class SFDLoadedEvent:
            """Triggered when the server loads a Scrutiny Firmware Description file, making Aliases and Variables available through the API """
            _filter_flag = 0x10
            firmware_id: str
            """The firmware ID that matches the SFD"""

            def msg(self) -> str:
                return f"Server has loaded a Firmware Description with firmware ID: {self.firmware_id}"

        @dataclass(frozen=True)
        class SFDUnLoadedEvent:
            """Triggered when the server unloads a Scrutiny Firmware Description file"""
            _filter_flag = 0x20
            firmware_id: str
            """The firmware ID that matches the SFD"""

            def msg(self) -> str:
                return f"Server has unloaded a Firmware Description with firmware ID: {self.firmware_id}"

        @dataclass(frozen=True)
        class DataloggingStateChanged:
            """Triggered when the server datalogging service changes state or when the acquisition/download completion ratio is updated"""

            _filter_flag = 0x40
            details: sdk.DataloggingInfo
            """The state of the datalogging service and the completion ratio"""

            def msg(self) -> str:
                msg = f"Datalogging state changed: {self.details.state.name}"
                if self.details.completion_ratio is not None:
                    msg += f" ({round(self.details.completion_ratio * 100)}%)"
                return msg

        @dataclass(frozen=True)
        class StatusUpdateEvent:
            """Triggered when the a new server status is received"""

            _filter_flag = 0x80
            info: sdk.ServerInfo
            """The status info received"""

            def msg(self) -> str:
                return f"New server status update received"

        @dataclass(frozen=True)
        class DataloggingListChanged:
            """Triggered when the list of datalogging acquisition changed on the server (new, removed or updated). 
            A call to :meth:`read_datalogging_acquisitions_metadata<ScrutinyClient.read_datalogging_acquisitions_metadata>` 
            can be used to fetch the details"""

            _filter_flag = 0x100

            change_type: DataloggingListChangeType
            """The action performed on the datalogging list. Useful to correctly update the client side list"""
            acquisition_reference_id: Optional[str]
            """The targeted acquisition. Will have a value for NEW, DELETE, UPDATE.  ``None`` for DELETE_ALL"""

            def msg(self) -> str:
                return f"List of datalogging acquisition has changed"

        LISTEN_NONE = 0x0
        """Listen to no events"""
        LISTEN_CONNECTED = ConnectedEvent._filter_flag
        """Listen for events of type :class:`ConnectedEvent<scrutiny.sdk.client.ScrutinyClient.Events.ConnectedEvent>`"""
        LISTEN_DISCONNECTED = DisconnectedEvent._filter_flag
        """Listen for events of type :class:`DisconnectedEvent<scrutiny.sdk.client.ScrutinyClient.Events.DisconnectedEvent>`"""
        LISTEN_DEVICE_READY = DeviceReadyEvent._filter_flag
        """Listen for events of type :class:`DeviceReadyEvent<scrutiny.sdk.client.ScrutinyClient.Events.DeviceReadyEvent>`"""
        LISTEN_DEVICE_GONE = DeviceGoneEvent._filter_flag
        """Listen for events of type :class:`DeviceGoneEvent<scrutiny.sdk.client.ScrutinyClient.Events.DeviceGoneEvent>`"""
        LISTEN_SFD_LOADED = SFDLoadedEvent._filter_flag
        """Listen for events of type :class:`SFDLoadedEvent<scrutiny.sdk.client.ScrutinyClient.Events.SFDLoadedEvent>`"""
        LISTEN_SFD_UNLOADED = SFDUnLoadedEvent._filter_flag
        """Listen for events of type :class:`SFDUnLoadedEvent<scrutiny.sdk.client.ScrutinyClient.Events.SFDUnLoadedEvent>`"""
        LISTEN_DATALOGGING_STATE_CHANGED = DataloggingStateChanged._filter_flag
        """Listen for events of type :class:`DataloggingStateChanged<scrutiny.sdk.client.ScrutinyClient.Events.DataloggingStateChanged>`"""
        LISTEN_STATUS_UPDATE_CHANGED = StatusUpdateEvent._filter_flag
        """Listen for events of type :class:`StatusUpdateEvent<scrutiny.sdk.client.ScrutinyClient.Events.StatusUpdateEvent>`"""
        LISTEN_DATALOGGING_LIST_CHANGED = DataloggingListChanged._filter_flag
        """Listen for events of type :class:`DataloggingListChanged<scrutiny.sdk.client.ScrutinyClient.Events.DataloggingListChanged>`"""
        LISTEN_ALL = 0xFFFFFFFF
        """Listen to all events"""

        _ANY_EVENTS = Union[
            ConnectedEvent, DisconnectedEvent, DeviceReadyEvent, DeviceGoneEvent,
            SFDLoadedEvent, SFDUnLoadedEvent, DataloggingStateChanged, StatusUpdateEvent,
            DataloggingListChanged
        ]

    @dataclass
    class _ThreadingEvents:
        stop_worker_thread: threading.Event
        disconnect: threading.Event
        disconnected: threading.Event
        msg_received: threading.Event
        sync_complete: threading.Event
        require_sync: threading.Event
        welcome_received: threading.Event

        def __init__(self) -> None:
            self.stop_worker_thread = threading.Event()
            self.disconnect = threading.Event()
            self.disconnected = threading.Event()
            self.msg_received = threading.Event()
            self.server_status_updated = threading.Event()
            self.sync_complete = threading.Event()
            self.require_sync = threading.Event()
            self.welcome_received = threading.Event()

    _name: Optional[str]        # Name of the client instance
    _server_state: ServerState  # State of the communication with the server. Connected/disconnected/connecting, etc
    _hostname: Optional[str]    # Hostname of the server
    _port: Optional[int]        # Port number of the server
    _logger: logging.Logger     # logging interface
    _encoding: str              # The API string encoding. utf-8
    _sock: Optional[socket.socket]    # The socket talking with the server
    _selector: Optional[selectors.DefaultSelector]  # Used for socket communication
    _stream_parser: StreamParser         # Used for socket communication
    _stream_maker: StreamMaker           # Used for socket communication
    _rx_message_callbacks: List[RxMessageCallback]  # List of callbacks to call for each message received. (mainly for testing)
    _reqid: int                 # The actual request ID. Increasing integer
    _timeout: float             # Default timeout value for server requests
    _write_timeout: float       # Default timeout value for write request
    _request_status_timer: Timer    # Timer for periodic server status update
    _require_status_update: bool    # boolean indicating that a new server status request should be sent
    _write_request_queue: "queue.Queue[Union[WriteRequest, FlushPoint, BatchWriteContext]]"  # Queue of write request given by the users.

    _pending_api_batch_writes: Dict[str, PendingAPIBatchWrite]  # Dict of all the pending batch write currently in progress,
    # indexed by the request token
    # Dict of all the pending memory read requests, indexed by their request_token
    _memory_read_completion_dict: Dict[str, api_parser.MemoryReadCompletion]
    # Dict of all the pending memory write requests, indexed by their request_token
    _memory_write_completion_dict: Dict[str, api_parser.MemoryWriteCompletion]
    # Dict of all the datalogging requests, indexed by their request_token
    _pending_datalogging_requests: Dict[str, sdk.datalogging.DataloggingRequest]
    # Dict of all the active watchable list download request, indexed by their request id
    _pending_watchable_download_request: Dict[int, WatchableListDownloadRequest]

    _worker_thread: Optional[threading.Thread]  # The thread that handles the communication
    _threading_events: _ThreadingEvents  # All the threading events grouped under a single object
    _sock_lock: threading.Lock  # A threading lock to access the socket
    _main_lock: threading.Lock  # A threading lock to access the client internal state variables
    _user_lock: threading.Lock  # A threading lock to access whatever resource the user of the SDK might access

    _callback_storage: Dict[int, CallbackStorageEntry]  # Dict of all pending server request indexed by their request ID
    _watchable_storage: Dict[str, WatchableHandle]  # A cache of all the WatchableHandle given to the user, indexed by their display path
    _watchable_path_to_id_map: Dict[str, str]   # A dict that maps the watchables from display path to their server id
    _server_info: Optional[ServerInfo]  # The actual server internal state given by inform_server_status
    _last_server_info: Optional[ServerInfo]  # The actual server internal state given by inform_server_status

    _active_batch_context: Optional[BatchWriteContext]  # The active write batch. All writes are appended to it if not None

    _listeners: List[listeners.BaseListener]   # List of registered listeners
    _event_queue: "queue.Queue[Events._ANY_EVENTS]"  # A queue containing all the events listened for
    _enabled_events: int                             # Flags indicating what events to listen for
    _datarate_measurements: DataRateMeasurements     # A measurement of the datarate with the server
    _server_timebase: RelativeTimebase          # A timebase that can convert server precise timings to unix timestamp.

    _force_fail_request: bool  # Flag for unit testing that will cause requests to fail prematurely

    def __enter__(self) -> "ScrutinyClient":
        return self

    def __exit__(self, exc_type: Optional[Type[BaseException]], exc_val: Optional[BaseException], exc_tb: Optional[types.TracebackType]) -> Literal[False]:
        self.disconnect()
        return False

    def __init__(self,
                 name: Optional[str] = None,
                 rx_message_callbacks: Optional[List[RxMessageCallback]] = None,
                 timeout: float = 4.0,
                 write_timeout: float = 5.0,
                 enabled_events: int = Events.LISTEN_NONE
                 ):
        """ 
            Creates a client that can communicate with a Scrutiny server

            :param name: Name of the client. Used for logging
            :param rx_message_callbacks: A callback to call each time a server message is received. Called from a separate thread. Mainly used for debugging and testing
            :param timeout: Default timeout to use when making a request to the server
            :param write_timeout: Default timeout to use when writing to the device memory
            :param enabled_events: A flag value constructed by ORing values from :class:`ScrutinyClient.Events<scrutiny.sdk.client.ScrutinyClient.Events>`. Can
                be changed later by invoking :meth:`listen_events<listen_events>`. See :ref:`Using events<page_using_events>` for more details
        """
        logger_name = self.__class__.__name__
        if name is not None:
            logger_name += f"[{name}]"
        self._logger = logging.getLogger(logger_name)

        self._name = name
        self._server_state = ServerState.Disconnected
        self._hostname = None
        self._port = None

        self._encoding = 'utf8'
        self._sock = None
        self._selector = None
        self._rx_message_callbacks = [] if rx_message_callbacks is None else rx_message_callbacks
        self._worker_thread = None
        self._threading_events = self._ThreadingEvents()
        self._sock_lock = threading.Lock()
        self._main_lock = threading.Lock()
        self._user_lock = threading.Lock()
        self._reqid = 0
        self._timeout = timeout
        self._write_timeout = write_timeout
        self._request_status_timer = Timer(self._UPDATE_SERVER_STATUS_INTERVAL)
        self._require_status_update = False
        self._server_info = None
        self._last_server_info = None
        self._write_request_queue = queue.Queue()
        self._pending_api_batch_writes = {}
        self._memory_read_completion_dict = {}
        self._memory_write_completion_dict = {}
        self._pending_datalogging_requests = {}
        self._pending_watchable_download_request = {}

        self._watchable_storage = {}
        self._watchable_path_to_id_map = {}
        self._callback_storage = {}
        self._connection_cancel_request = False

        self._active_batch_context = None
        self._listeners = []
        self._locked_for_connect = False

        self._stream_parser = TCPClientHandler.get_compatible_stream_parser()
        self._stream_maker = TCPClientHandler.get_compatible_stream_maker()
        self._datarate_measurements = DataRateMeasurements()

        self._event_queue = queue.Queue(maxsize=100)   # Not supposed to go much above 1 or 2
        self.listen_events(enabled_events)
        self._force_fail_request = False
        self._server_timebase = RelativeTimebase()

    def _trigger_event(self, evt: Events._ANY_EVENTS, loglevel: int = logging.NOTSET) -> None:
        if self._enabled_events & evt._filter_flag:
            try:
                if self._logger.isEnabledFor(loglevel):
                    self._logger.log(loglevel, evt.msg())
                self._event_queue.put_nowait(evt)
            except queue.Full:
                self._logger.error("Event queue is full. Dropping event")

    def _start_worker_thread(self) -> None:
        self._threading_events.stop_worker_thread.clear()
        self._threading_events.disconnect.clear()
        started_event = threading.Event()
        self._worker_thread = threading.Thread(target=self._worker_thread_task, args=[started_event], daemon=True)
        self._worker_thread.start()
        started_event.wait()
        self._logger.debug('Worker thread started')

    def _stop_worker_thread(self) -> None:
        if self._worker_thread is not None:
            self._logger.debug("Stopping worker thread")
            if self._worker_thread.is_alive():
                self._threading_events.stop_worker_thread.set()
                self._worker_thread.join()
                self._logger.debug("Worker thread stopped")
            else:
                self._logger.debug("Worker thread already stopped")
            self._worker_thread = None

    def _worker_thread_task(self, started_event: threading.Event) -> None:
        self._require_status_update = True  # Bootstrap status update loop
        self._datarate_measurements.enable()
        started_event.set()

        self._request_status_timer.start()
        # _sock will be None after a disconnect
        last_deferred_response_timeout_check = time.monotonic()
        while not self._threading_events.stop_worker_thread.is_set() and self._sock is not None:
            require_sync_before = False
            try:
                if self._threading_events.require_sync.is_set():
                    require_sync_before = True

                self._wt_process_next_server_status_update()

                for msg in self._wt_recv(timeout=0.005):
                    self._wt_process_rx_api_message(msg)

                self._wt_check_callbacks_timeouts()
                if time.monotonic() - last_deferred_response_timeout_check > 1.0:   # Avoid locking the main lock too often
                    self._check_deferred_response_timeouts()
                    last_deferred_response_timeout_check = time.monotonic()

                self._wt_process_write_watchable_requests()
                self._wt_process_device_state()
                self._datarate_measurements.update()

            except sdk.exceptions.ConnectionError as e:
                if self._connection_cancel_request:
                    self._logger.debug(f"Connection error in worker thread (caused by explicit cancel): {e}")
                else:
                    self._logger.error(f"Connection error in worker thread: {e}")
                self._wt_disconnect()    # Will set _sock to None
            except Exception as e:
                tools.log_exception(self._logger, e, "Unhandled exception in worker thread")
                self._wt_disconnect()    # Will set _sock to None

            if self._threading_events.disconnect.is_set():
                self._logger.debug(f"User required to disconnect")
                self._wt_disconnect()  # Will set _sock to None
                self._threading_events.disconnected.set()

            if require_sync_before:
                self._threading_events.require_sync.clear()
                self._threading_events.sync_complete.set()

        self._datarate_measurements.disable()
        self._logger.debug('Worker thread is exiting')
        self._threading_events.stop_worker_thread.clear()

    def _wt_process_msg_inform_server_status(self, msg: api_typing.S2C.InformServerStatus, reqid: Optional[int]) -> None:
        self._request_status_timer.start()
        info = api_parser.parse_inform_server_status(msg)
        self._logger.debug('Updating server status')
        with self._main_lock:
            self._server_info = info
            self._threading_events.server_status_updated.set()
        self._trigger_event(self.Events.StatusUpdateEvent(info=info))

    def _wt_process_msg_watchable_update(self, msg: api_typing.S2C.WatchableUpdate, reqid: Optional[int]) -> None:
        updates = api_parser.parse_watchable_update(msg)

        updated_watchables: List[WatchableHandle] = []
        for update in updates:
            with self._main_lock:
                watchable: Optional[WatchableHandle] = None
                if update.server_id in self._watchable_storage:
                    watchable = self._watchable_storage[update.server_id]

            if watchable is None:
                self._logger.error(f"Got watchable update for unknown watchable. Server ID={update.server_id}")
                continue
            else:
                if self._logger.isEnabledFor(DUMPDATA_LOGLEVEL):   # prgama: no cover
                    self._logger.log(DUMPDATA_LOGLEVEL, f"Updating value of {update.server_id} ({watchable.name})")

            update_dt = self._server_timebase.micro_to_dt(update.server_time_us)
            watchable._update_value(update.value, timestamp=update_dt)
            updated_watchables.append(watchable)

        for listener in self._listeners:
            listener._broadcast_update(updated_watchables)

    def _wt_process_msg_inform_write_completion(self, msg: api_typing.S2C.WriteCompletion, reqid: Optional[int]) -> None:
        completion = api_parser.parse_write_completion(msg)

        if completion.request_token not in self._pending_api_batch_writes:
            return   # Maybe triggered by another client. Silently ignore.

        batch_write = self._pending_api_batch_writes[completion.request_token]
        if completion.batch_index not in batch_write.update_dict:
            self._logger.error("The server returned a write completion with an unknown batch_index")
            return

        write_request = batch_write.update_dict[completion.batch_index]
        if completion.success:
            write_request._watchable._set_last_write_datetime()
            write_request._mark_complete(True, server_time_us=completion.server_time_us)
        else:
            write_request._mark_complete(False, "Server failed to write to the device", server_time_us=completion.server_time_us)
        del batch_write.update_dict[completion.batch_index]

    def _wt_process_msg_inform_memory_read_complete(self, msg: api_typing.S2C.ReadMemoryComplete, reqid: Optional[int]) -> None:
        completion = api_parser.parse_memory_read_completion(msg)
        with self._main_lock:
            if completion.request_token not in self._memory_read_completion_dict:
                self._memory_read_completion_dict[completion.request_token] = completion
            else:
                self._logger.error(f"Received duplicate memory read completion with request token {completion.request_token}")

    def _wt_process_msg_inform_memory_write_complete(self, msg: api_typing.S2C.WriteMemoryComplete, reqid: Optional[int]) -> None:
        completion = api_parser.parse_memory_write_completion(msg)
        with self._main_lock:
            if completion.request_token not in self._memory_write_completion_dict:
                self._memory_write_completion_dict[completion.request_token] = completion
            else:
                self._logger.error(f"Received duplicate memory write completion with request token {completion.request_token}")

    def _wt_process_msg_datalogging_acquisition_complete(self, msg: api_typing.S2C.InformDataloggingAcquisitionComplete, reqid: Optional[int]) -> None:
        completion = api_parser.parse_datalogging_acquisition_complete(msg)
        if completion.request_token not in self._pending_datalogging_requests:
            self._logger.warning('Received a notice of completion for a datalogging acquisition, but its request_token was unknown')
            return

        request = self._pending_datalogging_requests[completion.request_token]
        request._mark_complete_specialized(completion.success, completion.reference_id, completion.detail_msg)
        del self._pending_datalogging_requests[completion.request_token]

    def _wt_process_msg_datalogging_list_changed(self, msg: api_typing.S2C.InformDataloggingListChanged, reqid: Optional[int]) -> None:
        parsed = api_parser.parse_datalogging_list_changed(msg)
        self._trigger_event(
            self.Events.DataloggingListChanged(acquisition_reference_id=parsed.reference_id, change_type=parsed.action),
            loglevel=logging.DEBUG
        )

    def _wt_process_msg_get_watchable_list_response(self, msg: api_typing.S2C.GetWatchableList, reqid: Optional[int]) -> None:
        if reqid is None:
            self._logger.warning('Received a watchable list message, but the request ID was not available.')
            return

        content = api_parser.parse_get_watchable_list(msg)

        with self._main_lock:
            if reqid not in self._pending_watchable_download_request:
                self._logger.warning(f'Received a watchable list message, but the request ID was is not tied to any active request {reqid}')
                return

            req = self._pending_watchable_download_request[reqid]

        req._add_data(content.data, content.done)
        if content.done:
            req._mark_complete(success=True)

    def _wt_process_msg_welcome(self, msg: api_typing.S2C.Welcome, reqid: Optional[int]) -> None:
        welcome_data = api_parser.parse_welcome(msg)
        self._server_timebase.set_zero_to(welcome_data.server_time_zero_timestamp)
        self._threading_events.welcome_received.set()

    def _wt_process_next_server_status_update(self) -> None:
        if self._request_status_timer.is_timed_out() or self._require_status_update:
            self._require_status_update = False
            self._request_status_timer.stop()
            self.logger.debug("Requesting server status update")
            req = self._make_request(API.Command.Client2Api.GET_SERVER_STATUS)
            self._send(req)  # No callback, we have a continuous listener

    def _wt_check_callbacks_timeouts(self) -> None:
        now = time.monotonic()
        with self._main_lock:
            reqids = list(self._callback_storage.keys())

        for reqid in reqids:
            with self._main_lock:
                callback_entry: Optional[CallbackStorageEntry] = None
                if reqid in self._callback_storage:
                    callback_entry = self._callback_storage[reqid]

            if callback_entry is None:
                continue

            if now - callback_entry._creation_timestamp_monotonic > callback_entry._timeout:
                try:
                    callback_entry._callback(CallbackState.TimedOut, None)
                except (sdk.exceptions.ConnectionError):
                    raise
                except Exception:
                    pass
                callback_entry._future._wt_mark_completed(CallbackState.TimedOut)

                with self._main_lock:
                    if reqid in self._callback_storage:
                        del self._callback_storage[reqid]

    def _check_deferred_response_timeouts(self) -> None:
        with self._main_lock:
            for kstr in list(self._memory_read_completion_dict.keys()):
                if time.monotonic() - self._memory_read_completion_dict[kstr].local_monotonic_timestamp > self._MEMORY_READ_DATA_LIFETIME:
                    del self._memory_read_completion_dict[kstr]

            for kstr in list(self._memory_write_completion_dict.keys()):
                if time.monotonic() - self._memory_write_completion_dict[kstr].local_monotonic_timestamp > self._MEMORY_WRITE_DATA_LIFETIME:
                    del self._memory_write_completion_dict[kstr]

            for kint in list(self._pending_watchable_download_request.keys()):
                if self._pending_watchable_download_request[kint]._is_expired(self._DOWNLOAD_WATCHABLE_LIST_LIFETIME):
                    del self._pending_watchable_download_request[kint]

    def _wt_process_rx_api_message(self, msg: Dict[str, Any]) -> None:
        self._threading_events.msg_received.set()
        # These callbacks are mainly for testing.
        for callback in self._rx_message_callbacks:
            callback(self, msg)

        reqid: Optional[int] = msg.get('reqid', None)
        cmd: Optional[str] = msg.get('cmd', None)

        if cmd is None:
            self._logger.error('Got a message without a "cmd" field')
            self._logger.debug(msg)
        else:
            try:
                if cmd == API.Command.Api2Client.WATCHABLE_UPDATE:
                    self._wt_process_msg_watchable_update(cast(api_typing.S2C.WatchableUpdate, msg), reqid)
                elif cmd == API.Command.Api2Client.INFORM_SERVER_STATUS:
                    self._wt_process_msg_inform_server_status(cast(api_typing.S2C.InformServerStatus, msg), reqid)
                elif cmd == API.Command.Api2Client.INFORM_WRITE_COMPLETION:
                    self._wt_process_msg_inform_write_completion(cast(api_typing.S2C.WriteCompletion, msg), reqid)
                elif cmd == API.Command.Api2Client.INFORM_MEMORY_READ_COMPLETE:
                    self._wt_process_msg_inform_memory_read_complete(cast(api_typing.S2C.ReadMemoryComplete, msg), reqid)
                elif cmd == API.Command.Api2Client.INFORM_MEMORY_WRITE_COMPLETE:
                    self._wt_process_msg_inform_memory_write_complete(cast(api_typing.S2C.WriteMemoryComplete, msg), reqid)
                elif cmd == API.Command.Api2Client.INFORM_DATALOGGING_ACQUISITION_COMPLETE:
                    self._wt_process_msg_datalogging_acquisition_complete(cast(api_typing.S2C.InformDataloggingAcquisitionComplete, msg), reqid)
                elif cmd == API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED:
                    self._wt_process_msg_datalogging_list_changed(cast(api_typing.S2C.InformDataloggingListChanged, msg), reqid)
                elif cmd == API.Command.Api2Client.GET_WATCHABLE_LIST_RESPONSE:
                    self._wt_process_msg_get_watchable_list_response(cast(api_typing.S2C.GetWatchableList, msg), reqid)
                elif cmd == API.Command.Api2Client.WELCOME:
                    self._wt_process_msg_welcome(cast(api_typing.S2C.Welcome, msg), reqid)
            except sdk.exceptions.BadResponseError as e:
                tools.log_exception(self._logger, e, "Bad message from server")

            if reqid is not None:   # message is a response to a request
                self._wt_process_callbacks(cmd, msg, reqid)

    def _wt_process_callbacks(self, cmd: str, msg: Dict[str, Any], reqid: int) -> None:
        callback_entry: Optional[CallbackStorageEntry] = None
        with self._main_lock:
            if reqid in self._callback_storage:
                callback_entry = self._callback_storage[reqid]

        # We have a callback for that response
        if callback_entry is not None:
            error: Optional[Exception] = None

            if cmd == API.Command.Api2Client.ERROR_RESPONSE:
                error = Exception(msg.get('msg', "No error message provided"))
                self._logger.error(f"Server returned an error response. reqid={reqid}. {error}")

                try:
                    callback_entry._callback(CallbackState.ServerError, msg)
                except (sdk.exceptions.ConnectionError):
                    raise
                except Exception:
                    pass
                finally:
                    callback_entry._future._wt_mark_completed(CallbackState.ServerError, error=error)
            else:
                try:
                    self._logger.debug(f"Running {cmd} callback for request ID {reqid}")
                    callback_entry._callback(CallbackState.OK, msg)
                except (sdk.exceptions.ConnectionError):
                    raise
                except Exception as e:
                    error = e

                if error is not None:
                    tools.log_exception(self._logger, error, f"Callback raised an exception. cmd={cmd}, reqid={reqid}.")
                    callback_entry._future._wt_mark_completed(CallbackState.CallbackError, error=error)

                elif callback_entry._future.state == CallbackState.Pending:
                    callback_entry._future._wt_mark_completed(CallbackState.OK)

            with self._main_lock:
                if reqid in self._callback_storage:
                    del self._callback_storage[reqid]

    def _wt_process_write_watchable_requests(self) -> None:
        # Note _pending_api_batch_writes is always accessed from worker thread
        api_req = self._make_request(API.Command.Client2Api.WRITE_WATCHABLE, {'updates': []})
        api_req = cast(api_typing.C2S.WriteValue, api_req)

        # Clear old requests.
        # No need for lock here. The _request_queue crosses time domain boundaries
        now = time.perf_counter()
        if len(self._pending_api_batch_writes) > 0:
            tokens = list(self._pending_api_batch_writes.keys())
            for token in tokens:
                pending_batch = self._pending_api_batch_writes[token]
                if now - pending_batch.creation_perf_timestamp > pending_batch.timeout:
                    for request in pending_batch.update_dict.values():  # Completed request are already removed of that dict.
                        request._mark_complete(False, f"Timed out ({pending_batch.timeout} seconds)")
                    del self._pending_api_batch_writes[token]
                else:
                    for request in pending_batch.update_dict.values():  # Completed request are already removed of that dict.
                        if request.watchable.is_dead:
                            request._mark_complete(False, f"{request.watchable.name} is not available anymore")

                # Once a batch is fully processed, meaning all requests have been treated and removed
                # We can prune the remaining empty batch
                if len(pending_batch.update_dict) == 0:
                    del self._pending_api_batch_writes[token]

        # Process new requests
        n = 0
        batch_dict: Dict[int, WriteRequest] = {}
        while not self._write_request_queue.empty():
            obj = self._write_request_queue.get()
            if isinstance(obj, FlushPoint):
                break
            requests: List[WriteRequest] = []
            batch_timeout = self._write_timeout
            if isinstance(obj, BatchWriteContext):
                if n != 0:
                    raise RuntimeError("Missing FlushPoint before Batch")
                if len(obj.requests) > self._MAX_WRITE_REQUEST_BATCH_SIZE:
                    for request in obj.requests:
                        request._mark_complete(False, "Batch too big")
                    break
                requests = obj.requests
                batch_timeout = obj.timeout
            elif isinstance(obj, WriteRequest):
                requests = [obj]
            else:
                raise RuntimeError("Unsupported element in write queue")

            for request in requests:
                if n < self._MAX_WRITE_REQUEST_BATCH_SIZE:
                    if request._watchable._configuration is not None:
                        api_req['updates'].append({
                            'batch_index': n,
                            'watchable': request._watchable._configuration.server_id,
                            'value': request._value
                        })
                        batch_dict[n] = request
                        n += 1
                    else:
                        request._mark_complete(False, "Watchable has been made invalid")
                else:
                    request._mark_complete(False, "Batch overflowed")   # Should never happen because we enforce n==0 on batch

            if n >= self._MAX_WRITE_REQUEST_BATCH_SIZE:
                break

        if len(api_req['updates']) == 0:
            return

        def _wt_write_watchable_response_callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                confirmation = api_parser.parse_write_value_response(cast(api_typing.S2C.WriteValue, response))

                if confirmation.count != len(batch_dict):
                    request._mark_complete(False, f"Count mismatch in request and server confirmation.")
                else:
                    self._pending_api_batch_writes[confirmation.request_token] = PendingAPIBatchWrite(
                        update_dict=batch_dict,
                        confirmation=confirmation,
                        creation_perf_timestamp=time.perf_counter(),    # Used to prune the dict if no response after X time
                        timeout=batch_timeout
                    )
            else:
                # The WriteRequest is different because we give a future object to the client and it's
                # to wait for the initial response. We do our own error message handling because we do not have access to the future object generated by send()
                error = f"[{state.name}] No error message provided"
                if state == CallbackState.ServerError and response is not None:
                    msg = cast(api_typing.S2C.Error, response).get('msg', None)
                    if msg is not None:
                        error = msg
                request._mark_complete(False, error)

        self._send(api_req, _wt_write_watchable_response_callback, timeout=batch_timeout)
        # We don't need the future object here because the WriteRequest act as one.

    def _wt_process_device_state(self) -> None:
        """Check the state of the device and take action when it changes"""
        if self._server_info is not None:

            # ====  Check Device conn
            if self._last_server_info is not None and self._last_server_info.device_session_id is not None:
                if self._last_server_info.device_session_id != self._server_info.device_session_id:  # New value or None
                    self._wt_clear_all_watchables(ValueStatus.DeviceGone)
                    self._trigger_event(self.Events.DeviceGoneEvent(session_id=self._last_server_info.device_session_id), loglevel=logging.INFO)
                    if self._server_info.device_session_id is not None:
                        self._trigger_event(self.Events.DeviceReadyEvent(session_id=self._server_info.device_session_id), loglevel=logging.INFO)
            else:
                if self._server_info.device_session_id is not None:
                    self._trigger_event(self.Events.DeviceReadyEvent(session_id=self._server_info.device_session_id), loglevel=logging.INFO)

            # ====  Check SFD
            if self._last_server_info is not None and self._last_server_info.sfd_firmware_id is not None:
                if self._server_info.sfd_firmware_id != self._last_server_info.sfd_firmware_id:    # None or new value
                    self._wt_clear_all_watchables(ValueStatus.SFDUnloaded, [WatchableType.Alias, WatchableType.Variable])   # RPVs are still there.
                    self._trigger_event(self.Events.SFDUnLoadedEvent(firmware_id=self._last_server_info.sfd_firmware_id), loglevel=logging.INFO)
                    if self._server_info.sfd_firmware_id is not None:
                        self._trigger_event(self.Events.SFDLoadedEvent(firmware_id=self._server_info.sfd_firmware_id), loglevel=logging.INFO)
            else:
                if self._server_info.sfd_firmware_id is not None:
                    self._trigger_event(self.Events.SFDLoadedEvent(firmware_id=self._server_info.sfd_firmware_id), loglevel=logging.INFO)

            if self._last_server_info is not None:
                if self._last_server_info.datalogging.state != self._server_info.datalogging.state:
                    # Passage from/to NA are logged as debug only to keep the info log clean
                    loglevel = logging.DEBUG if DataloggingState.NA in (
                        self._last_server_info.datalogging.state, self._server_info.datalogging.state) else logging.INFO
                    self._trigger_event(self.Events.DataloggingStateChanged(self._server_info.datalogging), loglevel=loglevel)
                elif self._last_server_info.datalogging.completion_ratio != self._server_info.datalogging.completion_ratio:
                    self._trigger_event(self.Events.DataloggingStateChanged(self._server_info.datalogging), loglevel=logging.DEBUG)
        else:
            if self._last_server_info is not None:
                if self._last_server_info.device_session_id is not None:
                    self._trigger_event(self.Events.DeviceGoneEvent(session_id=self._last_server_info.device_session_id), loglevel=logging.INFO)

                if self._last_server_info.sfd_firmware_id is not None:
                    self._trigger_event(self.Events.SFDUnLoadedEvent(firmware_id=self._last_server_info.sfd_firmware_id), loglevel=logging.INFO)

        self._last_server_info = self._server_info

    def close_socket(self) -> None:
        """Forcefully attempt to close a socket to cancel any pending connection or requests"""
        # Does not rexpect _sock_lock on purpose.
        with tools.SuppressException():
            if self._sock is not None:
                self._connection_cancel_request = True  # Simply to mask the connection error we will cause
                self._sock.close()      # Try it. May fail, it's ok.

    def _wt_disconnect(self) -> None:
        """Disconnect from a Scrutiny server, called by the Worker Thread .
            Does not throw an exception in case of broken pipe
        """
        self.close_socket()

        with self._sock_lock:
            if self._sock is not None:
                self._logger.debug(f"Disconnecting from server at {self._hostname}:{self._port}")
                try:
                    self._sock.close()
                except socket.error as e:
                    tools.log_exception(self._logger, e, "Failed to close the socket", str_level=logging.DEBUG)

            if self._selector is not None:
                self._selector.close()

            self._stream_parser.reset()

            self._sock = None
            self._selector = None

        events_to_trigger: List[ScrutinyClient.Events._ANY_EVENTS] = []
        with self._main_lock:
            if self._last_server_info is not None:
                if self._last_server_info.device_session_id is not None:
                    events_to_trigger.append(self.Events.DeviceGoneEvent(session_id=self._last_server_info.device_session_id))

                if self._last_server_info.sfd_firmware_id is not None:
                    events_to_trigger.append(self.Events.SFDUnLoadedEvent(firmware_id=self._last_server_info.sfd_firmware_id))

                if self._server_state == ServerState.Connected and self._hostname is not None and self._port is not None:
                    events_to_trigger.append(self.Events.DisconnectedEvent(self._hostname, self._port))

            self._last_server_info = None

            with self._user_lock:   # Critical part, the user reads those properties
                self._wt_clear_all_watchables(ValueStatus.ServerGone)
                self._wt_clear_all_pending_requests("Server is disconnected")
                self._hostname = None
                self._port = None
                self._server_state = ServerState.Disconnected
                self._server_info = None

            for callback_entry in self._callback_storage.values():
                if callback_entry._future.state == CallbackState.Pending:
                    callback_entry._future._wt_mark_completed(CallbackState.Cancelled)
            self._callback_storage.clear()

        for event in events_to_trigger:
            self._trigger_event(event, loglevel=logging.INFO)

    def _wt_clear_all_watchables(self, new_status: ValueStatus, watchable_types: Optional[List[WatchableType]] = None) -> None:
        # Don't lock the main lock, supposed to be done beforehand
        assert new_status is not ValueStatus.Valid
        if watchable_types is None:
            watchable_types = [WatchableType.Alias, WatchableType.Variable, WatchableType.RuntimePublishedValue]
        server_ids = list(self._watchable_storage.keys())
        for server_id in server_ids:
            watchable = self._watchable_storage[server_id]
            if watchable.type in watchable_types:
                watchable._set_invalid(new_status)
                if watchable.display_path in self._watchable_path_to_id_map:
                    del self._watchable_path_to_id_map[watchable.display_path]
                del self._watchable_storage[server_id]

    def _wt_clear_all_pending_requests(self, failure_reason: str) -> None:
        """Cancels and clear all request handles that may take a long time to respond.
        These handles are passed to the users."""
        # Don't lock the main lock, supposed to be done beforehand
        self._memory_read_completion_dict.clear()
        self._memory_write_completion_dict.clear()

        for request in self._pending_watchable_download_request.values():
            request._mark_complete(success=False, failure_reason=failure_reason)
        self._pending_watchable_download_request.clear()

        for datalog_request in self._pending_datalogging_requests.values():
            datalog_request._mark_complete(success=False, failure_reason=failure_reason)
        self._pending_datalogging_requests.clear()

        for batch_write_request in self._pending_api_batch_writes.values():
            for write_req in batch_write_request.update_dict.values():
                write_req._mark_complete(success=False, failure_reason=failure_reason)
        self._pending_api_batch_writes.clear()

    def _register_callback(self, reqid: int, callback: ApiResponseCallback, timeout: float) -> ApiResponseFuture:
        future = ApiResponseFuture(reqid, default_wait_timeout=timeout + 0.5)    # Allow some margin for thread to mark it timed out
        callback_entry = CallbackStorageEntry(
            reqid=reqid,
            callback=callback,
            future=future,
            timeout=timeout
        )

        with self._main_lock:
            self._callback_storage[reqid] = callback_entry
        return future

    def _send(self,
              obj: api_typing.C2SMessage,
              callback: Optional[ApiResponseCallback] = None,
              timeout: Optional[float] = None
              ) -> Optional[ApiResponseFuture]:
        """Sends a message to the API. Return a future if a callback is specified. If no timeout is given, uses the default timeout value"""

        error: Optional[Exception] = None
        future: Optional[ApiResponseFuture] = None

        if timeout is None:
            timeout = self._timeout

        if not isinstance(obj, dict):
            raise TypeError(f'ScrutinyClient only sends data under the form of a dictionary. Received {obj.__class__.__name__}')

        if callback is not None:
            if 'reqid' not in obj:
                raise RuntimeError("Missing reqid in request")

            future = self._register_callback(obj['reqid'], callback, timeout=timeout)
            if self._force_fail_request:
                future._wt_mark_completed(CallbackState.SimulatedError, None)

        if not self._force_fail_request:
            with self._sock_lock:
                if self._sock is None or self._stream_maker is None:
                    raise sdk.exceptions.ConnectionError(f"Disconnected from server")

                try:
                    s = json.dumps(obj)
                    if self._logger.isEnabledFor(DUMPDATA_LOGLEVEL):    # pragma: no cover
                        self._logger.log(DUMPDATA_LOGLEVEL, f"Sending {s}")
                    data = self._stream_maker.encode(s.encode(self._encoding))
                    self._sock.send(data)
                    self._datarate_measurements.tx_data_rate.add_data(len(data))
                    self._datarate_measurements.tx_message_rate.add_data(1)
                except socket.error as e:
                    error = e
                    self._logger.debug(traceback.format_exc())

            if error:
                self.disconnect()
                raise sdk.exceptions.ConnectionError(f"Disconnected from server. {error}")

        return future

    def _wt_recv(self, timeout: Optional[float] = None) -> Generator[Dict[str, Any], None, None]:
        # No need to lock sock_lock here. Important is during disconnection
        error: Optional[Exception] = None
        obj: Optional[Dict[str, Any]] = None

        if self._sock is None or self._selector is None:
            raise sdk.exceptions.ConnectionError(f"Disconnected from server")

        server_gone = False
        try:
            events = self._selector.select(timeout)
            for key, _ in events:
                assert key.fileobj is self._sock
                data = self._sock.recv(4096)
                if not data:
                    server_gone = True
                else:
                    self._datarate_measurements.rx_data_rate.add_data(len(data))
                    self._stream_parser.parse(data)
        except socket.error as e:
            server_gone = True
            error = e
            self._logger.debug(traceback.format_exc())

        if server_gone:
            self._wt_disconnect()
            err_str = str(error) if error else ""
            raise sdk.exceptions.ConnectionError(f"Disconnected from server. {err_str}")

        while not self._stream_parser.queue().empty():
            try:
                data_str = self._stream_parser.queue().get().decode(self._encoding)
                if self._logger.isEnabledFor(DUMPDATA_LOGLEVEL):    # pragma: no cover
                    self._logger.log(DUMPDATA_LOGLEVEL, f"Received: {data_str}")
                obj = json.loads(data_str)
                if obj is not None:
                    self._datarate_measurements.rx_message_rate.add_data(1)
                    yield obj
            except json.JSONDecodeError as e:
                self._logger.error(f"Received malformed JSON from the server. {e}")
                self._logger.debug(traceback.format_exc())

    def _make_request(self, command: str, data: Optional[Dict[str, Any]] = None) -> api_typing.C2SMessage:
        with self._main_lock:
            reqid = self._reqid
            self._reqid += 1
            if self._reqid >= 2**32 - 1:
                self._reqid = 0

        cmd: api_typing.BaseC2SMessage = {
            'cmd': command,
            'reqid': reqid
        }

        if data is None:
            data = {}
        data = data.copy()
        data.update(cmd)

        return data

    def _enqueue_write_request(self, request: Union[WriteRequest, BatchWriteContext, FlushPoint]) -> None:
        self._write_request_queue.put(request)

    def __del__(self) -> None:
        self.disconnect()

    def _is_batch_write_in_progress(self) -> bool:
        return self._active_batch_context is not None

    def _process_write_request(self, request: WriteRequest) -> None:
        if self._is_batch_write_in_progress():
            assert self._active_batch_context is not None
            self._active_batch_context.requests.append(request)
        else:
            self._enqueue_write_request(request)

    def _cancel_download_watchable_list_request(self, reqid: int) -> None:
        with self._main_lock:
            if reqid not in self._pending_watchable_download_request:
                raise sdk.exceptions.OperationFailure(f"No download reqest identified by request ID : {reqid}")
            self._pending_watchable_download_request[reqid]._mark_complete(success=False, failure_reason="Cancelled by user")

    def _flush_batch_write(self, batch_write_context: BatchWriteContext) -> None:
        self._enqueue_write_request(FlushPoint())   # Flush Point required because Python thread-safe queue has no peek() method.
        self._enqueue_write_request(batch_write_context)

    def _end_batch(self) -> None:
        self._active_batch_context = None

    def _wait_write_batch_complete(self, batch: BatchWriteContext) -> None:
        start_time = time.monotonic()

        incomplete_count: Optional[int] = None
        try:
            for write_request in batch.requests:
                remaining_time = max(0, batch.timeout - (time.monotonic() - start_time))
                write_request.wait_for_completion(timeout=remaining_time)
            timed_out = False
        except sdk.exceptions.TimeoutException:
            timed_out = True

        if timed_out:
            incomplete_count = 0
            for request in batch.requests:
                if not request.completed:
                    incomplete_count += 1

            if incomplete_count > 0:
                raise sdk.exceptions.TimeoutException(
                    f"Incomplete batch write. {incomplete_count} write requests not completed in {batch.timeout} sec. ")

    # === User API ====

    def connect(self, hostname: str, port: int, wait_status: bool = True) -> "ScrutinyClient":
        """Connect to a Scrutiny server through a TCP socket. 

        :param hostname: The hostname or IP address of the server
        :param port: The listening port of the server
        :param wait_status: Wait for a server status update after the socket connection is established. 
            Ensure that a value is available when calling :meth:`get_latest_server_status()<get_latest_server_status>`

        :raise ConnectionError: In case of failure
        """
        self.disconnect()
        self._locked_for_connect = True
        self._connection_cancel_request = False
        self._threading_events.welcome_received.clear()
        with self._main_lock:
            self._hostname = hostname
            self._port = port
            connect_error: Optional[Exception] = None
            self._logger.debug(f"Connecting to {hostname}:{port}")
            with self._sock_lock:
                try:
                    self._server_state = ServerState.Connecting
                    self._stream_parser.reset()
                    self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    self._selector = selectors.DefaultSelector()
                    self._selector.register(self._sock, selectors.EVENT_READ)
                    self._sock.connect((hostname, port))
                    self._trigger_event(self.Events.ConnectedEvent(self._hostname, self._port), loglevel=logging.INFO)
                    self._server_state = ServerState.Connected
                    self._start_worker_thread()
                except socket.error as e:
                    # Connect may fail in many way.
                    # The user can close the socket to unblock the connection thread.
                    self._logger.debug(traceback.format_exc())
                    connect_error = e

        self._locked_for_connect = False
        if connect_error is not None:
            self.disconnect()
            raise sdk.exceptions.ConnectionError(f'Failed to connect to the server at "{hostname}:{port}". Error: {connect_error}')

        self._threading_events.welcome_received.wait(self._timeout)
        if not self._threading_events.welcome_received.is_set():
            self.disconnect()
            raise sdk.exceptions.TimeoutException(f'Did not receive a Welcome message from the server. Timeout={self._timeout}s')

        if wait_status:
            # Same logic as wait_server_status_update(), but without clearing the flag since we want at least 1 update.
            timeout = self._UPDATE_SERVER_STATUS_INTERVAL + 2
            self._threading_events.server_status_updated.wait(timeout=timeout)
            if not self._threading_events.server_status_updated.is_set():
                raise sdk.exceptions.TimeoutException(f"Server status did not update within a {timeout} seconds delay")
            
        return self

    def disconnect(self) -> None:
        """Disconnect from the server"""
        if self._worker_thread is None:
            self._wt_disconnect()  # Can call safely from this thread
            return

        if not self._worker_thread.is_alive():
            self._wt_disconnect()  # Can call safely from this thread
            return

        self.close_socket()
        self._threading_events.disconnected.clear()
        self._threading_events.disconnect.set()
        self._threading_events.disconnected.wait(timeout=2)  # Timeout avoid race condition if the thread was exiting

        self._stop_worker_thread()

    def listen_events(self, enabled_events: int, disabled_events: int = 0) -> None:
        """Select which events are to be listen for when calling :meth:`read_event<read_event>`.

        :param enabled_events: A flag value constructed by ORing values from :class:`ScrutinyClient.Events<scrutiny.sdk.client.ScrutinyClient.Events>`

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: If the flag value is negative
        """
        validation.assert_int_range(enabled_events, 'enabled_events', minval=0)
        self._enabled_events = enabled_events & (self.Events.LISTEN_ALL ^ disabled_events)

    def try_get_existing_watch_handle_by_server_id(self, server_id: str) -> Optional[WatchableHandle]:
        """Retrieve an existing watchable handle created after a call to :meth:`watch()<watch>` if it exists, identified by its unique server_id.
        This methods makes no request to the server and is therefore non-blocking.

        :param server_id: The server_id assigned to the handle returned by :meth:`watch()<watch>`

        :raise TypeError: Given parameter not of the expected type

        :return: A handle that can read/write the watched element or ``None`` if the element is not being watched.
        """
        validation.assert_type(server_id, 'server_id', str)
        handle: Optional[WatchableHandle] = None
        with tools.SuppressException(KeyError):
            handle = self._watchable_storage[server_id]  # No need to lock. This is atomic

        return handle

    def try_get_existing_watch_handle(self, path: str) -> Optional[WatchableHandle]:
        """Retrieve an existing watchable handle created after a call to :meth:`watch()<watch>` if it exists.
        This methods makes no request to the server and is therefore non-blocking.

        :param path: The path of the element being watched

        :raise TypeError: Given parameter not of the expected type

        :return: A handle that can read/write the watched element or ``None`` if the element is not being watched.
        """

        validation.assert_type(path, 'path', str)

        cached_watchable: Optional[WatchableHandle] = None
        with self._main_lock:
            if path in self._watchable_path_to_id_map:
                server_id = self._watchable_path_to_id_map[path]
                if server_id in self._watchable_storage:
                    cached_watchable = self._watchable_storage[server_id]

        return cached_watchable

    def watch(self, path: str) -> WatchableHandle:
        """Starts watching a watchable element identified by its display path (tree-like path)

        :param path: The path of the element to watch

        :raise OperationFailure: If the watch request fails to complete
        :raise TypeError: Given parameter not of the expected type

        :return: A handle that can read/write the watched element.
        """
        validation.assert_type(path, 'path', str)

        cached_watchable = self.try_get_existing_watch_handle(path)
        if cached_watchable:
            return cached_watchable

        watchable = WatchableHandle(self, path)

        def wt_subscribe_callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                response = cast(api_typing.S2C.SubscribeWatchable, response)
                watchable_defs = api_parser.parse_subscribe_watchable_response(response)
                if len(watchable_defs) != 1:
                    raise sdk.exceptions.BadResponseError(
                        f'The server did confirm the subscription of {len(response["subscribed"])} while we requested only for 1')

                if path not in watchable_defs:
                    raise sdk.exceptions.BadResponseError(
                        f'The server did not confirm the subscription for the right watchable. Got {list(response["subscribed"].keys())[0]}, expected {path}')

                watchable._configure(watchable_defs[path])
                assert watchable._configuration is not None
                with self._main_lock:
                    self._watchable_path_to_id_map[watchable.display_path] = watchable._configuration.server_id
                    self._watchable_storage[watchable._configuration.server_id] = watchable

        req = self._make_request(API.Command.Client2Api.SUBSCRIBE_WATCHABLE, {
            'watchables': [watchable.display_path]  # Single element
        })
        future = self._send(req, wt_subscribe_callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(f"Failed to subscribe to the watchable. {future.error_str}")

        watchable._assert_configured()
        assert watchable._configuration is not None  # To please mypy

        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(f"Now watching {watchable.display_path} (Server ID={watchable._configuration.server_id})")

        return watchable

    def unwatch(self, watchable_ref: Union[str, WatchableHandle]) -> None:
        """Stop watching a watchable element

        :param watchable_ref: The tree-like path of the watchable element or the handle to it

        :raise ValueError: If path is not valid
        :raise TypeError: Given parameter not of the expected type
        :raise NameNotFoundError: If the required path is not presently being watched
        :raise OperationFailure: If the subscription cancellation failed in any way
        """
        validation.assert_type(watchable_ref, 'watchable_ref', (str, WatchableHandle))
        if isinstance(watchable_ref, WatchableHandle):
            path = watchable_ref.display_path
        else:
            path = watchable_ref

        watchable: Optional[WatchableHandle] = None
        with self._main_lock:
            if path in self._watchable_path_to_id_map:
                server_id = self._watchable_path_to_id_map[path]
                if server_id in self._watchable_storage:
                    watchable = self._watchable_storage[server_id]

        if watchable is None:
            raise sdk.exceptions.NameNotFoundError(f"Cannot unwatch {path} as it is not being watched.")

        req = self._make_request(API.Command.Client2Api.UNSUBSCRIBE_WATCHABLE, {
            'watchables': [
                watchable.display_path
            ]
        })

        def wt_unsubscribe_callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK and watchable is not None:
                response = cast(api_typing.S2C.UnsubscribeWatchable, response)
                if len(response['unsubscribed']) != 1:
                    raise sdk.exceptions.BadResponseError(
                        f'The server did cancel the subscription of {len(response["unsubscribed"])} while we requested only for 1')

                if response['unsubscribed'][0] != watchable.display_path:
                    raise sdk.exceptions.BadResponseError(
                        f'The server did not cancel the subscription for the right watchable. Got {response["unsubscribed"][0]}, expected {watchable.display_path}')

        future = self._send(req, wt_unsubscribe_callback)
        assert future is not None
        error: Optional[Exception] = None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(f"Failed to unsubscribe to the watchable. {future.error_str}")

        with self._main_lock:
            if watchable.display_path in self._watchable_path_to_id_map:
                del self._watchable_path_to_id_map[watchable.display_path]

            if watchable._configuration is not None:
                if watchable._configuration.server_id in self._watchable_storage:
                    del self._watchable_storage[watchable._configuration.server_id]

        watchable._set_invalid(ValueStatus.NotWatched)
        if self._logger.isEnabledFor(logging.DEBUG):
            self._logger.debug(f"Done watching {watchable.display_path}")

    def wait_new_value_for_all(self, timeout: float = 5) -> None:
        """Wait for all watched elements to be updated at least once after the call to this method

        :param timeout: Amount of time to wait for the update

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise TimeoutException: If not all watched elements gets updated in time
        """
        timeout = validation.assert_float_range(timeout, 'timeout', minval=0)
        counter_map: Dict[str, Optional[int]] = {}
        with self._main_lock:
            watchable_storage_copy = self._watchable_storage.copy()  # Shallow copy

        for server_id in watchable_storage_copy:
            counter_map[server_id] = watchable_storage_copy[server_id]._update_counter

        start_time = time.monotonic()
        for server_id in watchable_storage_copy:
            timeout_remainder = max(round(timeout - (time.monotonic() - start_time), 2), 0)
            # Wait update will throw if the server has gone away as the _disconnect method will set all watchables "invalid"
            watchable_storage_copy[server_id].wait_update(previous_counter=counter_map[server_id], timeout=timeout_remainder)

    def wait_server_status_update(self, timeout: float = _UPDATE_SERVER_STATUS_INTERVAL + 0.5) -> None:
        """Wait for the server to broadcast a status update. Happens periodically

        :param timeout: Amount of time to wait for the update

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise TimeoutException: Server status update did not occurred within the timeout time
        """
        timeout = validation.assert_float_range(timeout, 'timeout', minval=0)
        self._threading_events.server_status_updated.clear()
        self._threading_events.server_status_updated.wait(timeout=timeout)

        if not self._threading_events.server_status_updated.is_set():
            raise sdk.exceptions.TimeoutException(f"Server status did not update within a {timeout} seconds delay")

    def request_server_status_update(self, wait: bool = False, timeout: Optional[float] = None) -> Optional[sdk.ServerInfo]:
        """Request the server with an immediate status update. Avoid waiting for the periodic request to be sent. 

        :param wait: Wait for the response if ``True``
        :param timeout: Amount of time to wait for the update. Have no effect if ``wait=False``. Use the SDK default timeout if ``None``

        :raise OperationFailure: Failed to get the server status
        :raise TimeoutException: Server status update did not occurred within the timeout time

        :return: The server status if ``wait=True``, ``None`` otherwise
        """
        req = self._make_request(API.Command.Client2Api.GET_SERVER_STATUS)
        self._send(req)

        if wait:
            kwargs = {}
            if timeout is not None:
                kwargs['timeout'] = timeout
            self.wait_server_status_update(**kwargs)
            return self.get_latest_server_status()
        return None

    def wait_device_ready(self, timeout: float) -> None:
        """Wait for a device to be connected to the server and have finished its handshake.

        :param timeout: Amount of time to wait for the device

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise InvalidValueError: If the watchable becomes invalid while waiting
        :raise TimeoutException: If the device does not become ready within the required timeout
        """

        timeout = validation.assert_float_range(timeout, 'timeout', minval=0)

        t1 = time.perf_counter()
        while True:
            server_status = self.get_latest_server_status()
            if server_status is not None:
                if server_status.device_comm_state == sdk.DeviceCommState.ConnectedReady:
                    break
            consumed_time = time.perf_counter() - t1
            remaining_time = max(timeout - consumed_time, 0)
            timed_out = False
            try:
                self.wait_server_status_update(remaining_time)
            except sdk.exceptions.TimeoutException:
                timed_out = True

            if timed_out:
                raise sdk.exceptions.TimeoutException(f'Device did not become ready within {timeout}s')

    def batch_write(self, timeout: Optional[float] = None) -> BatchWriteContext:
        """Starts a batch write. Write operations will be enqueued and committed together.
        Every write is guaranteed to be executed in the right order

        :param timeout: Amount of time to wait for the completion of the batch once committed. If ``None`` the default write timeout
            will be used.

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise OperationFailure: Failed to complete the batch write

        """
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)

        if self._active_batch_context is not None:
            raise sdk.exceptions.OperationFailure("Batch write cannot be nested")

        if timeout is None:
            timeout = self._write_timeout

        batch_context = BatchWriteContext(self, timeout)
        self._active_batch_context = batch_context
        return batch_context

    def get_installed_sfds(self) -> Dict[str, sdk.SFDInfo]:
        """Gets the list of Scrutiny Firmware Description file installed on the server

        :raise OperationFailure: Failed to get the SFD list

        :return: A dictionary mapping firmware IDS (hash) to a :class:`SFDInfo<scrutiny.sdk.SFDInfo>` structure
        """
        req = self._make_request(API.Command.Client2Api.GET_INSTALLED_SFD)

        @dataclass
        class Container:
            obj: Optional[Dict[str, sdk.SFDInfo]]

        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                cb_data.obj = api_parser.parse_get_installed_sfds_response(cast(api_typing.S2C.GetInstalledSFD, response))

        future = self._send(req, callback)
        assert future is not None
        future.wait()
        if future.state != CallbackState.OK or cb_data.obj is None:
            raise sdk.exceptions.OperationFailure(
                f"Failed to get the list of Scrutiny Firmware Description file installed on the server. {future.error_str}")

        return cb_data.obj

    def wait_process(self, timeout: Optional[float] = None) -> None:
        """Wait for the SDK thread to execute fully at least once. Useful for testing

        :param timeout: Amount of time to wait for the completion of the thread loops. If ``None`` the default timeout will be used.

        :raise TimeoutException: Worker thread does not complete a full loop within the given timeout
        """

        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)

        if timeout is None:
            timeout = self._timeout
        self._threading_events.sync_complete.clear()
        self._threading_events.require_sync.set()
        self._threading_events.sync_complete.wait(timeout=timeout)
        if not self._threading_events.sync_complete.is_set():
            raise sdk.exceptions.TimeoutException(f"Worker thread did not complete a full loop within the {timeout} seconds.")

    def read_memory(self, address: int, size: int, timeout: Optional[float] = None) -> bytes:
        """Read the device memory synchronously.

        :param address: The start address of the region to read
        :param size: The size of the region to read, in bytes.
        :param timeout: Maximum amount of time to wait to get the data back. If ``None``, the default timeout value will be used

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise OperationFailure: Failed to complete the reading
        :raise TimeoutException: If the read operation does not complete within the given timeout value
        """

        validation.assert_int_range(address, 'address', minval=0)
        validation.assert_int_range(size, 'size', minval=1)
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)

        time_start = time.monotonic()
        if timeout is None:
            timeout = self._timeout

        req = self._make_request(API.Command.Client2Api.READ_MEMORY, {
            'address': address,
            'size': size
        })

        @dataclass
        class Container:
            obj: Optional[str]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                response = cast(api_typing.S2C.ReadMemory, response)
                if 'request_token' not in response:
                    raise sdk.exceptions.BadResponseError('Missing request token in response')
                cb_data.obj = response['request_token']

        future = self._send(req, callback, timeout)
        assert future is not None
        future.wait()
        if future.state != CallbackState.OK or cb_data.obj is None:
            raise sdk.exceptions.OperationFailure(f"Failed to read the device memory. {future.error_str}")

        remaining_time = max(0, timeout - (time_start - time.monotonic()))
        request_token = cb_data.obj

        t = time.perf_counter()
        # No lock here because we have a 1 producer, 1 consumer scenario and we are waiting. We don't write
        while request_token not in self._memory_read_completion_dict:
            if time.perf_counter() - t >= remaining_time:
                break
            time.sleep(0.002)

        with self._main_lock:
            if request_token not in self._memory_read_completion_dict:
                raise sdk.exceptions.TimeoutException(
                    "Did not get memory read result after %0.2f seconds. (address=0x%08X, size=%d)" % (timeout, address, size))

            completion = self._memory_read_completion_dict[request_token]
            del self._memory_read_completion_dict[request_token]

        if not completion.success or completion.data is None:
            raise sdk.exceptions.OperationFailure(f"Failed to read the device memory. {completion.error}")

        return completion.data

    def write_memory(self, address: int, data: bytes, timeout: Optional[float] = None) -> None:
        """Write the device memory synchronously. This method will exit once the write is completed otherwise will throw an exception in case of failure

        :param address: The start address of the region to read
        :param data: The data to write
        :param timeout: Maximum amount of time to wait to get the write completion confirmation. If ``None``, the default write timeout value will be used

        :raise TypeError: Given parameter not of the expected type
        :raise ValueError: Given parameter has an invalid value
        :raise OperationFailure: Failed to complete the reading
        :raise TimeoutException: If the read operation does not complete within the given timeout value

        """

        validation.assert_int_range(address, 'address', minval=0)
        validation.assert_type(data, 'data', bytes)
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)

        time_start = time.perf_counter()
        if timeout is None:
            timeout = self._timeout

        req = self._make_request(API.Command.Client2Api.WRITE_MEMORY, {
            'address': address,
            'data': b64encode(data).decode('ascii')
        })

        @dataclass
        class Container:
            obj: Optional[str]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                response = cast(api_typing.S2C.WriteMemory, response)
                if 'request_token' not in response:
                    raise sdk.exceptions.BadResponseError('Missing request token in response')
                cb_data.obj = response['request_token']

        future = self._send(req, callback, timeout)
        assert future is not None
        future.wait()
        if future.state != CallbackState.OK or cb_data.obj is None:
            raise sdk.exceptions.OperationFailure(f"Failed to write the device memory. {future.error_str}")

        remaining_time = max(0, timeout - (time_start - time.perf_counter()))
        request_token = cb_data.obj

        t = time.perf_counter()
        # No lock here because we have a 1 producer, 1 consumer scenario and are waiting. We don't write
        while request_token not in self._memory_write_completion_dict:
            if time.perf_counter() - t >= remaining_time:
                break
            time.sleep(0.002)

        with self._main_lock:
            if request_token not in self._memory_write_completion_dict:
                raise sdk.exceptions.OperationFailure(
                    "Did not get memory write completion confirmation after %0.2f seconds. (address=0x%08X, size=%d)" % (timeout, address, len(data)))

            completion = self._memory_write_completion_dict[request_token]
            del self._memory_write_completion_dict[request_token]

        if not completion.success:
            raise sdk.exceptions.OperationFailure(f"Failed to write the device memory. {completion.error}")

    def read_datalogging_acquisition(self, reference_id: str, timeout: Optional[float] = None) -> sdk.datalogging.DataloggingAcquisition:
        """Reads a datalogging acquisition from the server storage identified by its reference ID

        :param reference_id: The acquisition unique ID
        :param timeout: The request timeout value. The default client timeout will be used if set to ``None`` Defaults to ``None``

        :raise OperationFailure: If fetching the acquisition fails

        :return: An object containing the acquisition, including the data, the axes, the trigger index, the graph name, etc
        """
        validation.assert_type(reference_id, 'reference_id', str)
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)

        if timeout is None:
            timeout = self._timeout

        req = self._make_request(API.Command.Client2Api.READ_DATALOGGING_ACQUISITION_CONTENT, {
            'reference_id': reference_id
        })

        @dataclass
        class Container:
            obj: Optional[sdk.datalogging.DataloggingAcquisition]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                cb_data.obj = api_parser.parse_read_datalogging_acquisition_content_response(
                    cast(api_typing.S2C.ReadDataloggingAcquisitionContent, response)
                )
        future = self._send(req, callback)
        assert future is not None
        future.wait(timeout)

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(
                f"Failed to read the datalogging acquisition with reference ID '{reference_id}'. {future.error_str}")

        assert cb_data.obj is not None
        acquisition = cb_data.obj
        return acquisition

    def start_datalog(self, config: sdk.datalogging.DataloggingConfig) -> sdk.datalogging.DataloggingRequest:
        """Requires the device to make a datalogging acquisition based on the given configuration

        :param config: The datalogging configuration including sampling rate, signals to log, trigger condition and operands, etc.

        :raise OperationFailure: If the request to the server fails
        :raise ValueError: Bad parameter value
        :raise TypeError: Given parameter not of the expected type

        :return: A `DataloggingRequest` handle that can provide the status of the acquisition process and used to fetch the data.
         """
        validation.assert_type(config, 'config', sdk.datalogging.DataloggingConfig)

        req_data: api_typing.C2S.RequestDataloggingAcquisition = {
            'cmd': "",  # Will be overridden
            "reqid": 0,  # Will be overridden

            'condition': config._trigger_condition.value,
            'sampling_rate_id': config._sampling_rate,
            'decimation': config._decimation,
            'name': config._name,
            'timeout': config._timeout,
            'trigger_hold_time': config._trigger_hold_time,
            'probe_location': config._trigger_position,
            'x_axis_type': config._x_axis_type.value,
            'x_axis_signal': config._get_api_x_axis_signal(),
            'yaxes': config._get_api_yaxes(),
            'operands': config._get_api_trigger_operands(),
            'signals': config._get_api_signals(),
        }

        req = self._make_request(API.Command.Client2Api.REQUEST_DATALOGGING_ACQUISITION, cast(Dict[str, Any], req_data))

        @dataclass
        class Container:
            request: Optional[sdk.datalogging.DataloggingRequest]
        cb_data: Container = Container(request=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                request_token = api_parser.parse_request_datalogging_acquisition_response(
                    cast(api_typing.S2C.RequestDataloggingAcquisition, response)
                )
                cb_data.request = sdk.datalogging.DataloggingRequest(client=self, request_token=request_token)
                self._pending_datalogging_requests[request_token] = cb_data.request

        future = self._send(req, callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(
                f"Failed to request the datalogging acquisition'. {future.error_str}")
        assert cb_data.request is not None
        return cb_data.request

    def read_datalogging_acquisitions_metadata(self, reference_id: str, timeout: Optional[float] = None) -> Optional[sdk.datalogging.DataloggingStorageEntry]:
        """Get the acquisition metadata from the server datalogging storage. 
        Returns a result similar to :meth:`list_stored_datalogging_acquisitions<list_stored_datalogging_acquisitions>`
        but with a single storage entry.

        :param reference_id: The acquisition reference_id (unique ID)
        :param timeout: The request timeout value. The default client timeout will be used if set to ``None`` Defaults to ``None``

        :raise OperationFailure: If fetching the metadata fails

        :return: The storage entry with its metadata or ``None`` if the given ID is not present in the storage
        """
        validation.assert_type(reference_id, 'reference_id', str)
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)

        if timeout is None:
            timeout = self._timeout

        req = self._make_request(API.Command.Client2Api.LIST_DATALOGGING_ACQUISITION, {
            'reference_id': reference_id
        })

        @dataclass
        class Container:
            obj: Optional[List[sdk.datalogging.DataloggingStorageEntry]]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                cb_data.obj = api_parser.parse_list_datalogging_acquisitions_response(
                    cast(api_typing.S2C.ListDataloggingAcquisition, response)
                )
        future = self._send(req, callback)
        assert future is not None
        future.wait(timeout)

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(
                f"Failed to read the datalogging acquisition list from the server database. {future.error_str}")

        assert cb_data.obj is not None

        if len(cb_data.obj) == 1:
            return cb_data.obj[0]
        else:
            return None

    def list_stored_datalogging_acquisitions(self,
                                             firmware_id: Optional[str] = None,
                                             before_datetime: Optional[datetime] = None,
                                             count: int = 500,
                                             timeout: Optional[float] = None) -> List[sdk.datalogging.DataloggingStorageEntry]:
        """Gets the list of datalogging acquisitions stored in the server database. 
        Acquisitions are returned ordered by acquisition time, from newest to oldest.

        :param firmware_id: When not ``None``, searches for acquisitions taken with this firmware ID
        :param before_datetime: An optional upper limit for the acquisition time. Will download acquisition taken before this datetime. Meant ot be used for UI lazy-loading
        :param count: Maximum number of acquisition to fetch. Upper limit is 10000
        :param timeout: The request timeout value. The default client timeout will be used if set to ``None`` Defaults to ``None``

        :raise OperationFailure: If fetching the list fails

        :return: A list of datalogging storage entries with acquisition metadata in them.
        """
        validation.assert_type(firmware_id, 'firmware_id', (str, type(None)))
        timeout = validation.assert_float_range_if_not_none(timeout, 'timeout', minval=0)
        if before_datetime is not None:
            validation.assert_type(before_datetime, 'before_datetime', datetime)

        count = validation.assert_int_range(count, 'count', minval=0, maxval=10000)

        if timeout is None:
            timeout = self._timeout

        data: Dict[str, Any] = {
            'firmware_id': firmware_id,
            'count': count,
            'before_timestamp': None
        }
        if before_datetime is not None:
            data['before_timestamp'] = before_datetime.timestamp()

        req = self._make_request(API.Command.Client2Api.LIST_DATALOGGING_ACQUISITION, data)

        @dataclass
        class Container:
            obj: Optional[List[sdk.datalogging.DataloggingStorageEntry]]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                cb_data.obj = api_parser.parse_list_datalogging_acquisitions_response(
                    cast(api_typing.S2C.ListDataloggingAcquisition, response)
                )
        future = self._send(req, callback)
        assert future is not None
        future.wait(timeout)

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(
                f"Failed to read the datalogging acquisition list from the server database. {future.error_str}")

        assert cb_data.obj is not None
        return cb_data.obj

    def configure_device_link(self, link_type: sdk.DeviceLinkType, link_config: Optional[sdk.BaseLinkConfig]) -> None:
        """Configure the communication link between the Scrutiny server and the device remote device. 
        If the link is configured in a way that a Scrutiny device is accessible, the server will automatically
        connect to it and inform the client about it. The `client.server.server_state.device_comm_state` will reflect this.

        :param link_type: Type of communication link to use. Serial, UDP, TCP, etc.
        :param link_config:  A configuration object that matches the link type.
            :attr:`UDP<scrutiny.sdk.DeviceLinkType.UDP>` : :class:`UDPLinkConfig<scrutiny.sdk.UDPLinkConfig>` /
            :attr:`TCP<scrutiny.sdk.DeviceLinkType.TCP>` : :class:`TCPLinkConfig<scrutiny.sdk.TCPLinkConfig>` /
            :attr:`Serial<scrutiny.sdk.DeviceLinkType.Serial>` : :class:`SerialLinkConfig<scrutiny.sdk.SerialLinkConfig>`

        :raise ValueError: Bad parameter value
        :raise TypeError: Given parameter not of the expected type
        :raise OperationFailure: If the request to the server fails
        """

        validation.assert_type(link_type, "link_type", sdk.DeviceLinkType)
        validation.assert_type(link_config, "link_config", sdk.BaseLinkConfig)

        assert link_type is not None
        assert link_config is not None

        api_map: Dict["DeviceLinkType", Tuple[str, Type[Union[BaseLinkConfig, None]]]] = {
            DeviceLinkType.NONE: ('none', sdk.NoneLinkConfig),
            DeviceLinkType.Serial: ('serial', sdk.SerialLinkConfig),
            DeviceLinkType.UDP: ('udp', sdk.UDPLinkConfig),
            DeviceLinkType.TCP: ('tcp', sdk.TCPLinkConfig),
            DeviceLinkType.RTT: ('rtt', sdk.RTTLinkConfig),
            DeviceLinkType._Dummy: ('dummy', type(None))
        }

        if link_type not in api_map:
            raise ValueError(f"Unsupported link type : {link_type.name}")

        link_type_api_name, config_type = api_map[link_type]

        if not isinstance(link_config, config_type):
            raise TypeError(f'link_config must be of type {config_type} when link_type is {link_type.name}. Got {link_type.__class__.__name__}')

        req = self._make_request(API.Command.Client2Api.SET_LINK_CONFIG, {
            'link_type': link_type_api_name,
            'link_config': link_config._to_api_format()
        })

        future = self._send(req, lambda *args, **kwargs: None)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(
                f"Failed to configure the device communication link. {future.error_str}")

    def user_command(self, subfunction: int, data: bytes = bytes()) -> sdk.UserCommandResponse:
        """
        Sends a UserCommand request to the device with the given subfunction and data. UserCommand is a request that calls a user defined callback
        in the device firmware. It allows a developer to take advantage of the scrutiny protocol to communicate non-scrutiny data with its device.

        :param subfunction: Subfunction of the request. From 0x0 to 0x7F
        :param data: The payload to send to the device

        :raise ValueError: Bad parameter value
        :raise TypeError: Given parameter not of the expected type
        :raise OperationFailure: If the command completion fails
        """
        validation.assert_int_range(subfunction, 'subfunction', 0, 0xFF)
        validation.assert_type(data, 'data', bytes)

        req = self._make_request(API.Command.Client2Api.USER_COMMAND, {
            'subfunction': subfunction,
            'data': b64encode(data).decode('utf8')
        })

        @dataclass
        class Container:
            obj: Optional[sdk.UserCommandResponse]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def wt_user_command_callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                response = cast(api_typing.S2C.UserCommand, response)
                cb_data.obj = api_parser.parse_user_command_response(response)

        future = self._send(req, wt_user_command_callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK or cb_data.obj is None:
            raise sdk.exceptions.OperationFailure(f"Failed to request the device UserCommand. {future.error_str}")

        return cb_data.obj

    def get_latest_server_status(self) -> ServerInfo:
        """Returns an immutable structure of data containing the latest server status that has been broadcast.
        This makes no request to the server, it simply returns the latest value. See :meth:`request_server_status_update<request_server_status_update>`
        to fetch a new status update from the server

        :raise ConnectionError: If the connection to the server is lost
        :raise InvalidValueError: If the server status is not available (never received it).
        """
        if self._locked_for_connect:    # Avoid blocking
            raise sdk.exceptions.ConnectionError(f"Disconnected from server")

        with self._main_lock:
            if not self._server_state == ServerState.Connected:
                raise sdk.exceptions.ConnectionError(f"Disconnected from server")
            info = self._server_info
        if info is None:
            raise sdk.exceptions.InvalidValueError("Server status is not available")

        # server_info is readonly and only its reference gets changed when updated.
        # We can safely return a reference here. The user can't mess it up
        return info

    def get_device_info(self) -> Optional[sdk.DeviceInfo]:
        """Gets all the available details about the device. 
        This information includes device id, name, communication parameters, special memory regions, datalogging details, available sampling rates, etc.

        :raise OperationFailure: If the request to the server fails

        :return: The device informations or ``None`` if not device is connected
        """
        req = self._make_request(API.Command.Client2Api.GET_DEVICE_INFO)

        @dataclass
        class Container:
            obj: Optional[sdk.DeviceInfo]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                cb_data.obj = api_parser.parse_get_device_info(cast(api_typing.S2C.GetDeviceInfo, response))
        future = self._send(req, callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(f"Failed to read the device information. {future.error_str}")

        return cb_data.obj

    def get_loaded_sfd(self) -> Optional[sdk.SFDInfo]:
        """
        Reads the details of the Scrutiny Firmware Description loaded on the server side. 
        This information includes the firmware ID and the SFD metadata such as project name, project version, author, etc..

        :raise OperationFailure: If the request to the server fails

        :return: The loaded SFD details or ``None`` if no SFD is loaded on the server
        """
        req = self._make_request(API.Command.Client2Api.GET_LOADED_SFD)

        @dataclass
        class Container:
            obj: Optional[sdk.SFDInfo]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                cb_data.obj = api_parser.parse_get_loaded_sfd(cast(api_typing.S2C.GetLoadedSFD, response))
        future = self._send(req, callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(f"Failed to read the device information. {future.error_str}")

        return cb_data.obj

    def register_listener(self, listener: listeners.BaseListener) -> None:
        """Register a new listener. The client will notify it each time a new value update is received from the server

        :param listener: The listener to register
        """
        with self._main_lock:
            self._listeners.append(listener)

    def get_watchable_count(self) -> Dict[WatchableType, int]:
        """
        Request the server with the number of available watchable items, organized per type

        :raise ValueError: Bad parameter value
        :raise TypeError: Given parameter not of the expected type
        :raise OperationFailure: If the command completion fails

        :return: A dictionary containing the number of watchables, classified by type
        """
        req = self._make_request(API.Command.Client2Api.GET_WATCHABLE_COUNT)

        @dataclass
        class Container:
            obj: Optional[Dict[WatchableType, int]]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def wt_get_watchable_count_callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                response = cast(api_typing.S2C.GetWatchableCount, response)
                cb_data.obj = api_parser.parse_get_watchable_count(response)

        future = self._send(req, wt_get_watchable_count_callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK or cb_data.obj is None:
            raise sdk.exceptions.OperationFailure(f"Failed to request the available watchable count. {future.error_str}")

        return cb_data.obj

    def download_watchable_list(self,
                                types: Optional[List[WatchableType]] = None,
                                max_per_response: int = 500,
                                name_patterns: List[str] = [],
                                partial_reception_callback: Optional[Callable[[
                                    Dict[sdk.WatchableType, Dict[str, sdk.WatchableConfiguration]], bool], None]] = None
                                ) -> WatchableListDownloadRequest:
        """
            Request the server for the list of watchable items available in its datastore.

            :param types: List of types to download. All of them if ``None``
            :param max_per_response: Maximum number of watchable per datagram sent by the server.
            :param name_patterns: List of name filters in the form of a glob string. Any watchable with a path that matches at least one name filter will be returned. 
                All watchables are returned if ``None``
            :param partial_reception_callback: A callback to be called by the client whenever new data is received by the server. Data might be segmented
                in several parts. Expected signature : ``my_callback(data, last_segment)`` where ``data`` is a dictionary of the form ``data[watchable_type][path] = watchable``
                and ``last_segment`` indicate if that data segment was the last one.
                If ``None`` is given, the received data will be stored inside the request object and can be fetched once the request has completed by 
                calling :meth:`get()<scrutiny.sdk.client.WatchableListDownloadRequest.get>`
                **Note** This callback is called from an internal thread.

            :raise ValueError: Bad parameter value
            :raise TypeError: Given parameter not of the expected type
            :raise ConnectionError: If the connection to the server is broken

            :return: A handle to the request object that can be used for synchronization (:meth:`wait_for_completion<scrutiny.sdk.client.WatchableListDownloadRequest.wait_for_completion>`) 
                or cancel the request (:meth:`cancel<scrutiny.sdk.client.WatchableListDownloadRequest.cancel>`)
        """
        validation.assert_type(max_per_response, 'max_per_response', int)
        if types is None:
            types = [WatchableType.Alias, WatchableType.RuntimePublishedValue, WatchableType.Variable]

        validation.assert_type(types, 'types', list)
        for type in types:
            validation.assert_type(type, 'types', WatchableType)
            if type not in WatchableType.all():
                raise ValueError(f"Watchable type {type} is not a valid type to download")

        validation.assert_type(name_patterns, 'name_patterns', list)
        for name_pattern in name_patterns:
            validation.assert_type(name_pattern, 'name_pattern', str)

        watchable_type_names = {
            WatchableType.Alias: "alias",
            WatchableType.RuntimePublishedValue: "rpv",
            WatchableType.Variable: "var",
        }

        filter_dict = {
            "type": [watchable_type_names[wt] for wt in types]
        }
        if len(name_patterns) > 0:
            filter_dict['name'] = name_patterns

        req = self._make_request(API.Command.Client2Api.GET_WATCHABLE_LIST, {
            'max_per_response': max_per_response,
            'filter': filter_dict
        })

        request_handle = WatchableListDownloadRequest(client=self, request_id=req['reqid'], new_data_callback=partial_reception_callback)
        with self._main_lock:
            self._pending_watchable_download_request[req['reqid']] = request_handle

        self._send(req)
        # responses will be catched by the worker thread and the request handle will be updated
        # using the response request_id echo.

        return request_handle

    def clear_datalogging_storage(self) -> None:
        """Delete all datalogging acquisition stored on the server.
        This action is irreversible

        :raise OperationFailure: If the request to the server fails
        """
        req = self._make_request(API.Command.Client2Api.DELETE_ALL_DATALOGGING_ACQUISITION)

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            pass
        future = self._send(req, callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(f"Failed to clear the datalogging storage. {future.error_str}")

    def delete_datalogging_acquisition(self, reference_id: str) -> None:
        """Delete a single datalogging acquisition stored on the server.
        This action is irreversible

        :param reference_id: The unique ``reference_id`` of the acquisition to delete.

        :raise OperationFailure: If the request to the server fails
        :raise TypeError: Given parameter not of the expected type
        """
        validation.assert_type(reference_id, 'reference_id', str)

        req = self._make_request(API.Command.Client2Api.DELETE_DATALOGGING_ACQUISITION, {
            'reference_id': reference_id
        })

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            pass
        future = self._send(req, callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(
                f"Failed to delete the datalogging acquisition with reference ID: {reference_id}. {future.error_str}")

    def update_datalogging_acquisition(self, reference_id: str, name: str) -> None:
        """Update a single datalogging acquisition stored on the server.

        :param reference_id: The unique ``reference_id`` of the acquisition to delete.
        :param name: New name for the acquisition. 

        :raise OperationFailure: If the request to the server fails
        :raise TypeError: Given parameter not of the expected type
        """
        validation.assert_type(reference_id, 'reference_id', str)
        validation.assert_type(name, 'name', str)

        req = self._make_request(API.Command.Client2Api.UPDATE_DATALOGGING_ACQUISITION, {
            'reference_id': reference_id,
            'name': name
        })

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            pass
        future = self._send(req, callback)
        assert future is not None
        future.wait()

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(
                f"Failed to update the datalogging acquisition with reference ID: {reference_id}. {future.error_str}")

    def has_event_pending(self) -> bool:
        return not self._event_queue.empty()

    def read_event(self, timeout: Optional[float] = None) -> Optional[Events._ANY_EVENTS]:
        """
        Read an event from the event queue using a blocking read operation

        :param timeout: Maximum amount of time to block. Blocks indefinitely if ``None``

        :return: The next event in the queue or ``None`` if there is no events after timeout is expired

        """
        try:
            return self._event_queue.get(block=True, timeout=timeout)
        except queue.Empty:
            return None

    def clear_event_queue(self) -> None:
        """Delete all pending events inside the event queue"""
        while not self._event_queue.empty():
            try:
                self._event_queue.get_nowait()
            except queue.Empty:
                break

    def get_local_stats(self) -> Statistics:
        """Return internal performance metrics"""

        return self.Statistics(
            rx_data_rate=self._datarate_measurements.rx_data_rate.get_value(),
            rx_message_rate=self._datarate_measurements.rx_message_rate.get_value(),
            tx_data_rate=self._datarate_measurements.tx_data_rate.get_value(),
            tx_message_rate=self._datarate_measurements.tx_message_rate.get_value()
        )

    def reset_local_stats(self) -> None:
        """Reset all performance metrics that are resettable (have an internal state)"""
        self._datarate_measurements.reset()

    def get_server_stats(self, timeout: Optional[float] = None) -> sdk.ServerStatistics:
        if timeout is None:
            timeout = self._timeout

        req = self._make_request(API.Command.Client2Api.GET_SERVER_STATS)

        @dataclass
        class Container:
            obj: Optional[sdk.ServerStatistics]
        cb_data: Container = Container(obj=None)  # Force pass by ref

        def callback(state: CallbackState, response: Optional[api_typing.S2CMessage]) -> None:
            if response is not None and state == CallbackState.OK:
                cb_data.obj = api_parser.parser_server_stats(
                    cast(api_typing.S2C.GetServerStats, response)
                )
        future = self._send(req, callback)
        assert future is not None
        future.wait(timeout)

        if future.state != CallbackState.OK:
            raise sdk.exceptions.OperationFailure(
                f"Failed to read the server statistics. {future.error_str}")

        assert cb_data.obj is not None
        stats = cb_data.obj
        return stats

    @property
    def logger(self) -> logging.Logger:
        """The python logger used by the Client"""
        return self._logger

    @property
    def name(self) -> str:
        return '' if self._name is None else self.name

    @property
    def server_state(self) -> ServerState:
        """The server communication state"""
        with self._user_lock:
            return ServerState(self._server_state)  # Make a copy

    @property
    def hostname(self) -> Optional[str]:
        """Hostname of the server"""
        with self._user_lock:
            return str(self._hostname) if self._hostname is not None else None

    @property
    def port(self) -> Optional[int]:
        """Port of the the server is listening to"""
        with self._user_lock:
            return int(self._port) if self._port is not None else None
