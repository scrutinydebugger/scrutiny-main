#    simplification_rules.py
#        Rules deciding if a struct should be registered as one of its submembers instead
#        of its full member tree
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['SimplificationRules']

import re
from copy import copy

from scrutiny.core.bintools.elf_dwarf_var_extractor.definitions import Compiler
from scrutiny.core.bintools.elf_dwarf_var_extractor.helpers import ElfParsingError, Context
from scrutiny.core.struct import Struct
from scrutiny.tools.typing import *


class SimplificationRules:
    """Rules deciding if a struct should be registered as one of its submembers instead of its full member tree"""

    # Rust wrapper types that are collapsed to their single descendant. Matched against the struct name (DW_AT_name, no namespace).
    # bool, f16, fixed-point and arbitrary-int types are left out on purpose: their leaf is a raw storage type that loses the meaning.
    RUST_COLLAPSIBLE_STRUCT_REGEXES: List[re.Pattern[str]] = [
        # core
        re.compile(r'^Atomic<([ui](8|16|32|64|128|size)|f(32|64)|\*mut .+)>$'),  # core::sync::atomic and the atomic crate
        re.compile(r'^Align\d+<'),          # core::sync::atomic::private, internal to Atomic
        re.compile(r'^UnsafeCell<'),
        re.compile(r'^Cell<'),
        re.compile(r'^ManuallyDrop<'),
        re.compile(r'^MaybeDangling<'),     # Internal to ManuallyDrop
        re.compile(r'^MaybeUninit<'),
        re.compile(r'^Wrapping<'),
        re.compile(r'^Saturating<'),
        re.compile(r'^Reverse<'),
        re.compile(r'^NonZero<'),
        re.compile(r'^NonZero\w+Inner$'),   # core::num::niche_types, internal to NonZero
        re.compile(r'^NonNull<'),
        re.compile(r'^Pin<'),
        # crates
        re.compile(r'^VolatileCell<'),      # vcell
        re.compile(r'^(RW|RO|WO)<'),        # volatile_register
        re.compile(r'^Mutex<'),             # critical_section, bare_metal, embassy_sync. spin and std have many descendants
        re.compile(r'^Atomic([UI](8|16|32|64|128|size)|F(32|64))$'),  # portable_atomic, atomic_float
        re.compile(r'^GroundedCell<'),      # grounded
        re.compile(r'^(InMemoryRegister|ReadWrite|ReadOnly|WriteOnly)<'),  # tock_registers
        re.compile(r'^CachePadded<'),       # crossbeam_utils
        re.compile(r'^(OrderedFloat|NotNan)<'),  # ordered_float
        re.compile(r'^InternalBitFlags$'),  # bitflags
    ]

    @staticmethod
    def get_struct_replacement(struct: Struct, context: Context) -> Optional[Struct.Member]:
        """Return the member that must be registered in place of a fully built struct, or ``None`` if the struct is kept as is.
        The ``byte_offset`` of the returned member is relative to the start of the struct.

        :param struct: The struct to evaluate
        :param context: The parsing context of the compile unit that defines the struct
        """
        if context.cu_compiler == Compiler.RUSTC:
            return SimplificationRules._get_rust_collapse_replacement(struct)
        return None

    @staticmethod
    def _get_rust_collapse_replacement(struct: Struct) -> Optional[Struct.Member]:
        """Collapse a known Rust wrapper type to its single descendant. Example: ``Atomic<u32>`` -> ``['v', 'value', '__0']``"""
        name_matches = False
        for regex in SimplificationRules.RUST_COLLAPSIBLE_STRUCT_REGEXES:
            if regex.match(struct.name):
                name_matches = True
                break
        if not name_matches:
            return None

        leaves: List[Tuple[List[str], Struct.Member]] = []
        SimplificationRules._collect_struct_leaves(struct, [], leaves)
        if len(leaves) != 1:
            return None

        leaf_path, leaf_member = leaves[0]
        # Arrays are left out. The array registration appends a path segment, which would not give a collapsed name.
        if leaf_member.member_type not in (Struct.Member.MemberType.BaseType, Struct.Member.MemberType.Pointer):
            return None

        return SimplificationRules._make_replacement_member(struct, leaf_path)

    @staticmethod
    def _collect_struct_leaves(struct: Struct, prefix: List[str], output: List[Tuple[List[str], Struct.Member]]) -> None:
        """Find every non-struct member of a struct, recursively. Zero-sized members (PhantomData, ()) are not part of the struct and produce no leaf.

        :param struct: The struct to scan
        :param prefix: The member path leading to this struct
        :param output: List where (member_path, member) are appended
        """
        for name, member in struct.members.items():
            member_path = prefix + [name]
            if member.member_type == Struct.Member.MemberType.SubStruct:
                assert member.substruct is not None
                SimplificationRules._collect_struct_leaves(member.substruct, member_path, output)
            else:
                output.append((member_path, member))

    @staticmethod
    def _make_replacement_member(struct: Struct, member_path: List[str]) -> Struct.Member:
        """Make a copy of a submember, possibly many levels deep, with a byte_offset relative to the start of the struct.

        :param struct: The struct to replace
        :param member_path: Names of the members to go through, starting from the struct. Example: ``['value', 'value', '__0']``
        """
        if len(member_path) == 0:
            raise ValueError("Empty member path")

        current_struct: Optional[Struct] = struct
        member: Optional[Struct.Member] = None
        total_byte_offset = 0
        for name in member_path:
            if current_struct is None:
                raise ValueError(f"Cannot go through member {name}. Parent is not a struct")
            if name not in current_struct.members:
                raise KeyError(f"No member {name} in struct {current_struct.name}")
            member = current_struct.members[name]
            if member.byte_offset is None:
                raise ElfParsingError(f"Member {name} has no byte_offset")
            total_byte_offset += member.byte_offset
            current_struct = member.substruct

        assert member is not None
        # Copy because the original byte_offset is relative to the member's own parent, not to the replaced struct
        replacement = copy(member)
        replacement.byte_offset = total_byte_offset
        return replacement
