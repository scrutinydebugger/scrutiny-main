#    test_datalogging_manager.py
#        Test the datalogging manager features
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2023 Scrutiny Debugger

import scrutiny.server.datalogging.definitions.api as api_datalogging
import scrutiny.server.datalogging.definitions.device as device_datalogging
from scrutiny.core import datalogging as core_datalogging
from scrutiny.server.datastore.datastore import *
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.core.variable import Variable
from scrutiny.core.basic_types import *
from test import ScrutinyUnitTest
from scrutiny.core.alias import Alias
from scrutiny.server.device.device_handler import DeviceHandler, DeviceAcquisitionRequestCompletionCallback
from scrutiny.server.device.device_info import DeviceInfo, FixedFreqLoop, VariableFreqLoop
from scrutiny.server.datalogging.datalogging_storage import DataloggingStorage

from scrutiny.server.datalogging.datalogging_manager import DataloggingManager
from scrutiny.tools.typing import *
from dataclasses import dataclass
import random
from scrutiny.core.codecs import UIntCodec


class StubbedDeviceHandler:

    @dataclass
    class DataloggingRequest:
        loop_id: int
        config: device_datalogging.Configuration
        callback: DeviceAcquisitionRequestCompletionCallback

    _connection_status: DeviceHandler.ConnectionStatus
    device_info: DeviceInfo
    _ready_for_datalogging_acquisition_request: bool
    _datalogger_state: device_datalogging.DataloggerState
    _datalogging_acquisition_completion_ratio: Optional[float]
    _datalogging_acquisition_download_progress: Optional[float]
    reset_datalogging_call_count: int
    last_request_received: Optional[DataloggingRequest]
    _datalogging_request_in_progress: bool

    def __init__(self):
        self._connection_status = DeviceHandler.ConnectionStatus.UNKNOWN
        self.device_info = DeviceInfo()
        self._ready_for_datalogging_acquisition_request = False
        self._datalogger_state = device_datalogging.DataloggerState.IDLE
        self._datalogging_acquisition_completion_ratio = 0
        self._datalogging_acquisition_download_progress = 0
        self.reset_datalogging_call_count = 0
        self.last_request_received = None
        self._datalogging_request_in_progress = False

        self.device_info.device_id = 'aaa'
        self.device_info.display_name = 'unit test'
        self.device_info.max_tx_data_size = 64
        self.device_info.max_rx_data_size = 64
        self.device_info.max_bitrate_bps = 0
        self.device_info.rx_timeout_us = 50000
        self.device_info.heartbeat_timeout_us = 50000000
        self.device_info.address_size_bits = 32
        self.device_info.protocol_major = 1
        self.device_info.protocol_minor = 0
        self.device_info.supported_feature_map = {
            '_64bits': True,
            'datalogging': True,
            'memory_write': True,
            'user_command': False
        }
        self.device_info.forbidden_memory_regions = []
        self.device_info.readonly_memory_regions = []
        self.device_info.runtime_published_values = []
        self.device_info.loops = [
            FixedFreqLoop(freq=1000, name="loop 1khz", support_datalogging=True),
            FixedFreqLoop(freq=10000, name="loop 10khz", support_datalogging=True),
            FixedFreqLoop(freq=100000, name="loop 100khz", support_datalogging=False),
            VariableFreqLoop(name="variable loop 1", support_datalogging=True)
        ]
        self.device_info.datalogging_setup = device_datalogging.DataloggingSetup(
            buffer_size=4096,
            encoding=device_datalogging.Encoding.RAW,
            max_signal_count=32
        )

    def get_connection_status(self) -> DeviceHandler.ConnectionStatus:
        return self._connection_status

    def set_connection_status(self, status: DeviceHandler.ConnectionStatus) -> None:
        self._connection_status = status

    def get_device_info(self) -> DeviceInfo:
        return self.device_info

    def datalogging_in_error(self) -> bool:
        return self._datalogger_state == device_datalogging.DataloggerState.ERROR

    def is_ready_for_datalogging_acquisition_request(self) -> bool:
        return self._ready_for_datalogging_acquisition_request

    def set_ready_for_datalogging_acquisition_request(self, val: bool) -> None:
        self._ready_for_datalogging_acquisition_request = val

    def get_datalogger_state(self) -> device_datalogging.DataloggerState:
        return self._datalogger_state

    def set_datalogger_state(self, val: device_datalogging.DataloggerState) -> None:
        self._datalogger_state = val

    def get_datalogging_acquisition_completion_ratio(self) -> float:
        return self._datalogging_acquisition_completion_ratio

    def set_datalogging_acquisition_completion_ratio(self, val: float) -> None:
        self._datalogging_acquisition_completion_ratio = val

    def get_datalogging_acquisition_download_progress(self) -> float:
        return self._datalogging_acquisition_download_progress

    def set_datalogging_acquisition_download_progress(self, val: float) -> None:
        self._datalogging_acquisition_download_progress = val

    def reset_datalogging(self):
        self._datalogger_state = device_datalogging.DataloggerState.IDLE
        self.reset_datalogging_call_count += 1

    def request_datalogging_acquisition(self, loop_id: int, config: device_datalogging.Configuration, callback: DeviceAcquisitionRequestCompletionCallback) -> None:
        self.last_request_received = self.DataloggingRequest(
            loop_id=loop_id,
            config=config,
            callback=callback
        )

    def datalogging_request_in_progress(self) -> bool:
        return self._datalogging_request_in_progress

    def set_datalogging_request_in_progress(self, val: bool) -> None:
        self._datalogging_request_in_progress = val


class TestDataloggingManager(ScrutinyUnitTest):

    def make_var_entry(self, path: str, address: int, datatype: EmbeddedDataType, endianness: Endianness = Endianness.Little) -> DatastoreVariableEntry:
        v = Variable(path, datatype, [], address, endianness)
        return DatastoreVariableEntry(path, v)

    def make_varbit_entry(self, path: str, address: int, datatype: EmbeddedDataType, bitoffset: int, bitsize: int, endianness: Endianness) -> DatastoreVariableEntry:
        v = Variable(path, datatype, [], address, endianness, bitoffset=bitoffset, bitsize=bitsize)
        return DatastoreVariableEntry(path, v)

    def make_rpv_entry(self, path: str, rpv_id: int, datatype: EmbeddedDataType) -> DatastoreRPVEntry:
        return DatastoreRPVEntry(path, RuntimePublishedValue(rpv_id, datatype))

    def setUp(self):
        self.device_handler = StubbedDeviceHandler()
        self.datastore = Datastore()
        self.datalogging_manager = DataloggingManager(self.datastore, self.device_handler)

        self.var1_u32 = self.make_varbit_entry('/var/abc/var1_u32', 0x100000, EmbeddedDataType.uint32,
                                               bitoffset=9, bitsize=5, endianness=Endianness.Little)
        self.var2_u32 = self.make_varbit_entry('/var/abc/var2_u32', 0x100004,
                                               EmbeddedDataType.uint32, bitoffset=9, bitsize=5, endianness=Endianness.Big)
        self.var3_f64 = self.make_var_entry('/var/abc/var3_f64', 0x100008, EmbeddedDataType.float64)
        self.var4_s16 = self.make_var_entry('/var/abc/var4_s16', 0x100010, EmbeddedDataType.sint16)

        self.rpv1000_bool = self.make_rpv_entry('/rpv/abc/rpv1000_bool', 0x1000, EmbeddedDataType.boolean)
        self.rpv2000_f32 = self.make_rpv_entry('/rpv/abc/rpv2000_f32', 0x2000, EmbeddedDataType.float32)

        self.alias_var1_u32 = DatastoreAliasEntry(
            Alias(
                fullpath='/alias/alias_var1_u32',
                target='/var/abc/var1_u32',
                target_type=WatchableType.Variable,
                gain=2.0,
                offset=50,
                max=100000,
                min=-200000),
            self.var1_u32)

        self.alias_rpv2000_f32 = DatastoreAliasEntry(
            Alias(
                fullpath='/alias/alias_rpv2000_f32',
                target='/rpv/abc/rpv2000_f32',
                target_type=WatchableType.RuntimePublishedValue,
                gain=2.0,
                offset=100,
                max=100000,
                min=-200000),
            self.rpv2000_f32)

        self.alias_var4_s16 = DatastoreAliasEntry(
            Alias(
                fullpath='/alias/alias_var4_s16',
                target='/var/abc/var4_s16',
                target_type=WatchableType.Variable,
                gain=2.0,
                offset=100,
                max=100000,
                min=-200000),
            self.var4_s16)

        self.datastore.add_entry(self.var1_u32)
        self.datastore.add_entry(self.var2_u32)
        self.datastore.add_entry(self.var3_f64)
        self.datastore.add_entry(self.var4_s16)
        self.datastore.add_entry(self.rpv1000_bool)
        self.datastore.add_entry(self.rpv2000_f32)
        self.datastore.add_entry(self.alias_var1_u32)
        self.datastore.add_entry(self.alias_rpv2000_f32)
        self.datastore.add_entry(self.alias_var4_s16)

    def make_test_request(self, operand_watchable: DatastoreEntry, x_axis_type: api_datalogging.XAxisType, x_axis_entry: Optional[DatastoreEntry] = None) -> api_datalogging.AcquisitionRequest:
        yaxis_list = [
            core_datalogging.AxisDefinition("Axis1", axis_id=100),
            core_datalogging.AxisDefinition("Axis2", axis_id=200),
            core_datalogging.AxisDefinition("Axis3", axis_id=300)
        ]

        return api_datalogging.AcquisitionRequest(
            name="some_request",
            decimation=2,
            probe_location=0.25,
            rate_identifier=1,   # Loop ID = 2. Number owned by Device Handler (stubbed here)
            timeout=0,
            trigger_hold_time=0.001,
            trigger_condition=api_datalogging.TriggerCondition(
                condition_id=api_datalogging.TriggerConditionID.GreaterThan,
                operands=[
                    api_datalogging.TriggerConditionOperand(type=api_datalogging.TriggerConditionOperandType.WATCHABLE, value=operand_watchable),
                    api_datalogging.TriggerConditionOperand(type=api_datalogging.TriggerConditionOperandType.LITERAL, value=100)
                ]
            ),
            x_axis_type=x_axis_type,
            x_axis_signal=api_datalogging.SignalDefinition('x-axis', x_axis_entry) if x_axis_entry is not None else None,
            signals=[
                api_datalogging.SignalDefinitionWithAxis('var1_u32', self.var1_u32, axis=yaxis_list[0]),
                api_datalogging.SignalDefinitionWithAxis('var1_u32', self.var1_u32, axis=yaxis_list[0]),    # Duplicate on purpose
                api_datalogging.SignalDefinitionWithAxis('var2_u32', self.var2_u32, axis=yaxis_list[1]),
                api_datalogging.SignalDefinitionWithAxis('var3_f64', self.var3_f64, axis=yaxis_list[1]),
                api_datalogging.SignalDefinitionWithAxis('rpv1000_bool', self.rpv1000_bool, axis=yaxis_list[2]),
                api_datalogging.SignalDefinitionWithAxis('alias_var1_u32', self.alias_var1_u32, axis=yaxis_list[2]),
                api_datalogging.SignalDefinitionWithAxis('alias_rpv2000_f32', self.alias_rpv2000_f32, axis=yaxis_list[2])
            ]
        )

    def make_random_data_for_request(self, req: api_datalogging.AcquisitionRequest, nb_points: int = 100) -> Tuple[List[List[bytes]], device_datalogging.AcquisitionMetadata]:
        time_codec = UIntCodec(4, Endianness.Little)
        data: List[List[bytes]] = []
        data_size = 0

        for signal_def in req.signals:
            entry = signal_def.entry
            if isinstance(entry, DatastoreAliasEntry):  # dereference alias
                entry = entry.refentry

            if isinstance(entry, DatastoreVariableEntry):
                dtype = entry.get_data_type()
                codec = entry.codec
            elif isinstance(entry, DatastoreRPVEntry):
                dtype = entry.get_data_type()
                codec = entry.codec
            else:
                raise NotImplementedError("Unsupported entry type")

            points: List[bytes] = []
            for i in range(nb_points):

                randval = random.random()
                if dtype == EmbeddedDataType.boolean:
                    points.append(codec.encode(i % 2 == 0))
                elif dtype.is_float():
                    points.append(codec.encode(randval))
                elif dtype.is_integer():
                    intval = int(randval * 200 - 100)
                    if not dtype.is_signed():
                        intval = abs(intval)

                    points.append(codec.encode(intval))
                else:
                    raise NotImplementedError(f"Unsupported data type: {dtype}")
            data.append(points)

        if req.x_axis_type == api_datalogging.XAxisType.MeasuredTime:
            points: List[bytes] = []
            for i in range(nb_points):
                points.append(time_codec.encode(i))
            data.append(points)

        data_size += sum([sum([len(point_data) for point_data in series]) for series in data])

        meta = device_datalogging.AcquisitionMetadata(
            acquisition_id=0,
            config_id=1,
            data_size=data_size,
            number_of_points=nb_points,
            points_after_trigger=nb_points // 2
        )

        return data, meta

    def test_convert_to_config(self):
        for i in range(6):
            if i == 0:
                req = self.make_test_request(operand_watchable=self.var1_u32, x_axis_type=api_datalogging.XAxisType.MeasuredTime)
            elif i == 1:
                req = self.make_test_request(operand_watchable=self.rpv1000_bool, x_axis_type=api_datalogging.XAxisType.IdealTime)
            elif i == 2:
                req = self.make_test_request(operand_watchable=self.alias_var1_u32,
                                             x_axis_type=api_datalogging.XAxisType.Signal, x_axis_entry=self.alias_var1_u32)  # X axis will not add a signal
            elif i == 3:
                req = self.make_test_request(operand_watchable=self.alias_rpv2000_f32,
                                             x_axis_type=api_datalogging.XAxisType.Signal, x_axis_entry=self.alias_rpv2000_f32)  # X axis will not add a signal
            elif i == 4:
                req = self.make_test_request(operand_watchable=self.alias_var4_s16,
                                             x_axis_type=api_datalogging.XAxisType.Signal, x_axis_entry=self.alias_var4_s16)  # X axis will add a signal
            elif i == 5:
                req = self.make_test_request(operand_watchable=self.alias_var4_s16,
                                             x_axis_type=api_datalogging.XAxisType.Indexed)  # X axis will add a signal
            else:
                raise NotImplementedError()

            config, signalmap = DataloggingManager.make_device_config_from_request(req)

            self.assertIn(self.var1_u32, signalmap, "i=%d" % i)
            self.assertIn(self.var2_u32, signalmap, "i=%d" % i)
            self.assertIn(self.var3_f64, signalmap, "i=%d" % i)
            self.assertIn(self.rpv1000_bool, signalmap, "i=%d" % i)
            self.assertIn(self.alias_var1_u32, signalmap, "i=%d" % i)
            self.assertIn(self.alias_rpv2000_f32, signalmap, "i=%d" % i)
            if i == 4:
                self.assertIn(self.alias_var4_s16, signalmap)

            self.assertEqual(req.decimation, config.decimation)
            self.assertEqual(req.probe_location, config.probe_location)
            self.assertEqual(req.timeout, config.timeout)
            self.assertEqual(req.trigger_hold_time, config.trigger_hold_time)

            self.assertEqual(req.trigger_condition.condition_id, config.trigger_condition.condition_id)
            self.assertEqual(len(config.trigger_condition.get_operands()), 2)

            operand1 = config.trigger_condition.get_operands()[0]
            operand2 = config.trigger_condition.get_operands()[1]
            assert isinstance(operand2, device_datalogging.LiteralOperand)

            literal_expected_value = 100
            if isinstance(req.trigger_condition.operands[0].value, DatastoreAliasEntry):
                # When we compare a literal with a scaled alias, we scale the literal to math the underlying variable.
                literal_expected_value -= req.trigger_condition.operands[0].value.aliasdef.get_offset()
                literal_expected_value /= req.trigger_condition.operands[0].value.aliasdef.get_gain()

            self.assertEqual(operand2.value, literal_expected_value)

            # 0 is Variable. 2 is Alias that points to variable
            if i in [0, 2]:
                self.assertIsInstance(operand1, device_datalogging.VarBitOperand)
                assert isinstance(operand1, device_datalogging.VarBitOperand)
                self.assertEqual(operand1.address, self.var1_u32.get_address())
                self.assertEqual(operand1.datatype, self.var1_u32.get_data_type())
                self.assertEqual(operand1.bitoffset, self.var1_u32.get_bitoffset())
                self.assertEqual(operand1.bitsize, self.var1_u32.get_bitsize())
            elif i in [1]:    # i is RPV
                self.assertIsInstance(operand1, device_datalogging.RPVOperand)
                assert isinstance(operand1, device_datalogging.RPVOperand)
                self.assertEqual(operand1.rpv_id, self.rpv1000_bool.get_rpv().id)
            elif i == 3:    # i is RPV
                self.assertIsInstance(operand1, device_datalogging.RPVOperand)
                assert isinstance(operand1, device_datalogging.RPVOperand)
                self.assertEqual(operand1.rpv_id, self.rpv2000_f32.rpv.id)
            elif i in [4, 5]:
                self.assertIsInstance(operand1, device_datalogging.VarOperand)
                assert isinstance(operand1, device_datalogging.VarOperand)
                self.assertEqual(operand1.address, self.var4_s16.get_address())
                self.assertEqual(operand1.datatype, self.var4_s16.get_data_type())
            else:
                raise NotImplementedError()

            signals = config.get_signals()
            len_by_iter = {
                0: 6,
                1: 5,
                2: 5,
                3: 5,
                4: 6,
                5: 5
            }

            self.assertEqual(len(signals), len_by_iter[i], "i=%d" % i)

            assert isinstance(signals[signalmap[self.var1_u32]], device_datalogging.MemoryLoggableSignal)
            assert isinstance(signals[signalmap[self.var2_u32]], device_datalogging.MemoryLoggableSignal)
            assert isinstance(signals[signalmap[self.var3_f64]], device_datalogging.MemoryLoggableSignal)

            self.assertEqual(signals[signalmap[self.var1_u32]].address, 0x100001)  # bitoffset 9 cause next memory cell. (little endian)
            self.assertEqual(signals[signalmap[self.var1_u32]].size, 1)    # bitsize 5 becomes 8bits

            self.assertEqual(signals[signalmap[self.var2_u32]].address, 0x100007)  # bitoffset 9 cause next memory cell. (Big endian) 100004 + 4 - 1
            self.assertEqual(signals[signalmap[self.var2_u32]].size, 1)    # bitsize 5 becomes 8bits

            self.assertEqual(signals[signalmap[self.var3_f64]].address, 0x100008)
            self.assertEqual(signals[signalmap[self.var3_f64]].size, 8)

            assert isinstance(signals[signalmap[self.rpv1000_bool]], device_datalogging.RPVLoggableSignal)
            self.assertEqual(signals[signalmap[self.rpv1000_bool]].rpv_id, 0x1000)

            assert isinstance(signals[signalmap[self.alias_var1_u32]], device_datalogging.MemoryLoggableSignal)
            self.assertEqual(signals[signalmap[self.alias_var1_u32]].address, 0x100001)  # bitoffset 9 cause next memory cell. (little endian)
            self.assertEqual(signals[signalmap[self.alias_var1_u32]].size, 1)    # bitsize 5 becomes 8bits

            assert isinstance(signals[signalmap[self.alias_rpv2000_f32]], device_datalogging.RPVLoggableSignal)
            self.assertEqual(signals[signalmap[self.alias_rpv2000_f32]].rpv_id, 0x2000)

            if i == 0:
                assert isinstance(signals[-1], device_datalogging.TimeLoggableSignal)   # Measured Time cause this to be inserted
            elif i == 4:
                alias = self.alias_var4_s16
                assert isinstance(signals[signalmap[self.alias_var4_s16]], device_datalogging.MemoryLoggableSignal)
                assert isinstance(alias.refentry, DatastoreVariableEntry)
                self.assertEqual(signals[signalmap[self.alias_var4_s16]].address, alias.refentry.get_address())
                self.assertEqual(signals[signalmap[self.alias_var4_s16]].size, alias.refentry.get_data_type().get_size_byte())

    def _process_until(self, fn, max_iter: int) -> None:
        i = 0
        while not fn() and i < max_iter:
            self.datalogging_manager.process()
            i += 1
        self.datalogging_manager.process()
        self.assertTrue(fn())

    def _wait_connected_without_datalogging(self, max_iter=5):
        self._process_until(self.datalogging_manager.is_device_connected_without_datalogging, max_iter)
        self.assertTrue(self.datalogging_manager.is_device_connected_without_datalogging())
        self.assertFalse(self.datalogging_manager.is_device_connected_with_datalogging())

    def _wait_connected_with_datalogging(self, max_iter=5):
        self._process_until(self.datalogging_manager.is_device_connected_with_datalogging, max_iter)
        self.assertTrue(self.datalogging_manager.is_device_connected_with_datalogging())
        self.assertFalse(self.datalogging_manager.is_device_connected_without_datalogging())

    def test_read_state(self):
        # Check that we can translate the datalogger state to a server state
        self.device_handler.set_connection_status(DeviceHandler.ConnectionStatus.UNKNOWN)
        self.datalogging_manager.process()
        state, completion = self.datalogging_manager.get_datalogging_state()
        self.assertEqual(state, api_datalogging.DataloggingState.NA)
        self.assertIsNone(completion)

        self.device_handler.set_connection_status(DeviceHandler.ConnectionStatus.CONNECTED_READY)
        self.device_handler.set_ready_for_datalogging_acquisition_request(True)
        self.device_handler.set_datalogger_state(device_datalogging.DataloggerState.IDLE)

        self._wait_connected_with_datalogging()
        self.datalogging_manager.process()

        self.assertEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.Standby, None))

        self.device_handler.set_datalogger_state(device_datalogging.DataloggerState.CONFIGURED)
        self.assertEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.Standby, None))

        self.device_handler.set_datalogger_state(device_datalogging.DataloggerState.ARMED)
        self.assertEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.WaitForTrigger, None))

        self.device_handler.set_datalogger_state(device_datalogging.DataloggerState.TRIGGERED)
        self.assertEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.Acquiring, 0))

        self.device_handler.set_datalogging_acquisition_completion_ratio(0.1)
        self.assertEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.Acquiring, 0.1))

        self.device_handler.set_datalogging_acquisition_completion_ratio(0.2)
        self.assertEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.Acquiring, 0.2))

        self.device_handler.set_datalogger_state(device_datalogging.DataloggerState.ACQUISITION_COMPLETED)
        self.assertEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.Downloading, 0))

        self.device_handler.set_datalogging_acquisition_download_progress(0.1)
        self.assertEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.Downloading, 0.1))

        self.device_handler.set_datalogging_acquisition_download_progress(0.3)
        self.assertEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.Downloading, 0.3))

        self.device_handler.set_datalogger_state(device_datalogging.DataloggerState.ERROR)
        self.assertEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.Error, None))

    def test_datalogging_not_available(self):
        # Check that we manager a device without datalogging support
        self.device_handler.device_info.supported_feature_map['datalogging'] = False
        self.device_handler.set_connection_status(DeviceHandler.ConnectionStatus.CONNECTED_READY)

        self._wait_connected_without_datalogging()
        self.datalogging_manager.process()

        self.assertEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.NA, None))

    def test_reset_datalogger_in_case_of_error(self):
        # Check that we reset the datalogger if it goes into error
        self.device_handler.set_connection_status(DeviceHandler.ConnectionStatus.CONNECTED_READY)
        self.device_handler.set_ready_for_datalogging_acquisition_request(True)
        self.device_handler.set_datalogger_state(device_datalogging.DataloggerState.IDLE)

        self._wait_connected_with_datalogging()

        self.assertEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.Standby, None))

        self.device_handler.set_datalogger_state(device_datalogging.DataloggerState.ERROR)
        self.assertNotEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.Standby, None))

        def reset_called() -> bool:
            return self.device_handler.reset_datalogging_call_count > 0
        self._process_until(reset_called, max_iter=5)

        self.assertFalse(self.datalogging_manager.is_device_connected_with_datalogging())
        self._wait_connected_with_datalogging()
        self.assertEqual(self.datalogging_manager.get_datalogging_state(), (api_datalogging.DataloggingState.Standby, None))

    def test_make_acquisition(self):
        # Do an acquisition cycle through a stubbed device handler. ensure the callback is called at the right time

        with DataloggingStorage.use_temp_storage():
            self.device_handler.set_connection_status(DeviceHandler.ConnectionStatus.CONNECTED_READY)
            self.device_handler.set_ready_for_datalogging_acquisition_request(True)
            self.device_handler.set_datalogger_state(device_datalogging.DataloggerState.IDLE)

            self._wait_connected_with_datalogging()

            yaxis_list = [
                core_datalogging.AxisDefinition("Axis1", axis_id=100),
                core_datalogging.AxisDefinition("Axis2", axis_id=200),
                core_datalogging.AxisDefinition("Axis3", axis_id=300)
            ]

            req = api_datalogging.AcquisitionRequest(
                name="some_request",
                decimation=2,
                probe_location=0.25,
                rate_identifier=0,   # Loop ID = 0. Number owned by Device Handler (stubbed here)
                timeout=0,
                trigger_hold_time=0.001,
                trigger_condition=api_datalogging.TriggerCondition(
                    condition_id=api_datalogging.TriggerConditionID.AlwaysTrue,
                    operands=[]
                ),
                x_axis_type=api_datalogging.XAxisType.IdealTime,
                x_axis_signal=None,
                signals=[
                    api_datalogging.SignalDefinitionWithAxis('var2_u32', self.var2_u32, axis=yaxis_list[0]),
                    api_datalogging.SignalDefinitionWithAxis('rpv1000_bool', self.rpv1000_bool, axis=yaxis_list[0]),
                    api_datalogging.SignalDefinitionWithAxis('alias_var1_u32', self.alias_var1_u32, axis=yaxis_list[1]),
                    api_datalogging.SignalDefinitionWithAxis('alias_rpv2000_f32', self.alias_rpv2000_f32, axis=yaxis_list[2])
                ]
            )

            @dataclass
            class CallbackContent:
                called: bool = False
                success: bool = False
                failure_reason: str = ""
                acq: Optional[api_datalogging.DataloggingAcquisition] = None

            @dataclass
            class StateContent:
                updated: bool = False
                state: api_datalogging.DataloggingState = api_datalogging.DataloggingState.NA
                completion: Optional[float] = None

            last_callback_call = CallbackContent()
            last_state = StateContent()

            def completion_callback(success: bool, failure_reason: str, acq: Optional[api_datalogging.DataloggingAcquisition]):
                last_callback_call.called = True
                last_callback_call.success = success
                last_callback_call.failure_reason = failure_reason
                last_callback_call.acq = acq

            def state_change_callback(state: api_datalogging.DataloggingState, completion: Optional[float]):
                last_state.updated = True
                last_state.state = state
                last_state.completion = completion

            def assert_state_change_and_clear(state: api_datalogging.DataloggingState, completion: Optional[float]):
                self.assertTrue(last_state.updated)
                self.assertEqual(last_state.state, state)
                self.assertEqual(last_state.completion, completion)
                last_state.updated = False

            self.datalogging_manager.register_datalogging_state_change_callback(state_change_callback)

            self.assertIsNone(self.device_handler.last_request_received)
            self.datalogging_manager.request_acquisition(req, completion_callback)
            self.datalogging_manager.process()
            self.assertIsNotNone(self.device_handler.last_request_received)
            device_req = self.device_handler.last_request_received
            self.assertFalse(last_state.updated)    # No state change yet

            # Simulate an acquisition progress by controlling the state of the device handler
            self.device_handler.set_datalogging_request_in_progress(True)

            self.device_handler.set_datalogger_state(device_datalogging.DataloggerState.ARMED)
            self.datalogging_manager.process()
            assert_state_change_and_clear(api_datalogging.DataloggingState.WaitForTrigger, None)

            self.device_handler.set_datalogger_state(device_datalogging.DataloggerState.TRIGGERED)
            self.device_handler.set_datalogging_acquisition_completion_ratio(0.1)
            self.datalogging_manager.process()
            assert_state_change_and_clear(api_datalogging.DataloggingState.Acquiring, 0.1)

            self.device_handler.set_datalogging_acquisition_completion_ratio(0.2)
            self.datalogging_manager.process()
            assert_state_change_and_clear(api_datalogging.DataloggingState.Acquiring, 0.2)

            self.device_handler.set_datalogger_state(device_datalogging.DataloggerState.ACQUISITION_COMPLETED)
            self.device_handler.set_datalogging_acquisition_completion_ratio(1)
            self.datalogging_manager.process()
            assert_state_change_and_clear(api_datalogging.DataloggingState.Downloading, 0)

            self.device_handler.set_datalogging_acquisition_download_progress(0.5)
            self.datalogging_manager.process()
            assert_state_change_and_clear(api_datalogging.DataloggingState.Downloading, 0.5)

            self.device_handler.set_datalogging_acquisition_download_progress(1)
            self.datalogging_manager.process()
            assert_state_change_and_clear(api_datalogging.DataloggingState.Downloading, 1)

            data, meta = self.make_random_data_for_request(req, nb_points=100)

            self.assertFalse(last_callback_call.called)
            device_req.callback(True, "", data, meta)
            self.datalogging_manager.process()
            self.assertTrue(last_callback_call.called)

            self.device_handler.set_datalogger_state(device_datalogging.DataloggerState.IDLE)
            self.datalogging_manager.process()
            assert_state_change_and_clear(api_datalogging.DataloggingState.Standby, None)


if __name__ == '__main__':
    import unittest
    unittest.main()
