#    variable_location.py
#        Contains the 2 types of variable location possible for a variable
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['AbsoluteLocation', 'ResolvedPathPointedLocation', 'UnresolvedPathPointedLocation']

from copy import copy
from dataclasses import dataclass
from scrutiny.core.basic_types import Endianness
from scrutiny.core.array import Array
from scrutiny.tools.typing import *


@dataclass(slots=True, init=False)
class UnresolvedPathPointedLocation:
    """Represent a location of a pointed element without resolving the array indices
    Example : /aaa/bbb/ccc  with "aaa/bbb" = array(2,3,4)
    """
    pointer_path: str
    pointer_offset: int
    array_segments: Dict[str, Array]

    def __init__(self, pointer_path: str, pointer_offset: int, array_segments: Optional[Dict[str, Array]]) -> None:
        self.pointer_path = pointer_path
        self.pointer_offset = pointer_offset
        self.array_segments = {}
        if array_segments is not None:
            self.array_segments = array_segments

        if not isinstance(self.pointer_path, str):
            raise TypeError('Address pointer_path be a valid string')
        if not isinstance(self.pointer_offset, int):
            raise TypeError('pointer_offset must be a valid integer')
        if not isinstance(self.array_segments, dict):
            raise TypeError('array_segments must be a dictionary')

    def copy(self) -> "UnresolvedPathPointedLocation":
        return copy(self)

    def add_offset(self, val: int) -> None:
        self.pointer_offset += val

    def get_offset(self) -> int:
        return self.pointer_offset


@dataclass(slots=True)
class ResolvedPathPointedLocation:
    """Represent a location of a pointed element with array indices resolved.
    Example : /aaa/bbb[2][1][0]/ccc"""
    pointer_path: str
    pointer_offset: int

    def __post_init__(self) -> None:
        if not isinstance(self.pointer_path, str):
            raise TypeError('Address pointer_path be a valid string')
        if not isinstance(self.pointer_offset, int):
            raise TypeError('pointer_offset must be a valid integer')

    def copy(self) -> "ResolvedPathPointedLocation":
        return copy(self)

    def get_offset(self) -> int:
        return self.pointer_offset

    def make_unresolved(self) -> "UnresolvedPathPointedLocation":
        return UnresolvedPathPointedLocation(
            pointer_offset=self.pointer_offset,
            pointer_path=self.pointer_path,
            array_segments=None
        )


@dataclass(slots=True)
class AbsoluteLocation:
    """Represent an address in memory. """
    address: int

    def __post_init__(self) -> None:
        if not isinstance(self.address, int):
            raise TypeError('Address must be a valid integer')

    def is_null(self) -> bool:
        """Return true if address is null"""
        return self.address == 0

    def get_address(self) -> int:
        """Return the address in a numerical format"""
        return self.address

    def add_offset(self, offset: int) -> None:
        """Modify the address by the given offset"""
        self.address += offset

    @classmethod
    def from_bytes(cls, data: Union[bytes, List[int], bytearray], endianness: Endianness) -> "AbsoluteLocation":
        """Reads the address encoded in binary with the given endianness"""
        if isinstance(data, list) or isinstance(data, bytearray):
            data = bytes(data)
        if not isinstance(data, bytes):
            raise ValueError(f'Data must be bytes, not {data.__class__.__name__}')

        if len(data) < 1:
            raise ValueError('Empty data')

        byteorder_map: Dict[Endianness, Literal['little', 'big']] = {
            Endianness.Little: 'little',
            Endianness.Big: 'big'
        }
        if endianness not in byteorder_map:
            raise ValueError(f'Invalid endianness "{endianness}" ')

        address = int.from_bytes(data, byteorder=byteorder_map[endianness], signed=False)
        return cls(address)

    def copy(self) -> 'AbsoluteLocation':
        """Return a copy of this AbsoluteLocation object"""
        return AbsoluteLocation(self.get_address())

    def __str__(self) -> str:
        return str(self.get_address())

    def __repr__(self) -> str:
        return '<%s - 0x%08X>' % (self.__class__.__name__, self.get_address())
