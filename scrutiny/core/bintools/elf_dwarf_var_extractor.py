#    elf_dwarf_var_extractor.py
#        Reads a .elf file, extract the DWARF debugging symbols and make a VarMap object out
#        of it.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

__all__ = ['ElfDwarfVarExtractor']

from elftools.dwarf.die import DIE
from elftools.dwarf.compileunit import CompileUnit
from elftools.dwarf.dwarfinfo import DWARFInfo
from elftools.elf.elffile import ELFFile
from sortedcontainers import SortedSet

import os
import logging
import inspect
from copy import deepcopy
from enum import Enum, auto
from dataclasses import dataclass
from inspect import currentframe
from fnmatch import fnmatch

from scrutiny.core.bintools.demangler import GccDemangler, BaseDemangler
from scrutiny.core.varmap import VarMap
from scrutiny.core.basic_types import *
from scrutiny.core.variable_location import AbsoluteLocation, UnresolvedPathPointedLocation
from scrutiny.core.struct import Struct
from scrutiny.core.array import TypedArray, Array
from scrutiny.core.pointer import Pointer
from scrutiny.core import path_tools
from scrutiny.core.embedded_enum import *
from scrutiny.exceptions import EnvionmentNotSetUpException
from scrutiny import tools
from scrutiny.core.logging import DUMPDATA_LOGLEVEL

from scrutiny.tools.typing import *


# region Constant definitions
class Attrs:
    DW_AT_declaration = 'DW_AT_declaration'
    DW_AT_comp_dir = 'DW_AT_comp_dir'
    DW_AT_specification = 'DW_AT_specification'
    DW_AT_abstract_origin = 'DW_AT_abstract_origin'
    DW_AT_name = 'DW_AT_name'
    DW_AT_linkage_name = 'DW_AT_linkage_name'
    DW_AT_MIPS_linkage_name = 'DW_AT_MIPS_linkage_name'
    DW_AT_external = 'DW_AT_external'
    DW_AT_byte_size = 'DW_AT_byte_size'
    DW_AT_encoding = 'DW_AT_encoding'
    DW_AT_const_value = 'DW_AT_const_value'
    DW_AT_type = 'DW_AT_type'
    DW_AT_data_member_location = 'DW_AT_data_member_location'
    DW_AT_bit_offset = 'DW_AT_bit_offset'
    DW_AT_bit_size = 'DW_AT_bit_size'
    DW_AT_data_bit_offset = 'DW_AT_data_bit_offset'
    DW_AT_location = 'DW_AT_location'
    DW_AT_MIPS_fde = 'DW_AT_MIPS_fde'
    DW_AT_producer = 'DW_AT_producer'
    DW_AT_count = 'DW_AT_count'
    DW_AT_upper_bound = 'DW_AT_upper_bound'
    DW_AT_lower_bound = 'DW_AT_lower_bound'


class Tags:
    DW_TAG_structure_type = 'DW_TAG_structure_type'
    DW_TAG_enumeration_type = 'DW_TAG_enumeration_type'
    DW_TAG_union_type = 'DW_TAG_union_type'
    DW_TAG_compile_unit = 'DW_TAG_compile_unit'
    DW_TAG_variable = 'DW_TAG_variable'
    DW_TAG_enumerator = 'DW_TAG_enumerator'
    DW_TAG_base_type = 'DW_TAG_base_type'
    DW_TAG_class_type = 'DW_TAG_class_type'
    DW_TAG_array_type = 'DW_TAG_array_type'
    DW_TAG_pointer_type = 'DW_TAG_pointer_type'
    DW_TAG_member = 'DW_TAG_member'
    DW_TAG_inheritance = 'DW_TAG_inheritance'
    DW_TAG_typedef = 'DW_TAG_typedef'
    DW_TAG_subrange_type = 'DW_TAG_subrange_type'
    DW_TAG_subroutine_type = 'DW_TAG_subroutine_type'
    DW_TAG_unspecified_type = 'DW_TAG_unspecified_type'


class DwarfEncoding(Enum):
    DW_ATE_address = 0x1
    DW_ATE_boolean = 0x2
    DW_ATE_complex_float = 0x3
    DW_ATE_float = 0x4
    DW_ATE_signed = 0x5
    DW_ATE_signed_char = 0x6
    DW_ATE_unsigned = 0x7
    DW_ATE_unsigned_char = 0x8
    DW_ATE_imaginary_float = 0x9
    DW_ATE_packed_decimal = 0xa
    DW_ATE_numeric_string = 0xb
    DW_ATE_edited = 0xc
    DW_ATE_signed_fixed = 0xd
    DW_ATE_unsigned_fixed = 0xe
    DW_ATE_decimal_float = 0xf
    DW_ATE_UTF = 0x10
    DW_ATE_lo_user = 0x80
    DW_ATE_hi_user = 0xff


class TypeOfVar(Enum):
    BaseType = auto()
    Struct = auto()
    Class = auto()
    Union = auto()
    Pointer = auto()
    Array = auto()
    EnumOnly = auto()  # Clang dwarf v2
    Subroutine = auto()  # Clang dwarf v2
    Void = auto()


ENCODING_2_DTYPE_MAP: Dict[DwarfEncoding, Dict[int, EmbeddedDataType]] = {
    DwarfEncoding.DW_ATE_address: {
        1: EmbeddedDataType.ptr8,
        2: EmbeddedDataType.ptr16,
        4: EmbeddedDataType.ptr32,
        8: EmbeddedDataType.ptr64,
        16: EmbeddedDataType.ptr128,
        32: EmbeddedDataType.ptr256
    },
    DwarfEncoding.DW_ATE_boolean: {
        1: EmbeddedDataType.boolean,
        2: EmbeddedDataType.uint16,
        4: EmbeddedDataType.uint32,
        8: EmbeddedDataType.uint64
    },
    DwarfEncoding.DW_ATE_complex_float: {
        1: EmbeddedDataType.cfloat8,
        2: EmbeddedDataType.cfloat16,
        4: EmbeddedDataType.cfloat32,
        8: EmbeddedDataType.cfloat64,
        16: EmbeddedDataType.cfloat128,
        32: EmbeddedDataType.cfloat256
    },
    DwarfEncoding.DW_ATE_float: {
        1: EmbeddedDataType.float8,
        2: EmbeddedDataType.float16,
        4: EmbeddedDataType.float32,
        8: EmbeddedDataType.float64,
        16: EmbeddedDataType.float128,
        32: EmbeddedDataType.float256

    },
    DwarfEncoding.DW_ATE_signed: {
        1: EmbeddedDataType.sint8,
        2: EmbeddedDataType.sint16,
        4: EmbeddedDataType.sint32,
        8: EmbeddedDataType.sint64,
        16: EmbeddedDataType.sint128,
        32: EmbeddedDataType.sint256
    },
    DwarfEncoding.DW_ATE_signed_char: {
        1: EmbeddedDataType.sint8,
        2: EmbeddedDataType.sint16,
        4: EmbeddedDataType.sint32,
        8: EmbeddedDataType.sint64,
        16: EmbeddedDataType.sint128,
        32: EmbeddedDataType.sint256
    },
    DwarfEncoding.DW_ATE_unsigned: {
        1: EmbeddedDataType.uint8,
        2: EmbeddedDataType.uint16,
        4: EmbeddedDataType.uint32,
        8: EmbeddedDataType.uint64,
        16: EmbeddedDataType.uint128,
        32: EmbeddedDataType.uint256
    },
    DwarfEncoding.DW_ATE_unsigned_char: {
        1: EmbeddedDataType.uint8,
        2: EmbeddedDataType.uint16,
        4: EmbeddedDataType.uint32,
        8: EmbeddedDataType.uint64,
        16: EmbeddedDataType.uint128,
        32: EmbeddedDataType.uint256
    },
    DwarfEncoding.DW_ATE_UTF: {
        1: EmbeddedDataType.sint8,
        2: EmbeddedDataType.sint16,
        4: EmbeddedDataType.sint32,
    }
}


class Architecture(Enum):
    UNKNOWN = auto()
    TI_C28x = auto()


class Compiler(Enum):
    UNKNOWN = auto()
    TI_C28_CGT = auto()
    CLANG = auto()
    GCC = auto()
    Tasking = auto()

# endregion

# region Helper classes


@dataclass(slots=True)
class PointeeTypeDescriptor:
    """Describe the type pointed by a pointer. Same as TypeDescriptor,
    but the type_die is optional since we can have a pointer to void"""
    type: TypeOfVar
    enum_die: Optional[DIE]
    type_die: Optional[DIE]

    def to_typedesc(self) -> "TypeDescriptor":
        """Convert to a TypeDescriptor. Only possible if there is a typedie associated with the pointee.
        We can't get convert if we point to void"""
        if self.type_die is None:
            raise ValueError("Missing type_die to make a full type descriptor")

        return TypeDescriptor(
            type=self.type,
            enum_die=self.enum_die,
            type_die=self.type_die,
            pointee=None
        )


@dataclass(slots=True)
class TypeDescriptor:
    """A class that contains multiple information about the type of a variable"""
    type: TypeOfVar
    """Type of variable. BaseType, Struct, Union, Pointer etc."""
    enum_die: Optional[DIE]
    """The enum associated with the type. Applies only for BaseType"""
    type_die: DIE
    """The DIE that define this type"""
    pointee: Optional[PointeeTypeDescriptor]
    """Pointee type when type=Pointer"""


@dataclass(slots=True)
class VarPathSegment:
    """When building a path, represent a segment added to the path. Keeps track of the array of that path node for later"""
    name: str
    """The name of the path segment"""
    array: Optional[TypedArray] = None
    """The array associated with that segment, if applicable"""


@dataclass(slots=True, init=False)
class ArraySegments:
    """Class that wraps a dict of arrays that represent every segments that has an array.
    Has the helper method to edit that array meaningfully"""

    _storage: Dict[str, TypedArray]
    """The array that we edit"""

    def __init__(self) -> None:
        self._storage = {}

    def add(self, segments: List[str], array: TypedArray) -> None:
        """Add a path node that has an array"""
        path = path_tools.join_segments(segments)
        if path in self._storage:
            raise KeyError(f"Duplicate array definition for {path}")
        self._storage[path] = array

    def rename_path(self, old: List[str], new: List[str]) -> None:
        """Change the path of an array"""
        old_path = path_tools.join_segments(old)
        new_path = path_tools.join_segments(new)

        if old_path not in self._storage:
            raise KeyError(f"Cannot rename missing array definition for {old_path}.")

        if new_path in self._storage:
            raise KeyError(f"Duplicate array definition for {new_path}")

        v = self._storage[old_path]
        del self._storage[old_path]
        self._storage[new_path] = v

    def to_varmap_format(self) -> Dict[str, Array]:
        """Return a dictionnary that gives the array information in the format required by the VarMap class"""
        # We use the same format here. Just future proofing the code.
        return cast(Dict[str, Array], deepcopy(self._storage))

    def shallow_copy(self) -> "ArraySegments":
        """Create a shallow copy of the storage. Returns a new dict that points to the same arrays"""
        o = ArraySegments()
        o._storage = self._storage.copy()
        return o

    def deep_copy(self) -> "ArraySegments":
        """Create a deep copy. Returns a new dict with a copy of the arrays"""
        o = ArraySegments()
        o._storage = deepcopy(self._storage)
        return o

    def clear(self) -> None:
        """Clear the storage"""
        self._storage.clear()


class VarPath:
    """Represent a path of a variable. This class exists to edit efficiently the path with meaningful methods.
    To be used while constructing the path"""

    __slots__ = ('segments', )

    segments: List[VarPathSegment]

    def __init__(self) -> None:
        self.segments = []

    def prepend_segment(self, name: str, array: Optional[TypedArray] = None) -> None:
        """Add a path segment at the beginning"""
        self.segments.insert(0, VarPathSegment(name=name, array=array))

    def get_segments_name(self) -> List[str]:
        """Return an array of all the segments names"""
        return [segment.name for segment in self.segments]

    def get_array_segments(self) -> ArraySegments:
        """Return the definition of all the array nodes that we have found so far"""
        out = ArraySegments()
        for i in range(len(self.segments)):
            array = self.segments[i].array
            if array is not None:
                segment_str = [x.name for x in self.segments[:i + 1]]
                out.add(segment_str, array)
        return out


class CuName:
    """
    Handles a compile unit name. Useful to build a unique name as small as possible.
    """
    PATH_JOIN_CHAR = '_'

    _fullpath: str
    _filename: str
    _display_name: str
    _segments: List[str]
    _numbered_name: Optional[str]

    def __hash__(self) -> int:
        return self._fullpath.__hash__()

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CuName):
            return False
        return self._fullpath == other._fullpath

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, CuName):
            return False
        return self._fullpath < other._fullpath

    def __gt__(self, other: object) -> bool:
        if not isinstance(other, CuName):
            return False
        return self._fullpath > other._fullpath

    def __init__(self, fullpath: str) -> None:
        self._fullpath = fullpath    # Must stay untouched.
        self._filename = os.path.basename(self._fullpath)
        self._display_name = self._filename
        # os.path.split return a tuple : (dir, basename)
        self._segments = os.path.split(os.path.normpath(self._fullpath))[0].split(os.sep)
        self._numbered_name = None

    def get_display_name(self) -> str:
        """Return a name that can be shown to the user"""
        if self._numbered_name is not None:
            return self._numbered_name
        return self._display_name.replace('/', '-')

    def get_fullpath(self) -> str:
        """Return the fullpath to the source file gotten from the ELF file"""
        return self._fullpath

    def go_up(self) -> None:
        """Add the closest directory name to the display name.
        /aaa/bbb/ccc, ddd -->  /aaa/bbb, ccc_ddd"""
        if len(self._segments) > 0:
            last_dir = self._segments.pop()
            if last_dir == '':
                raise ElfParsingError('Cannot go up')
            self._display_name = self.PATH_JOIN_CHAR.join([last_dir, self._display_name])
        else:
            raise ElfParsingError('Cannot go up')

    def make_unique_numbered_name(self, name_set: Set[str]) -> None:
        """Fallback solution to naming.
        We can generated a numbered name if there are collisions with the source file naming"""
        i = 0
        while True:
            candidate = 'cu%d_%s' % (i, self._filename)
            if candidate not in name_set:
                self._numbered_name = candidate
                return
            i += 1


@dataclass(slots=True)
class Context:
    """The context object that contains the parsing parameters. Those are globals when parsing"""
    arch: Architecture
    """The architecture the target the file is compiled for"""
    endianess: Endianness
    """The endianess of the firmware"""
    cu_compiler: Compiler
    """The compiler of the actual CompileUnit """
    address_size: Optional[int]
    """The size of a pointer. Sometime available at the CU level, sometime on the var itself. Act as a fallback when not specified on a var"""


class ElfParsingError(Exception):
    pass


class ParseErrors:
    """A class that represent a parsing error.
    We keep track of all the error we find so that we can fail unit tests without stopping the aprsing"""
    __slots__ = ('_exceptions', )

    _exceptions: List[Exception]

    def __init__(self) -> None:
        self._exceptions = []

    def register_error(self, e: Exception) -> None:
        self._exceptions.append(e)

    def total_count(self, exclude: Optional[List[Type[Exception]]] = None) -> int:
        if exclude is None:
            return len(self._exceptions)

        count = 0
        for e in self.iter_exc(exclude):
            count += 1
        return count

    def iter_exc(self, exclude: Optional[List[Type[Exception]]] = None) -> Generator[Exception, None, None]:
        exclude2 = tuple(exclude) if exclude is not None else tuple()
        for e in self._exceptions:
            if not isinstance(e, exclude2):
                yield e

    def get_first_exc(self, exclude: Optional[List[Type[Exception]]] = None) -> Optional[Exception]:
        if exclude is None:
            exclude = []
        gen = self.iter_exc(exclude)
        return next(gen, None)


# endregion

def get_linenumber() -> int:
    """Return the line number of the caller. For debugging purpose"""
    cf = currentframe()
    if cf is None:
        return -1
    if cf.f_back is None:
        return -1
    if cf.f_back.f_lineno is None:
        return -1

    return int(cf.f_back.f_lineno)


class ElfDwarfVarExtractor:
    """Tool that can parse a .elf file, parse the debug symbols and generate a VarMap object that is the base of Scrutiny
    to interpret a firmware memory layout"""

    DEFAULTS_NAMES: Dict[str, str] = {
        Tags.DW_TAG_structure_type: '<struct>',
        Tags.DW_TAG_enumeration_type: '<enum>',
        Tags.DW_TAG_union_type: '<union>'
    }

    STATIC = 'static'
    GLOBAL = 'global'
    MAX_CU_DISPLAY_NAME_LENGTH = 64
    DW_OP_ADDR = 3
    DW_OP_plus_uconst = 0x23

    _varmap: VarMap
    """The VarMap that we try to build"""
    _die2vartype_map: Dict[DIE, EmbeddedDataType]
    """Cache mapping a type DIE to a Scrutiny EmbeddedDataType."""
    _cu_name_map: Dict[CompileUnit, str]
    """Cache mapping a CompileUnit object to the name we shall use in the path for static variables"""
    _enum_die_map: Dict[DIE, EmbeddedEnum]
    """Cache mapping an enum die to a Scrutiny EmbeddedEnum object"""
    _struct_die_cache_map: Dict[Tuple[DIE, bool], Struct]
    """Cache mapping a struct die to a Scrutiny Struct"""
    _array_die_cache_map: Dict[Tuple[DIE, bool], TypedArray]
    """Cache mapping an array die to a Scrutiny TypedArray"""
    _cppfilt: Optional[str]
    """The path to cppfilt executable if provided"""
    _logger: logging.Logger
    """A logger"""
    _ignore_cu_patterns: List[str]
    """Ignore patterns given by the users listing what Compile Units to ignore"""
    _path_ignore_patterns: List[str]
    """Ignore patterns given by the user listing what variable path to drop """
    _anonymous_type_typedef_map: Dict[DIE, DIE]
    """A cache mapping anonymous types DIE to a typedef DIE. Basically typedef struct{...} MyStruct."""
    _initial_stack_depth: int
    """For debug logging. Check the stack depth at the beginning of the parsing to properly indent"""
    _parse_errors: ParseErrors
    """List of parsing errors we got"""
    _context: Context
    """The context object passed down during the recursive search stage of a compile unit scanning. Contains info such has compiler, architecture, endianness, etc."""
    _dwarfinfo: DWARFInfo
    """The dwarf info of the file being scanned"""
    _demangler: BaseDemangler
    """The demangler to use while scanning"""
    _allow_dereference_pointer:bool

    def __init__(self, filename: str,
                 cppfilt: Optional[str] = None,
                 ignore_cu_patterns: Optional[List[str]] = None,
                 path_ignore_patterns: Optional[List[str]] = None,
                 dereference_pointers: bool = True
                 ) -> None:
        self._varmap = VarMap()    # This is what we want to generate.
        self._die2vartype_map = {}
        self._anonymous_type_typedef_map = {}
        self._cu_name_map = {}   # maps a CompileUnit object to it's unique display name
        self._enum_die_map = {}
        self._struct_die_cache_map = {}
        self._array_die_cache_map = {}
        self._cppfilt = cppfilt
        self._ignore_cu_patterns = ignore_cu_patterns if ignore_cu_patterns is not None else []
        self._path_ignore_patterns = path_ignore_patterns if path_ignore_patterns is not None else []
        self._logger = logging.getLogger(self.__class__.__name__)
        self._context = Context(    # Default
            arch=Architecture.UNKNOWN,
            endianess=Endianness.Little,
            cu_compiler=Compiler.UNKNOWN,
            address_size=None
        )
        self._parse_errors = ParseErrors()
        self._allow_dereference_pointer = dereference_pointers

        self._scan_elf_file(filename)

    # region Public

    @classmethod
    def make_unique_display_name(cls, fullpath_list: List[str]) -> Dict[str, str]:
        """Build a unique name for a CompileUnit. Do some extensive effort to keep a meaningful name, as short as possible
        and avoid collisions if 2 files has the same name."""
        cuname_set = SortedSet([CuName(x) for x in sorted(fullpath_list)])
        outmap: Dict[str, str] = {}

        display_name_set: Set[str] = set()
        while len(cuname_set) > 0:
            consumed_set: Set[CuName] = set()
            for cuname in cuname_set:
                display_name = cuname.get_display_name()

                identical_name_set: Set[CuName] = set()
                for cuname2 in cuname_set:
                    if cuname2.get_display_name() == display_name:
                        identical_name_set.add(cuname2)

                if len(identical_name_set) == 1:
                    display_name_set.add(display_name)
                    consumed_set.add(cuname)
                    outmap[cuname.get_fullpath()] = display_name

            for consumed in consumed_set:
                cuname_set.remove(consumed)

            # Those that are left had duplicate name.
            # Change the name and try again
            for cuname in cuname_set:
                try:
                    cuname.go_up()
                    if len(cuname.get_display_name()) > cls.MAX_CU_DISPLAY_NAME_LENGTH:
                        raise ElfParsingError('Name too long')
                except Exception:
                    # Does not affect the given set.
                    # Only mark the Compile Unit as using a numbered name.
                    # This numbered name will be consumed on next loop iteration.
                    cuname.make_unique_numbered_name(display_name_set)

        return outmap

    @classmethod
    def split_demangled_name(cls, name: str) -> List[str]:
        """Transform a C++ nesting name to a path like structure
        namespace1::class2<T>::enum3::HELLO --> namespace1/class2<T>/enum3/HELLO
        """
        paranthesis_level = 0
        ducky_bracket_level = 0

        outname = ''
        is_in_bracket = False
        bracket_exit_pos = 0
        bracket_enter_pos = 0
        for i in range(len(name)):
            c = name[i]

            was_in_bracket = is_in_bracket
            if c == '(':
                paranthesis_level += 1
            elif c == ')':
                paranthesis_level -= 1
            elif c == '<':
                ducky_bracket_level += 1
            elif c == '>':
                ducky_bracket_level -= 1
            is_in_bracket = (paranthesis_level > 0 or ducky_bracket_level > 0)

            if not was_in_bracket and is_in_bracket:  # entering bracket
                bracket_enter_pos = i
                outname += name[bracket_exit_pos:i].replace('::', ';')

            if was_in_bracket and not is_in_bracket:    # exiting bracket
                bracket_exit_pos = i
                outname += name[bracket_enter_pos:i]    # No replace on purpose

        outname += name[bracket_exit_pos:].replace('::', ';')
        return outname.split(';')

    @classmethod
    def get_core_base_type(cls, encoding: DwarfEncoding, bytesize: int) -> EmbeddedDataType:
        """Convert a DWARF encoding into a Scrutiny EmbeddedDataType"""
        if encoding not in ENCODING_2_DTYPE_MAP:
            raise ValueError(f'Unknown encoding {encoding}')

        if bytesize not in ENCODING_2_DTYPE_MAP[encoding]:
            raise ValueError(f'Encoding {encoding} with {bytesize} bytes')

        return ENCODING_2_DTYPE_MAP[encoding][bytesize]

    def get_errors(self) -> ParseErrors:
        """Returns all the errors registered during the aprsing"""
        return self._parse_errors

    def get_varmap(self) -> VarMap:
        """Returns the varmap constructed by the parsing"""
        return self._varmap

    # endregion

    # region Prvate
    def _make_name_for_log(self, die: Optional[DIE]) -> str:
        """For debug logging. Name used to identify a DIE """
        if die is None:
            return "<None>"
        name = self._get_die_name(die, default='', nolog=True)

        return f'{die.tag} <{die.offset:x}> "{name}"'

    def _log_debug_process_die(self, die: DIE) -> None:
        """When printing the full debug information, print that a function has been called with its stack depth represneted as indentation"""
        if self._logger.isEnabledFor(DUMPDATA_LOGLEVEL):  # pragma: no cover
            stack_depth = len(inspect.stack()) - self._initial_stack_depth - 1
            stack_depth = max(stack_depth, 1)
            funcname = inspect.stack()[1][3]
            pad = '|  ' * (stack_depth - 1) + '|--'
            self._logger.debug(f"{pad}{funcname}({self._make_name_for_log(die)})")

    def _make_cu_name_map(self, dwarfinfo: DWARFInfo) -> None:
        """ Builds a dictionary that maps a CompileUnit object to a unique displayable name """

        fullpath_cu_map: Dict[str, List[CompileUnit]] = {}
        cu: CompileUnit
        for cu in dwarfinfo.iter_CUs():
            topdie: DIE = cu.get_top_DIE()
            if topdie.tag != Tags.DW_TAG_compile_unit:
                raise ElfParsingError('Top die should be a compile unit')

            comp_dir = None
            name = self._get_die_name_no_none(topdie, default='unnamed_cu')
            if Attrs.DW_AT_comp_dir in topdie.attributes:
                comp_dir = topdie.attributes[Attrs.DW_AT_comp_dir].value.decode('utf8')
                fullpath = os.path.normpath(os.path.join(comp_dir, name))
            else:
                fullpath = os.path.abspath(name)

            if fullpath not in fullpath_cu_map:
                fullpath_cu_map[fullpath] = []
            fullpath_cu_map[fullpath].append(cu)

        fullpath_to_displayname_map = self.make_unique_display_name(list(fullpath_cu_map.keys()))

        for fullpath, cu_list in fullpath_cu_map.items():
            for cu in cu_list:
                self._cu_name_map[cu] = fullpath_to_displayname_map[fullpath]

    def _get_cu_name(self, die: DIE) -> str:
        """Return the name of the CompileUnit in which this DIE is part of"""
        return self._cu_name_map[die.cu]

    def _get_enum_from_type_descriptor(self, type_desc: TypeDescriptor) -> Optional[EmbeddedEnum]:
        """Reads the enum of a type descriptor. If this is an array, return the enum of the subtype"""
        if type_desc.type == TypeOfVar.Array:
            type_desc = self._get_type_of_var(type_desc.type_die)

        if type_desc.enum_die is not None:
            if type_desc.enum_die in self._enum_die_map:
                return self._enum_die_map[type_desc.enum_die]
        return None

    def _get_die_name(self,
                      die: DIE,
                      default: Optional[str] = None,
                      nolog: bool = False,
                      raise_if_none: bool = False,
                      no_tag_default: bool = False) -> Optional[str]:
        """Return the name of a DIE.

        :param default: A default name if none is available
        :param nolog: Don't log the call for debug purpose
        :param raise_if_none: Raise an error if no name is avaialble and no default name is possible
        :param no_tag_default: If no default name is provided, do not use the default names per tag defined in DEFAULTS_NAMES
        """

        if not nolog:
            self._log_debug_process_die(die)
        if Attrs.DW_AT_name in die.attributes:
            return cast(str, die.attributes[Attrs.DW_AT_name].value.decode('ascii'))

        if default is not None:
            return default

        # Check if we have a DIE already identified as an anonymous class/struct/union/enum. Use the typedef if there is one
        if die in self._anonymous_type_typedef_map:
            typedef_die = self._anonymous_type_typedef_map[die]
            name = self._get_die_name(typedef_die, default=default, nolog=nolog, raise_if_none=raise_if_none)
            if name is not None:
                return name

        if die.tag in self.DEFAULTS_NAMES and no_tag_default is False:
            return self.DEFAULTS_NAMES[die.tag]

        if raise_if_none:
            raise ElfParsingError(f"No name available on die {die}")
        return None

    def _get_die_name_no_none(self, die: DIE, default: Optional[str] = None, nolog: bool = False) -> str:
        """Read the name of a DIE and throw an exception if no name is available."""
        name = self._get_die_name(die, default, nolog, raise_if_none=True)
        assert name is not None
        return name

    def _has_linkage_name(self, die: DIE) -> bool:
        """Tells if a DIE has a linkage name"""
        return self._get_mangled_linkage_name(die) is not None

    def _get_mangled_linkage_name(self, die: DIE) -> Optional[str]:
        """Return the mangled linkage name of a DIE if one is available. ``None`` if not available."""
        mangled_encoded: Optional[str] = None

        if Attrs.DW_AT_linkage_name in die.attributes:
            mangled_encoded = die.attributes[Attrs.DW_AT_linkage_name].value

        if self._context.cu_compiler == Compiler.TI_C28_CGT:
            if Attrs.DW_AT_MIPS_fde in die.attributes:
                mangled_encoded = die.attributes[Attrs.DW_AT_MIPS_fde].value
        else:
            if Attrs.DW_AT_MIPS_linkage_name in die.attributes:
                mangled_encoded = die.attributes[Attrs.DW_AT_MIPS_linkage_name].value

        # Tasking compiler encode the mangled name in DW_AT_Name  (-_-)
        if mangled_encoded is None:
            if self._context.cu_compiler == Compiler.Tasking:
                if Attrs.DW_AT_name in die.attributes:
                    name = cast(bytes, die.attributes[Attrs.DW_AT_name].value).decode('ascii')
                    if name.startswith('_Z'):   # Speed optimization to avoid invoking the demangler for everything
                        return name

        if isinstance(mangled_encoded, bytes):
            return mangled_encoded.decode('ascii')

        if isinstance(mangled_encoded, str):
            return mangled_encoded

        return None

    def _get_demangled_linkage_name(self, die: DIE) -> Optional[str]:
        """Get the demangled linkage name of a DIE. Invoke the demangler"""
        self._log_debug_process_die(die)
        mangled_name = self._get_mangled_linkage_name(die)
        if mangled_name is None:
            return None

        return self._demangler.demangle(mangled_name)

    def _post_process_splitted_demangled_name(self, parts: List[str]) -> List[str]:
        """To be called on the result of ``split_demangled_name`` to apply some context specific transformation"""
        if self._context.cu_compiler == Compiler.Tasking:
            # Tasking do something like that : /static/file1.cpp/_INTERNAL_9_file1_cpp_49335e60/NamespaceInFile1/NamespaceInFile1Nested1/file1StaticNestedVar1
            return [x for x in parts if not x.startswith('_INTERNAL_')]
        return parts

    def _is_external(self, die: DIE) -> bool:
        """Tells if the die is accessible from outside the compile unit. If it is, it's global, otherwise it's static."""
        try:
            return bool(die.attributes[Attrs.DW_AT_external].value)
        except Exception:
            return False

    def _scan_elf_file(self, filename: str) -> None:
        """Reads an ELF file and builds the varmap. Main entry point for scanning"""
        self._initial_stack_depth = len(inspect.stack())

        with open(filename, 'rb') as f:
            elffile = ELFFile(f)
            self._parse_errors = ParseErrors()

            if not elffile.has_dwarf_info():
                raise ElfParsingError('File has no DWARF info')

            self._dwarfinfo = elffile.get_dwarf_info()

            self._context.arch = self._identify_arch()
            self._context.endianess = self._identify_endianness(self._context.arch)
            self._varmap.set_endianness(self._context.endianess)

            self._make_cu_name_map(self._dwarfinfo)
            self._demangler = GccDemangler(self._cppfilt)  # todo : adapt according to compile unit producer

            if not self._demangler.can_run():
                raise EnvionmentNotSetUpException("Demangler cannot be used. %s" % self._demangler.get_error())

            bad_support_warning_written = False  # Prevent spamming the console
            for cu in self._dwarfinfo.iter_CUs():
                die = cu.get_top_DIE()

                # Check if we need to skip the Compile Unit
                cu_raw_name = cast(str, self._get_die_name(die, ''))
                if cu_raw_name != '':
                    cu_basename = os.path.basename(cu_raw_name)
                    must_skip = False
                    for pattern in self._ignore_cu_patterns:
                        if cu_basename == pattern or fnmatch(cu_raw_name, pattern):
                            must_skip = True
                            break
                    if must_skip:
                        self._logger.debug(f"Skipping Compile Unit: {cu_raw_name}")
                        continue

                # Process the Compile Unit
                self._context.cu_compiler = self._identify_compiler(cu)
                self._context.address_size = cu.header.address_size
                if cu.header.version not in (2, 3, 4):
                    if not bad_support_warning_written:
                        bad_support_warning_written = True
                        self._logger.warning(f"DWARF format version {cu.header.version} is not well supported, output may be incomplete")

                # Each compile unit is scanned in 2 passes.
                #  1. First, we build a map for every typedef
                #  2. Then we extract the variables.
                # 2 Passes are needed mostly because of how Tasking compiler connects typedefs together.
                # Sometime the type name is on the typedef DIE, but a struct has a type attribute that points to the type die directly,
                # without passing by the typedef first. In this case, we have no link tot he typedef, a new scan of the CU is needed to find it.
                # GCC and Clang does not do that. They map   struct -> typedef -> type

                self._build_typedef_map_recursive(die)   # Scan every typedef to know where they point
                self._extract_var_recursive(die)         # Recursion start point. We find the variables in here

    def _identify_arch(self) -> Architecture:
        """Identify we're building for what architecture. Unknown uses the default behaviors that works on most platforms."""
        machine_arch = self._dwarfinfo.config.machine_arch.lower().strip()
        if 'c2000' in machine_arch and 'ti' in machine_arch:
            return Architecture.TI_C28x

        return Architecture.UNKNOWN

    def _identify_compiler(self, cu: CompileUnit) -> Compiler:
        """Identify what compiler produced a compile unit. We can handle their little quirks"""
        cu_die = cu.get_top_DIE()
        if cu_die.tag != Tags.DW_TAG_compile_unit:
            return Compiler.UNKNOWN

        if Attrs.DW_AT_producer in cu_die.attributes:
            producer = str(cu_die.attributes[Attrs.DW_AT_producer].value).strip().lower()
            if 'ti' in producer and 'c2000' in producer:
                return Compiler.TI_C28_CGT
            if 'clang' in producer:
                return Compiler.CLANG
            if 'gnu' in producer:
                return Compiler.GCC
            if 'tasking' in producer:
                return Compiler.Tasking

        return Compiler.UNKNOWN

    def _identify_endianness(self, arch: Architecture) -> Endianness:
        """Identify the endianness. Based of the architecture"""
        # No easy way to know it. DW_AT_endianity is introduced in dwarf v4, but only applied on data block and not used by compilers...
        # We make the assumption that the endianness is the same at the binary level

        if arch == Architecture.TI_C28x:
            return Endianness.Big

        return Endianness.Little  # Little is the most common, default on this

    def _allowed_by_filters(self, fullname: str) -> bool:
        """Tells if we can register a variable to the varmap and log the reason for not allowing if applicable."""
        allow = True
        for ignore_pattern in self._path_ignore_patterns:
            if fnmatch(fullname, ignore_pattern):
                self._logger.debug(f"{fullname} matches ignore pattern {ignore_pattern}. Skipping")
                allow = False
                break

        return allow

    def _build_typedef_map_recursive(self, die: DIE) -> None:
        """Scan all typedef and create a reverse map so we can find a typedef from a type. Mostly encessary ebcause of Tasking compielr"""
        if die.tag == Tags.DW_TAG_typedef:
            self._die_process_typedef(die)

        for child in die.iter_children():
            try:
                self._build_typedef_map_recursive(child)
            except Exception as e:
                self._parse_errors.register_error(e)
                tools.log_exception(self._logger, e, f"Failed to scan typedefs var under {child}.")

    def _get_pointer_name_from_die(self, die: DIE) -> str:
        """Reads the name of a pointer DIE. We craft a name based of the size as
            - 1: a name is usually not available.
            - 2. We want all pointers to merge to the same type
            """
        if die.tag == Tags.DW_TAG_pointer_type:
            bytesize = self._get_size_from_pointer_die(die)
            return self._make_ptr_typename(bytesize)
        raise ElfParsingError(f"Cannot extract pointer name from die {die}")

    def _get_size_from_pointer_die(self, die: DIE) -> int:
        """Return the size of a pointer DIE. Use the context first (size defined at the CompileUnit level). If the CU does not define
        a size, check the pointer DIE itself."""
        if die.tag == Tags.DW_TAG_pointer_type:
            if self._context.address_size is not None:
                return self._context.address_size
        if Attrs.DW_AT_byte_size not in die.attributes:
            raise ElfParsingError(f'Cannot find the pointer size on die {die}')
        val = cast(int, die.attributes[Attrs.DW_AT_byte_size].value)
        return val

    def _get_typename_from_die(self, die: DIE) -> str:
        """Reads the name out of a base type DIE"""
        if die.tag == Tags.DW_TAG_base_type:
            return cast(bytes, die.attributes[Attrs.DW_AT_name].value).decode('ascii')
        raise ElfParsingError(f"Cannot extract type name from die {die}")

    def _get_size_from_type_die(self, die: DIE) -> int:
        """Return the size in multiple of 8 bits bytes of a given type DIE"""
        if Attrs.DW_AT_byte_size not in die.attributes:
            raise ElfParsingError(f'Missing DW_AT_byte_size on type die {die}')
        val = cast(int, die.attributes[Attrs.DW_AT_byte_size].value)
        if self._context.arch == Architecture.TI_C28x:
            return val * 2    # char = 16 bits

        return val

    def _has_member_byte_offset(self, die: DIE) -> bool:
        """Tells if an offset relative to the structure base is available on this member die"""
        return Attrs.DW_AT_data_member_location in die.attributes

    def _get_member_byte_offset(self, die: DIE) -> int:
        """Tell the offset at which this member is located relative to the structure base"""
        if Attrs.DW_AT_data_member_location not in die.attributes:
            # DWARF V4. 5.5.6: If the beginning of the data member is the same as the beginning of the containing entity then neither attribute is required.
            return 0

        val = die.attributes[Attrs.DW_AT_data_member_location].value
        if isinstance(val, int):
            return val

        if isinstance(val, list):
            if len(val) < 2:
                raise ElfParsingError(f"Invalid member offset data length for die {die}")

            if val[0] != self.DW_OP_plus_uconst:
                raise ElfParsingError(f"Does not know how to read member location for die {die}. Operator is unsupported")

            return tools.uleb128_decode(bytes(val[1:]))

        raise ElfParsingError(f"Does not know how to read member location for die {die}")

    def _get_location(self, die: DIE) -> Optional[AbsoluteLocation]:
        """Try to extract the location from a die. Returns ``None`` if not available"""
        if Attrs.DW_AT_location in die.attributes:
            dieloc = (die.attributes[Attrs.DW_AT_location].value)

            if not isinstance(dieloc, list):
                return None

            if len(dieloc) < 1:
                return None

            if dieloc[0] != self.DW_OP_ADDR:
                return None

            if len(dieloc) < 2:
                self._logger.warning(f'die location is too small: {dieloc}')
                return None

            return AbsoluteLocation.from_bytes(dieloc[1:], self._context.endianess)
        return None

    def _is_forward_declaration(self, die: DIE) -> bool:
        return Attrs.DW_AT_declaration in die.attributes and bool(die.attributes[Attrs.DW_AT_declaration].value) == True

    def _make_ptr_typename(self, bytesize: int) -> str:
        return f'ptr{bytesize * 8}'

    def _extract_var_recursive(self, die: DIE) -> None:
        # Finds all "variable" tags and create an entry in the varmap.
        # Types / structures / enums are discovered as we go. We only take
        # definitions that are used by a variables, the rest will be ignored.

        self._log_debug_process_die(die)

        if die.tag == Tags.DW_TAG_variable:
            self._die_process_variable(die)

        for child in die.iter_children():
            try:
                self._extract_var_recursive(child)
            except Exception as e:
                self._parse_errors.register_error(e)
                tools.log_exception(self._logger, e, f"Failed to extract var under {child}.")

# region DIE specific
    # Process die of type "base type". Register the type in the global index and maps it to a known type.
    def _die_process_base_type(self, die: DIE) -> None:
        self._log_debug_process_die(die)
        if die not in self._die2vartype_map:
            name = self._get_typename_from_die(die)
            encoding = DwarfEncoding(cast(int, die.attributes[Attrs.DW_AT_encoding].value))
            bytesize = self._get_size_from_type_die(die)
            basetype = self.get_core_base_type(encoding, bytesize)
            self._logger.debug(f"Registering base type: {name} as {basetype.name}")
            self._varmap.register_base_type(name, basetype)

            self._die2vartype_map[die] = basetype

    def _die_process_ptr_type(self, die: DIE) -> None:
        self._log_debug_process_die(die)
        if die not in self._die2vartype_map:
            address_size = self._get_size_from_pointer_die(die)
            typemap = {
                1: EmbeddedDataType.ptr8,
                2: EmbeddedDataType.ptr16,
                4: EmbeddedDataType.ptr32,
                8: EmbeddedDataType.ptr64,
                16: EmbeddedDataType.ptr128,
                32: EmbeddedDataType.ptr256,
            }
            if address_size not in typemap:
                raise ElfParsingError(f"Pointer with unsupported byte size {address_size}")
            self._die2vartype_map[die] = typemap[address_size]
            self._varmap.register_base_type(self._make_ptr_typename(address_size), typemap[address_size])

    def _die_process_enum(self, die: DIE) -> None:
        self._log_debug_process_die(die)

        name = self._read_enum_die_name(die)

        if die not in self._enum_die_map and name is not None:
            enum = EmbeddedEnum(name)

            for child in die.iter_children():
                if child.tag != Tags.DW_TAG_enumerator:
                    continue

                enumerator_name = self._get_die_name_no_none(child)
                if self._context.cu_compiler in [Compiler.TI_C28_CGT, Compiler.Tasking]:
                    # cl2000 embeds the full mangled path in the DW_AT_NAME attribute,
                    # ex :_ZN13FileNamespace14File3TestClass3BBBE = FileNamespace::File3TestClass::BBB
                    demangled_name = self._demangler.demangle(enumerator_name)
                    parts = self.split_demangled_name(demangled_name)
                    parts = self._post_process_splitted_demangled_name(parts)
                    enumerator_name = parts[-1]

                if Attrs.DW_AT_const_value in child.attributes:
                    value = cast(int, child.attributes[Attrs.DW_AT_const_value].value)
                    enum.add_value(name=enumerator_name, value=value)
                else:
                    self._logger.error('Enumerator without value')

            self._enum_die_map[die] = enum

    def _die_process_enum_only_type_and_make_name(self, enum_die: DIE) -> str:
        """With clang Dwarf V2, some enums may have no base type, so we try to deduce it from the properties on the enum"""
        enum = self._enum_die_map[enum_die]
        if Attrs.DW_AT_byte_size not in enum_die.attributes:
            raise ElfParsingError(f"Cannot determine enum size {enum_die}")
        bytesize = enum_die.attributes[Attrs.DW_AT_byte_size].value
        try:
            encoding = DwarfEncoding(cast(int, enum_die.attributes[Attrs.DW_AT_encoding].value))
        except Exception:
            encoding = DwarfEncoding.DW_ATE_signed if enum.has_signed_value() else DwarfEncoding.DW_ATE_unsigned
        basetype = self.get_core_base_type(encoding, bytesize)
        fakename = 'enum_default_'
        fakename += 's' if basetype.is_signed() else 'u'
        fakename += str(basetype.get_size_bit())
        self._varmap.register_base_type(fakename, basetype)
        return fakename

    def _die_process_variable(self,
                              die: DIE,
                              location: Optional[AbsoluteLocation] = None
                              ) -> None:
        """Process a variable die and insert a variable in the varmap object if it has an absolute address"""

        # Avoid fetching a location if already set (DW_AT_specification & DW_AT_abstract_origin)
        if location is None:
            location = self._get_location(die)

        if Attrs.DW_AT_specification in die.attributes:  # Defined somewhere else
            vardie = die.get_DIE_from_attribute(Attrs.DW_AT_specification)
            self._die_process_variable(vardie, location=location)  # Recursion
            return

        if Attrs.DW_AT_abstract_origin in die.attributes:  # Defined somewhere else
            vardie = die.get_DIE_from_attribute(Attrs.DW_AT_abstract_origin)
            self._die_process_variable(vardie, location=location)  # Recursion
            return

        if location is not None:
            type_desc = self._get_type_of_var(die)

            if type_desc.enum_die is not None:
                self._die_process_enum(type_desc.enum_die)

            # Composite type
            if type_desc.type in (TypeOfVar.Struct, TypeOfVar.Class, TypeOfVar.Union):
                struct = self._get_composite_type_def(type_desc.type_die, allow_dereferencing=self._allow_dereference_pointer)
                self._register_struct_var(die, struct, type_desc, location)
            elif type_desc.type == TypeOfVar.Array:
                array = self._get_array_def(type_desc.type_die, allow_dereferencing=self._allow_dereference_pointer)
                if array is not None:   # Incomplete arrays are possible in the debug symbols. Translate to "None" here.
                    self._register_array_var(die, array, type_desc, location)
            elif type_desc.type == TypeOfVar.Pointer:
                self._die_process_ptr_type(type_desc.type_die)
                varpath = self._make_varpath(die)
                path_segments = varpath.get_segments_name()

                was_added = self._maybe_register_variable(   # Register the pointer
                    path_segments=path_segments,
                    location=location,
                    original_type_name=self._get_pointer_name_from_die(type_desc.type_die)
                )

                dereference_pointer = self._allow_dereference_pointer

                if not was_added:
                    dereference_pointer = False
                # Try dereferencing the pointer
                if type_desc.pointee is None or type_desc.pointee.type == TypeOfVar.Void:
                    dereference_pointer = False

                if dereference_pointer:
                    assert type_desc.pointee is not None
                    pointee_typedesc = type_desc.pointee.to_typedesc()

                    pointer_path_segments = path_segments.copy()
                    pointer_path_segments[-1] = f'*{pointer_path_segments[-1]}'  # /aaa/bbb/*ccc : ccc is dereferenced
                    ptr_location = UnresolvedPathPointedLocation(
                        pointer_offset=0,
                        pointer_path=path_tools.join_segments(path_segments),
                        array_segments={}
                    )
                    if pointee_typedesc.type in (TypeOfVar.BaseType, TypeOfVar.EnumOnly):
                        # EnumOnly is for clang and dwarf v2.
                        typename = self._process_and_get_basetype_or_enumonly_typename(pointee_typedesc)
                        self._maybe_register_variable(
                            path_segments=pointer_path_segments,
                            location=ptr_location,
                            original_type_name=typename,
                            enum=self._get_enum_from_type_descriptor(pointee_typedesc)
                        )
                    elif pointee_typedesc.type in (TypeOfVar.Class, TypeOfVar.Struct, TypeOfVar.Union):
                        struct = self._get_composite_type_def(pointee_typedesc.type_die, allow_dereferencing=False)
                        self._register_struct_var(die, struct, pointee_typedesc, ptr_location)
                    elif pointee_typedesc.type in [TypeOfVar.Subroutine, TypeOfVar.Pointer]:
                        pass    # Ignore on purpose
                    else:
                        self._logger.warning(
                            f"Line {get_linenumber()}: Found a pointer to type die {self._make_name_for_log(pointee_typedesc.type_die)} (type={pointee_typedesc.type.name}). Not supported yet")

            # Base type
            elif type_desc.type in (TypeOfVar.BaseType, TypeOfVar.EnumOnly):
                varpath = self._make_varpath(die)
                path_segments = varpath.get_segments_name()
                typename = self._process_and_get_basetype_or_enumonly_typename(type_desc)
                self._maybe_register_variable(
                    path_segments=path_segments,
                    location=location,
                    original_type_name=typename,
                    enum=self._get_enum_from_type_descriptor(type_desc)
                )
            elif type_desc.type == TypeOfVar.Subroutine:
                self._logger.debug(f"Line {get_linenumber()}: Found a variable with a type {type_desc.type.name}. Ignored")
            else:
                self._logger.warning(
                    f"Line {get_linenumber()}: Found a variable with a type die {self._make_name_for_log(type_desc.type_die)} (type={type_desc.type.name}). Not supported yet")

    def _die_process_typedef(self, typedef_die: DIE) -> None:
        if Attrs.DW_AT_type in typedef_die.attributes:
            type_die = typedef_die.get_DIE_from_attribute(Attrs.DW_AT_type)
            # Any type that can be declared as anonymous
            if type_die.tag in (Tags.DW_TAG_class_type, Tags.DW_TAG_structure_type, Tags.DW_TAG_union_type, Tags.DW_TAG_enumeration_type):
                is_anonymous = self._get_die_name(type_die, no_tag_default=True) is None
                if is_anonymous:
                    self._anonymous_type_typedef_map[type_die] = typedef_die
# endregions

    def _read_enum_die_name(self, die: DIE) -> str:
        """Reads the name of the enum die. Handle name mangling and compiler quirks"""
        mangled_name: Optional[str] = None
        name = self._get_die_name(die, no_tag_default=True)

        if name is not None:
            if self._context.cu_compiler in [Compiler.TI_C28_CGT, Compiler.Tasking]:
                if Attrs.DW_AT_name in die.attributes:
                    # cl2000 embeds the full mangled path in the DW_AT_NAME attribute,
                    # ex : _ZN13FileNamespace14File3TestClass16File3EnumInClassE = FileNamespace::File3TestClass::File3EnumInClass
                    mangled_name = cast(str, die.attributes[Attrs.DW_AT_name].value.decode('ascii'))
        else:
            if Attrs.DW_AT_linkage_name in die.attributes:
                mangled_name = cast(str, die.attributes[Attrs.DW_AT_linkage_name].value.decode('ascii'))

        if mangled_name is not None:
            demangled_name = self._demangler.demangle(mangled_name)
            parts = self.split_demangled_name(demangled_name)
            parts = self._post_process_splitted_demangled_name(parts)
            name = parts[-1]

        if name is None:
            name = self._get_die_name_no_none(die)

        return name

    def _get_pointee_type_of_var(self, ptr_die: DIE) -> PointeeTypeDescriptor:
        """Does the same as _get_type_of_var, but for pointers. Return the type descriptor of the pointee.
        This can be a void type"""
        if Attrs.DW_AT_type not in ptr_die.attributes:
            pointee = PointeeTypeDescriptor(TypeOfVar.Void, None, None)
        else:
            pointee_typedesc = self._get_type_of_var(ptr_die)
            pointee = PointeeTypeDescriptor(
                type=pointee_typedesc.type,
                type_die=pointee_typedesc.type_die,
                enum_die=pointee_typedesc.enum_die
            )
        return pointee

    def _get_type_of_var(self, die: DIE) -> TypeDescriptor:
        """Go up the hiearchy to find the die that represent the type of the variable.
        For example : var -> const -> typedef -> volatile -> uint32.  Discard qualifiers and keeps just the "uint32" part

        """
        self._log_debug_process_die(die)
        prevdie = die
        enum: Optional[DIE] = None

        seen_dies: Set[DIE] = set()
        while True:
            try:
                nextdie = prevdie.get_DIE_from_attribute(Attrs.DW_AT_type)
            except KeyError as e:
                raise ElfParsingError(f"Cannot get the type of var. DIE {prevdie} has no attribute DW_AT_type")

            if nextdie in seen_dies:
                raise ElfParsingError(f"Circular type referenc for DIE {die}")
            seen_dies.add(nextdie)

            if nextdie.tag == Tags.DW_TAG_structure_type:
                return TypeDescriptor(TypeOfVar.Struct, enum, nextdie, None)
            elif nextdie.tag == Tags.DW_TAG_class_type:
                return TypeDescriptor(TypeOfVar.Class, enum, nextdie, None)
            elif nextdie.tag == Tags.DW_TAG_array_type:
                return TypeDescriptor(TypeOfVar.Array, enum, nextdie, None)
            elif nextdie.tag == Tags.DW_TAG_base_type:
                return TypeDescriptor(TypeOfVar.BaseType, enum, nextdie, None)
            elif nextdie.tag == Tags.DW_TAG_pointer_type:
                pointee = self._get_pointee_type_of_var(nextdie)
                return TypeDescriptor(TypeOfVar.Pointer, enum, nextdie, pointee)
            elif nextdie.tag == Tags.DW_TAG_union_type:
                return TypeDescriptor(TypeOfVar.Union, enum, nextdie, None)
            elif nextdie.tag == Tags.DW_TAG_subroutine_type:
                return TypeDescriptor(TypeOfVar.Subroutine, enum, nextdie, None)
            elif nextdie.tag == Tags.DW_TAG_unspecified_type:   # Can happen with pointer to void. Tasking uses this
                return TypeDescriptor(TypeOfVar.Void, enum, nextdie, None)
            elif nextdie.tag == Tags.DW_TAG_enumeration_type:
                enum = nextdie  # Will resolve on next iteration (if a type is available)
                if Attrs.DW_AT_type not in nextdie.attributes:  # Clang dwarfv2 may not have type, but has a byte size
                    if Attrs.DW_AT_byte_size in nextdie.attributes:
                        return TypeDescriptor(TypeOfVar.EnumOnly, enum, type_die=enum, pointee=None)
                    else:
                        raise ElfParsingError(f"Cannot find the enum underlying type {enum}")
            else:
                pass  # Keep going up the tree.

            prevdie = nextdie

    def _get_composite_type_def(self, die: DIE, allow_dereferencing: bool) -> Struct:
        """Reads a DIE of type Class / Struct or Union and return a Scrutiny Struct

        :param die: The DIE to read
        :param allow_dereferencing: Allow pointer dereferencing. Used to break circular referencing.
        """

        self._log_debug_process_die(die)

        cache_key = (die, allow_dereferencing)
        if cache_key in self._struct_die_cache_map:  # Cache hit
            return self._struct_die_cache_map[cache_key]

        # Cache miss
        if die.tag not in (Tags.DW_TAG_structure_type, Tags.DW_TAG_class_type, Tags.DW_TAG_union_type):
            raise ValueError('DIE must be a structure, class or union type')

        byte_size: Optional[int] = None

        if Attrs.DW_AT_byte_size in die.attributes:  # Can be absent on class with no size (no members, just methods)
            byte_size = int(die.attributes[Attrs.DW_AT_byte_size].value)

        struct = Struct(self._get_die_name_no_none(die), byte_size=byte_size)
        is_in_union = die.tag == Tags.DW_TAG_union_type

        # For each subdies of this struct/class/union. They should be members and inheritance
        for child in die.iter_children():
            if child.tag == Tags.DW_TAG_member:
                member = self._get_member_from_die(child, is_in_union, allow_dereferencing)
                if member is not None:
                    struct.add_member(member)
            elif child.tag == Tags.DW_TAG_inheritance:
                offset = 0
                if self._has_member_byte_offset(child):
                    offset = self._get_member_byte_offset(child)
                typedie = child.get_DIE_from_attribute(Attrs.DW_AT_type)
                if typedie.tag not in [Tags.DW_TAG_structure_type, Tags.DW_TAG_class_type]:   # Add union here?
                    self._logger.warning(f"Line {get_linenumber()}: Inheritance to a type die {self._make_name_for_log(typedie)}. Not supported yet")
                    continue
                parent_struct = self._get_composite_type_def(typedie, allow_dereferencing)
                struct.inherit(parent_struct, offset=offset)

        self._struct_die_cache_map[cache_key] = struct
        return struct

    def _get_array_def(self, die: DIE, allow_dereferencing: bool) -> Optional[TypedArray]:
        """Reads a DIE of type array and return a Scrutiny TypedArray object
        :param die: The DIE to read
        :param allow_dereferencing: Flag indicating if we shall dereference pointers in that array. Used to break circular referencing
        """
        self._log_debug_process_die(die)
        if die.tag != Tags.DW_TAG_array_type:
            raise ValueError('DIE must be an array')
        cache_key = (die, allow_dereferencing)
        if cache_key in self._array_die_cache_map:  # Cache hit
            return self._array_die_cache_map[cache_key]

        # Cache miss. We need to create it

        # Start by reading the array dimensions.
        subrange_dies: List[DIE] = []
        for child in die.iter_children():
            if child.tag == Tags.DW_TAG_subrange_type:
                subrange_dies.append(child)

        if len(subrange_dies) == 0:
            raise ElfParsingError(f"Found no subrange under array {die}")

        dims = []
        for subrange_die in subrange_dies:
            nb_element = 0
            if Attrs.DW_AT_count in subrange_die.attributes:
                nb_element = int(subrange_die.attributes[Attrs.DW_AT_count].value)
            elif Attrs.DW_AT_upper_bound in subrange_die.attributes:
                nb_element = int(subrange_die.attributes[Attrs.DW_AT_upper_bound].value) + 1
            else:
                self._logger.debug("Array with no dimension. Skipping")  # This can happen
                return None

            if Attrs.DW_AT_lower_bound in subrange_die.attributes:
                lower_bound = int(subrange_die.attributes[Attrs.DW_AT_lower_bound].value)
                if lower_bound != 0:
                    raise ElfParsingError(f"Array with lower bound that is not 0. {subrange_die}")

            dims.append(nb_element)
        # We have the dims!

        element_type = self._get_type_of_var(die)

        if element_type.enum_die is not None:   # May have a value only if element_type is a base type
            self._die_process_enum(element_type.enum_die)

        # For each type of element in the array, we handle differently.
        array_element_type: Union[Struct, EmbeddedDataType, Pointer]
        if element_type.type in (TypeOfVar.Class, TypeOfVar.Struct, TypeOfVar.Union):           # Array of composite type
            struct = self._get_composite_type_def(element_type.type_die, allow_dereferencing)   # Hopefully hit the cache
            if struct.byte_size is None:    # Structs are supposed to have a known size. It's important for array indexing
                raise ElfParsingError(f"Array of elements of unknown size: {die}")
            array_element_type = struct
            element_type_name = self._get_die_name_no_none(element_type.type_die)

        elif element_type.type in (TypeOfVar.BaseType, TypeOfVar.EnumOnly):  # Array of abse types
            element_type_name = self._process_and_get_basetype_or_enumonly_typename(element_type)
            array_element_type = self._varmap.get_vartype_from_base_type(element_type_name)

        elif element_type.type == TypeOfVar.Array:  # Array of array. Treat like bigger array.
            # Some compiler can have array of array for multidimensional array. Scrutiny treat as single array of dims of higher rank
            subarray = self._get_array_def(element_type.type_die, allow_dereferencing)
            if subarray is None:
                return None
            dims.extend(subarray.dims)
            element_type_name = subarray.element_type_name
            array_element_type = subarray.datatype
        elif element_type.type == TypeOfVar.Pointer:
            array_element_type = self._get_pointer_def(element_type.type_die, allow_dereferencing)
            element_type_name = self._get_pointer_name_from_die(element_type.type_die)
        else:
            # This can happen
            self._logger.warning(f"Line {get_linenumber()}: Array of element of type {element_type.type.name} not supported. Skipping")
            return None

        array_out = TypedArray(
            dims=tuple(dims),
            datatype=array_element_type,
            element_type_name=element_type_name
        )

        self._array_die_cache_map[cache_key] = array_out
        return array_out

    def _get_pointer_def(self, die: DIE, allow_dereferencing: bool) -> Pointer:
        """Reads a pointer DIE and return a Scrutiny pointer object.

        :param die: The pointer DIE to read
        :param allow_dereferencing: Allow reading the poiintee type. If ``False``, will act liek this is a void*
        """
        self._log_debug_process_die(die)
        if die.tag != Tags.DW_TAG_pointer_type:
            raise ValueError('DIE must be a pointer')

        self._die_process_ptr_type(die)
        ptr_size = self._get_size_from_pointer_die(die)
        VOID_PTR = Pointer(size=ptr_size, pointed_type=EmbeddedDataType.NA, pointed_typename=None, enum=None)
        if not allow_dereferencing:  # Pretend it's a void*. Breaks circular referencing if any
            return VOID_PTR
        pointee_typedesc = self._get_pointee_type_of_var(die)
        if pointee_typedesc.type == TypeOfVar.Void:  # It really is a void*
            return VOID_PTR
        assert pointee_typedesc.type_die is not None

        # Now we have a pointer to a type.
        if pointee_typedesc.type in (TypeOfVar.BaseType, TypeOfVar.EnumOnly):   # Pointer to base type
            pointed_typename = self._process_and_get_basetype_or_enumonly_typename(pointee_typedesc.to_typedesc())
            embedded_enum: Optional[EmbeddedEnum] = None
            if pointee_typedesc.enum_die is not None:
                self._die_process_enum(pointee_typedesc.enum_die)
                embedded_enum = self._enum_die_map[pointee_typedesc.enum_die]
            embedded_type = self._varmap.get_vartype_from_base_type(pointed_typename)   # Read back type from varmap
            return Pointer(size=ptr_size, pointed_type=embedded_type, pointed_typename=pointed_typename, enum=embedded_enum)
        elif pointee_typedesc.type in (TypeOfVar.Class, TypeOfVar.Struct, TypeOfVar.Union):
            struct = self._get_composite_type_def(pointee_typedesc.type_die, allow_dereferencing=False)  # Break dereferencing recursion
            return Pointer(size=ptr_size, pointed_type=struct, pointed_typename=None, enum=None)
        elif pointee_typedesc.type == TypeOfVar.Subroutine: # Nothing we can do with this.
            return VOID_PTR
        elif pointee_typedesc.type == TypeOfVar.Pointer:    # No double dereferencing.
            return VOID_PTR

        # We should not reach this.
        self._logger.warning(f"Pointer to a unsupported pointee. Cannot dereference. Pointee: {pointee_typedesc.type.name}")
        return Pointer(size=ptr_size, pointed_type=EmbeddedDataType.NA, pointed_typename=None, enum=None)

    def _get_member_from_die(self, die: DIE, is_in_union: bool, allow_dereferencing: bool) -> Optional[Struct.Member]:
        """Read a member die and generate a Struct.Member that we will later on use to register a variable.

        :param die: The DIE of type Member
        :param is_in_union: Flag indicating if that member is part of an union. We will use this to find the bitoffset and bitsize if this is a base type member
        :param allow_dereferencing: Allow dereferencing pointer member. Will read the pointee type if allowed, ignore otherwise. Used to prevent circular referencing

        """
        self._log_debug_process_die(die)

        name = self._get_die_name(die)
        if name is None:
            name = ''

        type_desc = self._get_type_of_var(die)
        embedded_enum: Optional[EmbeddedEnum] = None
        substruct: Optional[Struct] = None
        subarray: Optional[TypedArray] = None
        typename: Optional[str] = None
        pointer: Optional[Pointer] = None
        if type_desc.type in (TypeOfVar.Struct, TypeOfVar.Class, TypeOfVar.Union):
            # We recreate the definition instead of using a cached version.
            # Dereferencing state might produce different results
            substruct = self._get_composite_type_def(type_desc.type_die, allow_dereferencing)  # recursion
        elif type_desc.type in (TypeOfVar.BaseType, TypeOfVar.EnumOnly):
            if type_desc.enum_die is not None:
                self._die_process_enum(type_desc.enum_die)
                embedded_enum = self._enum_die_map[type_desc.enum_die]

            if type_desc.type == TypeOfVar.BaseType:
                self._die_process_base_type(type_desc.type_die)    # Just in case it is unknown yet
                typename = self._get_typename_from_die(type_desc.type_die)
            elif type_desc.type == TypeOfVar.EnumOnly:    # clang dwarf v2 may do that for enums
                assert type_desc.enum_die is type_desc.type_die
                typename = self._die_process_enum_only_type_and_make_name(type_desc.enum_die)
            else:
                raise ElfParsingError("Impossible to process base type")
        elif type_desc.type == TypeOfVar.Array:
            subarray = self._get_array_def(type_desc.type_die, allow_dereferencing)
            if subarray is None:    # Not available. Incomplete, no dimensions available
                return None
        elif type_desc.type == TypeOfVar.Pointer:
            pointer = self._get_pointer_def(type_desc.type_die, allow_dereferencing)
            typename = self._get_pointer_name_from_die(type_desc.type_die)
            embedded_enum = pointer.enum

        else:
            self._logger.warning(
                f"Line {get_linenumber()}: Found a member with a type die {self._make_name_for_log(type_desc.type_die)} (type={type_desc.type.name}). Not supported yet")
            return None

        if self._is_forward_declaration(die):    # We are looking at a forward declared member.
            return None

        if is_in_union:
            if self._has_member_byte_offset(die) and self._get_member_byte_offset(die) != 0:
                raise ElfParsingError("Encountered an union with a non-zero member location.")
            byte_offset = 0
        else:
            byte_offset = self._get_member_byte_offset(die)

        is_bitfield = Attrs.DW_AT_bit_offset in die.attributes or Attrs.DW_AT_bit_size in die.attributes

        bitoffset: Optional[int] = None
        bitsize: Optional[int] = None

        if is_bitfield:
            bytesize: Optional[int] = None

            if Attrs.DW_AT_byte_size in die.attributes:
                bytesize = int(die.attributes[Attrs.DW_AT_byte_size].value)
            elif type_desc.type in [TypeOfVar.BaseType, TypeOfVar.EnumOnly]:
                bytesize = self._get_size_from_type_die(type_desc.type_die)
            else:
                raise ElfParsingError(f'Cannot get byte size for bitfield {name}')

            if Attrs.DW_AT_bit_size not in die.attributes:
                raise ElfParsingError(f'Missing {Attrs.DW_AT_bit_size} for bitfield {name}')

            bitsize = int(die.attributes[Attrs.DW_AT_bit_size].value)

            if Attrs.DW_AT_bit_offset in die.attributes:
                bitoffset = int(die.attributes[Attrs.DW_AT_bit_offset].value)
            elif Attrs.DW_AT_data_bit_offset in die.attributes:
                bitoffset = int(die.attributes[Attrs.DW_AT_data_bit_offset].value)
            else:
                bitoffset = 0   # Dwarf V4 allow this.

            if self._context.endianess == Endianness.Little:
                bitoffset = (bytesize * 8) - bitoffset - bitsize

        member_type = Struct.Member.MemberType.BaseType
        if substruct is not None:
            member_type = Struct.Member.MemberType.SubStruct
        if subarray is not None:
            member_type = Struct.Member.MemberType.SubArray
        if pointer is not None:
            member_type = Struct.Member.MemberType.Pointer

        return Struct.Member(
            name=name,
            member_type=member_type,
            original_type_name=typename,
            byte_offset=byte_offset,
            bitoffset=bitoffset,
            bitsize=bitsize,
            substruct=substruct,
            subarray=subarray,
            pointer=pointer,
            embedded_enum=embedded_enum,
            is_unnamed=True if (len(name) == 0) else False
        )

    # We have an instance of a struct. Use the location and go down the structure recursively
    # using the members offsets to find the final address that we will apply to the output var
    def _register_struct_var(self, die: DIE, struct: Struct, type_desc: TypeDescriptor, location: Union[AbsoluteLocation, UnresolvedPathPointedLocation]) -> None:
        """Register an instance of a struct at a given location"""
        if isinstance(location, AbsoluteLocation) and location.is_null():
            self._logger.warning(f"Line {get_linenumber()}: Skipping structure {struct.name} at location NULL address.")
            self._logger.debug(f"{die}")
            return
        array_segments = ArraySegments()
        path_segments = self._make_varpath(die)  # Leftmost part.
        if isinstance(location, UnresolvedPathPointedLocation):
            path_segments.segments[-1].name = '*' + path_segments.segments[-1].name
        startpoint = Struct.Member(struct.name, member_type=Struct.Member.MemberType.SubStruct, bitoffset=None, bitsize=None, substruct=struct)

        # Start the recursion that will create all the sub elements
        self._register_member_as_var_recursive(path_segments.get_segments_name(), startpoint, location, offset=0, array_segments=array_segments)

    def _dereference_member_pointer(self,
                                    ptr: Pointer,
                                    path_segments: List[str],
                                    pointer_array_segments: ArraySegments,
                                    basic_type_enum: Optional[EmbeddedEnum] = None) -> None:
        """Common code to dereference struct member of type pointer or array of pointer. They are treated identically.
        :param ptr: The scrutiy Pointer object
        :param path_segments: The name segments gotten so far. They should go up to the pointer
        :param pointer_array_segments: The array segments that matches the name segments. they should stop at the pointer
        :param basic_type_enum: The enum in case we have a pointer to a base type. Leave None if non-applicable

        """
        dereferenced_array_segments = path_segments.copy()
        dereferenced_array_segments[-1] = f'*{dereferenced_array_segments[-1]}'  # /aaa/bbb/*ccc : ccc is dereferenced

        pointed_location = UnresolvedPathPointedLocation(
            pointer_offset=0,
            pointer_path=path_tools.join_segments(path_segments),
            array_segments=pointer_array_segments.to_varmap_format()
        )

        if isinstance(ptr.pointed_type, EmbeddedDataType):
            if ptr.pointed_type != EmbeddedDataType.NA:  # Void pointer
                assert ptr.pointed_typename is not None
                self._maybe_register_variable(
                    path_segments=dereferenced_array_segments,
                    location=pointed_location,
                    original_type_name=ptr.pointed_typename,
                    enum=basic_type_enum
                )
        elif isinstance(ptr.pointed_type, Struct):
            # mimic the behavior of _register_struct_var, without looking for a var die.
            pointed_startpoint = Struct.Member(
                name=ptr.pointed_type.name,
                member_type=Struct.Member.MemberType.SubStruct,
                bitoffset=None,
                bitsize=None,
                substruct=ptr.pointed_type
            )
            self._register_member_as_var_recursive(
                path_segments=dereferenced_array_segments,
                member=pointed_startpoint,
                base_location=pointed_location,
                offset=0,
                array_segments=ArraySegments()  # Fresh start, only pointer part has array so far
            )

    def _register_member_as_var_recursive(self,
                                          path_segments: List[str],
                                          member: Struct.Member,
                                          base_location: Union[AbsoluteLocation, UnresolvedPathPointedLocation],
                                          offset: int,
                                          array_segments: ArraySegments) -> None:
        """Recursive function that digs through structure member and create entries in the varmap
            :param path_segments: Path segements of the actual member
            :param member:  The actual member we are scanning
            :param base_location:   Location of the actual member
            :param offset:  Offset to apply tot he abse location
            :param array_segments:  Array segments matching the path segments so far
        """
        if member.member_type == Struct.Member.MemberType.SubStruct:
            assert member.substruct is not None
            struct = member.substruct
            # The actual member is a struct. For each submember, adjsut the path and location thenr ecurse
            for name, submember in struct.members.items():
                location = base_location.copy()
                new_path_segments = path_segments.copy()
                new_path_segments.append(name)

                if submember.member_type in (Struct.Member.MemberType.SubStruct, Struct.Member.MemberType.SubArray):
                    assert submember.byte_offset is not None
                    location.add_offset(submember.byte_offset)
                elif submember.byte_offset is not None:
                    offset = submember.byte_offset

                self._register_member_as_var_recursive(new_path_segments, submember, location, offset, array_segments)
        elif member.member_type == Struct.Member.MemberType.SubArray:
            array = member.get_array()
            # We group arrays element together.  /aaa/bbb/ccc/ccc[0].
            # Here, we start with /aaa/bbb/ccc and create /aaa/bbb/ccc/ccc with array on the last node
            path_segments.append(path_segments[-1])

            new_array_segments = array_segments.shallow_copy()
            new_array_segments.add(path_segments, array)
            if isinstance(array.datatype, EmbeddedDataType):
                # Array of base type. instantiate right away
                self._maybe_register_variable(
                    path_segments=path_segments,
                    original_type_name=array.element_type_name,
                    location=base_location,
                    array_segments=new_array_segments.to_varmap_format(),
                    enum=member.embedded_enum
                )
            elif isinstance(array.datatype, Struct):    # Array of struct/class/union
                # Start digging into the struct, with adjsuted path and array segments
                substruct = array.datatype
                member = Struct.Member(substruct.name, member_type=Struct.Member.MemberType.SubStruct,
                                       bitoffset=None, bitsize=None, substruct=substruct)
                self._register_member_as_var_recursive(path_segments, member, base_location, offset, new_array_segments)
            elif isinstance(array.datatype, Pointer):   # Array of pointers
                ptr = array.datatype
                was_added  = self._maybe_register_variable(
                    path_segments=path_segments,
                    original_type_name=array.element_type_name,
                    location=base_location,
                    array_segments=new_array_segments.to_varmap_format()
                )

                dereference = self._allow_dereference_pointer
                if not was_added:
                    dereference = False

                if dereference and isinstance(base_location, AbsoluteLocation):  # Only dereference one level. By design
                    self._dereference_member_pointer(   # Common code for pointers and array of pointers
                        ptr=ptr,
                        path_segments=path_segments,
                        pointer_array_segments=new_array_segments,
                        basic_type_enum=ptr.enum  # Will be None if this is a ptr to struct or other.
                    )
            else:
                raise ElfParsingError(f"Array of {array.datatype.__class__.__name__} are not expected")

        elif member.member_type == Struct.Member.MemberType.Pointer:
            location = base_location.copy()
            assert member.byte_offset is not None
            location.add_offset(member.byte_offset)
            ptr = member.get_pointer()

            was_added = self._maybe_register_variable(  # Create the pointer entry first
                path_segments=path_segments,
                original_type_name=self._make_ptr_typename(ptr.get_size()),
                location=location,
                bitoffset=member.bitoffset,
                bitsize=member.bitsize,
                array_segments=array_segments.to_varmap_format()
            )

            dereference = self._allow_dereference_pointer
            if not was_added:
                dereference = False

            # Dereference the pointer
            if dereference and isinstance(location, AbsoluteLocation):  # Only dereference one level. By design
                self._dereference_member_pointer(    # Common code for pointers and array of pointers
                    ptr=ptr,
                    path_segments=path_segments,
                    pointer_array_segments=array_segments,
                    basic_type_enum=ptr.enum  # Will be None if this is a ptr to struct or other.
                )

        elif member.member_type == Struct.Member.MemberType.BaseType:
            location = base_location.copy()
            assert member.byte_offset is not None
            assert member.original_type_name is not None
            location.add_offset(member.byte_offset)

            self._maybe_register_variable(
                path_segments=path_segments,
                original_type_name=member.original_type_name,
                location=location,
                bitoffset=member.bitoffset,
                bitsize=member.bitsize,
                array_segments=array_segments.to_varmap_format(),
                enum=member.embedded_enum
            )
        else:
            raise ElfParsingError(f"Unexpected struct member type {member.member_type} for member {member.name}")

    def _register_array_var(self, die: DIE, array: TypedArray, type_desc: TypeDescriptor, location: AbsoluteLocation) -> None:
        """Takes a variable of type Array and create an entry in the varmap.

            :param die: The variable DIE of type array
            :param array: The Scrutiny array that we built from the type die.
            :param type_desc: The type descriptor of the var die.
            :param location: The location of that die array.
        """

        if location.is_null():  # Ignore nullptr
            name = self._get_die_name(die, default="<no-name>")
            self._logger.warning(f"Line {get_linenumber()}: Skipping array {name} at location NULL address.")
            self._logger.debug(f"{die}")
            return

        # Analyze its path name
        varpath = self._make_varpath(die)
        path_segments_name = varpath.get_segments_name()
        array_segments = varpath.get_array_segments()

        if isinstance(array.datatype, EmbeddedDataType):    # Array of base types
            self._maybe_register_variable(
                path_segments=path_segments_name,
                location=location,
                original_type_name=array.element_type_name,
                enum=self._get_enum_from_type_descriptor(type_desc),
                array_segments=array_segments.to_varmap_format()
            )

        elif isinstance(array.datatype, Struct):    # Array of struct
            path_segments = varpath.get_segments_name()  # Leftmost part.
            struct = array.datatype
            startpoint = Struct.Member(struct.name, member_type=Struct.Member.MemberType.SubStruct, bitoffset=None, bitsize=None, substruct=struct)

            # Start the recursion that will create all the sub elements
            self._register_member_as_var_recursive(path_segments, startpoint, location, offset=0, array_segments=array_segments)

        elif isinstance(array.datatype, Pointer):   # Array of pointers
            was_added = self._maybe_register_variable(  # First regsiter the pointer variable.
                path_segments=path_segments_name,
                location=location,
                original_type_name=array.element_type_name,
                enum=None,
                array_segments=array_segments.to_varmap_format()
            )

            dereference = self._allow_dereference_pointer

            if not was_added:
                dereference = False

            # Then try to dereference
            if dereference and isinstance(location, AbsoluteLocation):
                pointed_location = UnresolvedPathPointedLocation(
                    pointer_offset=0,
                    pointer_path=path_tools.join_segments(path_segments_name),
                    array_segments=array_segments.to_varmap_format()
                )

                array_segments.clear()  # We start a new array segments struct for the dereferenced elements
                pointer_path_segments = path_segments_name.copy()
                pointer_path_segments[-1] = f'*{pointer_path_segments[-1]}'  # /aaa/bbb/*ccc : ccc is dereferenced

                if isinstance(array.datatype.pointed_type, EmbeddedDataType):   # uint32_t* my_array[10][20]
                    if array.datatype.pointed_type != EmbeddedDataType.NA:  # Ignore void pointers. we can't dereference them
                        assert array.datatype.pointed_typename is not None
                        self._maybe_register_variable(
                            path_segments=pointer_path_segments,
                            location=pointed_location,
                            original_type_name=array.datatype.pointed_typename,
                            enum=array.datatype.enum,
                            array_segments=array_segments.to_varmap_format()
                        )
                else:
                    # Do nothing on purpose
                    # Structs will fill array_segments
                    # pointer_array_segments will stay untouched
                    pass

        else:
            raise ElfParsingError(f"Array of {array.datatype.__class__.__name__} are not expected")

    def _maybe_register_variable(self,
                                 path_segments: List[str],
                                 location: Union[AbsoluteLocation, UnresolvedPathPointedLocation],
                                 original_type_name: str,
                                 bitsize: Optional[int] = None,
                                 bitoffset: Optional[int] = None,
                                 enum: Optional[EmbeddedEnum] = None,
                                 array_segments: Optional[Dict[str, Array]] = None
                                 ) -> bool:
        """Adds a variable to the varmap if it satisfies the filters provided by the users.

            :param path_segments: List of str representing each level of display tree
            :param location: The address of the variable
            :param original_type_name: The name of the underlying type. Must be a name coming from the binary. Will resolve to an EmbeddedDataType
            :param enum: Optional enum to associate with the type
        """
        fullname = path_tools.join_segments(path_segments)
        if isinstance(location, AbsoluteLocation):
            if location.is_null():
                self._logger.warning(f"Line {get_linenumber()}: Skipping variable {fullname} at location NULL address.")
                return False

        if self._allowed_by_filters(fullname):
            self._varmap.add_variable(
                path_segments=path_segments,
                location=location,
                original_type_name=original_type_name,
                bitsize=bitsize,
                bitoffset=bitoffset,
                enum=enum,
                array_segments=array_segments,
            )
            return True
        return False

    def _process_and_get_basetype_or_enumonly_typename(self, type_desc: TypeDescriptor) -> str:
        """Get the firmware type name of a TypeDescriptor for registering to the varmap.
        Will pass the type die into its specific process() function too.

        Handle real base type + Clang anonymous enums"""
        if type_desc.type == TypeOfVar.BaseType:   # Most common case
            self._die_process_base_type(type_desc.type_die)    # Just in case it is unknown yet
            typename = self._get_typename_from_die(type_desc.type_die)
        elif type_desc.type == TypeOfVar.EnumOnly:    # clang dwarf v2 may do that for enums
            assert type_desc.enum_die is type_desc.type_die
            assert type_desc.enum_die is not None
            typename = self._die_process_enum_only_type_and_make_name(type_desc.enum_die)
        else:
            raise ElfParsingError("Impossible to process base type")
        return typename

    def _make_varpath_recursive(self, die: DIE, varpath: Optional[VarPath] = None) -> VarPath:
        """Start from a variable DIE and go up the DWARF structure to build a path"""

        if varpath is None:
            varpath = VarPath()

        if die.tag == Tags.DW_TAG_compile_unit:  # Top level reached, we're done
            return varpath

        array: Optional[TypedArray] = None
        if die.tag == Tags.DW_TAG_variable:
            var_typedesc = self._get_type_of_var(die)
            if var_typedesc.type == TypeOfVar.Array:
                array = self._get_array_def(var_typedesc.type_die, allow_dereferencing=True)

        # Check if we have a linkage name. Those are complete and no further scan is required if available.
        name = self._get_demangled_linkage_name(die)
        if name is not None:
            parts = self.split_demangled_name(name)
            parts = self._post_process_splitted_demangled_name(parts)
            for i in range(len(parts) - 1, -1, -1):   # Need to prepend in reverse order to keep the order correct.
                if array is not None and i == len(parts) - 1:
                    varpath.prepend_segment(name=parts[i], array=array)
                    varpath.prepend_segment(name=parts[i])   # Add a level to group the array elements togethers /aaa/bbb/ccc/ccc[0]
                else:
                    varpath.prepend_segment(name=parts[i])
            return varpath

        # Try to get the name of the die and use it as a level of the path
        name = self._get_die_name(die)
        if name is None:
            if Attrs.DW_AT_specification in die.attributes:
                spec_die = die.get_DIE_from_attribute(Attrs.DW_AT_specification)
                name = self._get_die_name(spec_die)

        # There is a name available, we add it to the path and keep going
        if name is not None:
            varpath.prepend_segment(name=name, array=array)
            if array is not None:
                varpath.prepend_segment(name=name)  # Add a level to group the array elements togethers /aaa/bbb/ccc/ccc[0]
            parent = die.get_parent()
            if parent is not None:
                return self._make_varpath_recursive(parent, varpath)

        # Nothing available here. We're done
        return varpath

    def _make_varpath(self, die: DIE) -> VarPath:
        """Generate the display path for a die, either from the hierarchy or the linkage name"""
        varpath = self._make_varpath_recursive(die)  # Stops at the compile unit (without including it)

        if self._is_external(die):
            varpath.prepend_segment(self.GLOBAL)
        else:
            varpath.prepend_segment(self._get_cu_name(die))
            varpath.prepend_segment(self.STATIC)

        return varpath

    # endregion
