#    definitions.py
#        Global definitions of types, constants, enums used across the Scrutiny SDK
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2023 Scrutiny Debugger

__all__ = [
    'AddressSize',
    'ServerState',
    'WatchableType',
    'ValueStatus',
    'DeviceCommState',
    'DataloggingState',
    'DeviceLinkType',
    'DataloggingListChangeType',
    'SupportedFeatureMap',
    'DataloggingInfo',
    'DeviceInfo',
    'SFDGenerationInfo',
    'SFDMetadata',
    'SFDInfo',
    'BaseLinkConfig',
    'UDPLinkConfig',
    'TCPLinkConfig',
    'SerialLinkConfig',
    'RTTLinkConfig',
    'NoneLinkConfig',
    'CANLinkConfig',
    'SupportedLinkConfig',
    'DeviceLinkInfo',
    'ServerInfo',
    'UserCommandResponse',
    'WatchableConfiguration',
    'DataloggingEncoding',
    'SamplingRate',
    'FixedFreqSamplingRate',
    'VariableFreqSamplingRate',
    'DataloggingCapabilities',
    'ServerStatistics',
    'EmbeddedEnum'
]

import enum
from dataclasses import dataclass
from scrutiny.core.basic_types import MemoryRegion, EmbeddedDataType, WatchableType
from scrutiny.core.embedded_enum import EmbeddedEnum
from scrutiny.core.firmware_description import SFDMetadata, SFDGenerationInfo
from scrutiny.core.datalogging import DataloggingState
from scrutiny.tools import validation
import abc
from binascii import hexlify

from scrutiny.tools.typing import *


AddressSize = Literal[8, 16, 32, 64, 128]


class ServerState(enum.Enum):
    """(Enum) The state of the connection between the client and the server"""

    Disconnected = 0
    """Disconnected from the server"""
    Connecting = 1
    """Client is trying to connect, full TCP handshake is in progress"""
    Connected = 2
    """Socket is open and functional"""
    Error = -1
    """The communication closed after an error"""


class DeviceCommState(enum.Enum):
    """(Enum) The state of the connection with the device"""

    NA = 0
    Disconnected = 1
    """No device connected"""
    Connecting = 2
    """Handshake in progress between the server and the device"""
    ConnectedReady = 3
    """A device is connected and ready to respond to queries."""


class ValueStatus(enum.Enum):
    """(Enum) Represent the validity status of a watchable value"""

    Valid = 1
    """Value is valid"""

    NeverSet = 2
    """Invalid - Never received a value"""

    ServerGone = 3
    """Invalid - Server is gone and cannot provide updates anymore"""

    DeviceGone = 4
    """Invalid - The device is gone and cannot provide updates anymore"""

    SFDUnloaded = 4
    """Invalid - The Scrutiny Firmware Description file has been unloaded and the value is not available anymore"""

    NotWatched = 5
    """Invalid - The watchable is not being watched"""

    def _get_error(self) -> str:
        error = ""
        if self == ValueStatus.Valid:
            pass
        elif self == ValueStatus.NeverSet:
            error = 'Never set'
        elif self == ValueStatus.ServerGone:
            error = "Server has gone away"
        elif self == ValueStatus.DeviceGone:
            error = "Device has been disconnected"
        elif self == ValueStatus.SFDUnloaded:
            error = "Firmware Description File has been unloaded"
        elif self == ValueStatus.NotWatched:
            error = "Not watched"
        else:
            raise RuntimeError(f"Unknown value status {self}")

        return error


class DeviceLinkType(enum.Enum):
    """(Enum) The type of communication link used between the server and the device"""

    _Dummy = -1
    NONE = 0
    """No link. No device communication will happen"""
    UDP = 1
    """UDP/IP socket"""
    TCP = 2
    """TCP/IP Socket"""
    Serial = 3
    """Serial port"""
    RTT = 4
    """Segger JLink Real-Time Transfer port"""
    CAN = 5
    """CAN Bus"""
    # SPI = 6 # Todo


class DataloggingListChangeType(enum.Enum):
    """(Enum) The type of change that was performed on the server datalogging storage """

    DELETE = 0
    """An acquisition was deleted"""
    NEW = 1
    """A new acquisition is available"""
    UPDATE = 2
    """An acquisition was modified"""
    DELETE_ALL = 3
    """The server datalogging storage has been cleared completely"""


@dataclass(frozen=True)
class SupportedFeatureMap:
    """(Immutable struct) Represent the list of features that the connected device supports"""

    memory_write: bool
    """Indicates if the device allows write to memory"""

    datalogging: bool
    """Indicates if the device is able of doing datalogging"""

    user_command: bool
    """Indicates if the device has a callback set for the user command"""

    sixtyfour_bits: bool
    """Indicates if the device supports 64bits element. 64bits RPV and datalogging of 64bits elements (variable or RPV) are not possible if ``False``. 
    Watching 64 bits variables does not depends on the device and is therefore always possible"""


@dataclass(frozen=True)
class DataloggingInfo:
    """(Immutable struct) Information about the datalogger that are volatile (change during the normal operation)"""

    state: DataloggingState
    """The state of the datalogger in the device"""

    completion_ratio: Optional[float]
    """The completion ratio of the actually running acquisition. ``None`` if no acquisition being captured"""


class DataloggingEncoding(enum.Enum):
    """(Enum) Defines the data format used to store the samples in the datalogging buffer.
    This structure is a provision for the future where new encoding methods may be implemented (supporting compression for example)
    """
    RAW = 1


@dataclass(frozen=True, init=False)
class SamplingRate:
    """(Immutable struct) Represent a sampling rate supported by the device"""

    identifier: int
    """The unique identifier of the sampling rate. Matches the embedded device index in the loop array set in the configuration"""

    name: str
    """Name for display only"""


@dataclass(frozen=True)
class FixedFreqSamplingRate(SamplingRate):
    """(Immutable struct) Represent a fixed frequency sampling rate supported by the device"""

    frequency: float
    """The sampling rate frequency"""

    def __post_init__(self) -> None:
        validation.assert_type(self.identifier, 'identifier', int)
        validation.assert_type(self.name, 'name', str)
        validation.assert_type(self.frequency, 'frequency', float)


@dataclass(frozen=True)
class VariableFreqSamplingRate(SamplingRate):
    """(Immutable struct) Represent a variable frequency sampling rate supported by the device. Has no known frequency"""

    def __post_init__(self) -> None:
        validation.assert_type(self.identifier, 'identifier', int)
        validation.assert_type(self.name, 'name', str)


@dataclass(frozen=True)
class DataloggingCapabilities:
    """(Immutable struct) Tells what the device is able to achieve in terms of datalogging"""

    encoding: DataloggingEncoding
    """The encoding of data"""

    buffer_size: int
    """Size of the datalogging buffer"""

    max_nb_signal: int
    """Maximum number of signals per acquisition (including time if measured)"""

    sampling_rates: List[SamplingRate]
    """List of available sampling rates"""

    def __post_init__(self) -> None:
        validation.assert_type(self.encoding, 'encoding', DataloggingEncoding)
        validation.assert_type(self.buffer_size, 'buffer_size', int)
        validation.assert_type(self.max_nb_signal, 'max_nb_signal', int)
        validation.assert_type(self.sampling_rates, 'sampling_rates', list)
        for i in range(len(self.sampling_rates)):
            validation.assert_type(self.sampling_rates[i], f'sampling_rates[{i}]', SamplingRate)


@dataclass(frozen=True)
class DeviceInfo:
    """(Immutable struct) Information about the device connected to the server"""

    session_id: str
    """The unique ID assigned to the communication session between the server abd the device when this data was gathered"""

    device_id: str
    """A unique ID identifying the device and its software (Firmware ID). """

    display_name: str
    """The display name broadcast by the device"""

    max_tx_data_size: int
    """Maximum payload size that the device can send"""

    max_rx_data_size: int
    """Maximum payload size that the device can receive"""

    max_bitrate_bps: Optional[int]
    """Maximum bitrate between the device and the server. Requested by the device. ``None`` if no throttling is requested"""

    rx_timeout_us: int
    """Amount of time without data being received that the device will wait to restart its reception state machine (new frame)"""

    heartbeat_timeout: float
    """Timeout value without heartbeat message response to consider that the communication is broken, in seconds"""

    address_size_bits: AddressSize
    """Address size in the device"""

    protocol_major: int
    """Device communication protocol version (major number)"""

    protocol_minor: int
    """Device communication protocol version (minor number)"""

    supported_features: SupportedFeatureMap
    """Features supported by the device"""

    forbidden_memory_regions: List[MemoryRegion]
    """List of memory region that cannot be access"""

    readonly_memory_regions: List[MemoryRegion]
    """List of memory region that are read-only"""

    datalogging_capabilities: Optional[DataloggingCapabilities]
    """Contains the device datalogging capabilites. ``None`` if datalogging is not supported"""


@dataclass(frozen=True)
class SFDInfo:
    """(Immutable struct) Represent a Scrutiny Firmware Description"""

    firmware_id: str
    """Unique firmware hash"""

    metadata: Optional[SFDMetadata]
    """The firmware metadata embedded in the Scrutiny Firmware Description file if available. ``None`` if no metadata has been added to the SFD"""


class BaseLinkConfig(abc.ABC):
    def _to_api_format(self) -> Dict[str, Any]:
        raise NotImplementedError("Abstract class")


@dataclass(frozen=True)
class NoneLinkConfig(BaseLinkConfig):
    """(Immutable struct) An Empty object acting as configuration structure for a device link of type :attr:`NONE<scrutiny.sdk.DeviceLinkType.NONE>`
    Exists only to differentiate ``None`` (data not available) from :class:`NoneLinkConfig<scrutiny.sdk.NoneLinkConfig>` (data available - no link configured)
    """

    def _to_api_format(self) -> Dict[str, Any]:
        return {}


@dataclass(frozen=True)
class UDPLinkConfig(BaseLinkConfig):
    """(Immutable struct) The configuration structure for a device link of type :attr:`UDP<scrutiny.sdk.DeviceLinkType.UDP>`"""

    host: str
    """Target device hostname"""
    port: int
    """Device UDP port number"""

    def __post_init__(self) -> None:
        validation.assert_int_range(self.port, 'port', 0, 0xFFFF)

    def _to_api_format(self) -> Dict[str, Any]:
        return {
            'host': self.host,
            'port': self.port
        }


@dataclass(frozen=True)
class TCPLinkConfig(BaseLinkConfig):
    """(Immutable struct) The configuration structure for a device link of type :attr:`TCP<scrutiny.sdk.DeviceLinkType.TCP>`"""

    host: str
    """Target device hostname"""
    port: int
    """Device TCP port number"""

    def __post_init__(self) -> None:
        validation.assert_int_range(self.port, 'port', 0, 0xFFFF)
        validation.assert_type(self.host, 'host', str)

    def _to_api_format(self) -> Dict[str, Any]:
        return {
            'host': self.host,
            'port': self.port
        }


@dataclass(frozen=True)
class SerialLinkConfig(BaseLinkConfig):
    """(Immutable struct) The configuration structure for a device link of type :attr:`Serial<scrutiny.sdk.DeviceLinkType.Serial>`"""

    class StopBits(enum.Enum):
        """Number of stop bits as defined by RS-232"""
        ONE = 1
        ONE_POINT_FIVE = 1.5
        TWO = 2

        def get_numerical(self) -> float:
            """Return the number of stop bits as ``float``"""
            return float(self.value)

        @classmethod
        def from_float(cls, v: float, default: Optional["Self"] = None) -> "Self":
            try:
                return cls(v)
            except Exception:
                if default is None:
                    raise
                return default

        def to_float(self) -> float:
            return float(self.value)

    class DataBits(enum.Enum):
        """Number of data bits as defined by RS-232"""
        FIVE = 5
        SIX = 6
        SEVEN = 7
        EIGHT = 8

        def get_numerical(self) -> int:
            """Return the number of data bits as ``int``"""
            return int(self.value)

        @classmethod
        def from_int(cls, v: int, default: Optional["Self"] = None) -> "Self":
            try:
                return cls(v)
            except Exception:
                if default is None:
                    raise
                return default

        def to_int(self) -> int:
            return self.value

    class Parity(enum.Enum):
        """A serial port parity configuration"""
        NONE = "none"
        EVEN = "even"
        ODD = "odd"
        MARK = "mark"
        SPACE = "space"

        def get_displayable_name(self) -> str:
            """Return the value as ``str``"""
            return self.value

        @classmethod
        def from_str(cls, v: str, default: Optional["Self"] = None) -> "Self":
            try:
                return cls(v)
            except Exception:
                if default is None:
                    raise
                return default

        def to_str(self) -> str:
            return self.value

    port: str
    """Port name on the machine. COMX on Windows. /dev/xxx on posix platforms"""
    baudrate: int
    """Communication speed in baud/sec"""
    start_delay: float
    """A delay of communication silence after opening the port. Accomodate devices that triggers a bootloader upon port open (like Arduino)."""
    stopbits: StopBits = StopBits.ONE
    """Number of stop bits. 1, 1.5, 2"""
    databits: DataBits = DataBits.EIGHT
    """Number of data bits. 5, 6, 7, 8"""
    parity: Parity = Parity.NONE
    """Serial communication parity bits"""

    def __post_init__(self) -> None:
        validation.assert_type(self.port, 'port', str)
        validation.assert_int_range(self.baudrate, 'baudrate', minval=1)
        validation.assert_type(self.stopbits, 'stopbits', self.StopBits)
        validation.assert_type(self.databits, 'databits', self.DataBits)
        validation.assert_type(self.parity, 'parity', self.Parity)
        validation.assert_float_range(self.start_delay, 'start_delay', minval=0)

    def _to_api_format(self) -> Dict[str, Any]:
        return {
            'portname': self.port,
            'baudrate': self.baudrate,
            'stopbits': str(self.stopbits.value),
            'databits': self.databits.value,
            'parity': self.parity.value,
            'start_delay': self.start_delay
        }


@dataclass(frozen=True)
class RTTLinkConfig(BaseLinkConfig):
    """(Immutable struct) The configuration structure for a device link of type :attr:`RTT<scrutiny.sdk.DeviceLinkType.RTT>`"""

    class JLinkInterface(enum.Enum):
        """Type of JLink interface used when calling ``JLink.set_tif()``. 
        Refer to Segger documentation for more details. The values of this enum are not meant to be in sync with the Segger API.
        The server will convert the SDK value to a JLink enum
        """

        JTAG = 'jtag'
        """ARM Multi-ICE compatible JTAG adapter"""

        SWD = 'swd'
        """ARM Serial Wire Debug"""

        FINE = 'fine'
        """Segger Rx Fine adapter"""

        ICSP = 'icsp'
        """Microchip In-Circuit Serial Programming"""

        SPI = 'spi'
        """Motorola Serial Peripheral Interface"""

        C2 = 'c2'
        """SiLabs C2 Adapter"""

        def to_str(self) -> str:
            return self.value

        @classmethod
        def from_str(cls, v: str, default: Optional["Self"] = None) -> "Self":
            try:
                return cls(v)
            except Exception:
                if default is None:
                    raise
                return default

    target_device: str
    """Chip name passed to pylink ``JLink.connect()`` method"""

    jlink_interface: JLinkInterface
    """The type of JLink interface"""

    def __post_init__(self) -> None:
        validation.assert_type(self.target_device, 'target_device', str)
        validation.assert_type(self.jlink_interface, 'jlink_interface', self.JLinkInterface)

    def _to_api_format(self) -> Dict[str, Any]:
        return {
            'target_device': self.target_device,
            'jlink_interface': self.jlink_interface.value
        }

# region CAN bus


@dataclass(frozen=True)
class CANLinkConfig(BaseLinkConfig):
    """(Immutable struct) The configuration structure for a device link of type :attr:`CAN<scrutiny.sdk.DeviceLinkType.CAN>`"""

    class CANInterface(enum.Enum):
        """Type of CAN interface instantiated with ``python-can``."""

        SocketCAN = 0
        """Connect to a SocketCAN network interface."""
        Vector = 1
        """Use Vector hardware through the Vector XL API. The XL Driver library must be installed on the server"""
        KVaser = 2
        """Use KVaser hardware"""
        PCAN = 3
        """Use PCAN hardware through the PCAN API"""
        ETAS = 4
        """Use ETAS hardware through the ETAS DLL."""

    @dataclass(frozen=True)
    class SocketCANConfig:
        """
        (Immutable struct) A SocketCAN specific configuration used when 
        :attr:`CANLinkConfig.interface<scrutiny.sdk.CANLinkConfig.interface>` = :attr:`SocketCAN<scrutiny.sdk.CANLinkConfig.CANInterface.SocketCAN>`.

        Refer to ``python-can`` documentation for more details.
        """
        channel: str
        """The name of the network interface"""

        def __post_init__(self) -> None:
            validation.assert_type(self.channel, 'channel', str)

        def _to_api_format(self) -> Dict[str, Any]:
            return {
                'channel': self.channel
            }

    @dataclass(frozen=True)
    class VectorConfig:
        """
        (Immutable struct) A Vector specific configuration used when 
        :attr:`CANLinkConfig.interface<scrutiny.sdk.CANLinkConfig.interface>` = :attr:`Vector<scrutiny.sdk.CANLinkConfig.CANInterface.Vector>`. 
        
        Refer to ``python-can`` documentation for more details.
        """

        channel: Union[str, int]
        """The name of the channel or channel number"""
        bitrate: int
        """The bitrate in bit/sec"""
        data_bitrate: int
        """The data bitrate in bit/sec for CAN FD (requires a bitrate switch)"""

        def __post_init__(self) -> None:
            validation.assert_type(self.channel, 'channel', (str, int))
            if isinstance(self.channel, int):
                validation.assert_int_range(self.channel, 'channel', minval=0)

            validation.assert_int_range(self.bitrate, 'bitrate', minval=0)
            validation.assert_int_range(self.data_bitrate, 'data_bitrate', minval=0)

        def _to_api_format(self) -> Dict[str, Any]:
            return {
                'channel': self.channel,
                'bitrate': self.bitrate,
                'data_bitrate': self.data_bitrate
            }
        
    
    @dataclass(frozen=True)
    class KVaserConfig:
        """
        (Immutable struct) A KVaser specific configuration used when 
        :attr:`CANLinkConfig.interface<scrutiny.sdk.CANLinkConfig.interface>` = :attr:`KVaser<scrutiny.sdk.CANLinkConfig.CANInterface.KVaser>`. 
        
        Refer to ``python-can`` documentation for more details.
        """

        channel: int
        """The channel number"""
        bitrate: int
        """The bitrate in bit/sec"""
        data_bitrate: int
        """The data bitrate in bit/sec for CAN FD (requires a bitrate switch)"""
        fd_non_iso: bool
        """Enable non-ISO CAN FD mode (Bosch). ISO CAN FD if ``False``"""

        def __post_init__(self) -> None:
            validation.assert_int_range(self.channel, 'channel', minval=0)
            validation.assert_type(self.fd_non_iso, 'fd_non_iso', bool)
            validation.assert_int_range(self.bitrate, 'bitrate', minval=0)
            validation.assert_int_range(self.data_bitrate, 'data_bitrate', minval=0)

        def _to_api_format(self) -> Dict[str, Any]:
            return {
                'channel': self.channel,
                'bitrate': self.bitrate,
                'data_bitrate': self.data_bitrate,
                'fd_non_iso' : self.fd_non_iso
            }

    @dataclass(frozen=True)
    class PCANConfig:
        """
        (Immutable struct) A PCAN specific configuration used when 
        :attr:`CANLinkConfig.interface<scrutiny.sdk.CANLinkConfig.interface>` = :attr:`PCAN<scrutiny.sdk.CANLinkConfig.CANInterface.PCAN>`.
            
        Refer to ``python-can`` documentation for more details.
        """

        channel: str
        """The channel number"""
        bitrate: int
        """The bitrate in bit/sec"""

        def __post_init__(self) -> None:
            validation.assert_type(self.channel, 'channel', str)
            validation.assert_int_range(self.bitrate, 'bitrate', minval=0)

        def _to_api_format(self) -> Dict[str, Any]:
            return {
                'channel': self.channel,
                'bitrate': self.bitrate
            }

    @dataclass(frozen=True)
    class ETASConfig:
        """
        (Immutable struct) A ETAS specific configuration used when 
        :attr:`CANLinkConfig.interface<scrutiny.sdk.CANLinkConfig.interface>` = :attr:`ETAS<scrutiny.sdk.CANLinkConfig.CANInterface.ETAS>`. 
        
        Refer to ``python-can`` documentation for more details.
        """

        channel: str
        """The channel number"""
        bitrate: int
        """The bitrate in bit/sec"""
        data_bitrate: int
        """The data bitrate in bit/sec for CAN FD (requires a bitrate switch)"""

        def __post_init__(self) -> None:
            validation.assert_type(self.channel, 'channel', str)
            validation.assert_int_range(self.bitrate, 'bitrate', minval=0)
            validation.assert_int_range(self.data_bitrate, 'data_bitrate', minval=0)

        def _to_api_format(self) -> Dict[str, Any]:
            return {
                'channel': self.channel,
                'bitrate': self.bitrate,
                'data_bitrate': self.data_bitrate,
            }


    INTERFACE_CONFIG_MAP = {
        CANInterface.SocketCAN: SocketCANConfig,
        CANInterface.Vector: VectorConfig,
        CANInterface.KVaser: KVaserConfig,
        CANInterface.PCAN: PCANConfig,
        CANInterface.ETAS: ETASConfig,
    }


    def __post_init__(self) -> None:
        if not isinstance(self.interface, CANLinkConfig.CANInterface):
            raise TypeError("Invalid CAN interface")

        can_max = 0x1FFFFFFF if self.extended_id else 0x7FF
        validation.assert_int_range(self.txid, 'txid', minval=0, maxval=can_max)
        validation.assert_int_range(self.rxid, 'rxid', minval=0, maxval=can_max)

        validation.assert_type(self.extended_id, 'extended_id', bool)
        validation.assert_type(self.fd, 'fd', bool)
        validation.assert_type(self.bitrate_switch, 'bitrate_switch', bool)

        validation.assert_type(self.interface_config, 'interface_config', self.INTERFACE_CONFIG_MAP[self.interface])

    def _to_api_format(self) -> Dict[str, Any]:
        inteface_str = ""
        if self.interface == CANLinkConfig.CANInterface.SocketCAN:
            inteface_str = "socketcan"
        elif self.interface == CANLinkConfig.CANInterface.Vector:
            inteface_str = "vector"
        elif self.interface == CANLinkConfig.CANInterface.KVaser:
            inteface_str = "kvaser"
        elif self.interface == CANLinkConfig.CANInterface.PCAN:
            inteface_str = "pcan"
        elif self.interface == CANLinkConfig.CANInterface.ETAS:
            inteface_str = "etas"
        else:
            raise NotImplementedError(f"Unsupported interface type {self.interface}")

        return {
            'interface': inteface_str,
            'txid': self.txid,
            'rxid': self.rxid,
            'extended_id': self.extended_id,
            'fd': self.fd,
            'bitrate_switch': self.bitrate_switch,
            'subconfig': self.interface_config._to_api_format()
        }

    interface: CANInterface
    """The type of CAN interface used to access the CAN bus"""
    txid: int
    """The CAN ID used to transmit data from the server to the device"""
    rxid: int
    """The CAN ID used to transmit data from the device to the server"""
    extended_id: bool
    """A flag indicating if we use extended IDs (29 bits). Standard IDs (11 bits) are used when ``False``"""
    fd: bool
    """A flag indicating if we use CAN FD. Use of CAN 2.0 when ``False``"""
    bitrate_switch: bool
    """A flag telling if the server should do bitrate switch when transmitting. Only possible with CAN FD"""
    interface_config: Union[SocketCANConfig, VectorConfig, KVaserConfig, PCANConfig, ETASConfig]
    """A configuration specific to the interface"""

# endregion


SupportedLinkConfig = Union[UDPLinkConfig, TCPLinkConfig, SerialLinkConfig, RTTLinkConfig, NoneLinkConfig, CANLinkConfig]


@dataclass(frozen=True)
class DeviceLinkInfo:
    """(Immutable struct) Represent a communication link between the server and a device"""

    type: DeviceLinkType
    """Type of communication channel between the server and the device"""
    config: Optional[SupportedLinkConfig]
    """A channel type specific configuration"""
    operational: bool
    """Tells if the link is opened and working correctly"""


@dataclass(frozen=True)
class ServerInfo:
    """(Immutable struct) A summary of everything going on on the server side. Status broadcast by the server to every client."""

    device_comm_state: DeviceCommState
    """Status of the communication between the server and the device"""

    device_session_id: Optional[str]
    """A unique ID created each time a communication with the device is established. ``None`` when no communication with a device."""

    datalogging: DataloggingInfo
    """Datalogging state"""

    sfd_firmware_id: Optional[str]
    """The firmware ID of the Scrutiny Firmware Description file actually loaded on the server. ``None`` if none is loaded"""

    device_link: DeviceLinkInfo
    """Communication channel presently used to communicate with the device"""


@dataclass(frozen=True)
class UserCommandResponse:
    """(Immutable struct) Response returned by the device after performing a :meth:`ScrutinyClient.user_command<scrutiny.sdk.client.ScrutinyClient.user_command>`"""

    subfunction: int
    """The subfunction echoed by the device when sending a response"""

    data: bytes
    """The data returned by the device"""

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}(subfunction={self.subfunction}, data=b\'{hexlify(self.data).decode()}\')'


@dataclass(frozen=True)
class WatchableConfiguration:
    """(Immutable struct) Represents a watchable available in the server datastore"""

    server_id: str
    """The unique ID assigned to that watchable item by the server"""

    watchable_type: WatchableType
    """The type of the item, either a Variable, an Alias or a Runtime Published Value"""

    datatype: EmbeddedDataType
    """The data type of the value in the embedded firmware that this watchable refers to"""

    enum: Optional[EmbeddedEnum]
    """An optional enumeration associated with the possible values of the item"""


@dataclass(frozen=True)
class ServerStatistics:

    uptime: float
    """Time in seconds elapsed since the server has been started"""

    invalid_request_count: int
    """Number of invalid request the server received"""

    unexpected_error_count: int
    """Number of unexpected error the server encountered while processing a request"""

    client_count: int
    """Number of clients actually connected to the server"""

    to_all_clients_datarate_byte_per_sec: float
    """Datarate (byte/sec) going out of the API, all clients summed together"""

    from_any_client_datarate_byte_per_sec: float
    """Datarate (byte/sec) going in the API, all clients summed together"""

    msg_received: int
    """Number of message received, all clients summed together"""

    msg_sent: int
    """Number of message sent, all clients summed together"""

    device_session_count: int
    """Counter indicating how many new working connections has been established with a device """

    to_device_datarate_byte_per_sec: float
    """Datarate (byte/sec) traveling from the server to the device"""

    from_device_datarate_byte_per_sec: float
    """Datarate (byte/sec) traveling from the device to the server"""

    device_request_per_sec: float
    """Number of request/response per seconds exchanged between the server and the device"""
