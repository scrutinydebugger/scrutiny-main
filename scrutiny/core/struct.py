#    struct.py
#        Definition of a struct, mainly used for parsing DWARF symbols
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['Struct']

import enum
from scrutiny.core.embedded_enum import EmbeddedEnum
from copy import deepcopy
from scrutiny.tools.typing import *

if TYPE_CHECKING:
    from scrutiny.core.array import TypedArray


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
        subarray: Optional["TypedArray"]
        embedded_enum: Optional[EmbeddedEnum]
        is_unnamed: bool

        def __init__(self, name: str,
                     member_type: MemberType,
                     original_type_name: Optional[str] = None,
                     byte_offset: Optional[int] = None,
                     bitoffset: Optional[int] = None,
                     bitsize: Optional[int] = None,
                     substruct: Optional['Struct'] = None,
                     subarray: Optional["TypedArray"] = None,
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
