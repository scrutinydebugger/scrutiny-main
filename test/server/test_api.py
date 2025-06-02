#    test_api.py
#        Test the client API through a fake handler
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

import time
import queue
import random
import string
import json
import math
import logging
from uuid import uuid4
from scrutiny.core.basic_types import RuntimePublishedValue, MemoryRegion
from base64 import b64encode, b64decode
from dataclasses import dataclass

from scrutiny.server.server import ScrutinyServer
from scrutiny.server.api.API import API
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.server.sfd_storage import SFDStorage
from scrutiny.core.basic_types import EmbeddedDataType, Endianness, WatchableType
from scrutiny.server.api.dummy_client_handler import DummyConnection, DummyClientHandler, AbstractClientHandler
from scrutiny.server.device.device_handler import (DeviceHandler, DeviceStateChangedCallback, RawMemoryReadRequest,
                                                   RawMemoryWriteRequest, RawMemoryReadRequestCompletionCallback, RawMemoryWriteRequestCompletionCallback,
                                                   UserCommandCallback, DataloggerStateChangedCallback)
from scrutiny.server.device.device_info import DeviceInfo, FixedFreqLoop, VariableFreqLoop
from scrutiny.server.protocol.comm_handler import CommHandler
from scrutiny.server.active_sfd_handler import ActiveSFDHandler
from scrutiny.server.device.links.dummy_link import DummyLink
from scrutiny.core.variable import *
from scrutiny.core.embedded_enum import *
from scrutiny.core.alias import Alias
import scrutiny.core.datalogging as core_datalogging
import scrutiny.server.datalogging.definitions.api as api_datalogging
import scrutiny.server.datalogging.definitions.device as device_datalogging
from test.artifacts import get_artifact
from test import ScrutinyUnitTest
from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage
from datetime import datetime
import scrutiny.server.api.typing as api_typing
from scrutiny.tools.typing import *


# todo
# - Test rate limiter/data streamer


class StubbedDeviceHandler:
    connection_status: DeviceHandler.ConnectionStatus
    device_id: str
    server_session_id: Optional[str]
    link_type: str
    link_config: Dict[Any, Any]
    reject_link_config: bool
    datalogger_state: device_datalogging.DataloggerState
    datalogging_setup: Optional[device_datalogging.DataloggingSetup]
    device_state_change_callbacks: List[DeviceStateChangedCallback]
    datalogger_state_change_callbacks: List[DataloggerStateChangedCallback]
    comm_link: DummyLink
    device_info: DeviceInfo

    read_memory_queue: "queue.Queue[RawMemoryReadRequest]"
    write_memory_queue: "queue.Queue[RawMemoryWriteRequest]"
    user_command_history_queue: "queue.Queue[Tuple[int, bytes]]"

    def __init__(self, device_id, connection_status=DeviceHandler.ConnectionStatus.UNKNOWN):
        self.device_id = device_id
        self.server_session_id = None
        self.connection_status = connection_status
        self.link_type = 'none'
        self.link_config = {}
        self.reject_link_config = False
        self.datalogger_state = device_datalogging.DataloggerState.IDLE
        self.datalogging_setup = device_datalogging.DataloggingSetup(
            buffer_size=1024,
            encoding=device_datalogging.Encoding.RAW,
            max_signal_count=32
        )
        self.device_state_change_callbacks = []
        self.datalogger_state_change_callbacks = []
        self.read_memory_queue = queue.Queue()
        self.write_memory_queue = queue.Queue()
        self.user_command_history_queue = queue.Queue()
        self.comm_link = DummyLink()

        self.device_info = DeviceInfo()
        self.device_info.device_id = self.device_id
        self.device_info.display_name = self.__class__.__name__
        self.device_info.max_tx_data_size = 128
        self.device_info.max_rx_data_size = 64
        self.device_info.max_bitrate_bps = 10000
        self.device_info.rx_timeout_us = 50000
        self.device_info.heartbeat_timeout_us = 4000000
        self.device_info.address_size_bits = 32
        self.device_info.protocol_major = 1
        self.device_info.protocol_minor = 0
        self.device_info.supported_feature_map = {
            'memory_write': True,
            'datalogging': False,
            'user_command': True,
            '_64bits': True
        }
        self.device_info.forbidden_memory_regions = [MemoryRegion(0x1000, 0x500)]
        self.device_info.readonly_memory_regions = [MemoryRegion(0x2000, 0x600), MemoryRegion(0x3000, 0x700)]
        self.device_info.runtime_published_values = []
        self.device_info.loops = [
            FixedFreqLoop(1000, "Fixed Freq 1KHz"),
            FixedFreqLoop(10000, "Fixed Freq 10KHz"),
            VariableFreqLoop("Variable Freq"),
            VariableFreqLoop("Variable Freq No DL", support_datalogging=False)
        ]
        self.device_info.datalogging_setup = device_datalogging.DataloggingSetup(
            buffer_size=4096,
            encoding=device_datalogging.Encoding.RAW,
            max_signal_count=32
        )

    def get_connection_status(self) -> DeviceHandler.ConnectionStatus:
        return self.connection_status

    def set_connection_status(self, connection_status: DeviceHandler.ConnectionStatus) -> None:
        if connection_status == DeviceHandler.ConnectionStatus.CONNECTED_READY and (
                self.connection_status != DeviceHandler.ConnectionStatus.CONNECTED_READY or self.server_session_id is None):
            self.server_session_id = uuid4().hex
        elif connection_status != DeviceHandler.ConnectionStatus.CONNECTED_READY:
            self.server_session_id = None

        must_call_callbacks = self.connection_status != connection_status
        self.connection_status = connection_status

        if must_call_callbacks:
            logging.debug("Triggering device state change callback")
            for callback in self.device_state_change_callbacks:
                callback(connection_status)

    def get_comm_session_id(self) -> Optional[str]:
        return self.server_session_id

    def set_datalogging_setup(self, setup: Optional[device_datalogging.DataloggingSetup]) -> None:
        self.device_info.datalogging_setup = setup

    def get_datalogging_setup(self) -> Optional[device_datalogging.DataloggingSetup]:
        return self.device_info.datalogging_setup

    def get_datalogger_state(self) -> device_datalogging.DataloggerState:
        return self.datalogger_state

    def set_datalogger_state(self, state: device_datalogging.DataloggerState) -> None:
        self.datalogger_state = state
        for callback in self.datalogger_state_change_callbacks:
            callback(state, self.get_datalogging_acquisition_completion_ratio())

    def get_device_id(self) -> str:
        return self.device_id

    def get_link_type(self) -> str:
        return 'dummy'

    def get_comm_link(self) -> DummyLink:
        return self.comm_link

    def get_datalogging_acquisition_completion_ratio(self):
        return 0.5

    def get_device_info(self) -> Optional[DeviceInfo]:
        if self.connection_status == DeviceHandler.ConnectionStatus.CONNECTED_READY:
            return self.device_info
        return None

    def configure_comm(self, link_type: str, link_config: Dict[Any, Any]) -> None:
        self.link_type = link_type
        self.link_config = link_config

    def validate_link_config(self, link_type: str, link_config: Dict[Any, Any]):
        if self.reject_link_config:
            raise Exception('Bad config')

    def register_device_state_change_callback(self, callback):
        self.device_state_change_callbacks.append(callback)

    def register_datalogger_state_change_callback(self, callback):
        self.datalogger_state_change_callbacks.append(callback)

    def read_memory(self, address: int, size: int, callback: Optional[RawMemoryReadRequestCompletionCallback]):
        req = RawMemoryReadRequest(
            address=address,
            size=size,
            callback=callback
        )
        self.read_memory_queue.put(req)
        return req

    def write_memory(self, address: int, data: bytes, callback: Optional[RawMemoryWriteRequestCompletionCallback]):
        req = RawMemoryWriteRequest(
            address=address,
            data=data,
            callback=callback
        )
        self.write_memory_queue.put(req)
        return req

    def request_user_command(self, subfn: int, data: bytes, callback: UserCommandCallback):
        self.user_command_history_queue.put((subfn, data))
        if subfn == 2:
            if data == bytes([1, 2, 3, 4, 5]):
                callback(True, 2, bytes([10, 20, 30]), None)
            else:
                callback(False, 2, None, "Bad data")
        else:
            callback(False, subfn, None, "Unsupported subfunction")


class StubbedDataloggingManager:
    datastore: Datastore
    fake_device_handler: StubbedDeviceHandler
    datalogging_setup: device_datalogging.DataloggingSetup
    request_queue: "queue.Queue[api_datalogging.AcquisitionRequest]"

    callback_queue: "queue.Queue[Tuple[api_datalogging.APIAcquisitionRequestCompletionCallback, bool, core_datalogging.DataloggingAcquisition]]"

    def __init__(self, datastore: Datastore, fake_device_handler: StubbedDeviceHandler):
        self.datastore = datastore
        self.fake_device_handler = fake_device_handler
        self.request_queue = queue.Queue()
        self.callback_queue = queue.Queue()

    def get_device_setup(self) -> Optional[device_datalogging.DataloggingSetup]:
        return self.fake_device_handler.get_datalogging_setup()

    def request_acquisition(self, request: api_datalogging.AcquisitionRequest, callback: api_datalogging.APIAcquisitionRequestCompletionCallback) -> None:
        self.request_queue.put(request)
        acquisition = core_datalogging.DataloggingAcquisition(
            firmware_id='fake_firmware_id',
            name='fakename',
            reference_id='fake_refid',
            acq_time=datetime.now(),
            firmware_name='fake_firmware_name')

        # Defer callback to a while later because API depends on success of this function to take action.
        self.callback_queue.put((callback, True, acquisition))

    def process(self) -> None:
        if not self.callback_queue.empty():
            callback, success, acquisition = self.callback_queue.get()
            callback(success, "dummy msg", acquisition)

    def get_sampling_rate(self, identifier: int):
        info = self.fake_device_handler.get_device_info()
        assert info.loops is not None
        if not isinstance(identifier, int) or identifier < 0 or identifier >= len(info.loops):
            raise ValueError("Bad sampling rate ID")
        loop = info.loops[identifier]

        frequency = None
        if loop.get_loop_type() == api_datalogging.ExecLoopType.FIXED_FREQ:
            loop = cast(FixedFreqLoop, loop)
            frequency = loop.get_frequency()

        rate = api_datalogging.SamplingRate(
            name=loop.get_name(),
            rate_type=loop.get_loop_type(),
            device_identifier=identifier,
            frequency=frequency
        )

        return rate

    def is_valid_sample_rate_id(self, identifier: int) -> bool:
        try:
            self.get_sampling_rate(identifier)
        except ValueError:
            return False
        return True

    def is_ready_for_request(self) -> bool:
        return True

    def get_available_sampling_rates(self) -> List[api_datalogging.SamplingRate]:
        sampling_rates: List[api_datalogging.SamplingRate] = []
        info = self.fake_device_handler.get_device_info()
        if info is None:
            return []
        if info.loops is None:
            return []

        i = 0
        for loop in info.loops:
            if loop.support_datalogging:
                freq: Optional[float] = None
                if isinstance(loop, FixedFreqLoop):
                    freq = 1e7 / loop.get_timestep_100ns()
                sampling_rates.append(api_datalogging.SamplingRate(
                    name=loop.get_name(),
                    device_identifier=i,
                    rate_type=loop.get_loop_type(),
                    frequency=freq
                ))
            i += 1
        return sampling_rates


@dataclass
class FakeServer:
    datastore: Datastore
    device_handler: StubbedDeviceHandler
    datalogging_manager: StubbedDataloggingManager
    sfd_handler: ActiveSFDHandler

    def get_stats(self) -> ScrutinyServer.Statistics:
        return ScrutinyServer.Statistics(
            api=API.Statistics(
                invalid_request_count=10,
                unexpected_error_count=20,
                client_handler=AbstractClientHandler.Statistics(
                    client_count=1,
                    msg_received=2,
                    msg_sent=3,
                    input_datarate_byte_per_sec=10.1,
                    output_datarate_byte_per_sec=20.2
                )
            ),
            device=DeviceHandler.Statistics(
                device_session_count=30,
                comm_handler=CommHandler.Statistics(
                    rx_datarate_byte_per_sec=30.3,
                    tx_datarate_byte_per_sec=40.4,
                    request_per_sec=50.5
                )
            ),
            uptime=100.123
        )


class TestAPI(ScrutinyUnitTest):

    datastore: Datastore
    fake_device_handler: StubbedDeviceHandler
    fake_datalogging_manager: StubbedDataloggingManager
    sfd_handler: ActiveSFDHandler
    api: API

    def setUp(self):
        self.connections = [DummyConnection(), DummyConnection(), DummyConnection()]
        for conn in self.connections:
            conn.open()

        config = {
            'client_interface_type': 'dummy',
            'client_interface_config': {
            }
        }

        self.datastore = Datastore()
        self.fake_device_handler = StubbedDeviceHandler('0' * 64, DeviceHandler.ConnectionStatus.DISCONNECTED)
        self.fake_datalogging_manager = StubbedDataloggingManager(self.datastore, self.fake_device_handler)
        self.sfd_handler = ActiveSFDHandler(device_handler=self.fake_device_handler, datastore=self.datastore, autoload=False)
        fake_server = FakeServer(
            datastore=self.datastore,
            datalogging_manager=self.fake_datalogging_manager,
            device_handler=self.fake_device_handler,
            sfd_handler=self.sfd_handler
        )
        self.api = API(
            config=config,
            server=fake_server
        )
        self.api.handle_unexpected_errors = False
        client_handler = self.api.get_client_handler()
        assert isinstance(client_handler, DummyClientHandler)
        client_handler.set_connections(self.connections)
        self.api.start_listening()
        for i in range(len(self.connections)):
            resp = self.wait_and_load_response(conn_idx=i)
            self.assertEqual(resp['cmd'], API.Command.Api2Client.WELCOME)

    def tearDown(self):
        self.api.close()

    def process_all(self):
        self.api.process()
        self.sfd_handler.process()
        self.fake_datalogging_manager.process()

    def ensure_no_response_for(self, conn_idx=0, timeout=0.4):
        t1 = time.perf_counter()
        self.process_all()
        while not self.connections[conn_idx].from_server_available():
            if time.perf_counter() - t1 >= timeout:
                break
            self.process_all()
            time.sleep(0.01)

        json_str = self.connections[conn_idx].read_from_server()
        self.assertIsNone(json_str)

    def wait_for_response(self, conn_idx=0, timeout=1):
        t1 = time.perf_counter()
        self.process_all()
        while not self.connections[conn_idx].from_server_available():
            if time.perf_counter() - t1 >= timeout:
                break
            self.process_all()
            time.sleep(0.01)

        return self.connections[conn_idx].read_from_server()

    def wait_and_load_response(self, conn_idx=0, timeout=2):
        json_str = self.wait_for_response(conn_idx=conn_idx, timeout=timeout)
        self.assertIsNotNone(json_str)
        return json.loads(json_str)

    def send_request(self, req, conn_idx=0):
        self.connections[conn_idx].write_to_server(json.dumps(req))

    def assert_no_error(self, response, msg=None):
        self.assertIsNotNone(response)
        if 'cmd' in response:
            if 'msg' in response and msg is None:
                msg = response['msg']
            self.assertNotEqual(response['cmd'], API.Command.Api2Client.ERROR_RESPONSE, msg)

    def assert_is_error(self, response, msg=""):
        if 'cmd' in response:
            self.assertEqual(response['cmd'], API.Command.Api2Client.ERROR_RESPONSE, msg)
        else:
            raise Exception('Missing cmd field in response')

    def assert_is_response_command(self, resp, cmd):
        self.assertIn('cmd', resp)
        self.assertEqual(resp['cmd'], cmd)

    def wait_and_load_inform_server_status(self):
        response = cast(api_typing.S2C.InformServerStatus, self.wait_and_load_response())
        self.assert_is_response_command(response, API.Command.Api2Client.INFORM_SERVER_STATUS)
        return response

    def make_dummy_entries(self,
                           n,
                           entry_type=WatchableType.Variable,
                           prefix='path',
                           alias_bucket: List[DatastoreEntry] = [],
                           enum_dict: Optional[Dict[str, int]] = None
                           ) -> List[DatastoreEntry]:
        entries = []
        if entry_type == WatchableType.Alias:
            assert len(alias_bucket) >= n
            for entry in alias_bucket:
                assert not isinstance(entry, DatastoreAliasEntry)

        for i in range(n):
            name = '%s_%d' % (prefix, i)
            if entry_type == WatchableType.Variable:
                enum: Optional[EmbeddedEnum] = None
                if enum_dict is not None:
                    enum = EmbeddedEnum('some_enum')
                    for k, v in enum_dict.items():
                        enum.add_value(k, v)
                dummy_var = Variable('dummy', vartype=EmbeddedDataType.float32, path_segments=[
                    'a', 'b', 'c'], location=0x12345678, endianness=Endianness.Little, enum=enum)
                entry = DatastoreVariableEntry(name, variable_def=dummy_var)
            elif entry_type == WatchableType.Alias:
                entry = DatastoreAliasEntry(Alias(name, target='none'), refentry=alias_bucket[i])
            else:
                dummy_rpv = RuntimePublishedValue(id=i, datatype=EmbeddedDataType.float32)
                entry = DatastoreRPVEntry(name, rpv=dummy_rpv)
            entries.append(entry)
        return entries

    def make_random_string(self, n):
        letters = string.ascii_lowercase
        return ''.join(random.choice(letters) for i in range(n))

# ===== Test section ===============
    def test_echo(self):
        payload = self.make_random_string(100)
        req = {
            'cmd': 'echo',
            'payload': payload
        }
        self.send_request(req)
        response = self.wait_and_load_response()

        self.assertEqual(response['cmd'], 'response_echo')
        self.assertEqual(response['payload'], payload)

    # Fetch count of var/alias. Ensure response is well formatted and accurate
    def test_get_watchable_count(self):
        var_entries = self.make_dummy_entries(5, entry_type=WatchableType.Variable, prefix='var')
        alias_entries = self.make_dummy_entries(3, entry_type=WatchableType.Alias, prefix='alias', alias_bucket=var_entries)
        rpv_entries = self.make_dummy_entries(8, entry_type=WatchableType.RuntimePublishedValue, prefix='rpv')

        # Add entries in the datastore that we will reread through the API
        self.datastore.add_entries(var_entries)
        self.datastore.add_entries(alias_entries)
        self.datastore.add_entries(rpv_entries)

        req = {
            'cmd': 'get_watchable_count'
        }

        self.send_request(req)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        self.assertIn('cmd', response)
        self.assertIn('qty', response)
        self.assertIn('var', response['qty'])
        self.assertIn('alias', response['qty'])
        self.assertIn('rpv', response['qty'])

        self.assertEqual(response['cmd'], 'response_get_watchable_count')
        self.assertEqual(response['qty']['var'], 5)
        self.assertEqual(response['qty']['alias'], 3)
        self.assertEqual(response['qty']['rpv'], 8)

    def assert_get_watchable_list_response_format(self, response):
        self.assertIn('cmd', response)
        self.assertIn('qty', response)
        self.assertIn('done', response)
        self.assertIn('var', response['qty'])
        self.assertIn('alias', response['qty'])
        self.assertIn('rpv', response['qty'])
        self.assertIn('content', response)
        self.assertIn('var', response['content'])
        self.assertIn('alias', response['content'])
        self.assertIn('rpv', response['content'])
        self.assertEqual(response['cmd'], 'response_get_watchable_list')

    # Fetch list of var/alias. Ensure response is well formatted, accurate, complete, no duplicates
    def test_get_watchable_list_basic(self):
        var_entries = self.make_dummy_entries(5, entry_type=WatchableType.Variable, prefix='var')
        alias_entries = self.make_dummy_entries(2, entry_type=WatchableType.Alias, prefix='alias', alias_bucket=var_entries)
        rpv_entries = self.make_dummy_entries(8, entry_type=WatchableType.RuntimePublishedValue, prefix='rpv')

        expected_entries_in_response = {}
        for entry in var_entries:
            expected_entries_in_response[entry.get_id()] = entry
        for entry in alias_entries:
            expected_entries_in_response[entry.get_id()] = entry
        for entry in rpv_entries:
            expected_entries_in_response[entry.get_id()] = entry
        # Add entries in the datastore that we will reread through the API
        self.datastore.add_entries(var_entries)
        self.datastore.add_entries(alias_entries)
        self.datastore.add_entries(rpv_entries)

        req = {
            'cmd': 'get_watchable_list'
        }
        self.send_request(req)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        self.assert_get_watchable_list_response_format(response)

        self.assertEqual(response['done'], True)
        self.assertEqual(response['qty']['var'], 5)
        self.assertEqual(response['qty']['alias'], 2)
        self.assertEqual(response['qty']['rpv'], 8)
        self.assertEqual(len(response['content']['var']), 5)
        self.assertEqual(len(response['content']['alias']), 2)
        self.assertEqual(len(response['content']['rpv']), 8)

        # Put all entries in a single list, paired with the name of the parent key.
        all_entries_same_level = []
        all_entries_same_level += [(WatchableType.Variable, entry) for entry in response['content']['var']]
        all_entries_same_level += [(WatchableType.Alias, entry) for entry in response['content']['alias']]
        all_entries_same_level += [(WatchableType.RuntimePublishedValue, entry) for entry in response['content']['rpv']]

        # We make sure that the list is exact.
        for item in all_entries_same_level:
            entrytype = item[0]
            api_entry = item[1]

            self.assertIn('id', api_entry)
            self.assertIn('display_path', api_entry)

            self.assertIn(api_entry['id'], expected_entries_in_response)
            entry: DatastoreEntry = expected_entries_in_response[api_entry['id']]

            self.assertEqual(entry.get_id(), api_entry['id'])
            self.assertEqual(entry.get_type(), entrytype)
            self.assertEqual(API.get_datatype_name(entry.get_data_type()), api_entry['datatype'])
            self.assertEqual(entry.get_display_path(), api_entry['display_path'])

            del expected_entries_in_response[api_entry['id']]

        self.assertEqual(len(expected_entries_in_response), 0)

    def test_get_watchable_list_with_name_filter(self):
        var_entries = self.make_dummy_entries(5, entry_type=WatchableType.Variable, prefix='/includeme_var')
        alias_entries = self.make_dummy_entries(2, entry_type=WatchableType.Alias, prefix='/includeme_alias', alias_bucket=var_entries)
        rpv_entries = self.make_dummy_entries(8, entry_type=WatchableType.RuntimePublishedValue, prefix='/includeme_rpv')

        expected_entries_in_response = {}
        for entry in var_entries:
            expected_entries_in_response[entry.get_id()] = entry
        for entry in alias_entries:
            expected_entries_in_response[entry.get_id()] = entry
        for entry in rpv_entries:
            expected_entries_in_response[entry.get_id()] = entry
        # Add entries in the datastore that we will reread through the API
        self.datastore.add_entries(var_entries)
        self.datastore.add_entries(alias_entries)
        self.datastore.add_entries(rpv_entries)

        self.datastore.add_entries(self.make_dummy_entries(5, entry_type=WatchableType.Variable, prefix='/excludeme_var'))
        self.datastore.add_entries(self.make_dummy_entries(5, entry_type=WatchableType.Alias, prefix='/excludeme_alias', alias_bucket=var_entries))
        self.datastore.add_entries(self.make_dummy_entries(5, entry_type=WatchableType.RuntimePublishedValue, prefix='/excludeme_rpv'))

        req = {
            'cmd': 'get_watchable_list',
            'filter': {
                'name': '/includeme*'
            }
        }
        self.send_request(req)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        self.assert_get_watchable_list_response_format(response)

        self.assertEqual(response['done'], True)
        self.assertEqual(response['qty']['var'], 5)
        self.assertEqual(response['qty']['alias'], 2)
        self.assertEqual(response['qty']['rpv'], 8)
        self.assertEqual(len(response['content']['var']), 5)
        self.assertEqual(len(response['content']['alias']), 2)
        self.assertEqual(len(response['content']['rpv']), 8)

        # Put all entries in a single list, paired with the name of the parent key.
        all_entries_same_level = []
        all_entries_same_level += [(WatchableType.Variable, entry) for entry in response['content']['var']]
        all_entries_same_level += [(WatchableType.Alias, entry) for entry in response['content']['alias']]
        all_entries_same_level += [(WatchableType.RuntimePublishedValue, entry) for entry in response['content']['rpv']]

        # We make sure that the list is exact.
        for item in all_entries_same_level:
            entrytype = item[0]
            api_entry = item[1]

            self.assertIn('id', api_entry)
            self.assertIn('display_path', api_entry)

            self.assertIn(api_entry['id'], expected_entries_in_response)
            entry: DatastoreEntry = expected_entries_in_response[api_entry['id']]

            self.assertEqual(entry.get_id(), api_entry['id'])
            self.assertEqual(entry.get_type(), entrytype)
            self.assertEqual(API.get_datatype_name(entry.get_data_type()), api_entry['datatype'])
            self.assertEqual(entry.get_display_path(), api_entry['display_path'])

            del expected_entries_in_response[api_entry['id']]

        self.assertEqual(len(expected_entries_in_response), 0)

    # Fetch list of var/alias and sets all sort of type filter.

    def test_get_watchable_list_with_type_filter(self):
        self.do_test_get_watchable_list_with_type_filter(None)
        self.do_test_get_watchable_list_with_type_filter('')
        self.do_test_get_watchable_list_with_type_filter([])
        self.do_test_get_watchable_list_with_type_filter(['var'])
        self.do_test_get_watchable_list_with_type_filter(['alias'])
        self.do_test_get_watchable_list_with_type_filter(['rpv'])
        self.do_test_get_watchable_list_with_type_filter(['var', 'alias'])
        self.do_test_get_watchable_list_with_type_filter(['rpv', 'var'])
        self.do_test_get_watchable_list_with_type_filter(['var', 'alias', 'rpv'])

    # Fetch list of var/alias and sets a type filter.
    def do_test_get_watchable_list_with_type_filter(self, type_filter):
        self.datastore.clear()
        var_entries = self.make_dummy_entries(5, entry_type=WatchableType.Variable, prefix='var')
        alias_entries = self.make_dummy_entries(3, entry_type=WatchableType.Alias, prefix='alias', alias_bucket=var_entries)
        rpv_entries = self.make_dummy_entries(8, entry_type=WatchableType.RuntimePublishedValue, prefix='rpv')

        no_filter = True if type_filter is None or type_filter == '' or isinstance(type_filter, list) and len(type_filter) == 0 else False

        nbr_expected_var = 0
        nbr_expected_alias = 0
        nbr_expected_rpv = 0
        expected_entries_in_response = {}
        if no_filter or 'var' in type_filter:
            nbr_expected_var = len(var_entries)
            for entry in var_entries:
                expected_entries_in_response[entry.get_id()] = entry

        if no_filter or 'alias' in type_filter:
            nbr_expected_alias = len(alias_entries)
            for entry in alias_entries:
                expected_entries_in_response[entry.get_id()] = entry

        if no_filter or 'rpv' in type_filter:
            nbr_expected_rpv = len(rpv_entries)
            for entry in rpv_entries:
                expected_entries_in_response[entry.get_id()] = entry

        # Add entries in the datastore that we will reread through the API
        self.datastore.add_entries(var_entries)
        self.datastore.add_entries(alias_entries)
        self.datastore.add_entries(rpv_entries)

        req = {
            'cmd': 'get_watchable_list',
            'filter': {
                'type': type_filter
            }
        }
        self.send_request(req)
        response = self.wait_and_load_response()
        self.assert_no_error(response, 'type_filter = %s' % (str(type_filter)))

        self.assert_get_watchable_list_response_format(response)

        self.assertEqual(response['done'], True)
        self.assertEqual(response['qty']['var'], nbr_expected_var)
        self.assertEqual(response['qty']['alias'], nbr_expected_alias)
        self.assertEqual(response['qty']['rpv'], nbr_expected_rpv)
        self.assertEqual(len(response['content']['var']), nbr_expected_var)
        self.assertEqual(len(response['content']['alias']), nbr_expected_alias)
        self.assertEqual(len(response['content']['rpv']), nbr_expected_rpv)

        # Put all entries in a single list, paired with the name of the parent key.
        all_entries_same_level = []
        all_entries_same_level += [(WatchableType.Variable, entry) for entry in response['content']['var']]
        all_entries_same_level += [(WatchableType.Alias, entry) for entry in response['content']['alias']]
        all_entries_same_level += [(WatchableType.RuntimePublishedValue, entry) for entry in response['content']['rpv']]

        for item in all_entries_same_level:
            entrytype = item[0]
            api_entry = item[1]

            self.assertIn('id', api_entry)
            self.assertIn('display_path', api_entry)

            self.assertIn(api_entry['id'], expected_entries_in_response)
            entry = expected_entries_in_response[api_entry['id']]

            self.assertEqual(entry.get_id(), api_entry['id'])
            self.assertEqual(entry.get_type(), entrytype)
            self.assertEqual(entry.get_display_path(), api_entry['display_path'])

            del expected_entries_in_response[api_entry['id']]

        self.assertEqual(len(expected_entries_in_response), 0)

    # Fetch list of var/alias and sets a limit of items per response.
    # List should be broken in multiple messages

    def test_get_watchable_list_with_item_limit(self):
        nVar = 19
        nAlias = 17
        nRpv = 21
        max_per_response = 10
        var_entries = self.make_dummy_entries(nVar, entry_type=WatchableType.Variable, prefix='var')
        alias_entries = self.make_dummy_entries(nAlias, entry_type=WatchableType.Alias, prefix='alias', alias_bucket=var_entries)
        rpv_entries = self.make_dummy_entries(nRpv, entry_type=WatchableType.RuntimePublishedValue, prefix='rpv')

        expected_entries_in_response = {}

        for entry in var_entries:
            expected_entries_in_response[entry.get_id()] = entry

        for entry in alias_entries:
            expected_entries_in_response[entry.get_id()] = entry

        for entry in rpv_entries:
            expected_entries_in_response[entry.get_id()] = entry

        # Add entries in the datastore that we will reread through the API
        self.datastore.add_entries(var_entries)
        self.datastore.add_entries(alias_entries)
        self.datastore.add_entries(rpv_entries)

        req = {
            'cmd': 'get_watchable_list',
            'max_per_response': max_per_response
        }

        self.send_request(req)
        responses = []
        nresponse = math.ceil((nVar + nAlias + nRpv) / max_per_response)
        for i in range(nresponse):
            responses.append(self.wait_and_load_response())

        received_vars = []
        received_alias = []
        received_rpvs = []

        for i in range(len(responses)):
            response = responses[i]
            self.assert_no_error(response)
            self.assert_get_watchable_list_response_format(response)

            received_vars += response['content']['var']
            received_alias += response['content']['alias']
            received_rpvs += response['content']['rpv']

            if i < len(responses) - 1:
                self.assertEqual(response['done'], False)
                self.assertEqual(response['qty']['var'] + response['qty']['alias'] + response['qty']['rpv'], max_per_response)
                self.assertEqual(len(response['content']['var']) + len(response['content']['alias']) +
                                 len(response['content']['rpv']), max_per_response)
            else:
                remaining_items = nVar + nAlias + nRpv - (len(responses) - 1) * max_per_response
                self.assertEqual(response['done'], True)
                self.assertEqual(response['qty']['var'] + response['qty']['alias'] + response['qty']['rpv'], remaining_items)
                self.assertEqual(len(response['content']['var']) + len(response['content']['alias']) +
                                 len(response['content']['rpv']), remaining_items)

            # Put all entries in a single list, paired with the name of the parent key.
            all_entries_same_level = []
            all_entries_same_level += [(WatchableType.Variable, entry) for entry in response['content']['var']]
            all_entries_same_level += [(WatchableType.Alias, entry) for entry in response['content']['alias']]
            all_entries_same_level += [(WatchableType.RuntimePublishedValue, entry) for entry in response['content']['rpv']]

            for item in all_entries_same_level:

                entrytype = item[0]
                api_entry = item[1]

                self.assertIn('id', api_entry)
                self.assertIn('display_path', api_entry)

                self.assertIn(api_entry['id'], expected_entries_in_response)
                entry = expected_entries_in_response[api_entry['id']]

                self.assertEqual(entry.get_id(), api_entry['id'])
                self.assertEqual(entry.get_type(), entrytype)
                self.assertEqual(entry.get_display_path(), api_entry['display_path'])

                del expected_entries_in_response[api_entry['id']]

        self.assertEqual(len(expected_entries_in_response), 0)

    def assert_valid_value_update_message(self, msg):
        self.assert_no_error(msg)
        self.assertIn('cmd', msg)
        self.assertIn('updates', msg)

        self.assertEqual(msg['cmd'], 'watchable_update')
        self.assertIsInstance(msg['updates'], list)

        for update in msg['updates']:
            self.assertIn('id', update)
            self.assertIn('v', update)
            self.assertIn('t', update)

    def test_subscribe_single_var(self):
        entries = self.make_dummy_entries(10, entry_type=WatchableType.Variable, prefix='var')
        self.datastore.add_entries(entries)

        subscribed_entry = entries[2]
        req = {
            'cmd': 'subscribe_watchable',
            'watchables': [subscribed_entry.get_display_path()]
        }

        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        self.assertIn('cmd', response)
        self.assertIn('subscribed', response)
        self.assertIsInstance(response['subscribed'], dict)

        self.assertEqual(response['cmd'], 'response_subscribe_watchable')
        self.assertEqual(len(response['subscribed']), 1)
        self.assertIn(subscribed_entry.get_display_path(), response['subscribed'])
        obj1 = response['subscribed'][subscribed_entry.get_display_path()]
        self.assertEqual(obj1['id'], subscribed_entry.get_id())
        self.assertEqual(obj1['type'], 'var')
        self.assertEqual(obj1['datatype'], 'float32')
        self.assertNotIn('enum', obj1)  # No enum in this one

        self.assertIsNone(self.wait_for_response(timeout=0.2))

        self.datastore.set_value(subscribed_entry.get_id(), 1234)

        var_update_msg = self.wait_and_load_response()
        self.assert_valid_value_update_message(var_update_msg)
        self.assertEqual(len(var_update_msg['updates']), 1)

        update = var_update_msg['updates'][0]

        self.assertEqual(update['id'], subscribed_entry.get_id())
        self.assertEqual(update['v'], 1234)

    def test_subscribe_single_var_get_enum(self):
        subscribed_entry = self.make_dummy_entries(1, entry_type=WatchableType.Variable, prefix='var', enum_dict={'a': 1, 'b': 2, 'c': 3})[0]
        self.datastore.add_entry(subscribed_entry)

        req = {
            'cmd': 'subscribe_watchable',
            'watchables': [subscribed_entry.get_display_path()]
        }

        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        self.assertIn('cmd', response)
        self.assertIn('subscribed', response)
        self.assertIsInstance(response['subscribed'], dict)

        self.assertEqual(response['cmd'], 'response_subscribe_watchable')
        self.assertEqual(len(response['subscribed']), 1)
        self.assertIn(subscribed_entry.get_display_path(), response['subscribed'])
        obj1 = response['subscribed'][subscribed_entry.get_display_path()]
        self.assertEqual(obj1['id'], subscribed_entry.get_id())
        self.assertEqual(obj1['type'], 'var')
        self.assertEqual(obj1['datatype'], 'float32')
        self.assertIn('enum', obj1)  # No enum in this one
        self.assertIn('name', obj1['enum'])
        self.assertIn('values', obj1['enum'])
        self.assertEqual(obj1['enum']['name'], 'some_enum')
        self.assertEqual(obj1['enum']['values'], {'a': 1, 'b': 2, 'c': 3})

    def test_stop_watching_on_disconnect(self):
        entries = self.make_dummy_entries(2, entry_type=WatchableType.Variable, prefix='var')
        self.datastore.add_entries(entries)

        req = {
            'cmd': 'subscribe_watchable',
            'watchables': [entries[0].get_display_path(), entries[1].get_display_path()]
        }

        self.send_request(req, 0)   # connection 0
        response = self.wait_and_load_response(0)
        self.assert_no_error(response)

        self.send_request(req, 1)   # connection 1
        response = self.wait_and_load_response(1)
        self.assert_no_error(response)

        # Make sure we stop watching on disconnect
        self.assertEqual(len(self.datastore.get_watchers(entries[0])), 2)
        self.assertEqual(len(self.datastore.get_watchers(entries[1])), 2)
        self.connections[1].close()
        self.api.process()
        self.assertEqual(len(self.datastore.get_watchers(entries[0])), 1)
        self.assertEqual(len(self.datastore.get_watchers(entries[1])), 1)

    # Make sure that we can unsubscribe correctly to a variable and value update stops

    def test_subscribe_unsubscribe(self):
        entries = self.make_dummy_entries(10, entry_type=WatchableType.Variable, prefix='var')
        self.datastore.add_entries(entries)
        subscribed_entry = entries[2]
        subscribe_cmd = {
            'cmd': 'subscribe_watchable',
            'watchables': [subscribed_entry.get_display_path()]
        }

        # Subscribe through conn 0
        self.send_request(subscribe_cmd, 0)
        response = self.wait_and_load_response(0)
        self.assert_no_error(response)

        unsubscribe_cmd = {
            'cmd': 'unsubscribe_watchable',
            'watchables': [subscribed_entry.get_display_path()]
        }

        self.send_request(unsubscribe_cmd, 0)
        response = self.wait_and_load_response(0)
        self.assert_no_error(response)

        self.datastore.set_value(subscribed_entry.get_id(), 1111)
        self.assertIsNone(self.wait_for_response(0, timeout=0.1))

    # Make sure that the streamer send the value update once if many update happens before the value is outputted to the client.
    def test_do_not_send_duplicate_changes(self):
        entries = self.make_dummy_entries(10, entry_type=WatchableType.Variable, prefix='var')
        self.datastore.add_entries(entries)

        subscribed_entry = entries[2]
        req = {
            'cmd': 'subscribe_watchable',
            'watchables': [subscribed_entry.get_display_path()]
        }

        self.send_request(req, 0)
        response = self.wait_and_load_response(0)
        self.assert_no_error(response)

        self.api.streamer.freeze_connection(self.connections[0].get_id())
        self.datastore.set_value(subscribed_entry.get_id(), 1234)
        self.datastore.set_value(subscribed_entry.get_id(), 4567)
        self.api.streamer.unfreeze_connection(self.connections[0].get_id())

        var_update_msg = self.wait_and_load_response()
        self.assert_valid_value_update_message(var_update_msg)
        self.assertEqual(len(var_update_msg['updates']), 1)     # Only one update

        self.assertEqual(var_update_msg['updates'][0]['id'], subscribed_entry.get_id())
        self.assertEqual(var_update_msg['updates'][0]['v'], 4567)   # Got latest value

        self.assertIsNone(self.wait_for_response(0, timeout=0.1))   # No more message to send

    # Make sure we can read the list of installed SFD

    def test_get_sfd_list(self):
        dummy_sfd1_filename = get_artifact('test_sfd_1.sfd')
        dummy_sfd2_filename = get_artifact('test_sfd_2.sfd')
        with SFDStorage.use_temp_folder():
            sfd1 = SFDStorage.install(dummy_sfd1_filename, ignore_exist=True)
            sfd2 = SFDStorage.install(dummy_sfd2_filename, ignore_exist=True)

            req = {
                'cmd': 'get_installed_sfd'
            }

            self.send_request(req, 0)
            response = self.wait_and_load_response()
            self.assert_no_error(response)
            self.assertEqual(response['cmd'], 'response_get_installed_sfd')
            self.assertIn('sfd_list', response)

            installed_list = SFDStorage.list()
            self.assertEqual(len(installed_list), len(response['sfd_list']))

            for installed_firmware_id in installed_list:
                self.assertIn(installed_firmware_id, response['sfd_list'])
                gotten_metadata = response['sfd_list'][installed_firmware_id]
                real_metadata = SFDStorage.get_metadata(installed_firmware_id)
                self.assertEqual(real_metadata.to_dict(), gotten_metadata)

            SFDStorage.uninstall(sfd1.get_firmware_id_ascii())
            SFDStorage.uninstall(sfd2.get_firmware_id_ascii())

    # Check that we can load a SFD through the API and read the actually loaded SFD

    def test_load_and_get_loaded_sfd(self):
        dummy_sfd1_filename = get_artifact('test_sfd_1.sfd')
        dummy_sfd2_filename = get_artifact('test_sfd_2.sfd')
        with SFDStorage.use_temp_folder():
            sfd1 = SFDStorage.install(dummy_sfd1_filename, ignore_exist=True)
            sfd2 = SFDStorage.install(dummy_sfd2_filename, ignore_exist=True)

            # load #1
            req = {
                'cmd': 'load_sfd',
                'firmware_id': sfd1.get_firmware_id_ascii()
            }

            self.send_request(req, 0)

            # inform status should be trigger by callback
            response = self.wait_and_load_response()
            self.assertEqual(response['cmd'], 'inform_server_status')

            self.send_request({'cmd': 'get_loaded_sfd'})
            response = self.wait_and_load_response()

            self.assertEqual(response['cmd'], 'response_get_loaded_sfd')
            self.assertIn('metadata', response)
            self.assertIn('firmware_id', response)
            self.assertEqual(response['firmware_id'], sfd1.get_firmware_id_ascii())
            self.assertEqual(response['metadata'], sfd1.get_metadata().to_dict())

            # load #2
            req = {
                'cmd': 'load_sfd',
                'firmware_id': sfd2.get_firmware_id_ascii()
            }

            self.send_request(req, 0)

            # inform status should be trigger by callback
            response = self.wait_and_load_response()
            self.assert_no_error(response)
            self.assertEqual(response['cmd'], 'inform_server_status')

            self.send_request({'cmd': 'get_loaded_sfd'})
            response = self.wait_and_load_response()
            self.assertEqual(response['cmd'], 'response_get_loaded_sfd')

            self.assertIn('firmware_id', response)
            self.assertIn('metadata', response)
            self.assertEqual(response['firmware_id'], sfd2.get_firmware_id_ascii())
            self.assertEqual(response['metadata'], sfd2.get_metadata().to_dict())

            SFDStorage.uninstall(sfd1.get_firmware_id_ascii())
            SFDStorage.uninstall(sfd2.get_firmware_id_ascii())

    def test_get_device_info(self):
        self.fake_device_handler.set_connection_status(DeviceHandler.ConnectionStatus.CONNECTED_READY)
        self.fake_device_handler.get_comm_link().initialize()   # Makes operational
        self.assertTrue(self.fake_device_handler.get_comm_link().operational())

        self.wait_and_load_inform_server_status()   # ignore it. Triggered because of device status change

        req = {'cmd': 'get_device_info'}
        self.send_request(req, 0)
        response = cast(api_typing.S2C.GetDeviceInfo, self.wait_and_load_response())
        self.assert_no_error(response)

        self.assertEqual(response['cmd'], 'response_get_device_info')
        self.assertIn('available', response)
        self.assertIn('device_info', response)
        self.assertTrue(response['available'])
        self.assertIsNotNone(response['device_info'])
        device_info = self.fake_device_handler.get_device_info()

        device_info_exclude_propeties = ['runtime_published_values', 'loops', 'datalogging_setup']  # API does not provide those on purpose
        for attr in device_info.get_attributes():
            if attr not in device_info_exclude_propeties:    # Exclude list
                self.assertIn(attr, response['device_info'])

                if attr not in ['readonly_memory_regions', 'forbidden_memory_regions']:
                    self.assertEqual(getattr(device_info, attr), response['device_info'][attr])
                else:
                    region_list = getattr(device_info, attr)
                    self.assertEqual(len(region_list), len(response['device_info'][attr]))

                    for i in range(len(region_list)):
                        self.assertIn('start', response['device_info'][attr][i])
                        self.assertIn('size', response['device_info'][attr][i])
                        self.assertIn('end', response['device_info'][attr][i])

                        self.assertEqual(region_list[i].start, response['device_info'][attr][i]['start'])
                        self.assertEqual(region_list[i].size, response['device_info'][attr][i]['size'])
                        self.assertEqual(region_list[i].end, response['device_info'][attr][i]['end'])

        self.fake_device_handler.device_info = None
        req = {'cmd': 'get_device_info'}
        self.send_request(req, 0)
        response = cast(api_typing.S2C.GetDeviceInfo, self.wait_and_load_response())
        self.assert_no_error(response)

        self.assertIn('available', response)
        self.assertIn('device_info', response)
        self.assertFalse(response['available'])
        self.assertIsNone(response['device_info'])

    def test_get_server_status(self):
        self.fake_device_handler.set_datalogger_state(device_datalogging.DataloggerState.TRIGGERED)
        self.wait_and_load_inform_server_status()   # Datalogger state change trigers a message

        dummy_sfd1_filename = get_artifact('test_sfd_1.sfd')
        dummy_sfd2_filename = get_artifact('test_sfd_2.sfd')
        with SFDStorage.use_temp_folder():
            sfd1 = SFDStorage.install(dummy_sfd1_filename, ignore_exist=True)
            sfd2 = SFDStorage.install(dummy_sfd2_filename, ignore_exist=True)

            self.sfd_handler.request_load_sfd(sfd2.get_firmware_id_ascii())
            self.sfd_handler.process()
            self.fake_device_handler.set_connection_status(DeviceHandler.ConnectionStatus.CONNECTED_READY)
            self.wait_and_load_inform_server_status()   # Device state change trigers a message
            self.fake_device_handler.get_comm_link().initialize()   # Makes operational
            self.assertTrue(self.fake_device_handler.get_comm_link().operational())
            self.wait_and_load_inform_server_status()   # comm channel availability change triggers a message

            req = {
                'cmd': 'get_server_status'
            }

            self.send_request(req, 0)
            response = cast(api_typing.S2C.InformServerStatus, self.wait_and_load_response())
            self.assert_no_error(response)

            self.assertEqual(response['cmd'], 'inform_server_status')
            self.assertIn('device_status', response)
            self.assertEqual(response['device_status'], 'connected_ready')
            self.assertIn('device_session_id', response)
            self.assertIsNotNone(response['device_session_id'])
            self.assertIn('device_datalogging_status', response)
            self.assertIn('datalogger_state', response['device_datalogging_status'])
            self.assertIn('completion_ratio', response['device_datalogging_status'])
            self.assertEqual(response['device_datalogging_status']['datalogger_state'], 'acquiring')
            self.assertEqual(response['device_datalogging_status']['completion_ratio'], 0.5)
            self.assertIn('loaded_sfd_firmware_id', response)
            self.assertEqual(response['loaded_sfd_firmware_id'], sfd2.get_firmware_id_ascii())
            self.assertIn('device_comm_link', response)
            self.assertIn('link_type', response['device_comm_link'])
            self.assertEqual(response['device_comm_link']['link_type'], 'dummy')
            self.assertIn('link_operational', response['device_comm_link'])
            self.assertEqual(response['device_comm_link']['link_operational'], True)
            self.assertIn('link_config', response['device_comm_link'])
            self.assertEqual(response['device_comm_link']['link_config'], {})

            # Redo the test, but with no SFD loaded. We should get None
            self.sfd_handler.reset_active_sfd()
            response = self.wait_and_load_response()    # unloading an SFD should trigger an "inform_server_status" message
            self.assert_no_error(response)
            self.assertEqual(response['cmd'], 'inform_server_status')
            self.sfd_handler.process()

            req = {
                'cmd': 'get_server_status'
            }

            self.send_request(req, 0)
            response = cast(api_typing.S2C.InformServerStatus, self.wait_and_load_response())
            self.assert_no_error(response)

            self.assertEqual(response['cmd'], 'inform_server_status')
            self.assertIn('device_status', response)
            self.assertIn('device_session_id', response)
            self.assertIsNotNone(response['device_session_id'])
            self.assertEqual(response['device_status'], 'connected_ready')
            self.assertIn('loaded_sfd_firmware_id', response)
            self.assertIsNone(response['loaded_sfd_firmware_id'])

            self.assertIn('device_comm_link', response)
            self.assertIn('link_type', response['device_comm_link'])
            self.assertEqual(response['device_comm_link']['link_type'], 'dummy')
            self.assertIn('link_config', response['device_comm_link'])
            self.assertEqual(response['device_comm_link']['link_config'], {})

            SFDStorage.uninstall(sfd1.get_firmware_id_ascii())
            SFDStorage.uninstall(sfd2.get_firmware_id_ascii())

            # Changing the datalogger state should trigger a status message
            self.fake_device_handler.set_datalogger_state(device_datalogging.DataloggerState.ARMED)
            response = cast(api_typing.S2C.InformServerStatus, self.wait_and_load_response())
            self.assert_no_error(response)
            self.assertIn('device_datalogging_status', response)
            self.assertIsInstance(response['device_datalogging_status'], dict)
            self.assertIn('datalogger_state', response['device_datalogging_status'])
            self.assertIn('completion_ratio', response['device_datalogging_status'])
            self.assertEqual(response['device_datalogging_status']['datalogger_state'], 'waiting_for_trigger')
            self.assertEqual(response['device_datalogging_status']['completion_ratio'],
                             self.fake_device_handler.get_datalogging_acquisition_completion_ratio())

            # Changing the connection status should trigger a status message
            self.fake_device_handler.set_connection_status(DeviceHandler.ConnectionStatus.DISCONNECTED)
            response = cast(api_typing.S2C.InformServerStatus, self.wait_and_load_response())
            self.assert_no_error(response)
            self.assertIn('device_session_id', response)
            self.assertIsNone(response['device_session_id'])    # Expected None when not connected

            self.send_request(req, 0)
            response = cast(api_typing.S2C.InformServerStatus, self.wait_and_load_response())
            self.assert_no_error(response)
            self.assertIn('device_session_id', response)
            self.assertIsNone(response['device_session_id'])    # Expected None when not connected

            self.assertIsNone(self.wait_for_response(timeout=0.1))

    def test_server_status_sent_on_device_state_change(self):

        # API consider a connection active after the first message
        self.send_request(dict(cmd='echo', payload="123"))
        self.wait_and_load_response()

        self.assertEqual(self.fake_device_handler.get_connection_status(), DeviceHandler.ConnectionStatus.DISCONNECTED)
        self.fake_device_handler.set_connection_status(DeviceHandler.ConnectionStatus.CONNECTED_READY)
        msg = cast(api_typing.S2C.InformServerStatus, self.wait_and_load_response())
        self.assert_no_error(msg)
        self.assertEqual(msg['cmd'], API.Command.Api2Client.INFORM_SERVER_STATUS)
        self.assertEqual(msg['device_status'], API.DeviceCommStatus.CONNECTED_READY)

        self.fake_device_handler.set_connection_status(DeviceHandler.ConnectionStatus.DISCONNECTED)
        msg = cast(api_typing.S2C.InformServerStatus, self.wait_and_load_response())
        self.assert_no_error(msg)
        self.assertEqual(msg['cmd'], API.Command.Api2Client.INFORM_SERVER_STATUS)
        self.assertEqual(msg['device_status'], API.DeviceCommStatus.DISCONNECTED)

    def test_set_device_link(self):
        self.assertEqual(self.fake_device_handler.link_type, 'none')
        self.assertEqual(self.fake_device_handler.link_config, {})

        # Switch the device link for real
        req = {
            'cmd': 'set_link_config',
            'link_type': 'dummy',
            'link_config': {
                'channel_id': 10
            }
        }
        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_no_error(response)
        self.assertEqual(self.fake_device_handler.link_type, 'dummy')
        self.assertEqual(self.fake_device_handler.link_config, {'channel_id': 10})

        inform_status = self.wait_and_load_response()   # Expected when a link change succeed
        self.assert_no_error(inform_status)
        self.assertEqual(inform_status['cmd'], API.Command.Api2Client.INFORM_SERVER_STATUS)

        # Simulate that the device handler refused the configuration. Make sure we return a proper error
        req = {
            'cmd': 'set_link_config',
            'link_type': 'potato',
            'link_config': {
                'mium': 'mium'
            }
        }
        self.fake_device_handler.reject_link_config = True   # Emulate a bad config
        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_is_error(response)
        self.assertNotEqual(self.fake_device_handler.link_type, 'potato')
        self.assertNotEqual(self.fake_device_handler.link_config, {'mium': 'mium'})
        self.fake_device_handler.reject_link_config = False

        # Missing link_config
        req = {
            'cmd': 'set_link_config',
            'link_type': 'potato'
        }
        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_is_error(response)

        # Missing link_type
        req = {
            'cmd': 'set_link_config',
            'link_config': {}
        }
        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_is_error(response)

        # Missing 2 fields
        req = {
            'cmd': 'set_link_config'
        }
        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_is_error(response)

    def test_write_watchable(self):
        entries = self.make_dummy_entries(10, entry_type=WatchableType.Variable, prefix='var')
        self.datastore.add_entries(entries)

        subscribed_entry1 = entries[2]
        subscribed_entry2 = entries[5]
        req = {
            'cmd': 'subscribe_watchable',
            'watchables': [subscribed_entry1.get_display_path(), subscribed_entry2.get_display_path()]
        }

        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        req = {
            'cmd': 'write_watchable',
            'updates': [
                {
                    'batch_index': 0,
                    'watchable': subscribed_entry1.get_id(),
                    'value': 1234
                },
                {
                    'batch_index': 1,
                    'watchable': subscribed_entry2.get_id(),
                    'value': 3.1415926
                }
            ]
        }

        self.assertIsNone(self.datastore.pop_target_update_request())
        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        self.assertIn(response['cmd'], 'response_write_watchable')
        self.assertIn('count', response)
        self.assertIn('request_token', response)
        self.assertIsInstance(response['request_token'], str)
        self.assertGreater(len(response['request_token']), 0)
        self.assertEqual(response['count'], 2)

        request_token = response['request_token']

        req1 = self.datastore.pop_target_update_request()
        req2 = self.datastore.pop_target_update_request()

        self.assertIsNotNone(req1)
        self.assertIsNotNone(req2)

        # Expect them to be in order.
        self.assertEqual(req1.get_value(), 1234)
        self.assertEqual(req2.get_value(), 3.1415926)

        req1.complete(True)
        req2.complete(False)

        for i in range(2):
            response = self.wait_and_load_response()
            self.assert_no_error(response, 'i=%d' % i)

            self.assertEqual(response['cmd'], 'inform_write_completion', 'i=%d' % i)
            self.assertIn('watchable', response, 'i=%d' % i)
            self.assertIn('success', response, 'i=%d' % i)
            self.assertIn('request_token', response, 'i=%d' % i)
            self.assertIn('completion_server_time_us', response, 'i=%d' % i)

            if response['watchable'] == subscribed_entry1.get_id():
                self.assertEqual(response['success'], True, 'i=%d' % i)
                self.assertEqual(response['request_token'], request_token, 'i=%d' % i)
                self.assertEqual(response['completion_server_time_us'], req1.get_completion_server_time_us(), 'i=%d' % i)
            elif response['watchable'] == subscribed_entry2.get_id():
                self.assertEqual(response['success'], False, 'i=%d' % i)
                self.assertEqual(response['request_token'], request_token, 'i=%d' % i)
                self.assertEqual(response['completion_server_time_us'], req2.get_completion_server_time_us(), 'i=%d' % i)

    def test_subscribe_watchable_bad_ID(self):
        req = {
            'cmd': 'subscribe_watchable',
            'reqid': 123,
            'watchables': ['qwerty']
        }

        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_is_error(response)
        self.assertEqual(response['reqid'], 123)

    def test_write_watchable_bad_ID(self):
        req = {
            'cmd': 'write_watchable',
            'reqid': 555,
            'updates': [
                {
                    'batch_index': 0,
                    'watchable': 'qwerty',
                    'value': 1234
                }
            ]
        }

        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_is_error(response)
        self.assertEqual(response['reqid'], 555)

    def test_write_watchable_not_subscribed(self):
        entries = self.make_dummy_entries(1, entry_type=WatchableType.Variable, prefix='var')
        self.datastore.add_entries(entries)

        req = {
            'cmd': 'write_watchable',
            'reqid': 555,
            'updates': [
                {
                    'batch_index': 0,
                    'watchable': entries[0].get_id(),
                    'value': 1234
                }
            ]
        }

        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_is_error(response)
        self.assertEqual(response['reqid'], 555)

    def test_write_watchable_bad_values(self):
        varf32 = Variable('dummyf32', vartype=EmbeddedDataType.float32, path_segments=[
                          'a', 'b', 'c'], location=0x12345678, endianness=Endianness.Little)
        vars32 = Variable('dummys32', vartype=EmbeddedDataType.sint32, path_segments=[
                          'a', 'b', 'c'], location=0x12345678, endianness=Endianness.Little)
        varu32 = Variable('dummyu32', vartype=EmbeddedDataType.uint32, path_segments=[
                          'a', 'b', 'c'], location=0x12345678, endianness=Endianness.Little)
        varbool = Variable('dummybool', vartype=EmbeddedDataType.boolean, path_segments=[
                           'a', 'b', 'c'], location=0x12345678, endianness=Endianness.Little)

        entryf32 = DatastoreVariableEntry(varf32.name, variable_def=varf32)
        entrys32 = DatastoreVariableEntry(vars32.name, variable_def=vars32)
        entryu32 = DatastoreVariableEntry(varu32.name, variable_def=varu32)
        entrybool = DatastoreVariableEntry(varbool.name, variable_def=varbool)

        alias_f32 = Alias("alias_f32", target="xxx", target_type=WatchableType.Variable, gain=2.0, offset=-10, min=-100, max=100)
        alias_u32 = Alias("alias_u32", target="xxx", target_type=WatchableType.Variable, gain=2.0,
                          offset=-10, min=-100, max=100)  # Notice the min that can go oob
        alias_s32 = Alias("alias_s32", target="xxx", target_type=WatchableType.Variable, gain=2.0, offset=-10, min=-100, max=100)
        entry_alias_f32 = DatastoreAliasEntry(alias_f32, entryf32)
        entry_alias_u32 = DatastoreAliasEntry(alias_u32, entryu32)
        entry_alias_s32 = DatastoreAliasEntry(alias_s32, entrys32)

        entries: List[DatastoreEntry] = [entryf32, entrys32, entryu32, entrybool, entry_alias_f32, entry_alias_u32, entry_alias_s32]
        self.datastore.add_entries(entries)

        req = {
            'cmd': 'subscribe_watchable',
            'watchables': [entry.get_display_path() for entry in entries]
        }

        self.send_request(req, 0)
        response = self.wait_and_load_response()
        self.assert_no_error(response)

        class TestCaseDef(TypedDict, total=False):
            inval: Any
            outval: Any
            valid: bool
            exceptions: Dict[DatastoreEntry, Any]

        testcases: List[TestCaseDef] = [
            dict(inval=math.nan, valid=False),
            dict(inval=None, valid=False),
            dict(inval="asdasd", valid=False),

            dict(inval=int(123), valid=True, outval=int(123)),
            dict(inval="1234", valid=True, outval=1234),
            dict(inval="-2000.2", valid=True, outval=-2000.2),
            dict(inval="0x100", valid=True, outval=256),
            dict(inval="-0x100", valid=True, outval=-256),
            dict(inval=-1234.2, valid=True, outval=-1234.2),
            dict(inval=True, valid=True, outval=True),
            dict(inval="true", valid=True, outval=True),

        ]

        reqid = 0
        # The job of the API is to parse the request. Not interpret the data.
        # So we want the data to reach the datastore entry, but without conversion.
        # Value conversion and validation is done by the memory writer.

        for entry in entries:
            for testcase in testcases:
                reqid += 1
                req = {
                    'cmd': 'write_watchable',
                    'reqid': reqid,
                    'updates': [
                        {
                            'batch_index': 0,
                            'watchable': entry.get_id(),
                            'value': testcase['inval']
                        }
                    ]
                }

                self.send_request(req)
                response = self.wait_and_load_response()
                error_msg = "Reqid = %d. Entry=%s.  Testcase=%s" % (reqid, entry.get_display_path(), testcase)
                if not testcase['valid']:
                    self.assert_is_error(response, error_msg)
                    self.assertFalse(self.datastore.has_pending_target_update())
                else:
                    self.assert_no_error(response, error_msg)
                    self.assertTrue(self.datastore.has_pending_target_update())
                    update_request = self.datastore.pop_target_update_request()
                    if isinstance(entry, DatastoreAliasEntry):
                        self.assertIs(update_request.entry, entry.refentry)
                        self.assertEqual(update_request.get_value(), entry.aliasdef.compute_user_to_device(testcase['outval']), error_msg)
                    else:
                        self.assertEqual(update_request.get_value(), testcase['outval'], error_msg)
                    self.assertFalse(self.datastore.has_pending_target_update())

    def test_read_memory(self):
        read_size = 256
        read_address = 0x1000

        req = {
            'cmd': 'read_memory',
            "address": read_address,
            "size": read_size
        }

        self.send_request(req, 0)
        response = cast(api_typing.S2C.ReadMemory, self.wait_and_load_response())
        self.assert_no_error(response)

        self.assertEqual(response['cmd'], 'response_read_memory')
        self.assertIn('request_token', response)
        request_token = response['request_token']
        self.assertFalse(self.fake_device_handler.read_memory_queue.empty())
        read_request = self.fake_device_handler.read_memory_queue.get()
        self.assertTrue(self.fake_device_handler.read_memory_queue.empty())
        self.assertEqual(read_request.address, read_address)
        self.assertEqual(read_request.size, read_size)
        self.assertIsNotNone(read_request.completion_callback)
        payload = bytes([random.randint(0, 255) for x in range(read_request.size)])
        read_request.completion_callback(read_request, True, 1234.2, payload, "")

        response = cast(api_typing.S2C.ReadMemoryComplete, self.wait_and_load_response())
        self.assertIn('request_token', response)
        self.assertIn('data', response)
        self.assertIn('success', response)
        self.assertIn('request_token', response)
        self.assertIn('completion_server_time_us', response)
        self.assertEqual(response['cmd'], "inform_memory_read_complete")
        self.assertEqual(response['request_token'], request_token)
        self.assertEqual(response['success'], True)
        self.assertEqual(response['completion_server_time_us'], 1234.2)
        self.assertEqual(response['data'], b64encode(payload).decode('ascii'))

    def test_read_memory_failure(self):
        read_size = 256
        read_address = 0x1000

        req = {
            'cmd': 'read_memory',
            "address": read_address,
            "size": read_size
        }

        self.send_request(req, 0)
        response = cast(api_typing.S2C.ReadMemory, self.wait_and_load_response())
        self.assert_no_error(response)

        self.assertEqual(response['cmd'], 'response_read_memory')
        self.assertIn('request_token', response)
        request_token = response['request_token']
        self.assertFalse(self.fake_device_handler.read_memory_queue.empty())
        read_request = self.fake_device_handler.read_memory_queue.get()
        self.assertTrue(self.fake_device_handler.read_memory_queue.empty())
        self.assertEqual(read_request.address, read_address)
        self.assertEqual(read_request.size, read_size)
        self.assertIsNotNone(read_request.completion_callback)

        read_request.completion_callback(read_request, False, 1234.2, None, "")  # Simulate failure

        response = cast(api_typing.S2C.ReadMemoryComplete, self.wait_and_load_response())
        self.assertIn('request_token', response)
        self.assertIn('data', response)
        self.assertIn('success', response)
        self.assertIn('request_token', response)
        self.assertIn('completion_server_time_us', response)
        self.assertEqual(response['cmd'], "inform_memory_read_complete")
        self.assertEqual(response['request_token'], request_token)
        self.assertEqual(response['success'], False)
        self.assertEqual(response['completion_server_time_us'], 1234.2)
        self.assertIsNone(response['data'])

    def test_read_memory_bad_values(self):
        self.send_request({
            'cmd': 'read_memory'
        })
        self.assert_is_error(self.wait_and_load_response())

        self.send_request({
            'cmd': 'read_memory',
            "address": 0
        })
        self.assert_is_error(self.wait_and_load_response())

        self.send_request({
            'cmd': 'read_memory',
            "size": 100
        })
        self.assert_is_error(self.wait_and_load_response())

        for addr in [-1, "", None, 1.2]:
            self.send_request({
                'cmd': 'read_memory',
                "address": addr,
                "size": 100
            })
            self.assert_is_error(self.wait_and_load_response())

        for size in [-1, "", None, 1.2]:
            self.send_request({
                'cmd': 'read_memory',
                "address": 100,
                "size": size
            })
            self.assert_is_error(self.wait_and_load_response())

    def test_write_memory(self):
        payload = bytes([random.randint(0, 255) for i in range(256)])
        write_address = 0x1000

        req = {
            'cmd': 'write_memory',
            "address": write_address,
            "data": b64encode(payload).decode('ascii')
        }

        self.send_request(req, 0)
        response = cast(api_typing.S2C.WriteMemory, self.wait_and_load_response())
        self.assert_no_error(response)

        self.assertEqual(response['cmd'], 'response_write_memory')
        self.assertIn('request_token', response)
        request_token = response['request_token']
        self.assertFalse(self.fake_device_handler.write_memory_queue.empty())
        write_request = self.fake_device_handler.write_memory_queue.get()
        self.assertTrue(self.fake_device_handler.write_memory_queue.empty())
        self.assertEqual(write_request.address, write_address)
        self.assertEqual(write_request.data, payload)
        self.assertIsNotNone(write_request.completion_callback)
        write_request.completion_callback(write_request, True, 3.14159, "")

        response = cast(api_typing.S2C.WriteMemoryComplete, self.wait_and_load_response())
        self.assertIn('request_token', response)
        self.assertIn('success', response)
        self.assertIn('completion_server_time_us', response)
        self.assertIn('request_token', response)
        self.assertEqual(response['cmd'], "inform_memory_write_complete")
        self.assertEqual(response['request_token'], request_token)
        self.assertEqual(response['success'], True)
        self.assertEqual(response['completion_server_time_us'], 3.14159)

    def test_write_memory_failure(self):
        payload = bytes([random.randint(0, 255) for i in range(256)])
        write_address = 0x1000

        req = {
            'cmd': 'write_memory',
            "address": write_address,
            "data": b64encode(payload).decode('ascii')
        }

        self.send_request(req, 0)
        response = cast(api_typing.S2C.WriteMemory, self.wait_and_load_response())
        self.assert_no_error(response)

        self.assertEqual(response['cmd'], 'response_write_memory')
        self.assertIn('request_token', response)
        request_token = response['request_token']
        self.assertFalse(self.fake_device_handler.write_memory_queue.empty())
        write_request = self.fake_device_handler.write_memory_queue.get()
        self.assertTrue(self.fake_device_handler.write_memory_queue.empty())
        self.assertEqual(write_request.address, write_address)
        self.assertEqual(write_request.data, payload)
        self.assertIsNotNone(write_request.completion_callback)

        write_request.completion_callback(write_request, False, 3.14159, "")  # Simulate failure

        response = cast(api_typing.S2C.WriteMemoryComplete, self.wait_and_load_response())
        self.assertIn('request_token', response)
        self.assertIn('success', response)
        self.assertIn('request_token', response)
        self.assertIn('completion_server_time_us', response)
        self.assertEqual(response['cmd'], "inform_memory_write_complete")
        self.assertEqual(response['request_token'], request_token)
        self.assertEqual(response['success'], False)
        self.assertEqual(response['completion_server_time_us'], 3.14159)

    def test_write_memory_bad_values(self):
        self.send_request({
            'cmd': 'write_memory'
        })
        self.assert_is_error(self.wait_and_load_response())

        self.send_request({
            'cmd': 'write_memory',
            "address": 0
        })
        self.assert_is_error(self.wait_and_load_response())

        self.send_request({
            'cmd': 'write_memory',
            "data": b64encode(bytes([1, 2, 3])).decode('ascii')
        })
        self.assert_is_error(self.wait_and_load_response())

        for addr in [-1, "", None, 1.2]:
            self.send_request({
                'cmd': 'write_memory',
                "address": addr,
                "data": b64encode(bytes([1, 2, 3])).decode('ascii')
            })
            self.assert_is_error(self.wait_and_load_response())

        for data in [1, "", None, 1.2, b64encode(bytes()).decode('ascii')]:
            self.send_request({
                'cmd': 'write_memory',
                "address": 100,
                "data": data
            })
            self.assert_is_error(self.wait_and_load_response())

# region Datalogging

# REQUEST_ACQUISITION

    def test_get_device_info_datalogging(self):
        # Check that we can read the datalogging capabilities
        self.fake_device_handler.set_connection_status(DeviceHandler.ConnectionStatus.CONNECTED_READY)
        self.wait_and_load_inform_server_status()
        req: api_typing.C2S.GetDeviceInfo = {
            'cmd': 'get_device_info'
        }

        datalogging_device_setup = device_datalogging.DataloggingSetup(
            buffer_size=256,
            encoding=device_datalogging.Encoding.RAW,
            max_signal_count=32
        )

        self.fake_device_handler.set_datalogging_setup(datalogging_device_setup)

        self.send_request(req)
        response = cast(api_typing.S2C.GetDeviceInfo, self.wait_and_load_response())
        self.assert_no_error(response)
        self.assertEqual(response['cmd'], 'response_get_device_info')

        self.assertTrue(response['available'])
        self.assertIn('device_info', response)
        info = response['device_info']
        datalogging_capabilities = info['datalogging_capabilities']
        self.assertIsNotNone(datalogging_capabilities)
        self.assertEqual(datalogging_capabilities['buffer_size'], 256)
        self.assertEqual(datalogging_capabilities['encoding'], 'raw')
        self.assertEqual(datalogging_capabilities['max_nb_signal'], 32)

        self.assertEqual(len(datalogging_capabilities['sampling_rates']), 3)
        self.assertEqual(datalogging_capabilities['sampling_rates'][0]['identifier'], 0)
        self.assertEqual(datalogging_capabilities['sampling_rates'][0]['name'], 'Fixed Freq 1KHz')
        self.assertEqual(datalogging_capabilities['sampling_rates'][0]['frequency'], 1000)
        self.assertEqual(datalogging_capabilities['sampling_rates'][0]['type'], 'fixed_freq')

        self.assertEqual(datalogging_capabilities['sampling_rates'][1]['identifier'], 1)
        self.assertEqual(datalogging_capabilities['sampling_rates'][1]['name'], 'Fixed Freq 10KHz')
        self.assertEqual(datalogging_capabilities['sampling_rates'][1]['frequency'], 10000)
        self.assertEqual(datalogging_capabilities['sampling_rates'][1]['type'], 'fixed_freq')

        self.assertEqual(datalogging_capabilities['sampling_rates'][2]['identifier'], 2)
        self.assertEqual(datalogging_capabilities['sampling_rates'][2]['name'], 'Variable Freq')
        self.assertEqual(datalogging_capabilities['sampling_rates'][2]['frequency'], None)
        self.assertEqual(datalogging_capabilities['sampling_rates'][2]['type'], 'variable_freq')

        self.fake_device_handler.set_datalogging_setup(None)

        self.send_request(req)
        response = cast(api_typing.S2C.GetDeviceInfo, self.wait_and_load_response())
        self.assertIsNotNone(response['device_info'])
        self.assertIsNone(response['device_info']['datalogging_capabilities'])

    def test_list_datalogging_acquisition(self):
        # Check that we can read the list of acquisition in datalogging storage
        with SFDStorage.use_temp_folder():
            sfd1 = SFDStorage.install(get_artifact('test_sfd_1.sfd'), ignore_exist=True)
            sfd2 = SFDStorage.install(get_artifact('test_sfd_2.sfd'), ignore_exist=True)

            dtnow = datetime.now()
            with DataloggingStorage.use_temp_storage():
                acq1 = core_datalogging.DataloggingAcquisition(firmware_id=sfd1.get_firmware_id_ascii(),
                                                               reference_id="refid1", name="foo",
                                                               acq_time=datetime.fromtimestamp(dtnow.timestamp() + 4000))  # Newest
                acq2 = core_datalogging.DataloggingAcquisition(firmware_id=sfd1.get_firmware_id_ascii(),
                                                               reference_id="refid2", name="bar",
                                                               acq_time=datetime.fromtimestamp(dtnow.timestamp() + 3000))
                acq3 = core_datalogging.DataloggingAcquisition(firmware_id=sfd2.get_firmware_id_ascii(),
                                                               reference_id="refid3", name="baz",
                                                               acq_time=datetime.fromtimestamp(dtnow.timestamp() + 2000))
                acq4 = core_datalogging.DataloggingAcquisition(firmware_id="unknown_sfd",
                                                               reference_id="refid4", name="meow",
                                                               acq_time=datetime.fromtimestamp(dtnow.timestamp() + 1000))  # Oldest
                acq1.set_xdata(core_datalogging.DataSeries())
                acq2.set_xdata(core_datalogging.DataSeries())
                acq3.set_xdata(core_datalogging.DataSeries())
                acq4.set_xdata(core_datalogging.DataSeries())

                DataloggingStorage.save(acq1)
                DataloggingStorage.save(acq2)
                DataloggingStorage.save(acq3)
                DataloggingStorage.save(acq4)

                req: api_typing.C2S.ListDataloggingAcquisitions = {
                    'cmd': 'list_datalogging_acquisitions',
                    'count': 100
                }

                self.send_request(req)
                response = cast(api_typing.S2C.ListDataloggingAcquisition, self.wait_and_load_response())
                self.assert_no_error(response)
                self.assertEqual(response['cmd'], 'response_list_datalogging_acquisitions')
                self.assertEqual(len(response['acquisitions']), 4)
                self.assertEqual(response['acquisitions'][0]['firmware_id'], sfd1.get_firmware_id_ascii())
                self.assertEqual(response['acquisitions'][0]['reference_id'], 'refid1')
                self.assertEqual(response['acquisitions'][0]['timestamp'], int(acq1.acq_time.timestamp()))
                self.assertEqual(response['acquisitions'][0]['name'], 'foo')
                self.assertEqual(response['acquisitions'][0]['firmware_metadata'], sfd1.get_metadata().to_dict())

                self.assertEqual(response['acquisitions'][1]['firmware_id'], sfd1.get_firmware_id_ascii())
                self.assertEqual(response['acquisitions'][1]['reference_id'], 'refid2')
                self.assertEqual(response['acquisitions'][1]['timestamp'], int(acq2.acq_time.timestamp()))
                self.assertEqual(response['acquisitions'][1]['name'], 'bar')
                self.assertEqual(response['acquisitions'][1]['firmware_metadata'], sfd1.get_metadata().to_dict())

                self.assertEqual(response['acquisitions'][2]['firmware_id'], sfd2.get_firmware_id_ascii())
                self.assertEqual(response['acquisitions'][2]['reference_id'], 'refid3')
                self.assertEqual(response['acquisitions'][2]['timestamp'], int(acq3.acq_time.timestamp()))
                self.assertEqual(response['acquisitions'][2]['name'], 'baz')
                self.assertEqual(response['acquisitions'][2]['firmware_metadata'], sfd2.get_metadata().to_dict())

                self.assertEqual(response['acquisitions'][3]['firmware_id'], "unknown_sfd")
                self.assertEqual(response['acquisitions'][3]['reference_id'], 'refid4')
                self.assertEqual(response['acquisitions'][3]['timestamp'], int(acq4.acq_time.timestamp()))
                self.assertEqual(response['acquisitions'][3]['name'], 'meow')
                self.assertEqual(response['acquisitions'][3]['firmware_metadata'], None)

                req: api_typing.C2S.ListDataloggingAcquisitions = {
                    'cmd': 'list_datalogging_acquisitions',
                    'count': 2
                }

                self.send_request(req)
                response = cast(api_typing.S2C.ListDataloggingAcquisition, self.wait_and_load_response())
                self.assert_no_error(response)

                self.assertEqual(len(response['acquisitions']), 2)
                self.assertEqual(response['acquisitions'][0]['reference_id'], 'refid1')
                self.assertEqual(response['acquisitions'][1]['reference_id'], 'refid2')

                req: api_typing.C2S.ListDataloggingAcquisitions = {
                    'cmd': 'list_datalogging_acquisitions',
                    'before_timestamp': int(dtnow.timestamp() + 2001),
                    'count': 100
                }

                self.send_request(req)
                response = cast(api_typing.S2C.ListDataloggingAcquisition, self.wait_and_load_response())
                self.assert_no_error(response)

                self.assertEqual(len(response['acquisitions']), 2)
                self.assertEqual(response['acquisitions'][0]['reference_id'], 'refid3')
                self.assertEqual(response['acquisitions'][1]['reference_id'], 'refid4')

                req: api_typing.C2S.ListDataloggingAcquisitions = {
                    'cmd': 'list_datalogging_acquisitions',
                    'firmware_id': sfd1.get_firmware_id_ascii(),
                    'count': 100
                }

                self.send_request(req)
                response = cast(api_typing.S2C.ListDataloggingAcquisition, self.wait_and_load_response())
                self.assert_no_error(response)
                self.assertEqual(response['cmd'], 'response_list_datalogging_acquisitions')
                self.assertIn('acquisitions', response)
                self.assertEqual(len(response['acquisitions']), 2)
                self.assertEqual(response['acquisitions'][0]['firmware_id'], sfd1.get_firmware_id_ascii())
                self.assertEqual(response['acquisitions'][0]['reference_id'], 'refid1')
                self.assertEqual(response['acquisitions'][0]['timestamp'], int(acq1.acq_time.timestamp()))
                self.assertEqual(response['acquisitions'][0]['name'], 'foo')
                self.assertEqual(response['acquisitions'][0]['firmware_metadata'], sfd1.get_metadata().to_dict())

                self.assertEqual(response['acquisitions'][1]['firmware_id'], sfd1.get_firmware_id_ascii())
                self.assertEqual(response['acquisitions'][1]['reference_id'], 'refid2')
                self.assertEqual(response['acquisitions'][1]['timestamp'], int(acq2.acq_time.timestamp()))
                self.assertEqual(response['acquisitions'][1]['name'], 'bar')
                self.assertEqual(response['acquisitions'][1]['firmware_metadata'], sfd1.get_metadata().to_dict())

                req: api_typing.C2S.ListDataloggingAcquisitions = {
                    'cmd': 'list_datalogging_acquisitions',
                    'firmware_id': None,
                    'count': 100
                }

                self.send_request(req)
                response = cast(api_typing.S2C.ListDataloggingAcquisition, self.wait_and_load_response())
                self.assert_no_error(response)
                self.assertEqual(response['cmd'], 'response_list_datalogging_acquisitions')
                self.assertEqual(len(response['acquisitions']), 4)

                req: api_typing.C2S.ListDataloggingAcquisitions = {
                    'cmd': 'list_datalogging_acquisitions',
                    'firmware_id': 'inexistant_id',
                    'count': 100
                }

                self.send_request(req)
                response = cast(api_typing.S2C.ListDataloggingAcquisition, self.wait_and_load_response())
                self.assert_no_error(response)
                self.assertEqual(response['cmd'], 'response_list_datalogging_acquisitions')
                self.assertEqual(len(response['acquisitions']), 0)

                # Missing count - bad
                req: api_typing.C2S.ListDataloggingAcquisitions = {
                    'cmd': 'list_datalogging_acquisitions',
                    'firmware_id': 'inexistant_id'
                }
                self.send_request(req)
                self.assert_is_error(self.wait_and_load_response())

                # Bad timestamp
                req: api_typing.C2S.ListDataloggingAcquisitions = {
                    'cmd': 'list_datalogging_acquisitions',
                    'firmware_id': 'inexistant_id',
                    'before_timestamp': -1,
                    'count': 100
                }
                self.send_request(req)
                self.assert_is_error(self.wait_and_load_response())

                # Bad count
                req: api_typing.C2S.ListDataloggingAcquisitions = {
                    'cmd': 'list_datalogging_acquisitions',
                    'firmware_id': 'inexistant_id',
                    'count': -1
                }
                self.send_request(req)
                self.assert_is_error(self.wait_and_load_response())

                # timestamp None = no timestamp. OK
                req: api_typing.C2S.ListDataloggingAcquisitions = {
                    'cmd': 'list_datalogging_acquisitions',
                    'firmware_id': 'inexistant_id',
                    'before_timestamp': None,
                    'count': 100
                }
                self.send_request(req)
                self.assert_no_error(self.wait_and_load_response())

                req: api_typing.C2S.ListDataloggingAcquisitions = {
                    'cmd': 'list_datalogging_acquisitions',
                    'reference_id': 'inexistant_id'
                }
                self.send_request(req)
                response = self.wait_and_load_response()
                self.assert_no_error(response)
                self.assertEqual(len(response['acquisitions']), 0)

                req: api_typing.C2S.ListDataloggingAcquisitions = {
                    'cmd': 'list_datalogging_acquisitions',
                    'reference_id': 'refid2'
                }
                self.send_request(req)
                response = self.wait_and_load_response()
                self.assert_no_error(response)
                self.assertEqual(len(response['acquisitions']), 1)

                self.assertEqual(response['acquisitions'][0]['firmware_id'], sfd1.get_firmware_id_ascii())
                self.assertEqual(response['acquisitions'][0]['reference_id'], 'refid2')
                self.assertEqual(response['acquisitions'][0]['timestamp'], int(acq2.acq_time.timestamp()))
                self.assertEqual(response['acquisitions'][0]['name'], 'bar')
                self.assertEqual(response['acquisitions'][0]['firmware_metadata'], sfd1.get_metadata().to_dict())

    def test_update_datalogging_acquisition(self):
        # Rename an acquisition in datalogging storage through API
        with DataloggingStorage.use_temp_storage():
            watchable1 = core_datalogging.LoggedWatchable(path='/a/b/c', type=WatchableType.Variable)
            watchable2 = core_datalogging.LoggedWatchable(path='/a/b/d', type=WatchableType.Alias)
            watchable3 = core_datalogging.LoggedWatchable(path='/a/b/e', type=WatchableType.RuntimePublishedValue)
            axis1 = core_datalogging.AxisDefinition('Axis1', 0)
            axis2 = core_datalogging.AxisDefinition('Axis2', 1)
            acq1 = core_datalogging.DataloggingAcquisition(firmware_id='some_firmware_id', reference_id="refid1", name="foo")
            acq1.set_xdata(core_datalogging.DataSeries())
            acq1.add_data(core_datalogging.DataSeries(name="ds1", logged_watchable=watchable1), axis1)
            acq1.add_data(core_datalogging.DataSeries(name="ds2", logged_watchable=watchable2), axis1)
            acq1.add_data(core_datalogging.DataSeries(name="ds3", logged_watchable=watchable3), axis2)
            acq2 = core_datalogging.DataloggingAcquisition(firmware_id='some_firmware_id', reference_id="refid2", name="bar")
            acq2.set_xdata(core_datalogging.DataSeries(name="ds4"))
            acq3 = core_datalogging.DataloggingAcquisition(firmware_id='some_firmware_id', reference_id="refid3", name="baz")
            acq3.set_xdata(core_datalogging.DataSeries(name="ds5"))
            DataloggingStorage.save(acq1)
            DataloggingStorage.save(acq2)
            DataloggingStorage.save(acq3)

            req: api_typing.C2S.UpdateDataloggingAcquisition = {
                'cmd': 'update_datalogging_acquisition',
                'reference_id': 'refid2',
                'name': 'new_name!'
            }

            self.send_request(req)
            expected_response = {
                API.Command.Api2Client.UPDATE_DATALOGGING_ACQUISITION_RESPONSE: None,
                API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED: None
            }
            for i in range(2):
                response = self.wait_and_load_response()
                self.assert_no_error(response)
                expected_response[response['cmd']] = True
                if response['cmd'] == API.Command.Api2Client.UPDATE_DATALOGGING_ACQUISITION_RESPONSE:
                    response = cast(api_typing.S2C.UpdateDataloggingAcquisition, response)
                    acq2_reloaded = DataloggingStorage.read('refid2')
                    self.assertEqual(acq2_reloaded.name, 'new_name!')
                    self.assertEqual(acq2_reloaded.firmware_id, acq2.firmware_id)
                    self.assertLess((acq2_reloaded.acq_time - acq2.acq_time).total_seconds(), 1)
                elif response['cmd'] == API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED:
                    response = cast(api_typing.S2C.InformDataloggingListChanged, response)
                    self.assertEqual(response['action'], 'update')
                    self.assertEqual(response['reference_id'], 'refid2')
                else:
                    raise ValueError('Unexpected response %s' % response)

            for k in expected_response:
                self.assertIsNotNone(expected_response[k])

            req: api_typing.C2S.UpdateDataloggingAcquisition = {
                'cmd': 'update_datalogging_acquisition',
                'reference_id': 'refid1',
                'axis_name': [{'id': 0, 'name': 'NewAxis1Name'}]
            }

            self.send_request(req)
            expected_response = {
                API.Command.Api2Client.UPDATE_DATALOGGING_ACQUISITION_RESPONSE: None,
                API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED: None
            }
            for i in range(2):
                response = self.wait_and_load_response()
                self.assert_no_error(response)
                expected_response[response['cmd']] = True
                if response['cmd'] == API.Command.Api2Client.UPDATE_DATALOGGING_ACQUISITION_RESPONSE:
                    response = cast(api_typing.S2C.UpdateDataloggingAcquisition, response)
                    acq1_reloaded = DataloggingStorage.read('refid1')
                    acq_data = acq1_reloaded.get_data()
                    self.assertEqual(len(acq_data), 3)

                    # Datalogging Storage is expected to return data series in the same order as written
                    self.assertEqual(acq_data[0].axis.name, 'NewAxis1Name')
                    self.assertEqual(acq_data[1].axis.name, 'NewAxis1Name')
                    self.assertEqual(acq_data[2].axis.name, 'Axis2')
                    self.assertEqual(acq1_reloaded.firmware_id, acq2.firmware_id)
                    self.assertLess((acq1_reloaded.acq_time - acq2.acq_time).total_seconds(), 1)
                elif response['cmd'] == API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED:
                    response = cast(api_typing.S2C.InformDataloggingListChanged, response)
                    self.assertEqual(response['action'], 'update')
                    self.assertEqual(response['reference_id'], 'refid1')
                else:
                    raise ValueError('Unexpected response %s' % response)

            for k in expected_response:
                self.assertIsNotNone(expected_response[k])

            req: api_typing.C2S.UpdateDataloggingAcquisition = {
                'cmd': 'update_datalogging_acquisition',
                'reference_id': 'bad_ref_id',
                'name': 'meow'
            }

            self.send_request(req)
            self.assert_is_error(self.wait_and_load_response())

    def test_delete_datalogging_acquisition(self):
        with DataloggingStorage.use_temp_storage():
            acq1 = core_datalogging.DataloggingAcquisition(firmware_id='some_firmware_id', reference_id="refid1", name="foo")
            acq1.set_xdata(core_datalogging.DataSeries())
            acq2 = core_datalogging.DataloggingAcquisition(firmware_id='some_firmware_id', reference_id="refid2", name="bar")
            acq2.set_xdata(core_datalogging.DataSeries())
            acq3 = core_datalogging.DataloggingAcquisition(firmware_id='some_firmware_id', reference_id="refid3", name="baz")
            acq3.set_xdata(core_datalogging.DataSeries())
            DataloggingStorage.save(acq1)
            DataloggingStorage.save(acq2)
            DataloggingStorage.save(acq3)

            self.assertEqual(DataloggingStorage.count(), 3)
            req: api_typing.C2S.DeleteDataloggingAcquisition = {
                'cmd': 'delete_datalogging_acquisition',
                'reference_id': 'refid2',
            }
            acq_count_before = DataloggingStorage.count()
            self.send_request(req)

            timeout = 5
            t = time.perf_counter()
            while time.perf_counter() - t < timeout:
                self.process_all()
                if DataloggingStorage.count() != acq_count_before:
                    break
            if acq_count_before == DataloggingStorage.count():
                raise Exception("Failed to delete the acquisition")

            expected_response = {
                API.Command.Api2Client.DELETE_DATALOGGING_ACQUISITION_RESPONSE: None,
                API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED: None
            }
            for i in range(2):
                response = self.wait_and_load_response()
                self.assert_no_error(response)
                expected_response[response['cmd']] = True
                if response['cmd'] == API.Command.Api2Client.DELETE_DATALOGGING_ACQUISITION_RESPONSE:
                    response = cast(api_typing.S2C.DeleteDataloggingAcquisition, response)
                    self.assertEqual(DataloggingStorage.count(), 2)
                    with self.assertRaises(LookupError):
                        DataloggingStorage.read('refid2')

                    DataloggingStorage.read('refid1')
                    DataloggingStorage.read('refid3')
                elif response['cmd'] == API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED:
                    response = cast(api_typing.S2C.InformDataloggingListChanged, response)
                    self.assertEqual(response['action'], 'delete')
                    self.assertEqual(response['reference_id'], 'refid2')
                else:
                    raise ValueError('Unexpected response %s' % response)

            for k in expected_response:
                self.assertIsNotNone(expected_response[k])

            req: api_typing.C2S.DeleteDataloggingAcquisition = {
                'cmd': 'delete_datalogging_acquisition',
                'reference_id': 'bad_ref_id'
            }

            self.send_request(req)
            self.assert_is_error(self.wait_and_load_response())

    def test_delete_all_datalogging_acquisition(self):
        with DataloggingStorage.use_temp_storage():
            acq1 = core_datalogging.DataloggingAcquisition(firmware_id='some_firmware_id', reference_id="refid1", name="foo")
            acq1.set_xdata(core_datalogging.DataSeries())
            acq2 = core_datalogging.DataloggingAcquisition(firmware_id='some_firmware_id', reference_id="refid2", name="bar")
            acq2.set_xdata(core_datalogging.DataSeries())
            acq3 = core_datalogging.DataloggingAcquisition(firmware_id='some_firmware_id', reference_id="refid3", name="baz")
            acq3.set_xdata(core_datalogging.DataSeries())
            DataloggingStorage.save(acq1)
            DataloggingStorage.save(acq2)
            DataloggingStorage.save(acq3)

            self.assertEqual(DataloggingStorage.count(), 3)
            req: api_typing.C2S.DeleteDataloggingAcquisition = {
                'cmd': 'delete_all_datalogging_acquisition'
            }

            db_init_count = DataloggingStorage.get_init_count()
            self.send_request(req)
            t = time.perf_counter()
            timeout = 5
            while time.perf_counter() - t < timeout:
                self.process_all()
                if DataloggingStorage.get_init_count() != db_init_count:
                    break
            if db_init_count == DataloggingStorage.get_init_count():
                raise Exception("Failed to clear the database")

            expected_response = {
                API.Command.Api2Client.DELETE_ALL_DATALOGGING_ACQUISITION_RESPONSE: None,
                API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED: None
            }

            for i in range(2):
                response = self.wait_and_load_response()
                self.assert_no_error(response)
                expected_response[response['cmd']] = True
                if response['cmd'] == API.Command.Api2Client.DELETE_ALL_DATALOGGING_ACQUISITION_RESPONSE:
                    response = cast(api_typing.S2C.DeleteDataloggingAcquisition, response)
                    self.assertEqual(DataloggingStorage.count(), 0)
                elif response['cmd'] == API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED:
                    response = cast(api_typing.S2C.InformDataloggingListChanged, response)
                    self.assertEqual(response['action'], 'delete_all')
                else:
                    raise ValueError('Unexpected response %s' % response)

            for k in expected_response:
                self.assertIsNotNone(expected_response[k])

    def test_read_datalogging_acquisition_content(self):
        with DataloggingStorage.use_temp_storage():
            with SFDStorage.use_temp_folder():
                dummy_sfd1_filename = get_artifact('test_sfd_1.sfd')
                sfd1 = SFDStorage.install(dummy_sfd1_filename, ignore_exist=True)

                axis1 = core_datalogging.AxisDefinition(name="Axis1", axis_id=0)
                axis2 = core_datalogging.AxisDefinition(name="Axis2", axis_id=1)
                acq = core_datalogging.DataloggingAcquisition(firmware_id=sfd1.get_firmware_id_ascii(),
                                                              reference_id="refid1", name="foo", firmware_name="bar")

                acq.set_xdata(core_datalogging.DataSeries(
                    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
                    name='the x-axis',
                    logged_watchable=core_datalogging.LoggedWatchable(
                        path='/var/xaxis',
                        type=WatchableType.Variable)
                ))
                acq.add_data(core_datalogging.DataSeries(
                    [10, 20, 30, 40, 50, 60, 70, 80, 90],
                    name='series 1',
                    logged_watchable=core_datalogging.LoggedWatchable(
                        path='/var/data1',
                        type=WatchableType.Alias)
                ),
                    axis1)
                acq.add_data(core_datalogging.DataSeries(
                    [100, 200, 300, 400, 500, 600, 700, 800, 900],
                    name='series 2',
                    logged_watchable=core_datalogging.LoggedWatchable(
                        path='/var/data2',
                        type=WatchableType.RuntimePublishedValue)
                ), axis2)
                acq.set_trigger_index(3)
                DataloggingStorage.save(acq)

                req: api_typing.C2S.ReadDataloggingAcquisitionContent = {
                    'cmd': 'read_datalogging_acquisition_content',
                    'reference_id': 'refid1'
                }

                self.send_request(req)
                response = cast(api_typing.S2C.ReadDataloggingAcquisitionContent, self.wait_and_load_response())
                self.assert_no_error(response)
                self.assertEqual(response['cmd'], 'response_read_datalogging_acquisition_content')

                self.assertEqual(response['firmware_id'], sfd1.get_firmware_id_ascii())
                self.assertEqual(response['reference_id'], 'refid1')
                self.assertEqual(response['name'], 'foo')
                self.assertEqual(response['firmware_name'], "bar")
                self.assertEqual(len(response['signals']), 2)

                self.assertEqual(response['xdata']['name'], 'the x-axis')
                self.assertEqual(response['xdata']['data'], [0, 1, 2, 3, 4, 5, 6, 7, 8, 9])
                self.assertEqual(response['xdata']['watchable'], dict(path='/var/xaxis', type='var'))

                self.assertEqual(response['trigger_index'], 3)

                self.assertCountEqual(response['yaxes'], [dict(id=0, name="Axis1"), dict(id=1, name="Axis2")])

                all_series_name = [x['name'] for x in response['signals']]
                idx_series1 = all_series_name.index('series 1')
                idx_series2 = all_series_name.index('series 2')

                self.assertEqual(response['signals'][idx_series1]['name'], 'series 1')
                self.assertEqual(response['signals'][idx_series1]['data'], [10, 20, 30, 40, 50, 60, 70, 80, 90])
                self.assertEqual(response['signals'][idx_series1]['watchable'], dict(path='/var/data1', type='alias'))
                self.assertEqual(response['signals'][idx_series1]['axis_id'], 0)

                self.assertEqual(response['signals'][idx_series2]['name'], 'series 2')
                self.assertEqual(response['signals'][idx_series2]['data'], [100, 200, 300, 400, 500, 600, 700, 800, 900])
                self.assertEqual(response['signals'][idx_series2]['watchable'], dict(path='/var/data2', type='rpv'))
                self.assertEqual(response['signals'][idx_series2]['axis_id'], 1)

                req: api_typing.C2S.ReadDataloggingAcquisitionContent = {
                    'cmd': 'read_datalogging_acquisition',
                    'reference_id': 'bad_id'
                }

                self.send_request(req)
                response = cast(api_typing.S2C.ReadDataloggingAcquisitionContent, self.wait_and_load_response())
                self.assert_is_error(response)

    def send_request_datalogging_acquisition_and_fetch_result(self, req: api_typing.C2S.RequestDataloggingAcquisition) -> api_datalogging.AcquisitionRequest:
        self.send_request(req)
        request_token = None
        for i in range(3):
            response = self.wait_and_load_response()
            self.assert_no_error(response)
            self.assertIn(response['cmd'], [
                API.Command.Api2Client.INFORM_DATALOGGING_LIST_CHANGED,
                API.Command.Api2Client.REQUEST_DATALOGGING_ACQUISITION_RESPONSE,
                API.Command.Api2Client.INFORM_DATALOGGING_ACQUISITION_COMPLETE,
                API.Command.Api2Client.INFORM_SERVER_STATUS,
            ])

            if response['cmd'] == API.Command.Api2Client.REQUEST_DATALOGGING_ACQUISITION_RESPONSE:
                response = cast(api_typing.S2C.RequestDataloggingAcquisition, response)
                request_token = response['request_token']
            elif response['cmd'] == API.Command.Api2Client.INFORM_DATALOGGING_ACQUISITION_COMPLETE:
                response = cast(api_typing.S2C.InformDataloggingAcquisitionComplete, response)
                self.assertIsNotNone(request_token)
                self.assertEqual(response['request_token'], request_token)
                self.assertTrue(response['success'])

        self.assertFalse(self.fake_datalogging_manager.request_queue.empty())
        ar = self.fake_datalogging_manager.request_queue.get()
        self.assertTrue(self.fake_datalogging_manager.request_queue.empty())

        if self.connections[0].from_server_available():
            self.connections[0].read_from_server()

        return ar

    def test_request_datalogging_acquisition(self):
        self.fake_device_handler.set_connection_status(DeviceHandler.ConnectionStatus.CONNECTED_READY)
        with DataloggingStorage.use_temp_storage():

            var_entries: List[DatastoreVariableEntry] = self.make_dummy_entries(5, entry_type=WatchableType.Variable, prefix='var')
            rpv_entries: List[DatastoreRPVEntry] = self.make_dummy_entries(5, entry_type=WatchableType.RuntimePublishedValue, prefix='rpv')
            alias_entries_var: List[DatastoreAliasEntry] = self.make_dummy_entries(
                2, entry_type=WatchableType.Alias, prefix='alias_var_', alias_bucket=var_entries)
            alias_entries_rpv: List[DatastoreAliasEntry] = self.make_dummy_entries(
                3, entry_type=WatchableType.Alias, prefix='alias_rpv_', alias_bucket=rpv_entries)

            # Add entries in the datastore that we will reread through the API
            self.datastore.add_entries(var_entries)
            self.datastore.add_entries(rpv_entries)
            self.datastore.add_entries(alias_entries_var)
            self.datastore.add_entries(alias_entries_rpv)

            def create_default_request() -> api_typing.C2S.RequestDataloggingAcquisition:
                req: api_typing.C2S.RequestDataloggingAcquisition = {
                    'cmd': 'request_datalogging_acquisition',
                    'decimation': 100,
                    'probe_location': 0.7,
                    'sampling_rate_id': 1,
                    'timeout': 100.1,
                    'trigger_hold_time': 0.1,
                    'x_axis_type': 'ideal_time',
                    'condition': 'eq',
                    'yaxes': [dict(name="Axis1", id=0), dict(name="Axis2", id=100)],
                    'operands': [
                        dict(type='literal', value=123),
                        dict(type='watchable', value=var_entries[0].get_display_path())
                    ],
                    'signals': [
                        dict(path=var_entries[1].get_display_path(), name='var1', axis_id=0),
                        dict(path=alias_entries_var[0].get_display_path(), name='alias_var_1', axis_id=0),
                        dict(path=alias_entries_rpv[0].get_display_path(), name='alias_rpv_1', axis_id=100),
                        dict(path=rpv_entries[0].get_display_path(), name='rpv0', axis_id=100),
                    ]
                }
                return req

            req = create_default_request()
            ar = self.send_request_datalogging_acquisition_and_fetch_result(req)

            self.assertEqual(ar.decimation, 100)
            self.assertEqual(ar.probe_location, 0.7)
            self.assertEqual(ar.rate_identifier, 1)
            self.assertEqual(ar.timeout, 100.1)
            self.assertEqual(ar.trigger_hold_time, 0.1)
            self.assertEqual(ar.x_axis_type, api_datalogging.XAxisType.IdealTime)
            self.assertIsNone(ar.x_axis_signal)
            self.assertEqual(ar.trigger_condition.condition_id, api_datalogging.TriggerConditionID.Equal)
            self.assertCountEqual([x.name for x in ar.get_yaxis_list()], ["Axis1", "Axis2"])

            self.assertEqual(ar.trigger_condition.operands[0].type, api_datalogging.TriggerConditionOperandType.LITERAL)
            self.assertEqual(ar.trigger_condition.operands[0].value, 123)
            self.assertEqual(ar.trigger_condition.operands[1].type, api_datalogging.TriggerConditionOperandType.WATCHABLE)
            self.assertIs(ar.trigger_condition.operands[1].value, var_entries[0])

            self.assertIs(ar.signals[0].entry, var_entries[1])
            self.assertIs(ar.signals[1].entry, alias_entries_var[0])
            self.assertIs(ar.signals[2].entry, alias_entries_rpv[0])
            self.assertIs(ar.signals[3].entry, rpv_entries[0])

            self.assertEqual(ar.signals[0].name, 'var1')
            self.assertEqual(ar.signals[1].name, 'alias_var_1')
            self.assertEqual(ar.signals[2].name, 'alias_rpv_1')
            self.assertEqual(ar.signals[3].name, 'rpv0')

            yaxis_list = ar.get_yaxis_list()

            self.assertIn(ar.signals[0].axis, yaxis_list)
            self.assertIn(ar.signals[0].axis.name, "Axis1")
            self.assertIn(ar.signals[1].axis, yaxis_list)
            self.assertIn(ar.signals[1].axis.name, "Axis1")
            self.assertIn(ar.signals[2].axis, yaxis_list)
            self.assertIn(ar.signals[2].axis.name, "Axis2")
            self.assertIn(ar.signals[3].axis, yaxis_list)
            self.assertIn(ar.signals[3].axis.name, "Axis2")

            # conditions
            all_conditions = {
                'true': dict(condition_id=api_datalogging.TriggerConditionID.AlwaysTrue, nb_operands=0),
                'eq': dict(condition_id=api_datalogging.TriggerConditionID.Equal, nb_operands=2),
                'lt': dict(condition_id=api_datalogging.TriggerConditionID.LessThan, nb_operands=2),
                'let': dict(condition_id=api_datalogging.TriggerConditionID.LessOrEqualThan, nb_operands=2),
                'gt': dict(condition_id=api_datalogging.TriggerConditionID.GreaterThan, nb_operands=2),
                'get': dict(condition_id=api_datalogging.TriggerConditionID.GreaterOrEqualThan, nb_operands=2),
                'cmt': dict(condition_id=api_datalogging.TriggerConditionID.ChangeMoreThan, nb_operands=2),
                'within': dict(condition_id=api_datalogging.TriggerConditionID.IsWithin, nb_operands=3)
            }

            for api_cond in all_conditions:
                for nb_operand in range(all_conditions[api_cond]['nb_operands'] + 1):
                    req = create_default_request()
                    req['condition'] = api_cond
                    req['operands'] = []
                    for i in range(nb_operand):
                        req['operands'].append(dict(type='literal', value=i))
                    if nb_operand == all_conditions[api_cond]['nb_operands']:
                        ar = self.send_request_datalogging_acquisition_and_fetch_result(req)
                        self.assertEqual(ar.trigger_condition.condition_id, all_conditions[api_cond]['condition_id'])
                    else:
                        self.send_request(req)
                        self.assert_is_error(self.wait_and_load_response())

            req = create_default_request()
            req['condition'] = 'meow'
            self.send_request(req)
            self.assert_is_error(self.wait_and_load_response())

            # x axis
            # measured time ok
            req = create_default_request()
            req['x_axis_type'] = 'measured_time'
            ar = self.send_request_datalogging_acquisition_and_fetch_result(req)
            self.assertEqual(ar.x_axis_type, api_datalogging.XAxisType.MeasuredTime)
            self.assertIsNone(ar.x_axis_signal)

            req = create_default_request()
            req['x_axis_type'] = 'index'
            ar = self.send_request_datalogging_acquisition_and_fetch_result(req)
            self.assertEqual(ar.x_axis_type, api_datalogging.XAxisType.Indexed)
            self.assertIsNone(ar.x_axis_signal)

            # watchable ok
            req = create_default_request()
            req['x_axis_type'] = 'signal'
            req['x_axis_signal'] = dict(name="hello", path=rpv_entries[1].get_display_path())
            ar = self.send_request_datalogging_acquisition_and_fetch_result(req)
            self.assertEqual(ar.x_axis_type, api_datalogging.XAxisType.Signal)
            self.assertIs(ar.x_axis_signal.entry, rpv_entries[1])
            self.assertEqual(ar.x_axis_signal.name, 'hello')

            # watchable no name is ok
            req = create_default_request()
            req['x_axis_type'] = 'signal'
            req['x_axis_signal'] = dict(path=rpv_entries[1].get_display_path())
            ar = self.send_request_datalogging_acquisition_and_fetch_result(req)
            self.assertEqual(ar.x_axis_type, api_datalogging.XAxisType.Signal)
            self.assertIs(ar.x_axis_signal.entry, rpv_entries[1])
            self.assertEqual(ar.x_axis_signal.name, None)

            # watchable bad format
            req = create_default_request()
            req['x_axis_type'] = 'signal'
            req['x_axis_signal'] = "bad format"
            self.send_request(req)
            self.assert_is_error(self.wait_and_load_response())

            # watchable unknown ID
            req = create_default_request()
            req['x_axis_type'] = 'signal'
            req['x_axis_signal'] = dict(watchable='unknown_id')
            self.send_request(req)
            self.assert_is_error(self.wait_and_load_response())

            # watchable is missing
            req = create_default_request()
            req['x_axis_type'] = 'signal'
            self.send_request(req)
            self.assert_is_error(self.wait_and_load_response())

            # unknown type
            req = create_default_request()
            req['x_axis_type'] = 'meow'
            self.send_request(req)
            self.assert_is_error(self.wait_and_load_response())

            # unknown watchable
            req = create_default_request()
            req['signals'][0]['path'] = 'unknown_id'
            self.send_request(req)
            self.assert_is_error(self.wait_and_load_response())

            class Delete: pass
            delete = Delete()
            # Bad decimation
            for bad_decimation in ['meow', -1, 0, 1.5, None, [1], delete]:
                req = create_default_request()
                if bad_decimation == delete:
                    del req['decimation']
                else:
                    req['decimation'] = bad_decimation
                self.send_request(req)
                self.assert_is_error(self.wait_and_load_response(), msg=f"val={bad_decimation}")

            # Bad hold time
            for bad_hold_time in ['meow', -1, None, [1], (2**32) * 1e-7, delete]:  # max value
                req = create_default_request()
                if bad_hold_time == delete:
                    del req['trigger_hold_time']
                else:
                    req['trigger_hold_time'] = bad_hold_time
                self.send_request(req)
                self.assert_is_error(self.wait_and_load_response(), msg=f"val={bad_hold_time}")

            # Bad Timeout
            for bad_timeout in ['meow', -1, None, [1], (2**32) * 1e-7, delete]:
                req = create_default_request()
                if bad_timeout == delete:
                    del req['timeout']
                else:
                    req['timeout'] = bad_timeout
                self.send_request(req)
                self.assert_is_error(self.wait_and_load_response(), msg=f"val={bad_timeout}")

            # Bad Probe location
            for bad_probe_location in ['meow', -1, 1.1, 2, [1], delete]:
                req = create_default_request()
                if bad_probe_location == delete:
                    del req['probe_location']
                else:
                    req['probe_location'] = bad_probe_location
                self.send_request(req)
                self.assert_is_error(self.wait_and_load_response(), msg=f"val={bad_probe_location}")

            # Bad sampling rate
            for bad_rate_id in ['meow', -1, 11, 1.3, [1], delete]:   # Fake datalogging manager consider all sample rate id > 10 to be bad.
                req = create_default_request()
                if bad_rate_id == delete:
                    del req['sampling_rate_id']
                else:
                    req['sampling_rate_id'] = bad_rate_id
                self.send_request(req)
                self.assert_is_error(self.wait_and_load_response(), msg=f"val={bad_rate_id}")

            for bad_watchable_format in ['meow', -1, 11, [1]]:   # Fake datalogging manager consider all sample rate id > 10 to be bad.
                req = create_default_request()
                req['signals'][0] = bad_watchable_format
                self.send_request(req)
                self.assert_is_error(self.wait_and_load_response(), msg=f"val={bad_watchable_format}")

            for bad_axis_id in ['meow', -1, 1, [1], delete]:
                req = create_default_request()
                if bad_axis_id == delete:
                    del req['signals'][0]['axis_id']
                else:
                    req['signals'][0]['axis_id'] = bad_axis_id
                self.send_request(req)
                self.assert_is_error(self.wait_and_load_response(), msg=f"val={bad_axis_id}")

            for bad_signal_path in [-1, 1, [1], None, delete]:
                req = create_default_request()
                if bad_signal_path == delete:
                    del req['signals'][0]['path']
                else:
                    req['signals'][0]['path'] = bad_signal_path
                self.send_request(req)
                self.assert_is_error(self.wait_and_load_response(), msg=f"val={bad_signal_path}")

            for bad_signal_name in [-1, 1, [1]]:
                req = create_default_request()
                if bad_signal_name == delete:
                    del req['signals'][0]['name']
                else:
                    req['signals'][0]['name'] = bad_signal_name
                self.send_request(req)
                self.assert_is_error(self.wait_and_load_response(), msg=f"val={bad_signal_name}")

            for bad_axis_id in ['meow', 1.2, [1], delete]:
                req = create_default_request()
                if bad_axis_id == delete:
                    del req['yaxes'][0]['id']
                else:
                    req['yaxes'][0]['id'] = bad_axis_id
                self.send_request(req)
                self.assert_is_error(self.wait_and_load_response(), msg=f"val={bad_axis_id}")

            # duplicate id
            req = create_default_request()
            req['yaxes'][0]['id'] = req['yaxes'][1]['id']
            self.send_request(req)
            self.assert_is_error(self.wait_and_load_response())

            # ideal time on variable freq
            req = create_default_request()
            req['sampling_rate_id'] = 2  # 2 is variable in emulated device
            req['x_axis_type'] = 'ideal_time'
            self.send_request(req)
            self.assert_is_error(self.wait_and_load_response())

    def test_user_command(self):
        def base() -> api_typing.C2S.UserCommand:
            return {
                'cmd': 'user_command',
                'subfunction': 2,
                'data': b64encode(bytes([1, 2, 3, 4, 5])).decode('utf8')
            }

        req = base()

        self.send_request(req)
        response = self.wait_and_load_response()

        self.assertFalse(self.fake_device_handler.user_command_history_queue.empty())
        subfn, data = self.fake_device_handler.user_command_history_queue.get_nowait()
        self.assertTrue(self.fake_device_handler.user_command_history_queue.empty())
        self.assertEqual(subfn, 2)
        self.assertEqual(data, bytes([1, 2, 3, 4, 5]))

        self.assert_no_error(response)
        self.assertIn('cmd', response)
        self.assertIn('subfunction', response)
        self.assertIn('data', response)

        self.assertEqual(response['subfunction'], 2)
        self.assertEqual(b64decode(response['data']), bytes([10, 20, 30]))

        # Bad subfunction
        req['subfunction'] = 10  # unsupported
        self.send_request(req)
        response = self.wait_and_load_response()

        self.assertFalse(self.fake_device_handler.user_command_history_queue.empty())
        subfn, data = self.fake_device_handler.user_command_history_queue.get_nowait()
        self.assertTrue(self.fake_device_handler.user_command_history_queue.empty())
        self.assertEqual(subfn, 10)
        self.assertEqual(data, bytes([1, 2, 3, 4, 5]))
        self.assert_is_error(response)

        self.assertEqual(response['msg'], "Unsupported subfunction")

        class Delete:
            pass

        for val in [256, -1, 1.2, 'asd', True, None, Delete]:
            req = base()
            if val is Delete:
                del req['subfunction']
            else:
                req['subfunction'] = val
            self.send_request(req)
            self.assertTrue(self.fake_device_handler.user_command_history_queue.empty())    # API does not forward the request
            self.assert_is_error(self.wait_and_load_response())

        for val in [1, -1, 1.2, 'asd', True, None, Delete]:
            req = base()
            if val is Delete:
                del req['data']
            else:
                req['data'] = val
            self.send_request(req)
            self.assertTrue(self.fake_device_handler.user_command_history_queue.empty())    # API does not forward the request
            self.assert_is_error(self.wait_and_load_response())

    def test_get_server_stats(self):
        def base() -> api_typing.C2S.GetServerStats:
            return {
                'cmd': 'get_server_stats'
            }

        req = base()

        self.send_request(req)
        stats = self.api.server.get_stats()
        response = self.wait_and_load_response()

        self.assertEqual(response['uptime'], stats.uptime)
        self.assertEqual(response['invalid_request_count'], stats.api.invalid_request_count)
        self.assertEqual(response['unexpected_error_count'], stats.api.unexpected_error_count)
        self.assertEqual(response['client_count'], stats.api.client_handler.client_count)
        self.assertEqual(response['to_all_clients_datarate_byte_per_sec'], stats.api.client_handler.output_datarate_byte_per_sec)
        self.assertEqual(response['from_any_client_datarate_byte_per_sec'], stats.api.client_handler.input_datarate_byte_per_sec)
        self.assertEqual(response['msg_received'], stats.api.client_handler.msg_received)
        self.assertEqual(response['msg_sent'], stats.api.client_handler.msg_sent)
        self.assertEqual(response['device_session_count'], stats.device.device_session_count)
        self.assertEqual(response['to_device_datarate_byte_per_sec'], stats.device.comm_handler.tx_datarate_byte_per_sec)
        self.assertEqual(response['from_device_datarate_byte_per_sec'], stats.device.comm_handler.rx_datarate_byte_per_sec)
        self.assertEqual(response['device_request_per_sec'], stats.device.comm_handler.request_per_sec)


# endregion
if __name__ == '__main__':
    import unittest
    unittest.main()
