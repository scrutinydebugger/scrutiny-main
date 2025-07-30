#    typing.py
#        Type hint definitions for link configurations that are passed across the application
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from scrutiny.tools.typing import *


# region CAN bus
class SocketCanSubconfigDict(TypedDict):
    channel: str

class VirtualCanSubconfigDict(TypedDict):
    channel: str


class VectorSubconfigDict(TypedDict):
    channel: Union[str, int]
    bitrate: int
    data_bitrate: int


CANBUS_ANY_SUBCONFIG_DICT: TypeAlias = Union[SocketCanSubconfigDict, VectorSubconfigDict, VirtualCanSubconfigDict]


class CanBusConfigDict(TypedDict):
    interface: Literal['socketcan', 'vector', 'virtual']
    txid: int
    rxid: int
    extended_id: bool
    fd: bool
    bitrate_switch: bool

    subconfig: CANBUS_ANY_SUBCONFIG_DICT

# endregion

# region Serial


class SerialConfigDict(TypedDict):
    """
    Config given the the SerialLink object.
    Can be set through the API or config file with JSON format
    """
    portname: str
    baudrate: int
    stopbits: str
    databits: int
    parity: str
    start_delay: float

# endregion


# region UDP
class UdpConfigDict(TypedDict):
    """
    Config given the the UdpLink object.
    Can be set through the API or config file with JSON format
    """
    host: str
    port: int

# endregion

# region RTT


class RttConfigDict(TypedDict):
    """
    Config given the the RttLink object.
    Can be set through the API or config file with JSON format
    """
    target_device: str
    jlink_interface: str

# endregion
