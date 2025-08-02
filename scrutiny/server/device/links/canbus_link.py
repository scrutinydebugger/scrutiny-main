#    canbus_link.py
#        An abstraction layer that provides CAN Bus communication with a device
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = [
    'CanBusConfig',
    'CanBusLink'
]

import logging
import can
import time
from dataclasses import dataclass, asdict

from scrutiny.server.device.links.abstract_link import AbstractLink, LinkConfig
from scrutiny.server.device.links.typing import *
from scrutiny.tools.typing import *
from scrutiny.tools import validation
from scrutiny import tools

_use_stubbed_canbus_class = tools.MutableBool(False)


def use_stubbed_canbus_class(val: bool) -> None:
    _use_stubbed_canbus_class.val = val


class StubbedCanBus(can.BusABC):
    _write_callback: Optional[Callable[[can.Message, Optional[float]], None]]
    _read_callback: Optional[Callable[[Optional[float]], Optional[can.Message]]]

    _init_args: List[Any]
    _init_kwargs: Dict[str, Any]

    def get_init_args(self) -> List[Any]:
        return self._init_args

    def get_init_kwargs(self) -> Dict[str, Any]:
        return self._init_kwargs

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self._init_args = cast(List[Any], args)
        self._init_kwargs = kwargs
        self._write_callback = None
        self._read_callback = None

    def set_write_callback(self, callback: Callable[[can.Message, Optional[float]], None]) -> None:
        self._write_callback = callback

    def set_read_callback(self, callback: Callable[[Optional[float]], Optional[can.Message]]) -> None:
        self._read_callback = callback

    def send(self, msg: can.Message, timeout: Optional[float] = None) -> None:
        if self._write_callback is not None:
            self._write_callback(msg, timeout)

    def _recv_internal(self, timeout: Optional[float]) -> Tuple[Optional[can.Message], bool]:
        if self._read_callback is None:
            return (None, False)
        return (self._read_callback(timeout), False)


@dataclass
class BaseSubconfig:
    @classmethod
    def get_type_name(cls) -> str:
        if not hasattr(cls, '_TYPENAME'):
            raise RuntimeError("Subconfig with no type name")

        return str(getattr(cls, '_TYPENAME'))

    def to_dict(self) -> CANBUS_ANY_SUBCONFIG_DICT:
        return cast(CANBUS_ANY_SUBCONFIG_DICT, asdict(self))


@dataclass
class SocketCanSubconfig(BaseSubconfig):
    _TYPENAME = 'socketcan'

    channel: str

    def __post_init__(self) -> None:
        validation.assert_type(self.channel, 'channel', str)

    @classmethod
    def from_dict(cls, d: SocketCanSubconfigDict) -> Self:
        validation.assert_dict_key(d, 'channel', str)
        return cls(
            channel=d['channel']
        )

@dataclass
class KVaserCanSubconfig(BaseSubconfig):
    _TYPENAME = 'kvaser'

    channel:int
    bitrate: int
    data_bitrate: int
    fd_non_iso:bool


    def __post_init__(self) -> None:
        validation.assert_type(self.channel, 'channel', int)
        validation.assert_type(self.bitrate, 'bitrate', int)
        validation.assert_type(self.data_bitrate, 'data_bitrate', int)
        validation.assert_type(self.fd_non_iso, 'fd_non_iso', bool)

    @classmethod
    def from_dict(cls, d: KVaserCanSubconfigDict) -> "KVaserCanSubconfig":
        validation.assert_dict_key(d, 'channel', int)
        validation.assert_dict_key(d, 'bitrate', int)
        validation.assert_dict_key(d, 'data_bitrate', int)
        validation.assert_dict_key(d, 'fd_non_iso', bool)

        return KVaserCanSubconfig(
            channel=d['channel'],
            bitrate=d['bitrate'],
            data_bitrate=d['data_bitrate'],
            fd_non_iso=d['fd_non_iso']
        )

@dataclass
class PCANCanSubconfig(BaseSubconfig):
    _TYPENAME = 'pcan'

    channel:str
    bitrate: int

    def __post_init__(self) -> None:
        validation.assert_type(self.channel, 'channel', str)
        validation.assert_type(self.bitrate, 'bitrate', int)

    @classmethod
    def from_dict(cls, d: PCANCanSubconfigDict) -> "PCANCanSubconfig":
        validation.assert_dict_key(d, 'channel', str)
        validation.assert_dict_key(d, 'bitrate', int)

        return PCANCanSubconfig(
            channel=d['channel'],
            bitrate=d['bitrate']
        )

@dataclass
class ETASCanSubconfig(BaseSubconfig):
    _TYPENAME = 'etas'

    channel:str
    bitrate: int
    data_bitrate: int

    def __post_init__(self) -> None:
        validation.assert_type(self.channel, 'channel', str)
        validation.assert_type(self.bitrate, 'bitrate', int)
        validation.assert_type(self.data_bitrate, 'data_bitrate', int)

    @classmethod
    def from_dict(cls, d: ETASCanSubconfigDict) -> "ETASCanSubconfig":
        validation.assert_dict_key(d, 'channel', str)
        validation.assert_dict_key(d, 'bitrate', int)
        validation.assert_dict_key(d, 'data_bitrate', int)

        return ETASCanSubconfig(
            channel=d['channel'],
            bitrate=d['bitrate'],
            data_bitrate=d['data_bitrate']
        )


@dataclass
class VirtualCanSubConfig(BaseSubconfig):
    _TYPENAME = 'virtual'

    channel: str

    def __post_init__(self) -> None:
        validation.assert_type(self.channel, 'channel', str)

    @classmethod
    def from_dict(cls, d: VirtualCanSubconfigDict) -> Self:
        validation.assert_dict_key(d, 'channel', str)
        return cls(
            channel=d['channel']
        )


@dataclass
class VectorSubConfig(BaseSubconfig):
    _TYPENAME = 'vector'

    channel: Union[str, int]
    bitrate: int
    data_bitrate: int

    def __post_init__(self) -> None:
        validation.assert_type(self.channel, 'channel', (str, int))
        validation.assert_type(self.bitrate, 'bitrate', int)
        validation.assert_type(self.data_bitrate, 'data_bitrate', int)

    @classmethod
    def from_dict(cls, d: VectorSubconfigDict) -> "VectorSubConfig":
        validation.assert_dict_key(d, 'channel', (str, int))
        validation.assert_dict_key(d, 'bitrate', int)
        validation.assert_dict_key(d, 'data_bitrate', int)

        return VectorSubConfig(
            channel=d['channel'],
            bitrate=d['bitrate'],
            data_bitrate=d['data_bitrate']
        )

# endregion


ANY_SUBCONFIG: TypeAlias = Union[SocketCanSubconfig, VectorSubConfig, KVaserCanSubconfig, PCANCanSubconfig, ETASCanSubconfig]


@dataclass
class CanBusConfig:
    interface: SUPPORTED_INTERFACES
    txid: int
    rxid: int
    extended_id: bool
    fd: bool
    bitrate_switch: bool

    subconfig: ANY_SUBCONFIG

    def __post_init__(self) -> None:
        if not self.fd and self.bitrate_switch:
            raise ValueError("Bitrate switch is not possible without CAN FD enabled")

        if not self.extended_id:
            validation.assert_int_range(self.rxid, 'rxid', 0, 0x7FF)
            validation.assert_int_range(self.txid, 'txid', 0, 0x7FF)
        else:
            validation.assert_int_range(self.rxid, 'rxid', 0, 0x1FFFFFFF)
            validation.assert_int_range(self.txid, 'txid', 0, 0x1FFFFFFF)

    def to_dict(self) -> CanBusConfigDict:
        return {
            'interface': self.interface,
            'extended_id': self.extended_id,
            'rxid': self.rxid,
            'txid': self.txid,
            'fd': self.fd,
            'bitrate_switch': self.bitrate_switch,
            'subconfig': self.subconfig.to_dict()
        }

    @classmethod
    def from_dict(cls, d: CanBusConfigDict) -> "CanBusConfig":

        expected_keys: Dict[str, Any] = {
            'interface': str,
            'txid': int,
            'rxid': int,
            'extended_id': bool,
            'fd': bool,
            'bitrate_switch': bool,
            'subconfig': dict
        }
        validation.assert_type(d, 'config', dict)
        for k, t in expected_keys.items():
            validation.assert_dict_key(d, k, t)

        for k in d.keys():
            if k not in expected_keys:
                raise ValueError(f"Unsupported parameter {k}")

        subcfg_class: Optional[Type[Any]] = None
        for class_candidate in BaseSubconfig.__subclasses__():
            if class_candidate.get_type_name() == d['interface']:
                subcfg_class = class_candidate
                break
        if subcfg_class is None:
            raise NotImplementedError(f"Unsupported interface type {d['interface']}")

        try:
            subconfig = cast(ANY_SUBCONFIG, subcfg_class.from_dict(d['subconfig']))   # Validation happens here
        except Exception as e:
            raise ValueError(f"Invalid sub configuration for interface of type {d['interface']} : {e}") from e

        return CanBusConfig(
            interface=d['interface'],
            extended_id=d['extended_id'],
            rxid=d['rxid'],
            txid=d['txid'],
            fd=d['fd'],
            bitrate_switch=d['bitrate_switch'],
            subconfig=subconfig
        )


class CanBusLink(AbstractLink):
    logger: logging.Logger
    config: CanBusConfig
    _initialized: bool
    _init_timestamp: float
    _bus: Optional[can.BusABC]
    _ll_maxlen: int

    @classmethod
    def make(cls, config: LinkConfig) -> "CanBusLink":
        """ Return a serialLink instance from a config object"""
        return cls(config)

    def __init__(self, config: LinkConfig):
        self._bus = None
        self.validate_config(config)
        self._initialized = False
        self.logger = logging.getLogger(self.__class__.__name__)
        self._init_timestamp = time.monotonic()

        self.config = CanBusConfig.from_dict(cast(CanBusConfigDict, config))

    def _get_nearest_can_fd_size_smaller_or_equal_to(self, size: int) -> int:
        if size <= 8:
            return size
        if size < 12: return 8
        if size >= 64: return 64
        if size >= 48: return 48
        if size >= 32: return 32
        if size >= 24: return 24
        if size >= 20: return 20
        if size >= 16: return 16
        if size >= 12: return 12
        raise ValueError(f"Impossible data size for CAN FD : {size} ")

    def _chunk_data(self, data: bytes) -> Generator[bytes, None, None]:
        while len(data) > 0:
            chunk_size = self._get_nearest_can_fd_size_smaller_or_equal_to(len(data))
            if not self.config.fd:
                if chunk_size > 8:
                    chunk_size = 8

            chunk_data = data[:chunk_size]
            data = data[chunk_size:]
            yield chunk_data

    def get_config(self) -> LinkConfig:
        return cast(LinkConfig, self.config.to_dict())

    def get_bus(self) -> Optional[can.BusABC]:
        return self._bus

    def initialize(self) -> None:
        """Called by the device Handler when initiating communication. Should reset the channel to a working state"""

        self._bus = self.make_bus(self.config)
        self._initialized = True
        self._init_timestamp = time.monotonic()

    def destroy(self) -> None:
        """ Put the comm channel to a resource-free non-working state"""
        if self._bus is not None:
            self._bus.shutdown()
            self._bus = None
        self._initialized = False

    def operational(self) -> bool:
        """ Tells if this comm channel is in proper state to be functional"""
        if self._bus is None:
            return False
        is_shutdown = getattr(self._bus, '_is_shutdown', False)  # No api to know if it is shutdown
        return self._bus.state != can.BusState.ERROR and not is_shutdown and self.initialized()

    def read(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """ Reads bytes in a blocking fashion from the comm channel. None if no data available after timeout"""
        if not self.operational():
            return None
        assert self._bus is not None

        msg = self._bus.recv(timeout)
        if msg is None:
            return None
        if msg.is_error_frame:
            return None
        return bytes(msg.data)

    def write(self, data: bytes) -> None:
        """ Write data to the comm channel."""
        if self.operational():
            assert self._bus is not None
            for chunk in self._chunk_data(data):
                self._bus.send(
                    can.Message(
                        arbitration_id=self.config.txid,
                        is_extended_id=self.config.extended_id,
                        is_fd=self.config.fd,
                        data=chunk,
                        bitrate_switch=self.config.bitrate_switch
                    )
                )

    def initialized(self) -> bool:
        """ Tells if initialize() has been called"""
        return self._initialized

    def process(self) -> None:
        pass

    @staticmethod
    def validate_config(config: LinkConfig) -> None:
        """Raises an exception if the configuration is not adequate"""
        if not isinstance(config, dict):
            raise ValueError('Configuration is not a valid dictionary')

        CanBusConfig.from_dict(cast(CanBusConfigDict, config))

    @classmethod
    def make_bus(cls, config: CanBusConfig) -> can.BusABC:

        filters: List[can.typechecking.CanFilterExtended] = [
            {
                'can_id': config.rxid,
                'can_mask': 0x1FFFFFFF if config.extended_id else 0x7FF,
                'extended': config.extended_id
            }
        ]

        if config.interface == SocketCanSubconfig.get_type_name():
            assert isinstance(config.subconfig, SocketCanSubconfig)

            if not _use_stubbed_canbus_class:
                from can.interfaces.socketcan import SocketcanBus
                MySocketCanBus = SocketcanBus 
            else:
                MySocketCanBus = StubbedCanBus # type: ignore

            return MySocketCanBus(
                channel=config.subconfig.channel,
                ignore_rx_error_frames=True,
                can_filters=filters,
                fd=config.fd
            )

        elif config.interface == VectorSubConfig.get_type_name():
            assert isinstance(config.subconfig, VectorSubConfig)

            if not _use_stubbed_canbus_class:
                from can.interfaces.vector import VectorBus
                MyVectorCanBus = VectorBus 
            else:
                MyVectorCanBus = StubbedCanBus # type: ignore

            return MyVectorCanBus(
                channel=config.subconfig.channel,
                fd=config.fd,
                bitrate=config.subconfig.bitrate,
                can_filters=filters,
                data_bitrate=config.subconfig.data_bitrate
            )
        
        elif config.interface == KVaserCanSubconfig.get_type_name():
            assert isinstance(config.subconfig, KVaserCanSubconfig)

            if not _use_stubbed_canbus_class:
                from can.interfaces.kvaser import KvaserBus
                MyKvaserBus = KvaserBus 
            else:
                MyKvaserBus = StubbedCanBus # type: ignore

            return MyKvaserBus(
                channel=config.subconfig.channel,
                fd=config.fd,
                fd_non_iso=config.subconfig.fd_non_iso,
                bitrate=config.subconfig.bitrate,
                can_filters=filters,
                data_bitrate=config.subconfig.data_bitrate
            )
       
        elif config.interface == PCANCanSubconfig.get_type_name():
            assert isinstance(config.subconfig, PCANCanSubconfig)

            if not _use_stubbed_canbus_class:
                from can.interfaces.pcan import PcanBus
                MyPcanBus = PcanBus 
            else:
                MyPcanBus = StubbedCanBus # type: ignore

            return MyPcanBus(
                channel=config.subconfig.channel,
                fd=config.fd,
                bitrate=config.subconfig.bitrate,
                can_filters=filters,
            )

        elif config.interface == ETASCanSubconfig.get_type_name():
            assert isinstance(config.subconfig, ETASCanSubconfig)
            if not _use_stubbed_canbus_class:
                from can.interfaces.etas import EtasBus
                MyEtasBus = EtasBus 
            else:
                MyEtasBus = StubbedCanBus # type: ignore
                
            return MyEtasBus(
                channel=config.subconfig.channel,
                fd=config.fd,
                bitrate=config.subconfig.bitrate,
                data_bitrate=config.subconfig.data_bitrate,
                can_filters=filters,
            )

        elif config.interface == VirtualCanSubConfig.get_type_name():
            from can.interfaces.virtual import VirtualBus
            assert isinstance(config.subconfig, VirtualCanSubConfig)

            return VirtualBus(
                channel=config.subconfig.channel,
                protocol=can.CanProtocol.CAN_20 if not config.fd else can.CanProtocol.CAN_FD
            )

        raise NotImplementedError(f"Unsupported bus type: {config.interface}")
