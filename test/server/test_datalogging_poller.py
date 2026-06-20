#    test_datalogging_poller.py
#        A test suite for the datalogging poller
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from dataclasses import dataclass
from test import ScrutinyUnitTest

from scrutiny.server.device.submodules.datalogging_poller import DataloggingPoller
from scrutiny.server.device.request_dispatcher import RequestDispatcher, RequestRecord
from scrutiny.server.protocol import Protocol
from scrutiny.server.protocol.commands import DatalogControl
import scrutiny.server.datalogging.definitions.device as device_datalogging
from scrutiny.server.protocol.crc32 import crc32

from scrutiny.tools.typing import *

DatalogSubfn = DatalogControl.Subfunction


@dataclass
class DeviceStatus:
    state: device_datalogging.DataloggerState
    remaining_byte_from_trigger_to_complete: int
    byte_counter_since_trigger: int


class TestDataloggingPoller(ScrutinyUnitTest):

    def setUp(self) -> None:
        self.protocol = Protocol(1, 0)
        self.protocol.set_address_size_bits(32)
        self.dispatcher = RequestDispatcher()
        self.poller = DataloggingPoller(
            protocol=self.protocol,
            dispatcher=self.dispatcher,
            request_priority=0
        )

        setup = device_datalogging.DataloggingSetup(
            buffer_size=512,
            encoding=device_datalogging.Encoding.RAW,
            max_signal_count=32
        )
        self.poller.configure_datalogging_setup(setup)
        self.poller.set_max_response_payload_size(128)

        self.actual_status = DeviceStatus(device_datalogging.DataloggerState.IDLE, 0, 0)

        # State entry dispatches ResetDatalogger.
        self.poller.start()
        self.poller.process()
        reset_rec = self._wait_for_subfn_and_respond_to_getstatus(DatalogSubfn.ResetDatalogger)
        reset_rec.complete(success=True, response=self.protocol.respond_datalogging_reset_datalogger())

    def _pop_subfn(self, expected_subfn: DatalogSubfn) -> Any:
        """Pop the next request from the dispatcher and assert its subfunction."""
        rec = self.dispatcher.pop_next()
        self.assertIsNotNone(rec, f"Expected a {expected_subfn.name} request but dispatcher queue was empty")
        self.assertEqual(DatalogSubfn(rec.request.subfn), expected_subfn,
                         "Expected subfunction %s, got %s" % (expected_subfn.name, DatalogSubfn(rec.request.subfn).name))
        return rec

    def _process_get_status(self, rec: RequestRecord):
        rec.complete(success=True, response=self.protocol.respond_datalogging_get_status(
            state=self.actual_status.state,
            remaining_byte_from_trigger_to_complete=self.actual_status.remaining_byte_from_trigger_to_complete,
            byte_counter_since_trigger=self.actual_status.byte_counter_since_trigger
        ))

    def _wait_for_subfn_and_respond_to_getstatus(self, subfn: Optional[DatalogSubfn], max_process: int = 5):
        count = 0
        self.assertNotEqual(subfn, DatalogSubfn.GetStatus)

        while True:
            self.poller.process()
            rec = self.dispatcher.pop_next()
            if rec is None:
                if subfn is None:
                    return
                count += 1
                if count >= max_process:
                    self.fail(f"Request: {subfn.name} did not happen in {count} cycles")
            else:
                if DatalogSubfn(rec.request.subfn) == DatalogSubfn.GetStatus:
                    self._process_get_status(rec)
                else:
                    self.assertEqual(DatalogSubfn(rec.request.subfn), subfn,
                                     "Expected subfunction %s, got %s" % (subfn.name, DatalogSubfn(rec.request.subfn).name))
                    return rec

    def _assert_queue_empty(self) -> None:
        rec = self.dispatcher.pop_next()
        if rec is not None:
            self.fail("Expected dispatcher queue to be empty but found a %s request" % DatalogSubfn(rec.request.subfn).name)

    def bring_poller_to_completion(self):
        configure_rec = self._wait_for_subfn_and_respond_to_getstatus(DatalogSubfn.ConfigureDatalog)
        configure_rec.complete(success=True, response=self.protocol.respond_datalogging_configure())
        self.actual_status.state = device_datalogging.DataloggerState.CONFIGURED

        arm_rec = self._wait_for_subfn_and_respond_to_getstatus(DatalogSubfn.ArmTrigger)
        arm_rec.complete(success=True, response=self.protocol.respond_datalogging_arm_trigger())
        self.actual_status.state = device_datalogging.DataloggerState.ARMED

        self._wait_for_subfn_and_respond_to_getstatus(None)  # Wait a bit, nothing should happen.

        self.actual_status.state = device_datalogging.DataloggerState.TRIGGERED
        self.actual_status.remaining_byte_from_trigger_to_complete = 2
        self.poller.enqueue_status_update_request()

        self._wait_for_subfn_and_respond_to_getstatus(None)  # Wait a bit, nothing should happen.

        self.actual_status.state = device_datalogging.DataloggerState.ACQUISITION_COMPLETED
        self.actual_status.remaining_byte_from_trigger_to_complete = 0
        self.actual_status.byte_counter_since_trigger = 2
        self.poller.enqueue_status_update_request()

    def test_normal_acquisition_flow(self) -> None:
        protocol = self.protocol
        dispatcher = self.dispatcher
        poller = self.poller

        # Build a minimal acquisition config: 1 memory signal, 4 bytes per sample
        config = device_datalogging.Configuration()
        config.add_signal(device_datalogging.MemoryLoggableSignal(address=0x1000, size=4))

        # Raw acquisition payload: 2 samples * 4 bytes = 8 bytes
        raw_data = b'\x11\x22\x33\x44\x55\x66\x77\x88'
        acquisition_id = 42
        nb_points = 2

        callback_results: list = []

        def completion_callback(success: bool, detail: str, data: Optional[List[List[bytes]]], metadata: Optional[device_datalogging.AcquisitionMetadata]) -> None:
            callback_results.append((success, detail, data, metadata))

        self._wait_for_subfn_and_respond_to_getstatus(None)  # Wait a bit, nothing should happen.
        self._assert_queue_empty()

        poller.request_acquisition(loop_id=0, config=config, callback=completion_callback)
        poller.process()
        self._assert_queue_empty()

        self.bring_poller_to_completion()

        meta_rec = self._wait_for_subfn_and_respond_to_getstatus(DatalogSubfn.GetAcquisitionMetadata)
        expected_config_id = 1

        meta_rec.complete(success=True, response=protocol.respond_datalogging_get_acquisition_metadata(
            acquisition_id=acquisition_id,
            config_id=expected_config_id,
            nb_points=nb_points,
            datasize=len(raw_data),
            points_after_trigger=1
        ))

        read_rec = self._wait_for_subfn_and_respond_to_getstatus(DatalogSubfn.ReadAcquisition)
        data_crc = crc32(raw_data)
        read_rec.complete(success=True, response=protocol.respond_datalogging_read_acquisition(
            finished=True,
            rolling_counter=0,
            acquisition_id=acquisition_id,
            data=raw_data,
            crc=data_crc
        ))

        for i in range(5):
            poller.process()

        # Make sure we got our callback invoked
        self.assertEqual(len(callback_results), 1)

        success, detail, data, metadata = callback_results[0]

        self.assertTrue(success)
        self.assertIsNotNone(data)
        self.assertIsNotNone(metadata)

        self.assertEqual(metadata.acquisition_id, acquisition_id)
        self.assertEqual(metadata.config_id, expected_config_id)
        self.assertEqual(metadata.data_size, len(raw_data))
        self.assertEqual(metadata.number_of_points, nb_points)

        # data is deinterleaved: list[signal_index] -> list[sample_bytes]
        # 1 signal, 2 samples of 4 bytes each
        self.assertEqual(len(data), 1)
        signal_samples = data[0]
        self.assertEqual(len(signal_samples), nb_points)
        self.assertEqual(signal_samples[0], raw_data[0:4])
        self.assertEqual(signal_samples[1], raw_data[4:8])

    def test_buffer_fit_in_multiple_read_request(self) -> None:
        protocol = self.protocol
        dispatcher = self.dispatcher
        poller = self.poller
        poller.set_max_response_payload_size(32)

        # Build a minimal acquisition config: 1 memory signal, 4 bytes per sample
        config = device_datalogging.Configuration()
        config.add_signal(device_datalogging.MemoryLoggableSignal(address=0x1000, size=2))
        config.add_signal(device_datalogging.MemoryLoggableSignal(address=0x1002, size=2))
        config.add_signal(device_datalogging.MemoryLoggableSignal(address=0x1004, size=1))

        raw_data = bytes([c & 0xFF for c in range(265)])
        acquisition_id = 30
        nb_points = 53      # 53 points of 5 bytes = 265 bytes

        callback_results: list = []

        def completion_callback(success: bool, detail: str, data: Optional[List[List[bytes]]], metadata: Optional[device_datalogging.AcquisitionMetadata]) -> None:
            callback_results.append((success, detail, data, metadata))

        poller.request_acquisition(loop_id=0, config=config, callback=completion_callback)
        poller.process()
        self._assert_queue_empty()

        self.bring_poller_to_completion()

        meta_rec = self._wait_for_subfn_and_respond_to_getstatus(DatalogSubfn.GetAcquisitionMetadata)
        expected_config_id = 1

        meta_rec.complete(success=True, response=protocol.respond_datalogging_get_acquisition_metadata(
            acquisition_id=acquisition_id,
            config_id=expected_config_id,
            nb_points=nb_points,
            datasize=len(raw_data),
            points_after_trigger=1
        ))

        expected_chunk_size = [28, 28, 28, 28, 28, 28, 28, 28, 28, 13]

        cursor = 0
        for i, chunk_size in enumerate(expected_chunk_size):
            read_rec = self._wait_for_subfn_and_respond_to_getstatus(DatalogSubfn.ReadAcquisition)
            finished = False
            data_crc = None
            if i == len(expected_chunk_size) - 1:
                finished = True
                data_crc = crc32(raw_data)

            read_rec.complete(success=True, response=protocol.respond_datalogging_read_acquisition(
                finished=finished,
                rolling_counter=i,
                acquisition_id=acquisition_id,
                data=raw_data[cursor:cursor + chunk_size],
                crc=data_crc
            ))
            cursor += chunk_size

        for i in range(5):
            poller.process()

        # Make sure we got our callback invoked
        self.assertEqual(len(callback_results), 1)

        success, detail, data, metadata = callback_results[0]

        self.assertTrue(success)
        self.assertIsNotNone(data)
        self.assertIsNotNone(metadata)

        self.assertEqual(metadata.acquisition_id, acquisition_id)
        self.assertEqual(metadata.config_id, expected_config_id)
        self.assertEqual(metadata.data_size, len(raw_data))
        self.assertEqual(metadata.number_of_points, nb_points)

        # data is deinterleaved: list[signal_index] -> list[sample_bytes]
        # 1 signal, 2 samples of 4 bytes each
        self.assertEqual(len(data), 3)
        signal1_samples = data[0]
        signal2_samples = data[0]
        signal3_samples = data[0]
        self.assertEqual(len(signal1_samples), nb_points)
        self.assertEqual(len(signal2_samples), nb_points)
        self.assertEqual(len(signal3_samples), nb_points)


if __name__ == '__main__':
    import unittest
    unittest.main()
