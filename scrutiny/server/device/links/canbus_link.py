__all__ = [
    'CanBusConfig',
    'CanBusLink'
]

import logging
import can
import time
from dataclasses import dataclass, asdict

from scrutiny.server.device.links.abstract_link import AbstractLink, LinkConfig
from scrutiny.tools.typing import *
from scrutiny.tools import validation

@dataclass
class BaseSubconfig:
    @classmethod
    def get_type_name(cls) -> str:
        if not hasattr(cls, '_TYPENAME'):
            raise RuntimeError("Subconfig with no type name")
        
        return str(getattr(cls, '_TYPENAME'))
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SocketCanSubConfig(BaseSubconfig):
    _TYPENAME = 'socketcan'

    channel:str

    def __post_init__(self) -> None:
        validation.assert_type(self.channel, 'channel', str)


@dataclass
class VectorSubConfig(BaseSubconfig):
    _TYPENAME = 'vector'

    channel:Union[str, int]
    bitrate:int

    def __post_init__(self) -> None:
        validation.assert_type(self.channel, 'channel', (str, int))
        validation.assert_type(self.bitrate, 'bitrate', int)
    

ANY_SUBCONFIG:TypeAlias = Union[SocketCanSubConfig, VectorSubConfig]

class CanBusConfigDict(TypedDict):
    interface:str
    txid:int
    rxid:int
    extended_id:bool
    fd:bool
    min_frame_size:Optional[int]
    padding_byte:Optional[int]
    
    subconfig:Dict[str, Any]

@dataclass
class CanBusConfig:
    interface:str
    txid:int
    rxid:int
    extended_id:bool
    fd:bool
    min_frame_size:Optional[int]
    padding_byte:Optional[int]
    
    subconfig:ANY_SUBCONFIG

    def to_dict(self) -> CanBusConfigDict:
        return {
            'interface': self.interface,
            'extended_id' : self.extended_id, 
            'rxid' : self.rxid,
            'txid' : self.txid,
            'fd' : self.fd,
            'min_frame_size' : self.min_frame_size,
            'padding_byte' : self.padding_byte,
            'subconfig' : self.subconfig.to_dict()
        }

    @classmethod
    def from_dict(cls, d:CanBusConfigDict) -> "CanBusConfig":

        expected_keys:Dict[str, Any] = {
            'interface' : str,
            'txid' : int,
            'rxid' : int,
            'extended_id' : bool,
            'fd' : bool,
            'padding_byte' : (int, type(None)),
            'min_frame_size' : (int, type(None)),
            'subconfig' : dict
        }
        validation.assert_type(d, 'config', dict)  
        for k,t in expected_keys.items():
            validation.assert_dict_key(d, k, t)
        
        for k in d.keys():
            if k not in expected_keys:
                raise ValueError(f"Unsupported parameter {k}")
            
        min_frame_size = d['min_frame_size']
        padding_byte = d['padding_byte']
        if min_frame_size is not None:
            if padding_byte is None:
                padding_byte = 0xCC
            
            if d['fd']:
                if min_frame_size not in [1,2,3,4,5,6,7,8,12,16,20,24,32,64]:
                    raise ValueError(f"min_frame_size is invalid for CAN FD")
            else:
                if min_frame_size not in [1,2,3,4,5,6,7,8]:
                    raise ValueError(f"min_frame_size is invalid for CAN 2.0")

            validation.assert_int_range(padding_byte, 'padding_byte', minval=0, maxval=0xFF )

        subcfg_class:Optional[Type[Any]] = None
        for class_candidate in BaseSubconfig.__subclasses__():
            if class_candidate.get_type_name() == d['interface']:
                subcfg_class = class_candidate
                break
        if subcfg_class is None:
            raise NotImplementedError(f"Unsupported interface type {d['interface']}")

        subconfig = cast(ANY_SUBCONFIG, subcfg_class(**d['subconfig']))   # Validation happens here

        return CanBusConfig(
            interface=d['interface'],
            extended_id=d['extended_id'],
            rxid=d['rxid'],
            txid=d['txid'],
            fd=d['fd'],
            min_frame_size=min_frame_size,
            padding_byte=padding_byte,
            subconfig=subconfig
        )


class CanBusLink(AbstractLink):
    logger: logging.Logger
    config: CanBusConfig
    _initialized: bool
    _init_timestamp: float
    _bus: Optional[can.BusABC]
    _ll_maxlen:int

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
        self._ll_maxlen = 8

        self.config = CanBusConfig.from_dict(cast(CanBusConfigDict, config))

    def _get_nearest_can_fd_size(self, size: int) -> int:
        if size <= 8:
            return size
        if size <= 12: return 12
        if size <= 16: return 16
        if size <= 20: return 20
        if size <= 24: return 24
        if size <= 32: return 32
        if size <= 48: return 48
        if size <= 64: return 64
        raise ValueError(f"Impossible data size for CAN FD : {size} ")

    def _get_dlc(self, size:int) -> int:
        if size >= 1 and size <= 8: return size
        if self.config.fd:
            if size == 12: return 9
            elif size == 16: return 10
            elif size == 20: return 11
            elif size == 24: return 12
            elif size == 32: return 13
            elif size == 48: return 14
            elif size == 64: return 15
        raise ValueError(f"Invalid data size {size}")


    def _chunk_data(self, data:bytes) -> Generator[bytes, None, None]:
        while len(data) > 0:
            chunk_size = self._get_nearest_can_fd_size(len(data))
            if not self.config.fd:
                if chunk_size > 8:
                    chunk_size = 8
            
            chunk_data = data[:chunk_size]
            data = data[chunk_size:]

            if self.config.min_frame_size is not None:
                assert self.config.padding_byte is not None
                if len(chunk_data) < self.config.min_frame_size:
                    npad = len(chunk_data) - self.config.min_frame_size
                    chunk_data += bytes([self.config.padding_byte] * npad)
            
            yield chunk_data

    def get_config(self) -> LinkConfig:
        return cast(LinkConfig, self.config.to_dict())

    def initialize(self) -> None:
        """ Called by the device Handler when initiating communication. Should reset the channel to a working state"""

        self._bus = self.make_bus(self.config)
        self._initialized = True
        self._init_timestamp = time.monotonic()

    def destroy(self) -> None:
        """ Put the comm channel to a resource-free non-working state"""
        if self._bus is not None:
            self._bus.shutdown()
        self._initialized = False

    def operational(self) -> bool:
        """ Tells if this comm channel is in proper state to be functional"""
        if self._bus is None:
            return False
        return self._bus.state != can.BusState.ERROR and self.initialized()

    def read(self, timeout: Optional[float] = None) -> Optional[bytes]:
        """ Reads bytes in a blocking fashion from the comm channel. None if no data available after timeout"""
        if not self.operational():
            return None

        return None
    
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
                        dlc=self._get_dlc(len(chunk))
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
    def make_bus(cls, config:CanBusConfig) -> can.BusABC:

        filters:List[can.typechecking.CanFilterExtended] = [
            {
                'can_id' : config.rxid, 
                'can_mask' : 0x1FFFFFFF if config.extended_id else 0x7FF, 
                'extended':config.extended_id
            }
        ]

        if config.interface == SocketCanSubConfig.get_type_name():
            from can.interfaces.socketcan import SocketcanBus
            assert isinstance(config.subconfig, SocketCanSubConfig)

            return SocketcanBus(
                channel=config.subconfig.channel,
                ignore_rx_error_frames=True,
                can_filters=filters
            )
        
        elif config.interface == VectorSubConfig.get_type_name():
            from can.interfaces.vector import VectorBus
            assert isinstance(config.subconfig, VectorSubConfig)

            return VectorBus(
                channel=config.subconfig.channel,
                fd=config.fd,
                bitrate=config.subconfig.bitrate,
                can_filters=filters
            )

        raise NotImplementedError(f"Unsupported bus type: {config.interface}")
