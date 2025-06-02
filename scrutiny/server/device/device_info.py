#    device_info.py
#        All the information that can be extracted from the device through the Scrutiny protocol
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = [
    'ExecLoopType',
    'ExecLoop',
    'FixedFreqLoop',
    'VariableFreqLoop',
    'SupportedFeatureMap',
    'DeviceInfo'
]

from enum import Enum
from abc import abstractmethod

from scrutiny.core.basic_types import *
import scrutiny.server.datalogging.definitions.device as device_datalogging

from scrutiny.tools.typing import *


class ExecLoopType(Enum):
    FIXED_FREQ = 0
    VARIABLE_FREQ = 1


class ExecLoop:
    name: str
    support_datalogging: bool

    def __init__(self, name: str, support_datalogging: bool = True) -> None:
        self.name = name
        self.support_datalogging = support_datalogging

    def set_name(self, name: str) -> None:
        self.name = name

    def get_name(self) -> str:
        return self.name

    @abstractmethod
    def get_loop_type(self) -> ExecLoopType:
        raise NotImplementedError('Abstract method')


class FixedFreqLoop(ExecLoop):
    freq: float

    def __init__(self, freq: float, name: str, support_datalogging: bool = True) -> None:
        super().__init__(name, support_datalogging)
        self.freq = freq

    def get_loop_type(self) -> ExecLoopType:
        return ExecLoopType.FIXED_FREQ

    def get_timestep_100ns(self) -> int:
        return round(1e7 / self.freq)

    def get_frequency(self) -> float:
        return self.freq


class VariableFreqLoop(ExecLoop):

    def __init__(self, name: str, support_datalogging: bool = True):
        super().__init__(name, support_datalogging)

    def get_loop_type(self) -> ExecLoopType:
        return ExecLoopType.VARIABLE_FREQ


class SupportedFeatureMap(TypedDict):
    """Dictionnary of all possible supported features by the device (libscrutiny-embedded)"""
    memory_write: bool
    datalogging: bool
    user_command: bool
    _64bits: bool


class DeviceInfo:
    """Container for all data that can be gathered from a device while initializing the communication with it"""
    __slots__ = (
        'device_id',
        'display_name',
        'max_tx_data_size',
        'max_rx_data_size',
        'max_bitrate_bps',
        'rx_timeout_us',
        'heartbeat_timeout_us',
        'address_size_bits',
        'protocol_major',
        'protocol_minor',
        'supported_feature_map',
        'forbidden_memory_regions',
        'readonly_memory_regions',
        'runtime_published_values',
        'loops',
        'datalogging_setup'
    )

    device_id: Optional[str]
    """The device firmware ID uniquely identifying the firmware"""

    display_name: Optional[str]
    """The textual name broadcasted by the device"""

    max_tx_data_size: Optional[int]
    """The maximum payload size that the device can send. Limited by its internal buffer size"""

    max_rx_data_size: Optional[int]
    """The maximum payload size that the device can receive. Limited by its internal buffer size"""

    max_bitrate_bps: Optional[int]
    """The maximum bitrate requested by the device."""

    rx_timeout_us: Optional[int]
    """The amount of time, in microseconds that the device will wait before resetting it's internal reception state machine"""

    heartbeat_timeout_us: Optional[int]
    """The number of time, in microseconds, that the device will wait without receiving a heartbeat before resetting the session"""

    address_size_bits: Optional[int]
    """Device address size in bits. Value of sizeof(void*)*8 """

    protocol_major: Optional[int]
    """Protocol version major number"""

    protocol_minor: Optional[int]
    """Protocol version minor number"""

    supported_feature_map: Optional[SupportedFeatureMap]
    """Dictionary listing all supported feature"""

    forbidden_memory_regions: Optional[List[MemoryRegion]]
    """List of all memory regions that are forbidden to access broadcasted by the device"""

    readonly_memory_regions: Optional[List[MemoryRegion]]
    """List of all memory regions that are readonly broadcasted by the device"""

    runtime_published_values: Optional[List[RuntimePublishedValue]]
    """List of all RuntimePublishedValues (RPV) registered in the device firmware"""

    loops: Optional[List[ExecLoop]]
    """List of execution loops (tasks) exposed by the embedded device"""

    datalogging_setup: Optional[device_datalogging.DataloggingSetup]

    def get_attributes(self) -> Tuple[str, ...]:
        return self.__slots__

    def __init__(self) -> None:
        self.clear()

    def all_ready(self) -> bool:
        """Returns True when all attributes are set to something (not None)"""

        expected_props = set(self.__slots__)
        expected_props.remove('datalogging_setup')
        ready = True
        for attr in expected_props:
            if getattr(self, attr) is None:
                ready = False
                break

        # datalogging_setup can be None if not supported.
        if ready:
            assert self.supported_feature_map is not None
            if self.supported_feature_map['datalogging']:
                if self.datalogging_setup is None:
                    return False
        return ready

    def clear(self) -> None:
        """Clear all attributes by setting them to None"""
        for attr in self.__slots__:
            setattr(self, attr, None)

    def __str__(self) -> str:
        dict_out = {}
        for attr in self.__slots__:
            dict_out[attr] = getattr(self, attr)
        return str(dict_out)
