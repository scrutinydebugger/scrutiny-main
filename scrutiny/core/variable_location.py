
__all__ = ['AbsoluteLocation', 'PathPointedLocation']

from copy import copy
from dataclasses import dataclass
from scrutiny.core.basic_types import Endianness
from scrutiny.tools.typing import *


@dataclass(slots=True, frozen=True)
class PathPointedLocation:
    pointer_path: str
    pointer_offset: int

    def copy(self) -> "PathPointedLocation":
        return copy(self)


class AbsoluteLocation:
    """Represent an address in memory. """

    __slots__ = ['address']

    def __init__(self, address: int):
        if not isinstance(address, int):
            raise ValueError('Address must be a valid integer')

        self.address = address

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
