#    variable.py
#        Variable class represent a variable, will be included in VarMap
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

__all__ = ['Variable', 'VariableLayout']

import struct
from dataclasses import dataclass
from copy import copy

from scrutiny.core.basic_types import Endianness, EmbeddedDataType
from scrutiny.core.embedded_enum import EmbeddedEnum
from scrutiny.core.variable_location import AbsoluteLocation, ResolvedPathPointedLocation
from scrutiny.core.codecs import Codecs, Encodable, UIntCodec
from scrutiny.core import path_tools
from scrutiny.tools.typing import *
from scrutiny import tools

MASK_MAP: Dict[int, int] = {}
for i in range(64):
    v = 0
    for j in range(i):
        v |= (1 << j)
        MASK_MAP[i] = v

BITFIELD_MASK_MAP: Dict[int, Dict[int, int]] = {}
for offset in range(64):
    BITFIELD_MASK_MAP[offset] = {}
    for bitsize in range(1, 64):
        v = 0
        for i in range(offset, offset + bitsize):
            v |= (1 << i)
        BITFIELD_MASK_MAP[offset][bitsize] = v


@dataclass(init=False, slots=True)
class VariableLayout:
    """Contain the information necessary to decode or encode a variable in memory. 
    Does not contain it's location, just its bit format"""

    vartype: EmbeddedDataType
    """Type of variable"""
    endianness: Endianness
    """Endianness. Little or Big"""
    bitsize: Optional[int]
    """Size of the bitfield. ``None`` if not a bitfield"""
    bitfield: bool
    """Tells if this variable uses a bitfield. """
    bitoffset: Optional[int]
    """Offset, in bits, of the bitfield. ``None`` if not a bitfield"""
    enum: Optional[EmbeddedEnum]
    """An enum to interpret the value. ``None`` If no enum"""

    def __init__(self,
                 vartype: EmbeddedDataType,
                 endianness: Endianness,
                 bitsize: Optional[int] = None,
                 bitoffset: Optional[int] = None,
                 enum: Optional[EmbeddedEnum] = None
                 ) -> None:

        self.vartype = vartype
        self.endianness = endianness
        self.bitsize = bitsize
        self.bitoffset = bitoffset
        self.enum = enum

        var_size_bits = self.vartype.get_size_bit()
        if bitoffset is not None and bitsize is None:
            bitsize = var_size_bits - bitoffset
        elif bitoffset is None and bitsize is not None:
            bitoffset = 0

        self.bitfield = False if bitoffset is None or bitsize is None else True
        if self.bitfield:
            assert bitoffset is not None
            assert bitsize is not None
            if self.vartype.is_float():
                raise ValueError("Bitfield on float value is not possible.")

            if bitoffset < 0 or bitsize <= 0:
                raise ValueError("Bad bitfield definition")

            if bitoffset + bitsize > var_size_bits:
                raise ValueError(f"Bitfield definition does not fit in variable of type {self.vartype.name}. Offset={bitoffset}, size={bitsize}")

    def decode(self, data: Union[bytes, bytearray]) -> Encodable:
        """Decode the binary content in memory to a python value"""

        if self.bitfield:
            assert self.bitsize is not None
            if len(data) > 8:
                raise NotImplementedError('Does not support bitfield bigger than %dbits' % (8 * 8))
            initial_len = len(data)

            if self.endianness == Endianness.Little:
                padded_data = bytearray(data + b'\x00' * (8 - initial_len))
                uint_data = struct.unpack('<q', padded_data)[0]
                uint_data >>= self.bitoffset
                uint_data &= MASK_MAP[self.bitsize]
                data = struct.pack('<q', uint_data)
                data = data[0:initial_len]
            else:
                padded_data = bytearray(b'\x00' * (8 - initial_len) + data)
                uint_data = struct.unpack('>q', padded_data)[0]
                uint_data >>= self.bitoffset
                uint_data &= MASK_MAP[self.bitsize]
                data = struct.pack('>q', uint_data)
                data = data[-initial_len:]

        decoded = Codecs.get(self.vartype, endianness=self.endianness).decode(data)

        return decoded

    def encode(self, value: Encodable) -> Tuple[bytes, Optional[bytes]]:
        """
        Converts a python value to a binary content that can be written in memory.
        The write mask is used for bitfields
        """
        codec = Codecs.get(self.vartype, endianness=self.endianness)
        if self.bitfield and not isinstance(value, float):
            assert (self.bitoffset is not None)
            data = codec.encode(value << self.bitoffset)
            write_mask = self.get_bitfield_mask()
        else:
            data = codec.encode(value)
            write_mask = None

        return data, write_mask

    def has_enum(self) -> bool:
        """True if an enum is attached to that variable"""
        return self.enum is not None

    def get_enum(self) -> Optional[EmbeddedEnum]:
        """Return the enum attached to the variable. None if it does not exists"""
        return self.enum

    def get_size(self) -> int:
        """Returns the size of the variable in bytes"""
        size_bit = self.vartype.get_size_bit()
        return int(size_bit / 8)

    def is_bitfield(self) -> bool:
        """Returns True if this variable is a bitfield"""
        return self.bitfield

    def get_bitsize(self) -> Optional[int]:
        """Returns the size of the bitfield. None if this variable is not a bitfield """
        return self.bitsize

    def get_bitoffset(self) -> Optional[int]:
        """Returns the offset of the bitfield in the variable. None if this variable is not a bitfield"""
        return self.bitoffset

    def get_bitfield_mask(self) -> bytes:
        """Returns a mask that covers the bits targeted by this variable. Used to do masked_write on the device"""
        if not self.bitfield:
            return b'\xFF' * self.get_size()
        else:
            assert self.bitoffset is not None
            assert self.bitsize is not None
            return UIntCodec(self.get_size(), self.endianness).encode(BITFIELD_MASK_MAP[self.bitoffset][self.bitsize])

    def get_type(self) -> EmbeddedDataType:
        """Returns the data type of the variable"""
        return self.vartype

    def copy(self) -> Self:
        return copy(self)


class Variable:
    """
    One of the most basic type of data (with RPV and Alias).
    Represent a variable in memory. It has a name, location and type.
    It supports bitfields and variable endianness.
    """
    path_segments: List[str]
    """Lits of all the path segments"""
    location: Union[AbsoluteLocation, ResolvedPathPointedLocation]
    """Location of the variable in memory"""
    layout: VariableLayout
    """The memory layout, or how to interpret the bits"""

    def __init__(self,
                 vartype: EmbeddedDataType,
                 path_segments: List[str],
                 location: Union[int, AbsoluteLocation, ResolvedPathPointedLocation],
                 endianness: Endianness,
                 bitsize: Optional[int] = None,
                 bitoffset: Optional[int] = None,
                 enum: Optional[EmbeddedEnum] = None
                 ) -> None:

        self.path_segments = path_segments
        if isinstance(location, ResolvedPathPointedLocation):
            self.location = location.copy()
        elif isinstance(location, AbsoluteLocation):
            self.location = location.copy()
        elif isinstance(location, (int, float)):
            self.location = AbsoluteLocation(int(location))
        else:
            raise TypeError("Bad location type")

        self.layout = VariableLayout(
            vartype=vartype,
            endianness=endianness,
            bitsize=bitsize,
            bitoffset=bitoffset,
            enum=enum,
        )

    @classmethod
    def from_layout(cls,
                    path_segments: List[str],
                    location: Union[int, AbsoluteLocation, ResolvedPathPointedLocation],
                    layout: VariableLayout
                    ) -> "Variable":
        """Instantiate a Variable object from a path, location and a Layout """

        return Variable(
            path_segments=path_segments,
            location=location,
            vartype=layout.vartype,
            endianness=layout.endianness,
            bitsize=layout.bitsize,
            bitoffset=layout.bitoffset,
            enum=layout.enum
        )

    def get_fullname(self) -> str:
        """Returns the full path identifying this variable"""
        return path_tools.join_segments(self.path_segments)

    def has_absolute_address(self) -> bool:
        """Return ``True`` if the location is an absolute address, ``False`` otehrwise"""
        return isinstance(self.location, AbsoluteLocation)

    def has_pointed_address(self) -> bool:
        """Return ``True`` if the location is an pointed address, meaning it refers to another 
        variable path + offset. Returns ``False`` otherwise"""
        return isinstance(self.location, ResolvedPathPointedLocation)

    def get_address(self) -> int:
        """Get the variable address"""
        if isinstance(self.location, AbsoluteLocation):
            return self.location.get_address()
        raise ValueError("No address available")

    def get_pointer(self) -> ResolvedPathPointedLocation:
        """Get the variable pointer location"""
        if isinstance(self.location, ResolvedPathPointedLocation):
            return self.location.copy()
        raise ValueError("No pointer available")

    def decode(self, data: Union[bytes, bytearray]) -> Encodable:
        """Decode the binary content in memory to a python value"""
        return self.layout.decode(data)

    def encode(self, value: Encodable) -> Tuple[bytes, Optional[bytes]]:
        """
        Converts a python value to a binary content that can be written in memory.
        The write mask is used for bitfields
        """
        return self.layout.encode(value)

    def has_enum(self) -> bool:
        """True if an enum is attached to that variable"""
        return self.layout.has_enum()

    def get_enum(self) -> Optional[EmbeddedEnum]:
        """Return the enum attached to the variable. None if it does not exists"""
        return self.layout.get_enum()

    def get_size(self) -> int:
        """Returns the size of the variable in bytes"""
        return self.layout.get_size()

    def is_bitfield(self) -> bool:
        """Returns True if this variable is a bitfield"""
        return self.layout.is_bitfield()

    def get_bitsize(self) -> Optional[int]:
        """Returns the size of the bitfield. None if this variable is not a bitfield """
        return self.layout.get_bitsize()

    def get_bitoffset(self) -> Optional[int]:
        """Returns the offset of the bitfield in the variable. None if this variable is not a bitfield"""
        return self.layout.get_bitoffset()

    def get_bitfield_mask(self) -> bytes:
        """Returns a mask that covers the bits targeted by this variable. Used to do masked_write on the device"""
        return self.layout.get_bitfield_mask()

    def get_type(self) -> EmbeddedDataType:
        """Returns the data type of the variable"""
        return self.layout.get_type()

    @property
    def vartype(self) -> EmbeddedDataType:
        """Type of variable"""
        return self.layout.vartype

    @property
    def endianness(self) -> Endianness:
        """Endianness. Little or Big"""
        return self.layout.endianness

    @property
    def bitsize(self) -> Optional[int]:
        """Size of the bitfield. ``None`` if not a bitfield"""
        return self.layout.bitsize

    @property
    def bitfield(self) -> bool:
        """Tells if this variable uses a bitfield. """
        return self.layout.bitfield

    @property
    def bitoffset(self) -> Optional[int]:
        """Offset, in bits, of the bitfield. ``None`` if not a bitfield"""
        return self.layout.bitoffset

    @property
    def enum(self) -> Optional[EmbeddedEnum]:
        """An enum to interpret the value. ``None`` If no enum"""
        return self.layout.enum

    def get_layout_copy(self) -> VariableLayout:
        """Return a copy of the variable layout"""
        return self.layout.copy()

    def __repr__(self) -> str:
        return '<%s - %s (%s) @ %s>' % (self.__class__.__name__, self.get_fullname(), self.layout.vartype, self.location)
