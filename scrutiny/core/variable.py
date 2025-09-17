#    variable.py
#        Variable class represent a variable, will be included in VarMap
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = [
    'VariableLocation',
    'Struct',
    'Variable',
    'Array',
    'TypedArray',
    'UntypedArray'
]

import struct
import math
import enum
import abc
from scrutiny.core.basic_types import Endianness, EmbeddedDataType
from scrutiny.core.embedded_enum import EmbeddedEnum
from scrutiny.core.codecs import Codecs, Encodable, UIntCodec
from copy import deepcopy
from scrutiny.tools.typing import *

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


class VariableLocation:
    """Represent an address in memory. """

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
    def check_endianness(cls, endianness: Endianness) -> None:
        """Tells if given endianness is valid"""
        if endianness not in [Endianness.Little, Endianness.Big]:
            raise ValueError('Invalid endianness "%s" ' % endianness)

    @classmethod
    def from_bytes(cls, data: Union[bytes, List[int], bytearray], endianness: Endianness) -> "VariableLocation":
        """Reads the address encoded in binary with the given endianness"""
        if isinstance(data, list) or isinstance(data, bytearray):
            data = bytes(data)
        if not isinstance(data, bytes):
            raise ValueError('Data must be bytes, not %s' % (data.__class__.__name__))

        if len(data) < 1:
            raise ValueError('Empty data')

        cls.check_endianness(endianness)
        byteorder_map: Dict[Endianness, Literal['little', 'big']] = {
            Endianness.Little: 'little',
            Endianness.Big: 'big'
        }
        address = int.from_bytes(data, byteorder=byteorder_map[endianness], signed=False)
        return cls(address)

    def copy(self) -> 'VariableLocation':
        """Return a copy of this VariableLocation object"""
        return VariableLocation(self.get_address())

    def __str__(self) -> str:
        return str(self.get_address())

    def __repr__(self) -> str:
        return '<%s - 0x%08X>' % (self.__class__.__name__, self.get_address())


class Array(abc.ABC):
    __slots__ = ('dims', 'element_type_name', '_multipliers')

    dims: Tuple[int, ...]
    element_type_name: str
    _multipliers: Tuple[int, ...]

    def __init__(self, dims: Tuple[int, ...], element_type_name: str) -> None:
        if len(dims) == 0:
            raise ValueError("No dimensions set")
        for dim in dims:
            if dim <= 0:
                raise ValueError("Invalid dimension")

        self.dims = dims
        self.element_type_name = element_type_name
        self._multipliers = tuple([math.prod(dims[i + 1:]) for i in range(len(dims))])    # No need to check boundaries, prod([]) = 1

    @abc.abstractmethod
    def get_element_byte_size(self) -> int:
        raise NotImplementedError("Abstract method")

    def get_element_count(self) -> int:
        """Returns the total number of element in the array"""
        return math.prod(self.dims)

    def get_total_byte_size(self) -> int:
        """Return the total size in bytes of the array"""
        return self.get_element_count() * self.get_element_byte_size()

    def position_of(self, pos: Tuple[int, ...]) -> int:
        """Return the linear index that can be used to address an element based on a N-dimension position"""
        if len(pos) != len(self.dims):
            raise ValueError("Shape mismatch")

        nbdim = len(pos)
        index = 0
        for i in range(nbdim):
            if pos[i] >= self.dims[i] or pos[i] < 0:
                raise ValueError("Index out of bound")
            index += pos[i] * self._multipliers[i]

        return index

    def byte_position_of(self, pos: Tuple[int, ...]) -> int:
        """Return the linear bytes index that can be used to address an element based on a N-dimension position"""
        return self.position_of(pos) * self.get_element_byte_size()


class UntypedArray(Array):
    """Represent an N dimensions embedded array with no type, just a size available"""
    __slots__ = ('element_byte_size',)

    element_byte_size: int

    def __init__(self, dims: Tuple[int, ...], element_type_name: str, element_byte_size: int) -> None:
        super().__init__(dims, element_type_name)
        self.element_byte_size = element_byte_size

    def get_element_byte_size(self) -> int:
        """Return the size of a single element in bytes"""
        return self.element_byte_size


class TypedArray(Array):
    """Represent an N dimensions embedded array"""
    __slots__ = ('datatype', )

    datatype: Union["Struct", EmbeddedDataType]

    def __init__(self, dims: Tuple[int, ...], element_type_name: str, datatype: Union["Struct", EmbeddedDataType]) -> None:
        super().__init__(dims, element_type_name)
        self.datatype = datatype

    def get_element_byte_size(self) -> int:
        """Return the size of a single element in bytes"""
        if isinstance(self.datatype, EmbeddedDataType):
            return self.datatype.get_size_byte()
        if isinstance(self.datatype, Struct):
            if self.datatype.byte_size is not None:
                return self.datatype.byte_size
            raise RuntimeError(f"No element size available for struct {self.datatype.name}")
        raise RuntimeError(f"Unsupported datatype {self.datatype.__class__.__name__}")

    def to_untyped_array(self) -> UntypedArray:
        return UntypedArray(
            self.dims,
            self.element_type_name,
            element_byte_size=self.get_element_byte_size()
        )


class Struct:
    class Member:
        class MemberType(enum.Enum):
            BaseType = enum.auto()
            SubStruct = enum.auto()
            SubArray = enum.auto()

        name: str
        member_type: MemberType
        original_type_name: Optional[str]
        bitoffset: Optional[int]
        byte_offset: Optional[int]
        bitsize: Optional[int]
        substruct: Optional['Struct']
        subarray: Optional[TypedArray]
        embedded_enum: Optional[EmbeddedEnum]
        is_unnamed: bool

        def __init__(self, name: str,
                     member_type: MemberType,
                     original_type_name: Optional[str] = None,
                     byte_offset: Optional[int] = None,
                     bitoffset: Optional[int] = None,
                     bitsize: Optional[int] = None,
                     substruct: Optional['Struct'] = None,
                     subarray: Optional[TypedArray] = None,
                     embedded_enum: Optional[EmbeddedEnum] = None,
                     is_unnamed: bool = False
                     ):

            if member_type == self.MemberType.BaseType:
                if substruct is not None or subarray is not None:
                    raise ValueError("Cannot specify a substruct or a subarray for base type member")

            if member_type == self.MemberType.SubStruct:
                if substruct is None or subarray is not None:
                    raise ValueError("Substruct member must specify a substruct only")

            if member_type == self.MemberType.SubArray:
                if substruct is not None or subarray is None:
                    raise ValueError("SubArray member must specify a subarray only")

            if member_type == self.MemberType.BaseType:
                if original_type_name is None:
                    raise ValueError('A typename must be given for base type member')

            if bitoffset is not None:
                if not isinstance(bitoffset, int):
                    raise ValueError(f'bitoffset must be an integer value. Got {bitoffset.__class__.__name__}')
                if bitoffset < 0:
                    raise ValueError('bitoffset must be a positive integer')

            if bitsize is not None:
                if not isinstance(bitsize, int):
                    raise ValueError(f'bitsize must be an integer value. Got {bitsize.__class__.__name__}')
                if bitsize < 0:
                    raise ValueError('bitsize must be a positive integer')

            if byte_offset is not None:
                if not isinstance(byte_offset, int):
                    raise ValueError(f'byte_offset must be an integer value. Got {bitsize.__class__.__name__}')
                if byte_offset < 0:
                    raise ValueError('byte_offset must be a positive integer')

            if substruct is not None:
                if not isinstance(substruct, Struct):
                    raise ValueError(f'substruct must be Struct instance. Got {substruct.__class__.__name__}')

            if is_unnamed:
                if member_type != self.MemberType.SubStruct:
                    raise ValueError("Only substruct members can be unnamed")

            self.name = name
            self.member_type = member_type
            self.original_type_name = original_type_name
            self.bitoffset = bitoffset
            self.byte_offset = byte_offset
            self.bitsize = bitsize
            self.substruct = substruct
            self.subarray = subarray
            self.embedded_enum = embedded_enum
            self.is_unnamed = is_unnamed

        def get_substruct(self) -> "Struct":
            if self.substruct is None or self.member_type != self.MemberType.SubStruct:
                raise ValueError("Member is not a substruct")

            return self.substruct

        def get_array(self) -> "TypedArray":
            if self.subarray is None or self.member_type != self.MemberType.SubArray:
                raise ValueError("Member is not a subarray")
            return self.subarray

    name: str
    is_anonymous: bool
    members: Dict[str, "Struct.Member"]
    byte_size: Optional[int]

    def __init__(self, name: str, byte_size: Optional[int] = None) -> None:
        self.name = name
        self.byte_size = byte_size
        self.members = {}

    def add_member(self, member: "Struct.Member") -> None:
        """Add a member to the struct"""
        if not isinstance(member, Struct.Member):
            raise ValueError('Node must be a Struct.Member')

        if member.is_unnamed:
            # Unnamed struct,class,union are defined like this : struct { struct {int a; int b;}} x
            # They are considered as being declared at the same level as the members of the parent
            assert member.member_type == self.Member.MemberType.SubStruct
            assert member.substruct is not None
            assert member.byte_offset is not None

            for subtruct_member in member.substruct.members.values():
                substruct_member2 = deepcopy(subtruct_member)
                if substruct_member2.byte_offset is None:
                    raise RuntimeError("Expect byte_offset to be set to handle unnamed composite type")
                substruct_member2.byte_offset += member.byte_offset
                self.add_member(substruct_member2)
        else:
            if member.name in self.members:
                raise KeyError(f'Duplicate member {member.name}')

            self.members[member.name] = member

    def inherit(self, other: "Struct", offset: int = 0) -> None:
        for member in other.members.values():
            member2 = deepcopy(member)
            if member2.byte_offset is None:
                raise RuntimeError("Expect byte_offset to be set to handle inheritance")
            member2.byte_offset += offset
            self.add_member(member)


class Variable:
    """
    One of the most basic type of data (with RPV and Alias).
    Represent a variable in memory. It has a name, location and type.
    It supports bitfields and variable endianness.
    """

    name: str
    vartype: EmbeddedDataType
    path_segments: List[str]
    location: VariableLocation
    endianness: Endianness
    bitsize: Optional[int]
    bitfield: bool
    bitoffset: Optional[int]
    enum: Optional[EmbeddedEnum]

    def __init__(self,
                 name: str,
                 vartype: EmbeddedDataType,
                 path_segments: List[str],
                 location: Union[int, VariableLocation],
                 endianness: Endianness,
                 bitsize: Optional[int] = None,
                 bitoffset: Optional[int] = None,
                 enum: Optional[EmbeddedEnum] = None
                 ) -> None:

        self.name = name
        self.vartype = vartype
        self.path_segments = path_segments
        if isinstance(location, VariableLocation):
            self.location = location.copy()
        else:
            self.location = VariableLocation(location)
        self.endianness = endianness

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
                # Not sure if it is possible...
                raise ValueError("Bitfield on float value is not possible. Report this issue if you think it should!")

            if bitoffset < 0 or bitsize <= 0:
                raise ValueError("Bad bitfield definition")

            if bitoffset + bitsize > var_size_bits:
                raise ValueError("Bitfield definition does not fit in variable of type %s. Offset=%d, size=%d" % (self.vartype, bitoffset, bitsize))

        self.bitsize = bitsize
        self.bitoffset = bitoffset
        self.enum = enum

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

    def get_fullname(self) -> str:
        """Returns the full path identifying this variable"""
        if len(self.path_segments) == 0:
            path_str = '/'
        else:
            path_str = '/' + '/'.join(self.path_segments)
        return '%s/%s' % (path_str, self.name)

    def get_type(self) -> EmbeddedDataType:
        """Returns the data type of the variable"""
        return self.vartype

    def get_path_segments(self) -> List[str]:
        """Returns a list of segments representing the path to the variable. Exclude the variable name"""
        return self.path_segments

    def get_address(self) -> int:
        """Get the variable address"""
        return self.location.get_address()

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

    def __repr__(self) -> str:
        return '<%s - %s (%s) @ %s>' % (self.__class__.__name__, self.get_fullname(), self.vartype, self.location)
