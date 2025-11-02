#    API.py
#        Manages the TCP API to talk with the multiple clients. Can be a GUI client or a CLI
#        client
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = [
    'API',
    'APIConfig',
    'UpdateVarCallback',
    'TargetUpdateCallback',
    'InvalidRequestException'
]

import os
import enum
import logging
import traceback
import math
from dataclasses import dataclass
import functools
from uuid import uuid4
from fnmatch import fnmatch
import itertools
from base64 import b64encode, b64decode
import binascii
import threading
from datetime import datetime
from pathlib import Path
import tempfile
import shutil
import time

from scrutiny import tools
from scrutiny.tools import validation

from scrutiny.core.math_expr import parse_math_expr
from scrutiny.core.variable_factory import VariableFactory
from scrutiny.server.timebase import server_timebase
from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage
from scrutiny.server.datalogging.datalogging_manager import DataloggingManager
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.datastore_entry import DatastoreEntry
from scrutiny.server.device.device_handler import DeviceHandler, RawMemoryReadRequest, RawMemoryWriteRequest, UserCommandCallback
from scrutiny.server.active_sfd_handler import ActiveSFDHandler
from scrutiny.server.device.links import LinkConfig
from scrutiny.server.sfd_storage import SFDStorage
from scrutiny.core.basic_types import EmbeddedDataType, WatchableType
from scrutiny.core.firmware_description import FirmwareDescription
import scrutiny.server.datalogging.definitions.api as api_datalogging
import scrutiny.server.datalogging.definitions.device as device_datalogging
from scrutiny.server.device.device_info import ExecLoopType
from scrutiny.core.basic_types import MemoryRegion
import scrutiny.core.datalogging as core_datalogging
from scrutiny.core.typehints import EmptyDict

from scrutiny.server.api.tcp_client_handler import TCPClientHandler
from scrutiny.server.api.dummy_client_handler import DummyClientHandler
from scrutiny.server.api.value_streamer import ValueStreamer
from scrutiny.server.api.abstract_client_handler import AbstractClientHandler, ClientHandlerMessage
from scrutiny.server.device.links.abstract_link import LinkConfig as DeviceLinkConfig


import scrutiny.server.api.typing as api_typing
from scrutiny.tools.typing import *

if TYPE_CHECKING:
    from scrutiny.server.server import ScrutinyServer


class APIConfig(TypedDict, total=False):
    client_interface_type: str
    client_interface_config: Any


UpdateVarCallback = Callable[[str, DatastoreEntry], None]
TargetUpdateCallback = Callable[[str, DatastoreEntry], None]
EntryOrVarFactory: TypeAlias = Union[DatastoreEntry, VariableFactory]
EntryOrVarFactoryGenerator = Generator[Union[DatastoreEntry, VariableFactory], None, None]


class InvalidRequestException(Exception):
    def __init__(self, req: Any, msg: str) -> None:
        super().__init__(msg)
        self.req = req


def _check_request_dict(req: api_typing.C2SMessage, d: Any, name: str, types: Union[Type[Any], Iterable[Type[Any]]], prefix: str = '') -> None:
    try:
        validation.assert_dict_key(d, name, types, prefix)
    except Exception as e:
        raise InvalidRequestException(req, str(e)) from e


def _is_dict_with_key(d: Dict[Any, Any], k: Any) -> bool:
    return isinstance(d, dict) and k in d


class API:

    # List of commands that can be shared with the clients
    class Command:
        class Client2Api:
            ECHO = 'echo'
            GET_WATCHABLE_LIST = 'get_watchable_list'
            GET_WATCHABLE_COUNT = 'get_watchable_count'
            SUBSCRIBE_WATCHABLE = 'subscribe_watchable'
            UNSUBSCRIBE_WATCHABLE = 'unsubscribe_watchable'
            GET_INSTALLED_SFD = 'get_installed_sfd'
            GET_LOADED_SFD = 'get_loaded_sfd'
            UNINSTALL_SFD = 'uninstall_sfd'
            DOWNLOAD_SFD = 'download_sfd'
            UPLOAD_SFD_INIT = 'upload_sfd_init'
            UPLOAD_SFD_DATA = 'upload_sfd_data'
            LOAD_SFD = 'load_sfd'
            GET_SERVER_STATUS = 'get_server_status'
            GET_DEVICE_INFO = 'get_device_info'
            SET_LINK_CONFIG = "set_link_config"
            WRITE_WATCHABLE = "write_watchable"
            REQUEST_DATALOGGING_ACQUISITION = 'request_datalogging_acquisition'
            LIST_DATALOGGING_ACQUISITION = 'list_datalogging_acquisitions'
            READ_DATALOGGING_ACQUISITION_CONTENT = 'read_datalogging_acquisition_content'
            UPDATE_DATALOGGING_ACQUISITION = 'update_datalogging_acquisition'
            DELETE_DATALOGGING_ACQUISITION = 'delete_datalogging_acquisition'
            DELETE_ALL_DATALOGGING_ACQUISITION = 'delete_all_datalogging_acquisition'
            READ_MEMORY = "read_memory"
            WRITE_MEMORY = "write_memory"
            USER_COMMAND = "user_command"
            GET_SERVER_STATS = 'get_server_stats'
            DEBUG = 'debug'
            DEMO_MODE = 'demo_mode'

        class Api2Client:
            ECHO_RESPONSE = 'response_echo'
            WELCOME = 'welcome'
            GET_WATCHABLE_LIST_RESPONSE = 'response_get_watchable_list'
            GET_WATCHABLE_COUNT_RESPONSE = 'response_get_watchable_count'
            SUBSCRIBE_WATCHABLE_RESPONSE = 'response_subscribe_watchable'
            UNSUBSCRIBE_WATCHABLE_RESPONSE = 'response_unsubscribe_watchable'
            WATCHABLE_UPDATE = 'watchable_update'
            GET_INSTALLED_SFD_RESPONSE = 'response_get_installed_sfd'
            GET_LOADED_SFD_RESPONSE = 'response_get_loaded_sfd'
            UNINSTALL_SFD_RESPONSE = 'response_uninstall_sfd'
            DOWNLOAD_SFD_RESPONSE = 'response_download_sfd'
            UPLOAD_SFD_INIT_RESPONSE = 'response_upload_sfd_init'
            UPLOAD_SFD_DATA_RESPONSE = 'response_upload_sfd_data'
            SET_LINK_CONFIG_RESPONSE = 'response_set_link_config'
            INFORM_SERVER_STATUS = 'inform_server_status'
            GET_DEVICE_INFO = 'response_get_device_info'
            WRITE_WATCHABLE_RESPONSE = 'response_write_watchable'
            INFORM_WRITE_COMPLETION = 'inform_write_completion'
            INFORM_DATALOGGING_LIST_CHANGED = 'inform_datalogging_list_changed'
            LIST_DATALOGGING_ACQUISITION_RESPONSE = 'response_list_datalogging_acquisitions'
            REQUEST_DATALOGGING_ACQUISITION_RESPONSE = 'response_request_datalogging_acquisition'
            INFORM_DATALOGGING_ACQUISITION_COMPLETE = 'inform_datalogging_acquisition_complete'
            READ_DATALOGGING_ACQUISITION_CONTENT_RESPONSE = 'response_read_datalogging_acquisition_content'
            UPDATE_DATALOGGING_ACQUISITION_RESPONSE = 'response_update_datalogging_acquisition'
            DELETE_DATALOGGING_ACQUISITION_RESPONSE = 'response_delete_datalogging_acquisition'
            DELETE_ALL_DATALOGGING_ACQUISITION_RESPONSE = 'response_delete_all_datalogging_acquisition'
            READ_MEMORY_RESPONSE = "response_read_memory"
            INFORM_MEMORY_READ_COMPLETE = "inform_memory_read_complete"
            WRITE_MEMORY_RESPONSE = "response_write_memory"
            INFORM_MEMORY_WRITE_COMPLETE = "inform_memory_write_complete"
            USER_COMMAND_RESPONSE = "response_user_command"
            GET_SERVER_STATS = 'response_get_server_stats'
            DEMO_MODE_RESPONSE = 'response_demo_mode'
            ERROR_RESPONSE = 'error'

    @dataclass(slots=True)
    class SfdUploadState:
        expected_next_index: int
        upload_token: str
        total_size: int
        filepath: Path
        completed: bool

    @dataclass(frozen=True, slots=True)
    class Statistics:
        client_handler: AbstractClientHandler.Statistics
        invalid_request_count: int
        unexpected_error_count: int

    class DataloggingStateString:
        UNAVAILABLE: api_typing.DataloggingState = 'unavailable'
        STANDBY: api_typing.DataloggingState = 'standby'
        WAITING_FOR_TRIGGER: api_typing.DataloggingState = 'waiting_for_trigger'
        ACQUIRING: api_typing.DataloggingState = 'acquiring'
        DOWNLOADING: api_typing.DataloggingState = 'downloading'
        ERROR: api_typing.DataloggingState = 'error'

    class DeviceCommStatus:
        UNKNOWN: api_typing.DeviceCommStatus = 'unknown'
        DISCONNECTED: api_typing.DeviceCommStatus = 'disconnected'
        CONNECTING: api_typing.DeviceCommStatus = 'connecting'
        CONNECTED: api_typing.DeviceCommStatus = 'connected'
        CONNECTED_READY: api_typing.DeviceCommStatus = 'connected_ready'

    @dataclass(slots=True)
    class DataloggingSupportedTriggerCondition:
        condition_id: api_datalogging.TriggerConditionID
        nb_operands: int

    FLUSH_VARS_TIMEOUT: float = 0.1
    DATALOGGING_MAX_TIMEOUT: int = math.floor((2**32 - 1) * 1e-7)  # 100ns represented in sec
    DATALOGGING_MAX_HOLD_TIME: int = math.floor((2**32 - 1) * 1e-7)   # 100ns represented in sec
    SFD_MAX_UPLOAD_SIZE = 64 * 1024 * 1024
    TEMP_FILE_LIFETIME = 30
    TEMP_FILE_PRUNE_INTERVAL = 10

    DATATYPE_2_APISTR: Dict[EmbeddedDataType, api_typing.Datatype] = {
        EmbeddedDataType.sint8: 'sint8',
        EmbeddedDataType.sint16: 'sint16',
        EmbeddedDataType.sint32: 'sint32',
        EmbeddedDataType.sint64: 'sint64',
        EmbeddedDataType.sint128: 'sint128',
        EmbeddedDataType.sint256: 'sint256',
        EmbeddedDataType.uint8: 'uint8',
        EmbeddedDataType.uint16: 'uint16',
        EmbeddedDataType.uint32: 'uint32',
        EmbeddedDataType.uint64: 'uint64',
        EmbeddedDataType.uint128: 'uint128',
        EmbeddedDataType.uint256: 'uint256',
        EmbeddedDataType.float8: 'float8',
        EmbeddedDataType.float16: 'float16',
        EmbeddedDataType.float32: 'float32',
        EmbeddedDataType.float64: 'float64',
        EmbeddedDataType.float128: 'float128',
        EmbeddedDataType.float256: 'float256',
        EmbeddedDataType.cfloat8: 'cfloat8',
        EmbeddedDataType.cfloat16: 'cfloat16',
        EmbeddedDataType.cfloat32: 'cfloat32',
        EmbeddedDataType.cfloat64: 'cfloat64',
        EmbeddedDataType.cfloat128: 'cfloat128',
        EmbeddedDataType.cfloat256: 'cfloat256',
        EmbeddedDataType.boolean: 'boolean'
    }

    APISTR_2_DATATYPE: Dict[api_typing.Datatype, EmbeddedDataType] = {v: k for k, v in DATATYPE_2_APISTR.items()}

    DEVICE_CONN_STATUS_2_APISTR: Dict[DeviceHandler.ConnectionStatus, api_typing.DeviceCommStatus] = {
        DeviceHandler.ConnectionStatus.UNKNOWN: DeviceCommStatus.UNKNOWN,
        DeviceHandler.ConnectionStatus.DISCONNECTED: DeviceCommStatus.DISCONNECTED,
        DeviceHandler.ConnectionStatus.CONNECTING: DeviceCommStatus.CONNECTING,
        DeviceHandler.ConnectionStatus.CONNECTED_NOT_READY: DeviceCommStatus.CONNECTED,
        DeviceHandler.ConnectionStatus.CONNECTED_READY: DeviceCommStatus.CONNECTED_READY
    }

    APISTR_2_DEVICE_CONN_STATUS: Dict[api_typing.DeviceCommStatus, DeviceHandler.ConnectionStatus] = {
        v: k for k, v in DEVICE_CONN_STATUS_2_APISTR.items()}

    DATALOGGING_STATE_2_APISTR: Dict[api_datalogging.DataloggingState, api_typing.DataloggingState] = {
        api_datalogging.DataloggingState.NA: DataloggingStateString.UNAVAILABLE,
        api_datalogging.DataloggingState.Standby: DataloggingStateString.STANDBY,
        api_datalogging.DataloggingState.WaitForTrigger: DataloggingStateString.WAITING_FOR_TRIGGER,
        api_datalogging.DataloggingState.Acquiring: DataloggingStateString.ACQUIRING,
        api_datalogging.DataloggingState.Downloading: DataloggingStateString.DOWNLOADING,
        api_datalogging.DataloggingState.Error: DataloggingStateString.ERROR
    }

    APISTR_2_DATALOGGER_STATE: Dict[api_typing.DataloggingState, api_datalogging.DataloggingState] = {
        v: k for k, v in DATALOGGING_STATE_2_APISTR.items()}

    datalogging_supported_conditions: Dict[api_typing.DataloggingCondition, DataloggingSupportedTriggerCondition] = {
        'true': DataloggingSupportedTriggerCondition(condition_id=api_datalogging.TriggerConditionID.AlwaysTrue, nb_operands=0),
        'eq': DataloggingSupportedTriggerCondition(condition_id=api_datalogging.TriggerConditionID.Equal, nb_operands=2),
        'neq': DataloggingSupportedTriggerCondition(condition_id=api_datalogging.TriggerConditionID.NotEqual, nb_operands=2),
        'lt': DataloggingSupportedTriggerCondition(condition_id=api_datalogging.TriggerConditionID.LessThan, nb_operands=2),
        'let': DataloggingSupportedTriggerCondition(condition_id=api_datalogging.TriggerConditionID.LessOrEqualThan, nb_operands=2),
        'gt': DataloggingSupportedTriggerCondition(condition_id=api_datalogging.TriggerConditionID.GreaterThan, nb_operands=2),
        'get': DataloggingSupportedTriggerCondition(condition_id=api_datalogging.TriggerConditionID.GreaterOrEqualThan, nb_operands=2),
        'cmt': DataloggingSupportedTriggerCondition(condition_id=api_datalogging.TriggerConditionID.ChangeMoreThan, nb_operands=2),
        'within': DataloggingSupportedTriggerCondition(condition_id=api_datalogging.TriggerConditionID.IsWithin, nb_operands=3)
    }

    APISTR_2_WATCHABLE_TYPE: Dict[api_typing.WatchableType, WatchableType] = {
        'var': WatchableType.Variable,
        'alias': WatchableType.Alias,
        'rpv': WatchableType.RuntimePublishedValue
    }

    WATCHABLE_TYPE_2_APISTR: Dict[WatchableType, api_typing.WatchableType] = {v: k for k, v in APISTR_2_WATCHABLE_TYPE.items()}

    APISTR_2_DATALOGGING_ENCONDING: Dict[api_typing.DataloggingEncoding, device_datalogging.Encoding] = {
        'raw': device_datalogging.Encoding.RAW
    }

    DATALOGGING_ENCONDING_2_APISTR: Dict[device_datalogging.Encoding, api_typing.DataloggingEncoding] = {
        v: k for k, v in APISTR_2_DATALOGGING_ENCONDING.items()}

    APISTR_2_LOOP_TYPE: Dict[api_typing.LoopType, ExecLoopType] = {
        'fixed_freq': ExecLoopType.FIXED_FREQ,
        'variable_freq': ExecLoopType.VARIABLE_FREQ
    }

    LOOP_TYPE_2_APISTR: Dict[ExecLoopType, api_typing.LoopType] = {v: k for k, v in APISTR_2_LOOP_TYPE.items()}

    datastore: Datastore
    device_handler: DeviceHandler
    logger: logging.Logger
    connections: Set[str]
    streamer: ValueStreamer
    req_count: int
    client_handler: AbstractClientHandler
    sfd_handler: ActiveSFDHandler
    datalogging_manager: DataloggingManager
    handle_unexpected_errors: bool   # Always true, except during unit tests
    invalid_request_count: int
    unexpected_error_count: int
    temp_dir: "tempfile.TemporaryDirectory[str]"
    tempfile_timestamp_monotonic: Dict[str, float]
    last_tempfile_prune_timestamp_monotonic: float
    _sfd_upload_state: Dict[str, Dict[str, SfdUploadState]]

    def __init__(self,
                 config: APIConfig,
                 server: "ScrutinyServer",
                 enable_debug: bool = False,
                 rx_event: Optional[threading.Event] = None):
        self.validate_config(config)

        if config['client_interface_type'] == 'tcp':
            self.client_handler = TCPClientHandler(config['client_interface_config'], rx_event=rx_event)
        elif config['client_interface_type'] == 'dummy':
            self.client_handler = DummyClientHandler(config['client_interface_config'], rx_event=rx_event)
        else:
            raise NotImplementedError('Unsupported client interface type. %s', config['client_interface_type'])

        self.server = server
        self.datastore = self.server.datastore
        self.device_handler = self.server.device_handler
        self.sfd_handler = self.server.sfd_handler
        self.datalogging_manager = self.server.datalogging_manager
        self.logger = logging.getLogger('scrutiny.' + self.__class__.__name__)
        self.connections = set()            # Keep a list of all clients connections
        self.streamer = ValueStreamer()     # The value streamer takes cares of publishing values to the client without polling.
        self.req_count = 0
        self.handle_unexpected_errors = True
        self.invalid_request_count = 0
        self.unexpected_error_count = 0
        self.temp_dir = tempfile.TemporaryDirectory()
        self.tempfile_timestamp_monotonic = {}
        self.last_tempfile_prune_timestamp_monotonic = time.monotonic()
        self._sfd_upload_state = {}

        self.enable_debug = enable_debug

        # The method to call for each command
        self.ApiRequestCallbacks: Dict[str, Callable[[str, Any], None]] = {
            self.Command.Client2Api.ECHO: self.process_echo,
            self.Command.Client2Api.GET_WATCHABLE_LIST: self.process_get_watchable_list,
            self.Command.Client2Api.GET_WATCHABLE_COUNT: self.process_get_watchable_count,
            self.Command.Client2Api.SUBSCRIBE_WATCHABLE: self.process_subscribe_watchable,
            self.Command.Client2Api.UNSUBSCRIBE_WATCHABLE: self.process_unsubscribe_watchable,
            self.Command.Client2Api.GET_INSTALLED_SFD: self.process_get_installed_sfd,
            self.Command.Client2Api.UNINSTALL_SFD: self.process_uninstall_sfd,
            self.Command.Client2Api.LOAD_SFD: self.process_load_sfd,
            self.Command.Client2Api.GET_LOADED_SFD: self.process_get_loaded_sfd,
            self.Command.Client2Api.DOWNLOAD_SFD: self.process_download_sfd,
            self.Command.Client2Api.UPLOAD_SFD_INIT: self.process_upload_sfd_init,
            self.Command.Client2Api.UPLOAD_SFD_DATA: self.process_upload_sfd_data,
            self.Command.Client2Api.GET_SERVER_STATUS: self.process_get_server_status,
            self.Command.Client2Api.GET_DEVICE_INFO: self.process_get_device_info,
            self.Command.Client2Api.SET_LINK_CONFIG: self.process_set_link_config,
            self.Command.Client2Api.WRITE_WATCHABLE: self.process_write_value,
            self.Command.Client2Api.REQUEST_DATALOGGING_ACQUISITION: self.process_datalogging_request_acquisition,
            self.Command.Client2Api.LIST_DATALOGGING_ACQUISITION: self.process_list_datalogging_acquisition,
            self.Command.Client2Api.UPDATE_DATALOGGING_ACQUISITION: self.process_update_datalogging_acquisition,
            self.Command.Client2Api.DELETE_DATALOGGING_ACQUISITION: self.process_delete_datalogging_acquisition,
            self.Command.Client2Api.DELETE_ALL_DATALOGGING_ACQUISITION: self.process_delete_all_datalogging_acquisition,
            self.Command.Client2Api.READ_DATALOGGING_ACQUISITION_CONTENT: self.process_read_datalogging_acquisition_content,
            self.Command.Client2Api.READ_MEMORY: self.process_read_memory,
            self.Command.Client2Api.WRITE_MEMORY: self.process_write_memory,
            self.Command.Client2Api.USER_COMMAND: self.process_user_command,
            self.Command.Client2Api.GET_SERVER_STATS: self.process_server_stats,
            self.Command.Client2Api.DEMO_MODE: self.process_demo_mode
        }

        if enable_debug:
            import ipdb  # type: ignore
            API.Command.Client2Api.DEBUG = 'debug'
            self.ApiRequestCallbacks[API.Command.Client2Api.DEBUG] = self.process_debug

        self.sfd_handler.register_sfd_loaded_callback(self.sfd_loaded_callback)
        self.sfd_handler.register_sfd_unloaded_callback(self.sfd_unloaded_callback)
        self.device_handler.register_device_state_change_callback(self.device_state_changed_callback)
        self.datalogging_manager.register_datalogging_state_change_callback(self.datalogging_state_changed_callback)

    @classmethod
    def get_datatype_name(cls, datatype: EmbeddedDataType) -> api_typing.Datatype:
        if datatype not in cls.DATATYPE_2_APISTR:
            raise ValueError('Unknown datatype : %s' % (str(datatype)))

        return cls.DATATYPE_2_APISTR[datatype]

    @classmethod
    def get_watchable_type_name(cls, watchable_type: WatchableType) -> api_typing.WatchableType:
        if watchable_type not in cls.WATCHABLE_TYPE_2_APISTR:
            raise ValueError('Unknown watchable type : %s' % (str(watchable_type)))

        return cls.WATCHABLE_TYPE_2_APISTR[watchable_type]

    @classmethod
    def _make_sfd_info(cls, firmware_id: str) -> api_typing.SFDInfo:
        return {
            'firmware_id': firmware_id,
            'metadata': SFDStorage.get_metadata(firmware_id).to_dict(),
            'filesize': SFDStorage.get_filesize(firmware_id)
        }

    def sfd_loaded_callback(self, sfd: FirmwareDescription) -> None:
        # Called when a SFD is loaded after a device connection
        self.logger.debug("SFD Loaded callback called")
        self.send_server_status_to_all_clients()

    def sfd_unloaded_callback(self) -> None:
        # Called when a SFD is unloaded (device disconnected)
        self.logger.debug("SFD unloaded callback called")
        self.send_server_status_to_all_clients()

    def device_state_changed_callback(self, new_status: DeviceHandler.ConnectionStatus) -> None:
        """Called when the device state changes"""
        self.logger.debug("Device state change callback called")
        if new_status in [DeviceHandler.ConnectionStatus.DISCONNECTED, DeviceHandler.ConnectionStatus.CONNECTED_READY]:
            self.send_server_status_to_all_clients()

    def datalogging_state_changed_callback(self,
                                           datalogging_state: api_datalogging.DataloggingState,
                                           completion_ratio: Optional[float]) -> None:
        """Called when the datalogger state or completion ratio changes"""
        self.logger.debug("Datalogger state change callback called")
        self.send_server_status_to_all_clients()

    def get_client_handler(self) -> AbstractClientHandler:
        return self.client_handler

    def open_connection(self, conn_id: str) -> None:
        self.connections.add(conn_id)
        self.streamer.new_connection(conn_id)
        self.send_welcome_message(conn_id)

    def close_connection(self, conn_id: str) -> None:
        self.datastore.stop_watching_all(conn_id)   # Removes this connection as a watcher from all entries
        self.connections.remove(conn_id)
        self.streamer.clear_connection(conn_id)
        shutil.rmtree(os.path.join(self.temp_dir.name, conn_id), ignore_errors=True)
        with tools.SuppressException(KeyError):
            del self._sfd_upload_state[conn_id]

    def is_new_connection(self, conn_id: str) -> bool:
        # Tells if a connection ID is new (not known)
        return True if conn_id not in self.connections else False

    # Extract a chunk of data from the value streamer and send it to the clients.
    def stream_all_we_can(self) -> None:
        for conn_id in self.connections:
            chunk = self.streamer.get_stream_chunk(conn_id)     # get a list of entry to send to this connection

            if len(chunk) == 0:
                continue

            msg: api_typing.S2C.WatchableUpdate = {
                'cmd': self.Command.Api2Client.WATCHABLE_UPDATE,
                'reqid': None,
                'updates': [dict(id=x.get_id(), v=x.get_value(), t=x.get_value_change_server_time_us()) for x in chunk]
            }

            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=msg))

    def validate_config(self, config: APIConfig) -> None:
        if 'client_interface_type' not in config:
            raise ValueError('Missing entry in API config : client_interface_type ')

        if 'client_interface_config' not in config:
            raise ValueError('Missing entry in API config : client_interface_config')

    # Launch the client interface handler
    def start_listening(self) -> None:
        self.client_handler.start()

    # to be called periodically
    def process(self) -> None:
        self.client_handler.process()   # Get incoming requests

        while not self.client_handler.new_conn_queue.empty():
            conn_id = self.client_handler.new_conn_queue.get()
            if self.is_new_connection(conn_id):
                self.logger.debug('Opening connection %s' % conn_id)
                self.open_connection(conn_id)

        while self.client_handler.available():
            popped = self.client_handler.recv()
            if popped is None:
                self.logger.critical("Received an empty message, ignoring")
                continue
            conn_id = popped.conn_id
            obj = cast(api_typing.C2SMessage, popped.obj)
            self.process_request(conn_id, obj)

        # Close  dead connections
        conn_to_close = [conn_id for conn_id in self.connections if not self.client_handler.is_connection_active(conn_id)]
        for conn_id in conn_to_close:
            self.logger.debug('Closing connection %s' % conn_id)
            self.close_connection(conn_id)

        self.streamer.process()     # Decides which message needs to go out
        self.stream_all_we_can()    # Gives the message to the client handler
        self.client_handler.process()  # Give a chance to outgoing message to be written to output buffer

        if time.monotonic() - self.last_tempfile_prune_timestamp_monotonic > self.TEMP_FILE_PRUNE_INTERVAL:
            self.prune_temp_files()
            self.last_tempfile_prune_timestamp_monotonic = time.monotonic()

    # Process a request gotten from the Client Handler

    def process_request(self, conn_id: str, req: api_typing.C2SMessage) -> None:
        # Handle an incoming request from the client handler
        try:
            self.req_count += 1
            if self.logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
                self.logger.debug('[Conn:%s] Processing request #%d - %s' % (conn_id, self.req_count, req))

            _check_request_dict(req, req, 'cmd', str)

            cmd = req['cmd']

            # Fetch the right function from a global dict and call it
            # Response are sent in each callback. Not all requests requires a response
            if cmd in self.ApiRequestCallbacks:
                self.ApiRequestCallbacks[cmd](conn_id, req)
            else:
                raise InvalidRequestException(req, 'Unsupported command %s' % cmd)

        except InvalidRequestException as e:
            self.invalid_request_count += 1
            # Client sent a bad request. Controlled error
            if self.logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
                self.logger.debug('[Conn:%s] Invalid request #%d. %s' % (conn_id, self.req_count, str(e)))
            response = self.make_error_response(req, str(e))
            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))
        except Exception as e:
            # Unknown internal error
            if self.handle_unexpected_errors:
                self.unexpected_error_count += 1
                tools.log_exception(self.logger, e, f'[Conn:{conn_id}] Unexpected error while processing request #{self.req_count}.')
                response = self.make_error_response(req, 'Internal error')
                self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))
            else:
                raise e

    def process_debug(self, conn_id: str, req: Dict[Any, Any]) -> None:
        # Start ipdb tracing upon reception of a "debug" message (if enabled)
        if self.enable_debug:
            import ipdb
            ipdb.set_trace()

    # === ECHO ====
    def process_echo(self, conn_id: str, req: api_typing.C2S.Echo) -> None:
        _check_request_dict(req, req, 'payload', str)
        response: api_typing.S2C.Echo = {
            'cmd': self.Command.Api2Client.ECHO_RESPONSE,
            'reqid': self.get_req_id(req),
            'payload': req['payload']
        }
        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    # === WELCOME ====
    def send_welcome_message(self, conn_id: str) -> None:
        welcome: api_typing.S2C.Welcome = {
            'cmd': API.Command.Api2Client.WELCOME,
            'reqid': None,
            'server_time_zero_timestamp': server_timebase.get_zero_timestamp()
        }
        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=welcome))

    #  ===  GET_WATCHABLE_LIST     ===
    def process_get_watchable_list(self, conn_id: str, req: api_typing.C2S.GetWatchableList) -> None:
        # Improvement : This may be a big response. Generate multi-packet response in a worker thread
        # Not asynchronous by choice
        default_max_per_response = 1000
        max_per_response = default_max_per_response
        if 'max_per_response' in req:
            _check_request_dict(req, req, 'max_per_response', int)
            max_per_response = req['max_per_response']

        name_filters: Optional[List[str]] = None
        type_to_include: List[WatchableType] = []
        if _is_dict_with_key(cast(Dict[str, Any], req), 'filter'):
            if _is_dict_with_key(cast(Dict[str, Any], req['filter']), 'type'):
                if isinstance(req['filter']['type'], list):
                    for t in req['filter']['type']:
                        if t not in self.APISTR_2_WATCHABLE_TYPE:
                            raise InvalidRequestException(req, 'Unsupported type filter :"%s"' % (t))

                        type_to_include.append(self.APISTR_2_WATCHABLE_TYPE[t])

            if 'name' in req['filter']:
                if isinstance(req['filter']['name'], list):
                    for filt in req['filter']['name']:
                        if not isinstance(filt, str):
                            raise InvalidRequestException(req, "Invalid name filter")
                    name_filters = req['filter']['name']
                elif isinstance(req['filter']['name'], str):
                    name_filters = [req['filter']['name']]
                else:
                    raise InvalidRequestException(req, "Invalid name filter")

        if len(type_to_include) == 0:
            type_to_include = [WatchableType.Variable, WatchableType.Alias, WatchableType.RuntimePublishedValue]

        def filtered_generator(gen: EntryOrVarFactoryGenerator) -> EntryOrVarFactoryGenerator:
            if name_filters is None:
                yield from gen
            else:
                for element in gen:
                    for name_filter in name_filters:
                        if isinstance(element, DatastoreEntry):
                            if fnmatch(element.display_path, name_filter):
                                yield element
                                break   # Break the filter loop, next entry
                        elif isinstance(element, VariableFactory):
                            if fnmatch(element.get_access_name(), name_filter):
                                yield element
                                break   # Break the filter loop, next entry

        def empty_generator() -> Generator[DatastoreEntry, None, None]:
            yield from []

        class WatchableGroup(enum.Enum):
            RuntimePublishedValue = 'rpv'
            Alias = 'alias'
            Variable = 'var'
            VariableFactory = 'var_factory'

        # Sends RPV first, variable last
        priority = [WatchableGroup.RuntimePublishedValue, WatchableGroup.Alias, WatchableGroup.Variable, WatchableGroup.VariableFactory]
        generators: Dict[WatchableGroup, EntryOrVarFactoryGenerator] = {}

        for group_type in priority:
            gen: EntryOrVarFactoryGenerator
            if group_type == WatchableGroup.RuntimePublishedValue:
                gen = self.datastore.get_all_entries(
                    WatchableType.RuntimePublishedValue) if WatchableType.RuntimePublishedValue in type_to_include else empty_generator()
            elif group_type == WatchableGroup.Alias:
                gen = self.datastore.get_all_entries(WatchableType.Alias) if WatchableType.Alias in type_to_include else empty_generator()
            elif group_type == WatchableGroup.Variable:
                gen = self.datastore.get_all_entries(WatchableType.Variable) if WatchableType.Variable in type_to_include else empty_generator()
            elif group_type == WatchableGroup.VariableFactory:
                gen = self.datastore.get_all_variable_factory() if WatchableType.Variable in type_to_include else empty_generator()
            else:
                raise RuntimeError("Unsupported element group")

            generators[group_type] = filtered_generator(gen)

        done = False

        remainders: Dict[WatchableGroup, List[EntryOrVarFactory]] = {
            WatchableGroup.RuntimePublishedValue: [],
            WatchableGroup.Alias: [],
            WatchableGroup.Variable: [],
            WatchableGroup.VariableFactory: []
        }

        while not done:
            batch_count = 0
            batch_content: Dict[WatchableGroup, List[EntryOrVarFactory]] = {
                WatchableGroup.RuntimePublishedValue: [],
                WatchableGroup.Alias: [],
                WatchableGroup.Variable: [],
                WatchableGroup.VariableFactory: [],
            }

            stopiter_count = 0
            for group_type in priority:
                possible_remainder = max_per_response - batch_count
                batch_content[group_type] += remainders[group_type][0:possible_remainder]
                remainder_consumed = len(batch_content[group_type])
                remainders[group_type] = remainders[group_type][remainder_consumed:]
                batch_count += remainder_consumed

                slice_stop = max_per_response - batch_count
                the_slice = list(itertools.islice(generators[group_type], slice_stop))
                batch_content[group_type] += the_slice
                batch_count += len(the_slice)

                if len(remainders[group_type]) == 0:
                    try:
                        peek = next(generators[group_type])
                        remainders[group_type].append(peek)
                    except StopIteration:
                        stopiter_count += 1

            done = (stopiter_count == len(priority))

            response: api_typing.S2C.GetWatchableList = {
                'cmd': self.Command.Api2Client.GET_WATCHABLE_LIST_RESPONSE,
                'reqid': self.get_req_id(req),
                'qty': {
                    'var': len(batch_content[WatchableGroup.Variable]),
                    'alias': len(batch_content[WatchableGroup.Alias]),
                    'rpv': len(batch_content[WatchableGroup.RuntimePublishedValue]),
                    'var_factory': len(batch_content[WatchableGroup.VariableFactory])
                },
                'content': {
                    'var': [self.make_datastore_entry_definition(cast(DatastoreEntry, x), include_type=False) for x in batch_content[WatchableGroup.Variable]],
                    'alias': [self.make_datastore_entry_definition(cast(DatastoreEntry, x), include_type=False) for x in batch_content[WatchableGroup.Alias]],
                    'rpv': [self.make_datastore_entry_definition(cast(DatastoreEntry, x), include_type=False) for x in batch_content[WatchableGroup.RuntimePublishedValue]],
                    'var_factory': [self.make_variable_factory_definition(cast(VariableFactory, x), include_type=False) for x in batch_content[WatchableGroup.VariableFactory]],
                },
                'done': done
            }

            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  GET_WATCHABLE_COUNT ===
    def process_get_watchable_count(self, conn_id: str, req: api_typing.C2S.GetWatchableCount) -> None:
        # Returns the number of watchable per type
        response: api_typing.S2C.GetWatchableCount = {
            'cmd': self.Command.Api2Client.GET_WATCHABLE_COUNT_RESPONSE,
            'reqid': self.get_req_id(req),
            'qty': {
                'var': self.datastore.get_entries_count(WatchableType.Variable),
                'alias': self.datastore.get_entries_count(WatchableType.Alias),
                'rpv': self.datastore.get_entries_count(WatchableType.RuntimePublishedValue),
                'var_factory': self.datastore.get_var_factory_count()
            }
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  SUBSCRIBE_WATCHABLE ===
    def process_subscribe_watchable(self, conn_id: str, req: api_typing.C2S.SubscribeWatchable) -> None:
        # Add the connection ID to the list of watchers of given datastore entries.
        # datastore callback will write the new values in the API output queue (through the value streamer)
        _check_request_dict(req, req, 'watchables', list)

        # Check existence of all watchable before doing anything.
        subscribed: Dict[str, api_typing.DatastoreEntryDefinitionWithId] = {}
        for path in req['watchables']:
            entry: Optional[DatastoreEntry] = None
            try:
                entry = self.datastore.get_entry_by_display_path(path)  # Will raise an exception if not existent
            except KeyError as e:
                pass

            if entry is None:
                pass

            if entry is None:
                raise InvalidRequestException(req, 'Unknown watchable : %s' % str(path))

            entry_definition = cast(api_typing.DatastoreEntryDefinitionWithId, self.make_datastore_entry_definition(entry))
            entry_definition['id'] = entry.get_id()
            subscribed[path] = entry_definition

        for path in req['watchables']:
            self.datastore.start_watching(
                subscribed[path]['id'],
                watcher=conn_id,    # We use the API connection ID as datastore watcher ID
                value_change_callback=self.entry_value_change_callback
            )

        response: api_typing.S2C.SubscribeWatchable = {
            'cmd': self.Command.Api2Client.SUBSCRIBE_WATCHABLE_RESPONSE,
            'reqid': self.get_req_id(req),
            'subscribed': subscribed
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  UNSUBSCRIBE_WATCHABLE ===
    def process_unsubscribe_watchable(self, conn_id: str, req: api_typing.C2S.UnsubscribeWatchable) -> None:
        # Unsubscribe client from value update of the given datastore entries
        _check_request_dict(req, req, 'watchables', list)

        # Check existence of all entries before doing anything
        for path in req['watchables']:
            try:
                self.datastore.get_entry_by_display_path(path)  # Will raise an exception if not existent
            except KeyError as e:
                raise InvalidRequestException(req, 'Unknown watchable : %s' % str(path))

        for path in req['watchables']:
            entry = self.datastore.get_entry_by_display_path(path)
            self.datastore.stop_watching(entry, watcher=conn_id)

        response: api_typing.S2C.UnsubscribeWatchable = {
            'cmd': self.Command.Api2Client.SUBSCRIBE_WATCHABLE_RESPONSE,
            'reqid': self.get_req_id(req),
            'unsubscribed': req['watchables']
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  GET_INSTALLED_SFD ===
    def process_get_installed_sfd(self, conn_id: str, req: api_typing.C2S.GetInstalledSFD) -> None:
        # Request to know the list of installed Scrutiny Firmware Description on this server
        firmware_id_list = SFDStorage.list()
        info_list: List[api_typing.SFDInfo] = []
        for firmware_id in firmware_id_list:
            info_list.append(self._make_sfd_info(firmware_id))

        response: api_typing.S2C.GetInstalledSFD = {
            'cmd': self.Command.Api2Client.GET_INSTALLED_SFD_RESPONSE,
            'reqid': self.get_req_id(req),
            'sfd_list': info_list
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  UNINSTALL_SFD ===
    def process_uninstall_sfd(self, conn_id: str, req: api_typing.C2S.UninstallSFD) -> None:
        _check_request_dict(req, req, 'firmware_id_list', list)

        for firmware_id in req['firmware_id_list']:
            if not isinstance(firmware_id, str):
                raise InvalidRequestException(req, "Given firmware_id must be a string")

            if not SFDStorage.is_valid_firmware_id(firmware_id):
                raise InvalidRequestException(req, "Given firmware_id does not have the correct format. Expecting a 128bits hex string")

            if not SFDStorage.is_installed(firmware_id):
                raise InvalidRequestException(req, f"Firmware ID {firmware_id} is not installed")

        for firmware_id in req['firmware_id_list']:
            SFDStorage.uninstall(firmware_id)

        response: api_typing.S2C.UninstallSFD = {
            'cmd': self.Command.Api2Client.UNINSTALL_SFD_RESPONSE,
            'reqid': self.get_req_id(req)
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  GET_LOADED_SFD ===
    def process_get_loaded_sfd(self, conn_id: str, req: api_typing.C2S.GetLoadedSFD) -> None:
        # Request to get the actively loaded Scrutiny Firmware Description. Loaded by the SFD Handler
        # upon connection with a known device
        sfd = self.sfd_handler.get_loaded_sfd()

        loaded_sfd_info: Optional[api_typing.SFDInfo] = None
        if sfd is not None:
            filesize: Optional[int] = None
            with tools.SuppressException(Exception):
                filesize = SFDStorage.get_filesize(sfd.get_firmware_id_ascii())

            loaded_sfd_info = {
                'firmware_id': sfd.get_firmware_id_ascii(),
                'metadata': sfd.metadata.to_dict(),
                'filesize': filesize
            }

        response: api_typing.S2C.GetLoadedSFD = {
            'cmd': self.Command.Api2Client.GET_LOADED_SFD_RESPONSE,
            'reqid': self.get_req_id(req),
            'sfd': loaded_sfd_info
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  LOAD_SFD ===
    def process_load_sfd(self, conn_id: str, req: api_typing.C2S.LoadSFD) -> None:
        # Forcibly load a Scrutiny Firmware Description through API
        _check_request_dict(req, req, 'firmware_id', str)

        try:
            self.sfd_handler.request_load_sfd(req['firmware_id'])
        except Exception as e:
            self.logger.error('Cannot load SFD %s. %s' % (req['firmware_id'], str(e)))
        # Do not send a response. There's a callback on SFD Loading that will notify everyone once completed.

    # === DOWNLOAD_SFD ===
    def process_download_sfd(self, conn_id: str, req: api_typing.C2S.DownloadSFD) -> None:
        _check_request_dict(req, req, 'firmware_id', str)

        firmware_id = req['firmware_id']
        if not SFDStorage.is_installed(firmware_id):
            raise InvalidRequestException(req, f"No firmware with ID {firmware_id}")

        file = SFDStorage.get_file_location(firmware_id)

        if not os.path.isfile(file):    # not supposed to happen ever.
            raise FileNotFoundError("Requested SFD file is missing")

        file_stat = os.stat(file)
        filesize = file_stat.st_size
        chunk_size = TCPClientHandler.STREAM_MTU // 2 - 256

        if 'max_chunk_size' in req:
            if not isinstance(req['max_chunk_size'], int):
                raise InvalidRequestException(req, "Invalid max_chunk_size")

            if req['max_chunk_size'] <= 0:
                raise InvalidRequestException(req, "Invalid max_chunk_size")

            chunk_size = min(chunk_size, req['max_chunk_size'])

        if chunk_size <= 0:
            raise ValueError("Internal Error. Bad chunk size")
        chunk_size = 100

        if filesize == 0:
            raise InvalidRequestException(req, "SFD file is invalid")

        req_id = self.get_req_id(req)

        max_chunk_count = getattr(self, '_UNITTEST_DOWNLOAD_SFD_MAX_CHUNK_COUNT', 0)

        tmp = tempfile.TemporaryFile()

        def send_task() -> None:
            try:
                with tools.TemporaryFileCopy(file) as tmp_filename:
                    with open(tmp_filename, 'rb') as f:
                        index = 0
                        while self.client_handler.is_connection_active(conn_id):
                            chunk_data = f.read(chunk_size)
                            if len(chunk_data) == 0:
                                break

                            if max_chunk_count != 0 and index >= max_chunk_count:
                                continue

                            msg: api_typing.S2C.DownloadSFD = {
                                'cmd': self.Command.Api2Client.DOWNLOAD_SFD_RESPONSE,
                                'reqid': req_id,
                                'firmware_id': firmware_id,
                                'total_size': filesize,
                                'file_chunk': {
                                    'chunk_index': index,
                                    'data': b64encode(chunk_data).decode('ascii')
                                }
                            }

                            index += 1

                            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=msg))
            except Exception as e:
                tools.log_exception(self.logger, e, "Failed to send the SFD content")
                self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=self.make_error_response(req, str(e))))

        threading.Thread(target=send_task, daemon=True).start()

    # === UPLOAD_SFD_INIT ===
    def process_upload_sfd_init(self, conn_id: str, req: api_typing.C2S.UploadSFDInit) -> None:
        reqid = self.get_req_id(req)
        if reqid is None:
            raise InvalidRequestException(req, "Missing request ID")
        _check_request_dict(req, req, 'firmware_id', str)
        _check_request_dict(req, req, 'total_size', int)

        if req['total_size'] < 0:
            raise InvalidRequestException(req, "Invalid total_size")

        if not SFDStorage.is_valid_firmware_id(req['firmware_id']):
            raise InvalidRequestException(req, "Invalid firmware ID")

        if req['total_size'] > self.SFD_MAX_UPLOAD_SIZE:
            raise InvalidRequestException(req, f"Size too big. Max={self.SFD_MAX_UPLOAD_SIZE}")

        upload_token = uuid4().hex
        if conn_id not in self._sfd_upload_state:
            self._sfd_upload_state[conn_id] = {}

        filepath = self._get_temp_filepath(conn_id, upload_token)
        if os.path.isfile(filepath):    # pragma: no cover
            # Should not happen. The filename is a uuid
            self.logger.error(f"Duplicate file {filepath}")
            raise RuntimeError("Duplicate file")
        self.logger.debug(f"Created file : {filepath}")
        self.create_temp_file(filepath)
        self._sfd_upload_state[conn_id][upload_token] = self.SfdUploadState(
            expected_next_index=0,
            upload_token=upload_token,
            total_size=req['total_size'],
            filepath=filepath,
            completed=False
        )

        msg: api_typing.S2C.UploadSFDInit = {
            'cmd': self.Command.Api2Client.UPLOAD_SFD_INIT_RESPONSE,
            'reqid': self.get_req_id(req),
            'token': upload_token,
            'will_overwrite': SFDStorage.is_installed(req['firmware_id'])
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=msg))

    # === UPLOAD_SFD_INIT ===

    def process_upload_sfd_data(self, conn_id: str, req: api_typing.C2S.UploadSFDData) -> None:
        reqid = self.get_req_id(req)
        if reqid is None:
            raise InvalidRequestException(req, "Missing request ID")
        _check_request_dict(req, req, 'token', str)

        upload_token = req['token']
        try:
            upload_status = self._sfd_upload_state[conn_id][upload_token]
        except KeyError:
            raise InvalidRequestException(req, "Unknown token")

        filepath = upload_status.filepath

        def raise_invalid_request(error: str) -> NoReturn:
            try:
                del self._sfd_upload_state[conn_id][upload_token]
            except KeyError as e:
                tools.log_exception(self.logger, e, f"Failed to delete upload state struct for conn: {conn_id}")

            try:
                if os.path.isfile(filepath):
                    os.remove(filepath)
                    self.logger.debug(f"Deleted {filepath}")
            except OSError as e:    # pragma: no cover
                tools.log_exception(self.logger, e, "Failed to delete temp file")
            raise InvalidRequestException(req, error)

        try:
            _check_request_dict(req, req, 'file_chunk.data', str)
            _check_request_dict(req, req, 'file_chunk.chunk_index', int)
        except Exception as e:
            raise_invalid_request(str(e))

        chunk_index = req['file_chunk']['chunk_index']

        if upload_status.expected_next_index != chunk_index:
            raise_invalid_request(f'Unexpected chunk_index. Expected {upload_status.expected_next_index}')

        filestat = os.stat(filepath)
        actual_size = filestat.st_size

        try:
            data_chunk = b64decode(req['file_chunk']['data'], validate=True)
        except binascii.Error:
            raise_invalid_request("Invalid base64 data chunk")

        new_size = actual_size + len(data_chunk)
        if new_size > self.SFD_MAX_UPLOAD_SIZE:
            raise_invalid_request(f"Total size too big. Max size = {self.SFD_MAX_UPLOAD_SIZE}")

        if new_size > upload_status.total_size:
            raise_invalid_request("Size mismatch. Received more data than total_size")

        with open(filepath, 'ab') as f:
            f.write(data_chunk)

        self._update_tempfile_timestamp(filepath)

        sfd_info: Optional[api_typing.SFDInfo] = None
        if new_size == upload_status.total_size:
            sfd = SFDStorage.install(str(filepath), ignore_exist=True)
            sfd_info = self._make_sfd_info(sfd.get_firmware_id_ascii())
            upload_status.completed = True

            with tools.LogException(self.logger, OSError, "Failed to delete uploaded SFD"):
                os.remove(filepath)

            with tools.LogException(self.logger, KeyError, "Failed to delete the SFD upload status structure"):
                del self._sfd_upload_state[conn_id][upload_token]

        upload_status.expected_next_index += 1
        msg: api_typing.S2C.UploadSFDData = {
            'cmd': self.Command.Api2Client.UPLOAD_SFD_DATA_RESPONSE,
            'reqid': self.get_req_id(req),
            'completed': upload_status.completed,
            'actual_size': new_size,
            'sfd_info': sfd_info
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=msg))

    #  ===  GET_SERVER_STATUS ===

    def process_get_server_status(self, conn_id: str, req: api_typing.C2S.GetServerStatus) -> None:
        # Request the server status.
        obj = self.craft_inform_server_status(reqid=self.get_req_id(req))
        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=obj))

    #  ===  GET_DEVICE_INFO ===
    def process_get_device_info(self, conn_id: str, req: api_typing.C2S.GetDeviceInfo) -> None:
        device_info_input = self.device_handler.get_device_info()
        session_id = self.device_handler.get_comm_session_id()

        def make_memory_region_map(regions: Optional[List[MemoryRegion]]) -> List[Dict[Literal['start', 'end', 'size'], int]]:
            output: List[Dict[Literal['start', 'end', 'size'], int]] = []
            if regions is not None:
                for region in regions:
                    output.append({'start': region.start, 'end': region.end, 'size': region.size})
            return output

        def make_datalogging_capabilities(
                dl_setup: Optional[device_datalogging.DataloggingSetup],
                sampling_rates: List[api_datalogging.SamplingRate]
        ) -> Optional[api_typing.DataloggingCapabilities]:

            if dl_setup is None or sampling_rates is None:
                return None

            assert sampling_rates is not None

            output_sampling_rates: List[api_typing.SamplingRate] = []
            for rate in sampling_rates:
                output_sampling_rates.append({
                    'identifier': rate.device_identifier,
                    'name': rate.name,
                    'frequency': rate.frequency,
                    'type': self.LOOP_TYPE_2_APISTR[rate.rate_type]
                })

            return {
                'buffer_size': dl_setup.buffer_size,
                'encoding': self.DATALOGGING_ENCONDING_2_APISTR[dl_setup.encoding],
                'max_nb_signal': dl_setup.max_signal_count,
                'sampling_rates': output_sampling_rates
            }

        device_info_output: Optional[api_typing.DeviceInfo] = None
        if device_info_input is not None and device_info_input.all_ready():
            assert session_id is not None  # If we have data, we have a session
            max_bitrate_bps: Optional[int] = None
            if device_info_input.max_bitrate_bps is not None and device_info_input.max_bitrate_bps > 0:
                max_bitrate_bps = device_info_input.max_bitrate_bps
            device_info_output = {
                'session_id': session_id,
                'device_id': cast(str, device_info_input.device_id),
                'display_name': cast(str, device_info_input.display_name),
                'max_tx_data_size': cast(int, device_info_input.max_tx_data_size),
                'max_rx_data_size': cast(int, device_info_input.max_rx_data_size),
                'max_bitrate_bps': max_bitrate_bps,
                'rx_timeout_us': cast(int, device_info_input.rx_timeout_us),
                'heartbeat_timeout_us': cast(int, device_info_input.heartbeat_timeout_us),
                'address_size_bits': cast(int, device_info_input.address_size_bits),
                'protocol_major': cast(int, device_info_input.protocol_major),
                'protocol_minor': cast(int, device_info_input.protocol_minor),
                'supported_feature_map': cast(Dict[api_typing.SupportedFeature, bool], device_info_input.supported_feature_map),
                'forbidden_memory_regions': make_memory_region_map(device_info_input.forbidden_memory_regions),
                'readonly_memory_regions': make_memory_region_map(device_info_input.readonly_memory_regions),
                'datalogging_capabilities': make_datalogging_capabilities(  # Capabilities = setup + sampling rate (loops)
                    device_info_input.datalogging_setup,
                    self.datalogging_manager.get_available_sampling_rates()
                )
            }

        response: api_typing.S2C.GetDeviceInfo = {
            'cmd': self.Command.Api2Client.GET_DEVICE_INFO,
            'reqid': self.get_req_id(req),
            'available': True if device_info_output is not None else False,
            'device_info': device_info_output
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    #  ===  SET_LINK_CONFIG ===
    def process_set_link_config(self, conn_id: str, req: api_typing.C2S.SetLinkConfig) -> None:
        # With this request, the user can change the device connection through an API call
        _check_request_dict(req, req, 'link_type', str)
        _check_request_dict(req, req, 'link_config', dict)

        link_config_err: Optional[Exception] = None
        try:
            self.device_handler.validate_link_config(req['link_type'], cast(DeviceLinkConfig, req['link_config']))
        except Exception as e:
            link_config_err = e

        if link_config_err:
            raise InvalidRequestException(req, "Link configuration is not good for given link type. " + str(link_config_err))

        self.device_handler.configure_comm(req['link_type'], cast(LinkConfig, req['link_config']))
        response: api_typing.S2C.Empty = {
            'cmd': self.Command.Api2Client.SET_LINK_CONFIG_RESPONSE,
            'reqid': self.get_req_id(req)
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

        self.send_server_status_to_all_clients()

    #  ===  WRITE_WATCHABLE ===
    def process_write_value(self, conn_id: str, req: api_typing.C2S.WriteValue) -> None:
        # We first fetch the entries as it will raise an exception if the ID does not exist
        # We don't want to trigger a write if an entry is bad in the request
        #
        # Important to consider that we can get a batch with multiple write to the same entry,
        # and they need to be reported correctly + written in the correct order.
        _check_request_dict(req, req, 'updates', list)

        for update in req['updates']:
            _check_request_dict(req, update, 'batch_index', int)
            _check_request_dict(req, update, 'watchable', str)

            if 'value' not in update:
                raise InvalidRequestException(req, 'Missing "value" field')

            value = update['value']
            if isinstance(value, str):
                valstr = value.lower().strip()
                if valstr == "true":
                    value = True
                elif valstr == "false":
                    value = False
                else:
                    try:
                        value = parse_math_expr(valstr)
                    except Exception:
                        value = None
            if value is None or not isinstance(value, (int, float, bool)):
                raise InvalidRequestException(req, 'Invalid value')
            if not math.isfinite(value):
                raise InvalidRequestException(req, 'Invalid value')
            update['value'] = value

            try:
                entry = self.datastore.get_entry(update['watchable'])
            except KeyError:
                raise InvalidRequestException(req, 'Unknown watchable ID %s' % update['watchable'])

            if not self.datastore.is_watching(entry, conn_id):
                raise InvalidRequestException(req, 'Cannot update entry %s without being subscribed to it' % entry.get_id())

        if len(set(update['batch_index'] for update in req['updates'])) != len(req['updates']):
            raise InvalidRequestException(req, "Duplicate batch_index in request")

        request_token = uuid4().hex
        for update in req['updates']:
            callback = functools.partial(self.entry_target_update_callback, request_token, update['batch_index'])
            self.datastore.update_target_value(update['watchable'], update['value'], callback=callback)

        response: api_typing.S2C.WriteValue = {
            'cmd': self.Command.Api2Client.WRITE_WATCHABLE_RESPONSE,
            'reqid': self.get_req_id(req),
            'request_token': request_token,
            'count': len(req['updates'])
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    def process_read_memory(self, conn_id: str, req: api_typing.C2S.ReadMemory) -> None:

        _check_request_dict(req, req, 'address', int)
        _check_request_dict(req, req, 'size', int)

        if req['address'] < 0:
            raise InvalidRequestException(req, '"address" field is not valid')

        if req['size'] <= 0:
            raise InvalidRequestException(req, '"size" field is not valid')

        request_token = uuid4().hex
        closure_data = dict(request_token=request_token, conn_id=conn_id)

        def callback(request: RawMemoryReadRequest, success: bool, completion_server_time_us: float, data: Optional[bytes], error: str) -> None:
            self.read_raw_memory_callback(request, success, completion_server_time_us, data, error, **closure_data)

        self.device_handler.read_memory(req['address'], req['size'], callback=callback)

        response: api_typing.S2C.ReadMemory = {
            'cmd': self.Command.Api2Client.READ_MEMORY_RESPONSE,
            'reqid': self.get_req_id(req),
            'request_token': request_token
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    def process_write_memory(self, conn_id: str, req: api_typing.C2S.WriteMemory) -> None:
        _check_request_dict(req, req, 'address', int)
        _check_request_dict(req, req, 'data', str)

        try:
            data = b64decode(req['data'], validate=True)
        except binascii.Error:
            raise InvalidRequestException(req, '"data" field is not a valid base64 string')

        if req['address'] < 0:
            raise InvalidRequestException(req, '"address" field is not valid')

        if len(data) <= 0:
            raise InvalidRequestException(req, '"data" field is not valid')

        request_token = uuid4().hex
        closure_data = dict(request_token=request_token, conn_id=conn_id)

        def callback(request: RawMemoryWriteRequest, success: bool, completion_server_time_us: float, error: str) -> None:
            self.write_raw_memory_callback(request, success, completion_server_time_us, error, **closure_data)

        self.device_handler.write_memory(req['address'], data, callback=callback)

        response: api_typing.S2C.WriteMemory = {
            'cmd': self.Command.Api2Client.WRITE_MEMORY_RESPONSE,
            'reqid': self.get_req_id(req),
            'request_token': request_token
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    def process_user_command(self, conn_id: str, req: api_typing.C2S.UserCommand) -> None:
        _check_request_dict(req, req, 'subfunction', int)

        if req['subfunction'] < 0 or req['subfunction'] > 0xFF:
            raise InvalidRequestException(req, "Invalid subfunction")

        data = bytes()
        if 'data' in req:
            _check_request_dict(req, req, 'data', str)

            try:
                data = b64decode(req['data'], validate=True)
            except binascii.Error:
                raise InvalidRequestException(req, '"data" field is not a valid base64 string')

        callback = cast(UserCommandCallback, functools.partial(self.user_command_callback, req, conn_id))
        self.device_handler.request_user_command(req['subfunction'], data, callback)

    def user_command_callback(self, req: api_typing.C2S.UserCommand, conn_id: str, success: bool, subfunction: int, data: Optional[bytes], error: Optional[str]) -> None:
        if success:
            assert data is not None
            response: api_typing.S2C.UserCommand = {
                'cmd': self.Command.Api2Client.USER_COMMAND_RESPONSE,
                'reqid': self.get_req_id(req),
                'subfunction': subfunction,
                'data': b64encode(data).decode('utf8')
            }
            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))
        else:
            assert error is not None
            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=self.make_error_response(req, error)))

    def read_raw_memory_callback(self,
                                 request: RawMemoryReadRequest,
                                 success: bool,
                                 completion_server_time_us: float,
                                 data: Optional[bytes],
                                 error: str,
                                 conn_id: str,
                                 request_token: str
                                 ) -> None:
        data_out: Optional[str] = None
        if data is not None and success:
            data_out = b64encode(data).decode('ascii')

        response: api_typing.S2C.ReadMemoryComplete = {
            'cmd': self.Command.Api2Client.INFORM_MEMORY_READ_COMPLETE,
            'reqid': None,
            'request_token': request_token,
            'success': success,
            'data': data_out,
            'detail_msg': error if success == False else None,
            'completion_server_time_us': completion_server_time_us
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    def write_raw_memory_callback(self,
                                  request: RawMemoryWriteRequest,
                                  success: bool,
                                  completion_server_time_us: float,
                                  error: str,
                                  conn_id: str,
                                  request_token: str
                                  ) -> None:
        response: api_typing.S2C.WriteMemoryComplete = {
            'cmd': self.Command.Api2Client.INFORM_MEMORY_WRITE_COMPLETE,
            'reqid': None,
            'request_token': request_token,
            'success': success,
            'completion_server_time_us': completion_server_time_us,
            'detail_msg': error if success == False else None,
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    # === DATALOGGING_REQUEST_ACQUISITION ==

    def process_datalogging_request_acquisition(self, conn_id: str, req: api_typing.C2S.RequestDataloggingAcquisition) -> None:
        if not self.datalogging_manager.is_ready_for_request():
            raise InvalidRequestException(req, 'Device is not ready to receive a request')

        FieldType = Literal['yaxes', 'sampling_rate_id', 'decimation', 'timeout', 'trigger_hold_time',
                            'probe_location', 'condition', 'operands', 'signals', 'x_axis_type']

        required_fileds: Dict[FieldType, Type[Any]] = {
            'yaxes': list,
            'sampling_rate_id': int,
            'decimation': int,
            'timeout': float,
            'trigger_hold_time': float,
            'probe_location': float,
            'condition': str,
            'operands': list,
            'signals': list,
            'x_axis_type': str
        }

        field: FieldType
        for field in required_fileds:
            if field not in req:
                raise InvalidRequestException(req, "Missing field %s in request" % field)

            expected_type = required_fileds[field]
            if expected_type is float and isinstance(req[field], int):
                req[field] = float(req[field])  # type:ignore

            if expected_type is int and isinstance(req[field], float):
                assert isinstance(req[field], float)
                if int(req[field]) - req[field] != 0:   # type:ignore
                    raise InvalidRequestException(req, 'Field %s must be an integer' % field)
                req[field] = int(req[field])    # type:ignore

            if not isinstance(req[field], expected_type):
                raise InvalidRequestException(req, "Invalid field %s" % field)

        if not self.datalogging_manager.is_valid_sample_rate_id(req['sampling_rate_id']):
            raise InvalidRequestException(req, "Given sampling_rate_id is not supported for this device.")

        sampling_rate = self.datalogging_manager.get_sampling_rate(req['sampling_rate_id'])

        if req['decimation'] <= 0:
            raise InvalidRequestException(req, 'decimation must be a positive integer')

        if req['timeout'] < 0:
            raise InvalidRequestException(req, 'timeout must be a positive value or zero')

        if req['timeout'] > self.DATALOGGING_MAX_TIMEOUT:
            raise InvalidRequestException(req, 'timeout must be smaller than %ds' % int(self.DATALOGGING_MAX_TIMEOUT))

        if req['trigger_hold_time'] < 0:
            raise InvalidRequestException(req, 'trigger_hold_time must be a positive value or zero')

        if req['trigger_hold_time'] > self.DATALOGGING_MAX_HOLD_TIME:
            raise InvalidRequestException(req, 'trigger_hold_time must be a smaller than %ds' % int(self.DATALOGGING_MAX_HOLD_TIME))

        if req['probe_location'] < 0 or req['probe_location'] > 1:
            raise InvalidRequestException(req, 'probe_location must be a value between 0 and 1')

        if req['condition'] not in self.datalogging_supported_conditions.keys():
            raise InvalidRequestException(req, 'Unknown trigger condition %s')

        if len(req['operands']) != self.datalogging_supported_conditions[req['condition']].nb_operands:
            raise InvalidRequestException(req, 'Bad number of condition operands for condition %s' % req['condition'])

        axis_type_map = {
            "index": api_datalogging.XAxisType.Indexed,
            'ideal_time': api_datalogging.XAxisType.IdealTime,
            'measured_time': api_datalogging.XAxisType.MeasuredTime,
            'signal': api_datalogging.XAxisType.Signal
        }

        if req['x_axis_type'] not in axis_type_map:
            raise InvalidRequestException(req, 'Unsupported X Axis type')
        x_axis_type = axis_type_map[req['x_axis_type']]
        x_axis_entry: Optional[DatastoreEntry] = None
        x_axis_signal: Optional[api_datalogging.SignalDefinition] = None
        if x_axis_type == api_datalogging.XAxisType.Signal:

            if 'x_axis_signal' not in req or not isinstance(req['x_axis_signal'], dict):
                raise InvalidRequestException(req, 'Missing a valid x_axis_signal required when x_axis_type=watchable')

            if 'path' not in req['x_axis_signal']:
                raise InvalidRequestException(req, 'Missing x_axis_signal.path field')

            if not isinstance(req['x_axis_signal']['path'], str):
                raise InvalidRequestException(req, 'Invalid x_axis_signal.path field')

            with tools.SuppressException():
                x_axis_entry = self.datastore.get_entry_by_display_path(req['x_axis_signal']['path'])

            if x_axis_entry is None:
                raise InvalidRequestException(req, 'Cannot find watchable with given path %s' % req['x_axis_signal']['path'])

            x_axis_signal = api_datalogging.SignalDefinition(
                name=None if 'name' not in req['x_axis_signal'] else str(req['x_axis_signal']['name']),
                entry=x_axis_entry,
            )
        elif x_axis_type == api_datalogging.XAxisType.IdealTime:
            if sampling_rate.rate_type == ExecLoopType.VARIABLE_FREQ:
                raise InvalidRequestException(req, 'Cannot use ideal time on variable frequency rate')

        operands: List[api_datalogging.TriggerConditionOperand] = []

        for given_operand in req['operands']:
            if given_operand['type'] == 'literal':
                if not isinstance(given_operand['value'], (int, float, bool)):
                    raise InvalidRequestException(req, "Unsupported datatype for operand")

                operands.append(api_datalogging.TriggerConditionOperand(api_datalogging.TriggerConditionOperandType.LITERAL, given_operand['value']))
            elif given_operand['type'] == 'watchable':
                if not isinstance(given_operand['value'], str):
                    raise InvalidRequestException(req, "Unsupported datatype for operand")
                watchable: Optional[DatastoreEntry] = None
                with tools.SuppressException():
                    watchable = self.datastore.get_entry_by_display_path(given_operand['value'])

                if watchable is None:
                    raise InvalidRequestException(req, "Cannot find watchable with given path %s" % given_operand['value'])

                operands.append(api_datalogging.TriggerConditionOperand(api_datalogging.TriggerConditionOperandType.WATCHABLE, watchable))
            else:
                raise InvalidRequestException(req, 'Unknown operand type')

        signals_to_log: List[api_datalogging.SignalDefinitionWithAxis] = []
        if len(req['signals']) == 0:
            raise InvalidRequestException(req, 'Missing watchable to log')

        if not isinstance(req['yaxes'], list):
            raise InvalidRequestException(req, "Invalid Y-Axis list")

        yaxis_map: Dict[int, api_datalogging.AxisDefinition] = {}
        for yaxis in req['yaxes']:
            _check_request_dict(req, yaxis, 'name', str)
            _check_request_dict(req, yaxis, 'id', int)

            if (yaxis['id'] in yaxis_map):
                raise InvalidRequestException(req, "Duplicate Y-Axis ID")

            yaxis_map[yaxis['id']] = api_datalogging.AxisDefinition(name=yaxis['name'], axis_id=yaxis['id'])

        for signal_def in req['signals']:
            _check_request_dict(req, signal_def, 'path', str)
            signal_entry: Optional[DatastoreEntry] = None

            with tools.SuppressException():
                signal_entry = self.datastore.get_entry_by_display_path(signal_def['path'])

            if signal_entry is None:
                raise InvalidRequestException(req, "Cannot find watchable with given path : %s" % signal_def['path'])

            if 'name' not in signal_def:
                signal_def['name'] = None

            if not (isinstance(signal_def['name'], str) or signal_def['name'] is None):
                raise InvalidRequestException(req, 'Invalid signal name')

            if 'axis_id' not in signal_def or not isinstance(signal_def['axis_id'], int):
                raise InvalidRequestException(req, 'Invalid signal axis ID')

            if signal_def['axis_id'] not in yaxis_map:
                raise InvalidRequestException(req, 'Invalid signal axis ID')

            signals_to_log.append(api_datalogging.SignalDefinitionWithAxis(
                name=signal_def['name'],
                entry=signal_entry,
                axis=yaxis_map[signal_def['axis_id']]
            ))

        acq_name: Optional[str] = None
        if 'name' in req:
            if req['name'] is not None and not isinstance(req['name'], str):
                raise InvalidRequestException(req, 'Invalid acquisition name')
            acq_name = req['name']

        acq_req = api_datalogging.AcquisitionRequest(
            name=acq_name,
            rate_identifier=req['sampling_rate_id'],
            decimation=req['decimation'],
            timeout=req['timeout'],
            trigger_hold_time=req['trigger_hold_time'],
            probe_location=req['probe_location'],
            x_axis_type=x_axis_type,
            x_axis_signal=x_axis_signal,
            trigger_condition=api_datalogging.TriggerCondition(
                condition_id=self.datalogging_supported_conditions[req['condition']].condition_id,
                operands=operands
            ),
            signals=signals_to_log
        )

        # We use a partial func to pass the request token and conn id
        request_token = uuid4().hex
        callback = functools.partial(self.datalogging_acquisition_completion_callback, conn_id, request_token)

        self.datalogging_manager.request_acquisition(
            request=acq_req,
            callback=callback
        )

        response: api_typing.S2C.RequestDataloggingAcquisition = {
            'cmd': API.Command.Api2Client.REQUEST_DATALOGGING_ACQUISITION_RESPONSE,
            'reqid': self.get_req_id(req),
            'request_token': request_token
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    def datalogging_acquisition_completion_callback(self, requestor_conn_id: str, request_token: str, success: bool, detail_msg: str, acquisition: Optional[api_datalogging.DataloggingAcquisition]) -> None:
        reference_id: Optional[str] = None
        if success:
            assert acquisition is not None
            reference_id = acquisition.reference_id

        # Tell the requestor that his request is completed.
        completion_msg: api_typing.S2C.InformDataloggingAcquisitionComplete = {
            'cmd': API.Command.Api2Client.INFORM_DATALOGGING_ACQUISITION_COMPLETE,
            'reqid': None,
            'success': success,
            'reference_id': reference_id,
            'request_token': request_token,
            'detail_msg': detail_msg
        }
        self.client_handler.send(ClientHandlerMessage(conn_id=requestor_conn_id, obj=completion_msg))

        # Inform all client so they can auto load the new data.
        if success:
            assert acquisition is not None
            broadcast_msg: api_typing.S2C.InformDataloggingListChanged = {
                'cmd': API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED,
                'reqid': None,
                'reference_id': acquisition.reference_id,
                'action': 'new'
            }

            for conn_id in self.connections:
                self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=broadcast_msg))

    # === LIST_DATALOGGING_ACQUISITION ===
    def process_list_datalogging_acquisition(self, conn_id: str, req: api_typing.C2S.ListDataloggingAcquisitions) -> None:
        reference_id: Optional[str] = None
        if 'reference_id' in req:
            if not isinstance(req['reference_id'], str) and req['reference_id'] is not None:
                raise InvalidRequestException(req, 'Invalid reference ID')
            reference_id = req['reference_id']

        if reference_id is None:    # Search all acquisition with given criteria
            _check_request_dict(req, req, 'count', int)

            firmware_id: Optional[str] = None
            if 'firmware_id' in req:
                if not isinstance(req['firmware_id'], str) and req['firmware_id'] is not None:
                    raise InvalidRequestException(req, 'Invalid firmware ID')
                firmware_id = req['firmware_id']

            before_datetime: Optional[datetime] = None
            if 'before_timestamp' in req and req['before_timestamp'] is not None:
                _check_request_dict(req, req, 'before_timestamp', (int, float))

                if req['before_timestamp'] < 0:
                    raise InvalidRequestException(req, 'Invalid before_timestamp value')
                try:
                    before_datetime = datetime.fromtimestamp(req['before_timestamp'])
                except Exception:
                    raise InvalidRequestException(req, 'Invalid before_timestamp value')

            MAX_COUNT = 10000
            if req['count'] < 0 or req['count'] > MAX_COUNT:
                raise InvalidRequestException(req, f'Invalid count value. Value must be between 0 and {MAX_COUNT}')

            reference_id_list = DataloggingStorage.list(firmware_id=firmware_id, before_datetime=before_datetime, count=req['count'])

        else:   # Search a single acquisition
            try:
                DataloggingStorage.read(reference_id)
                reference_id_list = [reference_id]
            except LookupError:
                reference_id_list = []

        # Common logic to the 2 type of search
        acquisitions: List[api_typing.DataloggingAcquisitionMetadata] = []
        for reference_id in reference_id_list:
            acq = DataloggingStorage.read(reference_id)
            firmware_metadata: Optional[api_typing.SFDMetadata] = None
            if SFDStorage.is_installed_or_demo(acq.firmware_id):
                firmware_metadata = SFDStorage.get_metadata(acq.firmware_id).to_dict()
            acquisitions.append({
                'firmware_id': acq.firmware_id,
                'name': acq.name,
                'timestamp': acq.acq_time.timestamp(),
                'reference_id': reference_id,
                'firmware_metadata': firmware_metadata
            })

        response: api_typing.S2C.ListDataloggingAcquisition = {
            'cmd': API.Command.Api2Client.LIST_DATALOGGING_ACQUISITION_RESPONSE,
            'reqid': self.get_req_id(req),
            'acquisitions': acquisitions
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    # === UPDATE_DATALOGGING_ACQUISITION ===
    def process_update_datalogging_acquisition(self, conn_id: str, req: api_typing.C2S.UpdateDataloggingAcquisition) -> None:
        _check_request_dict(req, req, 'reference_id', str)

        err: Optional[Exception]
        if 'name' in req:
            _check_request_dict(req, req, 'name', str)
            err = None
            try:
                DataloggingStorage.update_acquisition_name(req['reference_id'], cast(str, req['name']))
            except LookupError as e:
                err = e

            if err:
                raise InvalidRequestException(req, "Failed to update acquisition. %s" % (str(err)))

        if 'axis_name' in req:
            if not isinstance(req['axis_name'], list):
                raise InvalidRequestException(req, 'Invalid axis name list')

            for axis_name_entry in req['axis_name']:
                _check_request_dict(req, axis_name_entry, 'id', int)
                _check_request_dict(req, axis_name_entry, 'name', str)

                err = None
                try:
                    DataloggingStorage.update_axis_name(
                        reference_id=req['reference_id'],
                        axis_id=axis_name_entry['id'],
                        new_name=axis_name_entry['name']
                    )
                except LookupError as e:
                    err = e

                if err:
                    raise InvalidRequestException(req, "Failed to update acquisition. %s" % (str(err)))

        response: api_typing.S2C.UpdateDataloggingAcquisition = {
            'cmd': API.Command.Api2Client.UPDATE_DATALOGGING_ACQUISITION_RESPONSE,
            'reqid': self.get_req_id(req)
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

        broadcast_msg: api_typing.S2C.InformDataloggingListChanged = {
            'cmd': API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED,
            'reqid': None,
            'reference_id': req['reference_id'],
            'action': 'update'
        }

        for conn_id in self.connections:
            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=broadcast_msg))

    # === DELETE_DATALOGGING_ACQUISITION ===
    def process_delete_datalogging_acquisition(self, conn_id: str, req: api_typing.C2S.DeleteDataloggingAcquisition) -> None:
        _check_request_dict(req, req, 'reference_id', str)

        err: Optional[Exception] = None
        try:
            DataloggingStorage.delete(req['reference_id'])
        except LookupError as e:
            err = e

        if err:
            raise InvalidRequestException(req, "Failed to delete acquisition. %s" % (str(err)))

        response: api_typing.S2C.DeleteDataloggingAcquisition = {
            'cmd': API.Command.Api2Client.DELETE_DATALOGGING_ACQUISITION_RESPONSE,
            'reqid': self.get_req_id(req),
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

        broadcast_msg: api_typing.S2C.InformDataloggingListChanged = {
            'cmd': API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED,
            'reqid': None,
            'reference_id': req['reference_id'],
            'action': 'delete'
        }

        for conn_id in self.connections:
            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=broadcast_msg))

    # === DELETE_ALL_DATALOGGING_ACQUISITION ===
    def process_delete_all_datalogging_acquisition(self, conn_id: str, req: api_typing.C2S.DeleteDataloggingAcquisition) -> None:
        err: Optional[Exception] = None
        try:
            DataloggingStorage.clear_all()
        except LookupError as e:
            err = e

        if err:
            raise InvalidRequestException(req, "Failed to clear datalogging storage. %s" % (str(err)))

        response: api_typing.S2C.DeleteDataloggingAcquisition = {
            'cmd': API.Command.Api2Client.DELETE_ALL_DATALOGGING_ACQUISITION_RESPONSE,
            'reqid': self.get_req_id(req),
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

        broadcast_msg: api_typing.S2C.InformDataloggingListChanged = {
            'cmd': API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED,
            'reqid': None,
            'reference_id': None,
            'action': 'delete_all'
        }

        for conn_id in self.connections:
            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=broadcast_msg))

    # === READ_DATALOGGING_ACQUISITION_CONTENT ===
    def process_read_datalogging_acquisition_content(self, conn_id: str, req: api_typing.C2S.ReadDataloggingAcquisitionContent) -> None:
        _check_request_dict(req, req, 'reference_id', str)

        err: Optional[Exception] = None
        acquisition: api_datalogging.DataloggingAcquisition
        try:
            acquisition = DataloggingStorage.read(req['reference_id'])
        except LookupError as e:
            err = e

        if err:
            raise InvalidRequestException(req, "Failed to read acquisition. %s" % (str(err)))

        def dataseries_to_api_signal_data(ds: core_datalogging.DataSeries) -> api_typing.DataloggingSignalData:
            logged_watchable: Optional[api_typing.LoggedWatchable] = None
            if ds.logged_watchable is not None:
                logged_watchable = {
                    'path': ds.logged_watchable.path,
                    'type': ds.logged_watchable.type.value
                }
            signal: api_typing.DataloggingSignalData = {
                'name': ds.name,
                'watchable': logged_watchable,
                'data': [f if math.isfinite(f) else str(f) for f in ds.get_data()]
            }
            return signal

        def dataseries_to_api_signal_data_with_axis(ds: core_datalogging.DataSeries, axis_id: int) -> api_typing.DataloggingSignalDataWithAxis:
            signal: api_typing.DataloggingSignalDataWithAxis = cast(api_typing.DataloggingSignalDataWithAxis, dataseries_to_api_signal_data(ds))
            signal['axis_id'] = axis_id
            return signal

        yaxis_list: List[api_typing.DataloggingAxisDef] = []
        acq_axis_2_api_axis_map: Dict[api_datalogging.AxisDefinition, api_typing.DataloggingAxisDef] = {}
        for axis in acquisition.get_unique_yaxis_list():
            yaxis_out: api_typing.DataloggingAxisDef = {'name': axis.name, 'id': axis.axis_id}
            acq_axis_2_api_axis_map[axis] = yaxis_out
            yaxis_list.append(yaxis_out)

        signals: List[api_typing.DataloggingSignalDataWithAxis] = []
        for dataseries_with_axis in acquisition.get_data():
            signals.append(dataseries_to_api_signal_data_with_axis(ds=dataseries_with_axis.series, axis_id=dataseries_with_axis.axis.axis_id))

        response: api_typing.S2C.ReadDataloggingAcquisitionContent = {
            'cmd': API.Command.Api2Client.READ_DATALOGGING_ACQUISITION_CONTENT_RESPONSE,
            'reqid': self.get_req_id(req),
            'firmware_id': acquisition.firmware_id,
            'firmware_name': acquisition.firmware_name,
            'name': '' if acquisition.name is None else acquisition.name,
            'timestamp': acquisition.acq_time.timestamp(),
            'reference_id': acquisition.reference_id,
            'trigger_index': acquisition.trigger_index,
            'signals': signals,
            'xdata': dataseries_to_api_signal_data(acquisition.xdata),
            'yaxes': yaxis_list
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    # === GET_SERVER_STATS ===
    def process_server_stats(self, conn_id: str, req: api_typing.C2S.ReadDataloggingAcquisitionContent) -> None:
        stats = self.server.get_stats()
        response: api_typing.S2C.GetServerStats = {
            'cmd': API.Command.Api2Client.GET_SERVER_STATS,
            'reqid': self.get_req_id(req),
            'uptime': stats.uptime,
            'invalid_request_count': stats.api.invalid_request_count,
            'unexpected_error_count': stats.api.unexpected_error_count,
            'client_count': stats.api.client_handler.client_count,
            'to_all_clients_datarate_byte_per_sec': stats.api.client_handler.output_datarate_byte_per_sec,
            'from_any_client_datarate_byte_per_sec': stats.api.client_handler.input_datarate_byte_per_sec,
            'msg_received': stats.api.client_handler.msg_received,
            'msg_sent': stats.api.client_handler.msg_sent,
            'device_session_count': stats.device.device_session_count,
            'to_device_datarate_byte_per_sec': stats.device.comm_handler.tx_datarate_byte_per_sec,
            'from_device_datarate_byte_per_sec': stats.device.comm_handler.rx_datarate_byte_per_sec,
            'device_request_per_sec': stats.device.comm_handler.request_per_sec,
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    # === DEMO_MODE ===
    def process_demo_mode(self, conn_id: str, req: api_typing.C2S.DemoMode) -> None:
        _check_request_dict(req, req, 'enable', bool)

        if req['enable']:
            self.device_handler.start_demo_device()
        else:
            self.device_handler.stop_demo_mode()

        response: api_typing.S2C.DemoMode = {
            'cmd': API.Command.Api2Client.DEMO_MODE_RESPONSE,
            'reqid': self.get_req_id(req),
            'enabled': self.device_handler.demo_mode_active()
        }

        self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=response))

    def craft_inform_server_status(self, reqid: Optional[int] = None) -> api_typing.S2C.InformServerStatus:
        # Make a Server to client message that inform the actual state of the server
        # Query the state of all subpart of the software.
        sfd = self.sfd_handler.get_loaded_sfd()
        device_link_type = self.device_handler.get_link_type()
        device_comm_link = self.device_handler.get_comm_link()

        loaded_sfd_firmware_id: Optional[str] = None
        if sfd is not None:
            loaded_sfd_firmware_id = sfd.get_firmware_id_ascii()

        if device_comm_link is None:
            link_config = cast(EmptyDict, {})
            link_operational = False
        else:
            link_config = cast(api_typing.LinkConfig, device_comm_link.get_config())
            link_operational = device_comm_link.operational()

        datalogging_state_and_completion = self.datalogging_manager.get_datalogging_state()
        datalogging_state_api = self.DATALOGGING_STATE_2_APISTR.get(datalogging_state_and_completion[0], API.DataloggingStateString.UNAVAILABLE)
        completion_ratio = datalogging_state_and_completion[1]

        response: api_typing.S2C.InformServerStatus = {
            'cmd': self.Command.Api2Client.INFORM_SERVER_STATUS,
            'reqid': reqid,
            'device_status': self.DEVICE_CONN_STATUS_2_APISTR[self.device_handler.get_connection_status()],
            'device_session_id': self.device_handler.get_comm_session_id(),  # str when connected_ready. None when not connected_ready
            'loaded_sfd_firmware_id': loaded_sfd_firmware_id,
            'datalogging_status': {
                'datalogging_state': datalogging_state_api,
                'completion_ratio': completion_ratio
            },
            'device_comm_link': {
                'link_type': cast(api_typing.LinkType, device_link_type),
                'link_operational': link_operational,
                'link_config': link_config,
                'demo_mode': self.device_handler.demo_mode_active(),
            }
        }

        return response

    def send_server_status_to_all_clients(self) -> None:
        msg_obj = self.craft_inform_server_status()
        for conn_id in self.connections:
            self.client_handler.send(ClientHandlerMessage(conn_id=conn_id, obj=msg_obj))

    def entry_value_change_callback(self, conn_id: str, datastore_entry: DatastoreEntry) -> None:
        # This callback is given to the datastore when we a client start watching an entry.
        self.streamer.publish(datastore_entry, conn_id)
        self.stream_all_we_can()

    def entry_target_update_callback(self,
                                     request_token: str,
                                     batch_index: int,
                                     success: bool,
                                     datastore_entry: DatastoreEntry,
                                     completion_server_time_us: float) -> None:
        # This callback is given to the datastore when we make a write request (target update request)
        # It will be called once the request is completed.
        watchers = self.datastore.get_watchers(datastore_entry)

        msg: api_typing.S2C.WriteCompletion = {
            'cmd': self.Command.Api2Client.INFORM_WRITE_COMPLETION,
            'reqid': None,
            'watchable': datastore_entry.get_id(),
            'request_token': request_token,
            'batch_index': batch_index,
            'success': success,
            'completion_server_time_us': completion_server_time_us
        }

        for watcher_conn_id in watchers:
            self.client_handler.send(ClientHandlerMessage(conn_id=watcher_conn_id, obj=msg))

    def make_datastore_entry_definition(self,
                                        entry: DatastoreEntry,
                                        include_type: bool = True,
                                        include_display_path: bool = True,
                                        include_datatype: bool = True,
                                        include_enum: bool = True
                                        ) -> api_typing.DatastoreEntryDefinition:
        # Craft the data structure sent by the API to give the available watchables
        definition: api_typing.DatastoreEntryDefinition = {

        }

        if include_datatype:
            definition['dtype'] = self.get_datatype_name(entry.get_data_type())

        if include_display_path:
            definition['path'] = entry.get_display_path()

        if include_type:
            definition['type'] = self.get_watchable_type_name(entry.get_type())

        if include_enum and entry.has_enum():
            enum = entry.get_enum()
            assert enum is not None
            enum_def = enum.get_def()
            definition['enum'] = {  # Cherry pick items to avoid sending too much to client
                'name': enum.get_name(),
                'values': enum_def['values']
            }

        return definition

    def make_variable_factory_definition(self,
                                         factory: VariableFactory,
                                         include_type: bool = True,
                                         include_display_path: bool = True,
                                         include_datatype: bool = True,
                                         include_enum: bool = True
                                         ) -> api_typing.VariableFactoryDefinition:
        # Craft the data structure sent by the API to give the available watchables
        definition: api_typing.VariableFactoryDefinition = {
            'factory_params': {
                'array_nodes': {}
            }
        }

        var = factory.get_base_variable()

        if include_datatype:
            definition['dtype'] = self.get_datatype_name(var.get_type())

        if include_display_path:
            definition['path'] = factory.get_access_name()

        if include_type:
            definition['type'] = self.get_watchable_type_name(WatchableType.Variable)

        if include_enum and var.has_enum():
            enum = var.get_enum()
            assert enum is not None
            enum_def = enum.get_def()
            definition['enum'] = {  # Cherry pick items to avoid sending too much to client
                'name': enum.get_name(),
                'values': enum_def['values']
            }

        for path, array in factory.get_array_nodes().items():
            definition['factory_params']['array_nodes'][path] = list(array.dims)

        return definition

    def make_error_response(self, req: api_typing.C2SMessage, msg: str) -> api_typing.S2C.Error:
        # craft a standardized error message
        cmd = '<empty>'
        if 'cmd' in req:
            cmd = req['cmd']

        response: api_typing.S2C.Error = {
            'cmd': self.Command.Api2Client.ERROR_RESPONSE,
            'reqid': self.get_req_id(req),
            'request_cmd': cmd,
            'msg': msg
        }
        return response

    def get_req_id(self, req: api_typing.C2SMessage) -> Optional[int]:
        reqid = req['reqid'] if 'reqid' in req else None
        if reqid is not None:
            if not isinstance(reqid, int):
                raise InvalidRequestException(req, "Invalid request ID")

        return reqid

    def close(self) -> None:
        self.client_handler.stop()

    def get_stats(self) -> Statistics:
        return self.Statistics(
            invalid_request_count=self.invalid_request_count,
            unexpected_error_count=self.unexpected_error_count,
            client_handler=self.client_handler.get_stats()
        )

    def _get_temp_filepath(self, conn_id: str, name: str) -> Path:
        tempdir = Path(self.temp_dir.name) / conn_id
        os.makedirs(tempdir, exist_ok=True)
        tempfile = tempdir / name
        return tempfile

    def _get_file_timestamp_dict_key(self, filepath: Union[Path, str]) -> str:
        filepath = Path(filepath).absolute()
        return os.path.normpath(str(filepath))

    def _update_tempfile_timestamp(self, filepath: Union[Path, str]) -> None:
        filepath_str = self._get_file_timestamp_dict_key(filepath)
        self.tempfile_timestamp_monotonic[filepath_str] = time.monotonic()

    def _get_tempfile_timestamp(self, filepath: Union[Path, str]) -> Optional[float]:
        filepath_str = self._get_file_timestamp_dict_key(filepath)
        try:
            return self.tempfile_timestamp_monotonic[filepath_str]
        except KeyError:
            return None

    def create_temp_file(self, filepath: Union[str, Path]) -> None:
        open(filepath, 'wb').close()
        self._update_tempfile_timestamp(filepath)

    def prune_temp_files(self) -> None:
        for dirpath, dirnames, filenames in os.walk(self.temp_dir.name):
            for filename in filenames:
                filepath = os.path.join(dirpath, filename)
                timestamp = self._get_tempfile_timestamp(filepath)
                if timestamp is not None:
                    if time.monotonic() - timestamp > self.TEMP_FILE_LIFETIME:
                        try:
                            os.remove(filepath)
                            self.logger.debug(f"Pruning temporary file {filepath}")
                        except OSError as e:
                            tools.log_exception(self.logger, e, f"Failed to prune file : {filepath}")
