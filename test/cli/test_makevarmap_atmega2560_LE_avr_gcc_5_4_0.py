#    test_makevarmap_atmega2560_LE_avr_gcc_5_4_0.py
#        Test suite for symbol extraction. AvrGCC dwarf V4
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

import unittest

from scrutiny.core.basic_types import *
from scrutiny.core.variable import *
from test.artifacts import get_artifact
from test import ScrutinyUnitTest
from test.cli.base_varmap_test import BaseVarmapTest, KnownEnumTypedDict

from scrutiny.tools.typing import *


KNOWN_ENUMS: KnownEnumTypedDict = {
    "Bno055DriverError": {
        "name": 'Error',
        "values": {
            "NO_ERROR": 0,
            "NO_INIT": 1,
            "NOT_READY": 2,
            "FAILED_READ_INFO": 3,
            "INTERRUPT_READ_ENABLED": 4
        }
    },

    "SystemStatusCode": {
        "name": 'Vals',
        "values": {
            "SystemIdle": 0,
            "SystemError": 1,
            "InitializingPeripherals": 2,
            "SystemInitialization": 3,
            "ExecutingSelfTest": 4,
            "SensorFusionAlgorithmRunning": 5,
            "SystemRunningWithoutSensorFusion": 6
        }
    },

    "SystemErrorCode": {
        "name": "Vals",
        "values": {
            "NoError": 0,
            "PeripheralInitError": 1,
            "SystemInitError": 2,
            "SelfTestFailed": 3,
            "RegisterMapValueOOR": 4,
            "RegisterMapAddrOOR": 5,
            "RegisterMapWriteError": 6,
            "LowPowerNotAvailableForSelectedOM": 7,
            "AccelerometerPowerModeNotAvailable": 8,
            "FusionAlgorithmError": 9,
            "SensorConfigurationError": 10
        }
    },

    "InterruptReadState": {
        "name": 'InterruptReadState',
        "values": {
            "IDLE": 0,
            "READ_ACCEL": 1,
            "READ_GYRO": 2,
            "READ_MAG": 3,
            "ERROR": 4
        }
    },

    "InterruptReadMode": {
        "name": 'InterruptReadMode',
        "values": {
            "SINGLE": 0,
            "CONTINUOUS": 1
        }
    },

    "CommHandlerState": {
        "name": "State",
        "values": {
            "Idle": 0,
            "Receiving": 1,
            "Transmitting": 2
        }
    },

    "CommHandlerRxFSMState": {
        "name": "RxFSMState",
        "values": {
            "WaitForCommand": 0,
            "WaitForSubfunction": 1,
            "WaitForLength": 2,
            "WaitForData": 3,
            "WaitForCRC": 4,
            "WaitForProcess": 5,
            "Error": 6
        }
    },

    "CommHandlerRxError": {
        "name": "RxError",
        "values": {
            "None": 0,
            "Overflow": 1,
            "Disabled": 2,
            "InvalidCommand": 3,
        }
    },

    "CommHandlerTxError": {
        "name": "TxError",
        "values": {
            "None": 0,
            "Overflow": 1,
            "Busy": 2,
            "Disabled": 3
        }
    },

    "DataloggerState": {
        "name": "State",
        "values": {
            "IDLE": 0,
            "CONFIGURED": 1,
            "ARMED": 2,
            "TRIGGERED": 3,
            "ACQUISITION_COMPLETED": 4,
            "ERROR": 5
        }
    },

    #   TODO : To enable when arrays are supported
    #    "LoggableType": {
    #        "name" : "LoggableType",
    #        "values" : {
    #            "MEMORY": 0,
    #            "RPV": 1,
    #            "TIME": 2
    #        }
    #    },

    "SupportedTriggerConditions": {
        "name": "SupportedTriggerConditions",
        "values": {
            "AlwaysTrue": 0,
            "Equal": 1,
            "NotEqual": 2,
            "LessThan": 3,
            "LessOrEqualThan": 4,
            "GreaterThan": 5,
            "GreaterOrEqualThan": 6,
            "ChangeMoreThan": 7,
            "IsWithin": 8
        }
    },

    # TODO : Enable when arrays are supported
    #    "OperandType": {
    #        "name":"OperandType",
    #        "values" : {
    #            "LITERAL": 0,
    #            "VAR": 1,
    #            "VARBIT": 2,
    #            "RPV": 3
    #        }
    #    },

    "DataloggingError": {
        "name": "DataloggingError",
        "values": {
            "NoError": 0,
            "UnexpectedRelease": 1,
            "UnexpectedClaim": 2
        }
    },

    "Main2LoopMessageID": {
        "name": "Main2LoopMessageID",
        "values": {
            "RELEASE_DATALOGGER_OWNERSHIP": 0,
            "TAKE_DATALOGGER_OWNERSHIP": 1,
            "DATALOGGER_ARM_TRIGGER": 2,
            "DATALOGGER_DISARM_TRIGGER": 3
        }
    },

    "Loop2MainMessageID": {
        "name": "Loop2MainMessageID",
        "values": {
            "DATALOGGER_OWNERSHIP_TAKEN": 0,
            "DATALOGGER_OWNERSHIP_RELEASED": 1,
            "DATALOGGER_DATA_ACQUIRED": 2,
            "DATALOGGER_STATUS_UPDATE": 3
        }
    }
}


class TestMakeVarMap_ATMega2560_LE_avr_gcc_5_4_0(BaseVarmapTest, ScrutinyUnitTest):
    bin_filename = get_artifact('scrutiny-nsec2024_untagged.elf')
    memdump_filename = None
    known_enums = KNOWN_ENUMS

    _CPP_FILT = 'c++filt'

    def test_main_cpp(self):
        self.assert_var('/static/main.cpp/task_100hz()/var_100hz', EmbeddedDataType.uint32)
        self.assert_var('/static/main.cpp/task_1hz()/var_1hz', EmbeddedDataType.uint32)
        self.assert_var('/static/main.cpp/task_1hz()/led_state', EmbeddedDataType.sint16)

        self.assert_var('/static/main.cpp/loop/last_timestamp_us', EmbeddedDataType.uint32)
        self.assert_var('/static/main.cpp/loop/last_timestamp_task_1hz_us', EmbeddedDataType.uint32)
        self.assert_var('/static/main.cpp/loop/last_timestamp_task_100hz_us', EmbeddedDataType.uint32)

    def test_loop_handlers(self):
        self.assert_var('/global/task_idle_loop_handler/m_timebase/m_time_100ns', EmbeddedDataType.uint32)
        self.assert_var('/global/task_idle_loop_handler/m_main2loop_msg/m_written', EmbeddedDataType.boolean)
        self.assert_var('/global/task_idle_loop_handler/m_main2loop_msg/data/message_id', EmbeddedDataType.uint8, enum='Main2LoopMessageID')
        self.assert_var('/global/task_idle_loop_handler/m_loop2main_msg/m_written', EmbeddedDataType.boolean)
        self.assert_var('/global/task_idle_loop_handler/m_loop2main_msg/data/message_id', EmbeddedDataType.uint8, enum='Loop2MainMessageID')

        self.assert_var('/global/task_idle_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/state',
                        EmbeddedDataType.uint8, enum='DataloggerState')
        self.assert_var(
            '/global/task_idle_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/bytes_to_acquire_from_trigger_to_completion', EmbeddedDataType.uint16)
        self.assert_var('/global/task_idle_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/write_counter_since_trigger', EmbeddedDataType.uint16)

        self.assert_var('/global/task_idle_loop_handler/m_owns_datalogger', EmbeddedDataType.boolean)
        self.assert_var('/global/task_idle_loop_handler/m_datalogger_data_acquired', EmbeddedDataType.boolean)
        self.assert_var('/global/task_idle_loop_handler/m_support_datalogging', EmbeddedDataType.boolean)

        self.assert_var('/global/task_100hz_loop_handler/m_timestep_100ns', EmbeddedDataType.uint32)
        self.assert_var('/global/task_100hz_loop_handler/m_timebase/m_time_100ns', EmbeddedDataType.uint32)
        self.assert_var('/global/task_100hz_loop_handler/m_main2loop_msg/m_written', EmbeddedDataType.boolean)
        self.assert_var('/global/task_100hz_loop_handler/m_main2loop_msg/data/message_id', EmbeddedDataType.uint8, enum='Main2LoopMessageID')
        self.assert_var('/global/task_100hz_loop_handler/m_loop2main_msg/m_written', EmbeddedDataType.boolean)
        self.assert_var('/global/task_100hz_loop_handler/m_loop2main_msg/data/message_id', EmbeddedDataType.uint8, enum='Loop2MainMessageID')
        self.assert_var('/global/task_100hz_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/state',
                        EmbeddedDataType.uint8, enum='DataloggerState')
        self.assert_var(
            '/global/task_100hz_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/bytes_to_acquire_from_trigger_to_completion', EmbeddedDataType.uint16)
        self.assert_var('/global/task_100hz_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/write_counter_since_trigger', EmbeddedDataType.uint16)

        self.assert_var('/global/task_100hz_loop_handler/m_owns_datalogger', EmbeddedDataType.boolean)
        self.assert_var('/global/task_100hz_loop_handler/m_datalogger_data_acquired', EmbeddedDataType.boolean)
        self.assert_var('/global/task_100hz_loop_handler/m_support_datalogging', EmbeddedDataType.boolean)

        self.assert_var('/global/task_20hz_loop_handler/m_timestep_100ns', EmbeddedDataType.uint32)
        self.assert_var('/global/task_20hz_loop_handler/m_timebase/m_time_100ns', EmbeddedDataType.uint32)
        self.assert_var('/global/task_20hz_loop_handler/m_main2loop_msg/m_written', EmbeddedDataType.boolean)
        self.assert_var('/global/task_20hz_loop_handler/m_main2loop_msg/data/message_id', EmbeddedDataType.uint8, enum='Main2LoopMessageID')
        self.assert_var('/global/task_20hz_loop_handler/m_loop2main_msg/m_written', EmbeddedDataType.boolean)
        self.assert_var('/global/task_20hz_loop_handler/m_loop2main_msg/data/message_id', EmbeddedDataType.uint8, enum='Loop2MainMessageID')
        self.assert_var('/global/task_20hz_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/state',
                        EmbeddedDataType.uint8, enum='DataloggerState')
        self.assert_var(
            '/global/task_20hz_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/bytes_to_acquire_from_trigger_to_completion', EmbeddedDataType.uint16)
        self.assert_var('/global/task_20hz_loop_handler/m_loop2main_msg/data/data/datalogger_status_update/write_counter_since_trigger', EmbeddedDataType.uint16)

        self.assert_var('/global/task_20hz_loop_handler/m_owns_datalogger', EmbeddedDataType.boolean)
        self.assert_var('/global/task_20hz_loop_handler/m_datalogger_data_acquired', EmbeddedDataType.boolean)
        self.assert_var('/global/task_20hz_loop_handler/m_support_datalogging', EmbeddedDataType.boolean)

    def test_main_handler(self):
        # self.assert_var("/static/scrutiny_integration.cpp/config/m_rx_buffer", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_rx_buffer_size", EmbeddedDataType.uint16)
        # self.assert_var("/static/scrutiny_integration.cpp/config/m_tx_buffer", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_tx_buffer_size", EmbeddedDataType.uint16)
        # self.assert_var("/static/scrutiny_integration.cpp/config/m_forbidden_address_ranges", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_forbidden_range_count", EmbeddedDataType.uint8)
        # self.assert_var("/static/scrutiny_integration.cpp/config/m_readonly_address_ranges", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_readonly_range_count", EmbeddedDataType.uint8)
        # self.assert_var("/static/scrutiny_integration.cpp/config/m_rpvs", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_rpv_count", EmbeddedDataType.uint16)
        # self.assert_var("/static/scrutiny_integration.cpp/config/m_rpv_read_callback", EmbeddedDataType.pointer)
        # self.assert_var("/static/scrutiny_integration.cpp/config/m_rpv_write_callback", EmbeddedDataType.pointer)
        # self.assert_var("/static/scrutiny_integration.cpp/config/m_loops", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_loop_count", EmbeddedDataType.uint8)
        # self.assert_var("/static/scrutiny_integration.cpp/config/m_user_command_callback", EmbeddedDataType.pointer)
        # self.assert_var("/static/scrutiny_integration.cpp/config/m_datalogger_buffer", EmbeddedDataType.pointer)
        self.assert_var("/static/scrutiny_integration.cpp/config/m_datalogger_buffer_size", EmbeddedDataType.uint16)
        # self.assert_var("/static/scrutiny_integration.cpp/config/m_datalogger_trigger_callback", EmbeddedDataType.pointer)

        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_timebase/m_time_100ns", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_state", EmbeddedDataType.uint8, enum='CommHandlerState')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_enabled", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_session_id", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_session_active", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_heartbeat_timestamp", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_last_heartbeat_challenge", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_first_heartbeat_received", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_rx_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_tx_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_request/command_id", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_request/subfunction_id", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_request/data_length", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_request/data_max_length", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_request/crc", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_rx_state",
                        EmbeddedDataType.uint8, enum='CommHandlerRxFSMState')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_rx_error", EmbeddedDataType.uint8, enum='CommHandlerRxError')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_request_received", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_per_state_data/crc_bytes_received", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_per_state_data/length_bytes_received", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_per_state_data/data_bytes_received", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_last_rx_timestamp", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_response/command_id", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_response/subfunction_id", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_response/response_code", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_response/data_length", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_response/data_max_length", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_active_response/crc", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_nbytes_to_send", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_nbytes_sent", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_comm_handler/m_tx_error", EmbeddedDataType.uint8, enum='CommHandlerTxError')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_processing_request", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_disconnect_pending", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/max_bitrate", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/session_counter_seed", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/memory_write_enable", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_rx_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_tx_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_forbidden_range_count", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_readonly_range_count", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_rpv_count", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_loop_count", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_config/m_datalogger_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_enabled", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_process_again_timestamp_taken", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_process_again_timestamp", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_state",
                        EmbeddedDataType.uint8, enum='DataloggerState')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_trigger_timestamp", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_trigger_cursor_location", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_remaining_data_to_write", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_manual_trigger", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/items_count", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/decimation", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/probe_location", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/timeout_100ns", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/trigger/condition",
                        EmbeddedDataType.uint8, enum='SupportedTriggerConditions')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/trigger/operand_count", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config/trigger/hold_time_100ns", EmbeddedDataType.uint32)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config_valid", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_buffer_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_reader/m_read_cursor", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_reader/m_finished", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_reader/m_read_started", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_max_entries", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_next_entry_write_index", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_first_valid_entry_index", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_entry_write_counter", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_entry_size", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_entries_count", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_full", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_encoder/m_error", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_decimation_counter", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_acquisition_id", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_config_id", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_log_points_after_trigger", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_trigger/previous_val", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_trigger/rising_edge_timestamp", EmbeddedDataType.uint32)
        self.assert_var(
            "/static/scrutiny_integration.cpp/main_handler/m_datalogging/datalogger/m_trigger/conditions/m_data/cmt/initialized", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/threadsafe_data/datalogger_state",
                        EmbeddedDataType.uint8, enum='DataloggerState')
        self.assert_var(
            "/static/scrutiny_integration.cpp/main_handler/m_datalogging/threadsafe_data/bytes_to_acquire_from_trigger_to_completion", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/threadsafe_data/write_counter_since_trigger", EmbeddedDataType.uint16)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/error", EmbeddedDataType.uint8, enum='DataloggingError')
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/request_arm_trigger", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/request_ownership_release", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/request_disarm_trigger", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/pending_ownership_release", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/reading_in_progress", EmbeddedDataType.boolean)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/read_acquisition_rolling_counter", EmbeddedDataType.uint8)
        self.assert_var("/static/scrutiny_integration.cpp/main_handler/m_datalogging/read_acquisition_crc", EmbeddedDataType.uint32)

    def test_scrutiny_integration(self):
        self.assert_var(
            "/static/scrutiny_integration.cpp/rpv_write_callback(scrutiny::RuntimePublishedValue, scrutiny::AnyType const*)/some_counter", EmbeddedDataType.uint32)

    def test_bno055(self):
        self.assert_var('/global/bno055/m_i2c_addr', EmbeddedDataType.uint8)
        self.assert_var('/global/bno055/m_last_error_code', EmbeddedDataType.uint8)
        self.assert_var('/global/bno055/m_error', EmbeddedDataType.uint8, enum='Bno055DriverError')
        self.assert_var('/global/bno055/m_sys_status_at_boot', EmbeddedDataType.uint16, enum='SystemStatusCode')
        self.assert_var('/global/bno055/m_sys_error_at_boot', EmbeddedDataType.uint16, enum='SystemErrorCode')
        self.assert_var('/global/bno055/m_chip_info/acc_chip_id', EmbeddedDataType.uint8)
        self.assert_var('/global/bno055/m_chip_info/gyro_chip_id', EmbeddedDataType.uint8)
        self.assert_var('/global/bno055/m_chip_info/mag_chip_id', EmbeddedDataType.uint8)
        self.assert_var('/global/bno055/m_chip_info/sw_revision', EmbeddedDataType.uint16)
        self.assert_var('/global/bno055/m_chip_info/bootloader_version', EmbeddedDataType.uint8)
        self.assert_var('/global/bno055/m_double_buffer_flag', EmbeddedDataType.boolean)
        self.assert_var('/global/bno055/m_interrupt_read_state', EmbeddedDataType.uint8, enum='InterruptReadState')
        self.assert_var('/global/bno055/m_interrupt_read_mode', EmbeddedDataType.uint8, enum='InterruptReadMode')

        self.assert_var('/global/bno055/m_acc/x', EmbeddedDataType.sint16)
        self.assert_var('/global/bno055/m_acc/y', EmbeddedDataType.sint16)
        self.assert_var('/global/bno055/m_acc/z', EmbeddedDataType.sint16)

        self.assert_var('/global/bno055/m_gyro/x', EmbeddedDataType.sint16)
        self.assert_var('/global/bno055/m_gyro/y', EmbeddedDataType.sint16)
        self.assert_var('/global/bno055/m_gyro/z', EmbeddedDataType.sint16)

        self.assert_var('/global/bno055/m_mag/x', EmbeddedDataType.sint16)
        self.assert_var('/global/bno055/m_mag/y', EmbeddedDataType.sint16)
        self.assert_var('/global/bno055/m_mag/z', EmbeddedDataType.sint16)

        # self.assert_var('/global/bno055/m_i2c_rx_buffer', array)
        self.assert_var('/global/bno055/m_i2c_data_available', EmbeddedDataType.boolean)
        self.assert_var('/global/bno055/m_i2c_data_len', EmbeddedDataType.uint8)


if __name__ == '__main__':
    import unittest
    unittest.main()
