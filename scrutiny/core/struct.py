#    struct.py
#        Definition of a struct, mainly used for parsing DWARF symbols
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2025 Scrutiny Debugger

__all__ = ['Struct']

import enum
from dataclasses import dataclass
from scrutiny.core.embedded_enum import EmbeddedEnum
from copy import copy
from scrutiny.tools.typing import *

if TYPE_CHECKING:
    from scrutiny.core.array import TypedArray
    from scrutiny.core.pointer import Pointer


class Struct:
    """Represents a C/C++ struct, class, or union parsed from DWARF debug information"""

    class Member:
        """Represents a single field (member) within a ``Struct``"""

        class MemberType(enum.Enum):
            """Discriminant indicating the kind of data a ``Member`` holds"""

            BaseType = enum.auto()
            SubStruct = enum.auto()
            SubArray = enum.auto()
            Pointer = enum.auto()

        name: str
        """Name of the struct member as declared in source code"""
        member_type: MemberType
        """Discriminant describing what kind of value this member holds"""
        original_type_name: Optional[str]
        """Original C/C++ type name string, if available"""
        bitoffset: Optional[int]
        """Bit-level offset used for bit-fields. ``None`` for non-bitfield members"""
        byte_offset: Optional[int]
        """Byte offset of this member from the start of the enclosing struct"""
        bitsize: Optional[int]
        """Size in bits for bit-field members, or ``None`` for non-bitfield members"""
        substruct: Optional['Struct']
        """Nested ``Struct`` instance, present only when ``member_type`` is ``MemberType.SubStruct``"""
        subarray: Optional["TypedArray"]
        """Nested ``TypedArray`` instance, present only when ``member_type`` is ``MemberType.SubArray``"""
        pointer: Optional["Pointer"]
        """``Pointer`` instance, present only when ``member_type`` is ``MemberType.Pointer``"""
        embedded_enum: Optional[EmbeddedEnum]
        """Optional ``EmbeddedEnum`` associated with this member for symbolic value display"""
        is_unnamed: bool
        """``True`` if this member represents an anonymous (unnamed) nested struct, class or union whose
        members are merged into the parent scope"""


        @dataclass(slots=True)
        class _RequiredSubData:
            substruct: bool
            subarray: bool
            pointer: bool

        _REQUIRED_SUBDATA_MAP: Dict[MemberType, _RequiredSubData] = {
            MemberType.BaseType: _RequiredSubData(substruct=False, subarray=False, pointer=False),
            MemberType.SubStruct: _RequiredSubData(substruct=True, subarray=False, pointer=False),
            MemberType.SubArray: _RequiredSubData(substruct=False, subarray=True, pointer=False),
            MemberType.Pointer: _RequiredSubData(substruct=False, subarray=False, pointer=True),
        }


        def __init__(self, name: str,
                     member_type: MemberType,
                     original_type_name: Optional[str] = None,
                     byte_offset: Optional[int] = None,
                     bitoffset: Optional[int] = None,
                     bitsize: Optional[int] = None,
                     substruct: Optional['Struct'] = None,
                     subarray: Optional["TypedArray"] = None,
                     pointer: Optional["Pointer"] = None,
                     embedded_enum: Optional[EmbeddedEnum] = None,
                     is_unnamed: bool = False
                     ):
            # Avoid circular import on load
            from scrutiny.core.array import TypedArray
            from scrutiny.core.pointer import Pointer

            if member_type not in self._REQUIRED_SUBDATA_MAP:
                raise ValueError("Unsupported member type")

            required_subdata = self._REQUIRED_SUBDATA_MAP[member_type]

            if required_subdata.substruct:
                if substruct is None:
                    raise ValueError(f"Missing substruct for member of type {member_type.name}")
            else:
                if substruct is not None:
                    raise ValueError(f"Cannot specify a substruct for member of type {member_type.name}")

            if required_subdata.subarray:
                if subarray is None:
                    raise ValueError(f"Missing subarray for member of type {member_type.name}")
            else:
                if subarray is not None:
                    raise ValueError(f"Cannot specify a subarray for member of type {member_type.name}")

            if required_subdata.pointer:
                if pointer is None:
                    raise ValueError(f"Missing pointer for member of type {member_type.name}")
            else:
                if pointer is not None:
                    raise ValueError(f"Cannot specify a pointer for member of type {member_type.name}")

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
                    raise ValueError(f'byte_offset must be an integer value. Got {byte_offset.__class__.__name__}')
                if byte_offset < 0:
                    raise ValueError('byte_offset must be a positive integer')

            if substruct is not None:
                if not isinstance(substruct, Struct):
                    raise ValueError(f'substruct must be Struct instance. Got {substruct.__class__.__name__}')

            if subarray is not None:
                if not isinstance(subarray, TypedArray):
                    raise ValueError(f'subarray must be TypedArray instance. Got {subarray.__class__.__name__}')

            if pointer is not None:
                if not isinstance(pointer, Pointer):
                    raise ValueError(f'pointer must be Pointer instance. Got {pointer.__class__.__name__}')

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
            self.pointer = pointer
            self.embedded_enum = embedded_enum
            self.is_unnamed = is_unnamed

        def get_substruct(self) -> "Struct":
            """Return the nested ``Struct`` for this member.

            :raises ValueError: If this member is not of type ``MemberType.SubStruct``.
            """
            if self.substruct is None or self.member_type != self.MemberType.SubStruct:
                raise ValueError("Member is not a substruct")

            return self.substruct

        def get_array(self) -> "TypedArray":
            """Return the ``TypedArray`` for this member.

            :raises ValueError: If this member is not of type ``MemberType.SubArray``.
            """
            if self.subarray is None or self.member_type != self.MemberType.SubArray:
                raise ValueError("Member is not a subarray")
            return self.subarray

        def get_pointer(self) -> "Pointer":
            """Return the ``Pointer`` for this member.

            :raises ValueError: If this member is not of type ``MemberType.Pointer``.
            """
            if self.pointer is None or self.member_type != self.MemberType.Pointer:
                raise ValueError("Member is not a pointer")
            return self.pointer

    name: str
    """Name of the struct as declared in source code"""
    is_anonymous: bool
    """``True`` if this struct is anonymous (has no tag name in C/C++)"""
    members: Dict[str, "Struct.Member"]
    """Mapping of member name to ``Member`` instance"""
    byte_size: Optional[int]
    """Total size of the struct in bytes, or ``None`` if not yet determined"""

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
                substruct_member2 = copy(subtruct_member)
                if substruct_member2.byte_offset is None:
                    raise RuntimeError("Expect byte_offset to be set to handle unnamed composite type")
                substruct_member2.byte_offset += member.byte_offset
                self.add_member(substruct_member2)
        else:
            if member.name in self.members:
                raise KeyError(f'Duplicate member {member.name}')

            self.members[member.name] = member

    def inherit(self, other: "Struct", offset: int = 0) -> None:
        """Copy all members from another ``Struct`` into this one, adjusting their byte offsets.

        Used to model C++ inheritance, where base class members are absorbed into the derived struct
        shifted by ``offset`` bytes.

        :param other: The base ``Struct`` whose members are to be inherited.
        :param offset: Byte offset added to each inherited member's ``byte_offset``.
        :raises RuntimeError: If any inherited member has no ``byte_offset`` set.
        """
        for member in other.members.values():
            member2 = copy(member)
            if member2.byte_offset is None:
                raise RuntimeError("Expect byte_offset to be set to handle inheritance")
            member2.byte_offset += offset
            self.add_member(member2)
