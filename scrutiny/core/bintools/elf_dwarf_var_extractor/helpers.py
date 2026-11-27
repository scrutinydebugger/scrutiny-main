__all__ = [
    'ElfParsingError', 
    'get_core_base_type', 
    'PointeeTypeDescriptor', 
    'TypeDescriptor', 
    'VarPathSegment', 
    'ArraySegments', 
    'VarPath', 
    'CuName', 
    'Context',
    'split_path_crossplatform',
    'make_unique_display_name',
    'is_external',
    'identify_compiler',
    'identify_endianness',
    'get_typename_from_die',
    'get_size_from_type_die',
    'has_member_byte_offset',
    'get_member_byte_offset',
    'is_forward_declaration',
    'make_ptr_typename',
    'is_supported_base_type',
    'find_parent_die_of_type',
]

from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from elftools.dwarf.die import DIE
from elftools.dwarf.compileunit import CompileUnit
from elftools.elf.elffile import ELFFile

from scrutiny.core.bintools.demangler import BaseDemangler
from scrutiny.core.basic_types import *
from scrutiny.core.array import TypedArray, Array
from scrutiny.core import path_tools
from scrutiny.core.embedded_enum import *
from scrutiny import tools
from scrutiny.tools.sorted_set import SortedSet

from scrutiny.core.bintools.elf_dwarf_var_extractor.definitions import Attrs, Tags, DwarfEncoding, TypeOfVar, Architecture, Compiler
from scrutiny.tools.typing import *

MAX_CU_DISPLAY_NAME_LENGTH = 64
DW_OP_plus_uconst = 0x23

class ElfParsingError(Exception):
    pass

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
        1: EmbeddedDataType.bool8,
        2: EmbeddedDataType.bool16,
        4: EmbeddedDataType.bool32,
        8: EmbeddedDataType.bool64
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
        1: EmbeddedDataType.uint8,
        2: EmbeddedDataType.uint16,
        4: EmbeddedDataType.uint32,
        8: EmbeddedDataType.uint64,
    }
}

def get_core_base_type(encoding: DwarfEncoding, bytesize: int, char_bit: Literal[8, 16]) -> EmbeddedDataType:
    """Convert a DWARF encoding into a Scrutiny EmbeddedDataType"""
    if encoding not in ENCODING_2_DTYPE_MAP:
        raise ValueError(f'Unknown encoding {encoding}')

    eight_bit_size = bytesize * (char_bit // 8)
    if eight_bit_size not in ENCODING_2_DTYPE_MAP[encoding]:
        raise ValueError(f'Encoding {encoding} with {eight_bit_size} 8bits bytes')

    return ENCODING_2_DTYPE_MAP[encoding][eight_bit_size]

def split_path_crossplatform(fullpath: str) -> Tuple[str, List[str]]:
    is_windows_path = (
        (len(fullpath) >= 3 and fullpath[1] == ':' and fullpath[2] in '/\\')  # drive letter: C:\ or C:/
        or fullpath.startswith('\\\\')   # UNC: \\server\share
        or '\\' in fullpath              # any backslash
    )
    p = PureWindowsPath(fullpath) if is_windows_path else PurePosixPath(fullpath)
    filename = p.name
    parts: List[str] = list(p.parent.parts)
    if parts and parts[0] == p.anchor:
        parts[0] = ''
    return filename, parts

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
    die: Optional[DIE] = None
    """The die that created that segments None if unavailable."""

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
        """Return a dictionary that gives the array information in the format required by the VarMap class"""
        # We use the same format here. Just future proofing the code.
        return {
            path: arr.to_untyped_array() for path, arr in self._storage.items()    # Make a copy
        }

    def shallow_copy(self) -> "ArraySegments":
        """Create a shallow copy of the storage. Returns a new dict that points to the same arrays"""
        o = ArraySegments()
        o._storage = self._storage.copy()
        return o

    def clear(self) -> None:
        """Clear the storage"""
        self._storage.clear()

class VarPath:
    """Represent a path of a variable. This class exists to edit efficiently the path with meaningful methods.
    To be used while constructing the path"""

    __slots__ = ('segments', )

    segments: List[VarPathSegment]
    """The segments of the path. Each element contains a string and array information that goes with that segment"""

    def __init__(self) -> None:
        self.segments = []

    def prepend_segment(self, name: str, array: Optional[TypedArray] = None, die:Optional[DIE]=None) -> None:
        """Add a path segment at the beginning"""
        self.segments.insert(0, VarPathSegment(name=name, array=array, die=die))

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
    """the full path of the compile unit gotten from the dwarf symbol"""
    _filename: str
    """The basename of ``_fullpath``"""
    _display_name: str
    """The name displayed to the user. Subsection of the fullpath"""
    _segments: List[str]
    """The fullpath broken down in string segments"""
    _numbered_name: Optional[str]
    """A numbered name autogenerated to overcome name collisions"""

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
        self._filename, self._segments = split_path_crossplatform(fullpath)
        self._display_name = self._filename
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
        We can generate a numbered name if there are collisions with the source file naming"""
        i = 0
        while True:
            candidate = 'cu%d_%s' % (i, self._filename)
            if candidate not in name_set:
                self._numbered_name = candidate
                return
            i += 1

@dataclass(slots=True)
class Context:
    """The context object that contains the parsing parameters. These are globals when parsing"""
    arch: Architecture
    """The architecture the target the file is compiled for"""
    endianess: Endianness
    """The endianness of the firmware"""
    cu_compiler: Compiler
    """The compiler of the actual CompileUnit"""
    address_size: Optional[int]
    """The size of a pointer. Sometimes available at the CU level, sometimes on the var itself. Acts as a fallback when not specified on a var"""

    def get_char_bit(self) -> Literal[8, 16]:
        if self.arch == Architecture.TI_C28x:
            return 16
        return 8

    def get_demangle_format(self) -> BaseDemangler.Format:
        if self.cu_compiler == Compiler.RUSTC:
            return BaseDemangler.Format.Rust
        return BaseDemangler.Format.GnuV3    


def make_unique_display_name(fullpath_list: List[str]) -> Dict[str, str]:
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
                if len(cuname.get_display_name()) > MAX_CU_DISPLAY_NAME_LENGTH:
                    raise ElfParsingError('Name too long')
            except Exception:
                # Does not affect the given set.
                # Only mark the Compile Unit as using a numbered name.
                # This numbered name will be consumed on next loop iteration.
                cuname.make_unique_numbered_name(display_name_set)

    return outmap


def is_external(die: DIE) -> bool:
    """Tells if the die is accessible from outside the compile unit. If it is, it's global, otherwise it's static."""
    try:
        return bool(die.attributes[Attrs.DW_AT_external].value)
    except Exception:
        return False


def identify_compiler(cu: CompileUnit) -> Compiler:
    """Identify what compiler produced a compile unit. We can handle their little quirks"""
    cu_die = cu.get_top_DIE()
    if cu_die.tag != Tags.DW_TAG_compile_unit:
        return Compiler.UNKNOWN

    if Attrs.DW_AT_producer in cu_die.attributes:
        producer = str(cu_die.attributes[Attrs.DW_AT_producer].value).strip().lower()
        if 'ti' in producer and 'c2000' in producer:
            return Compiler.TI_C28_CGT
        if 'rustc' in producer:
            return Compiler.RUSTC
        if 'clang' in producer:
            return Compiler.CLANG
        if 'gnu' in producer:
            return Compiler.GCC
        if 'tasking' in producer:
            return Compiler.Tasking
        if 'IAR ANSI C/C++ Compiler'.lower() in producer:
            return Compiler.IAR_ICC

    return Compiler.UNKNOWN


def identify_endianness(elffile: ELFFile) -> Endianness:
    """Identify the endianness. Based on the elffile"""
    # The endianness of an ELF file should match the target architecture in 99.99% of cases.

    if elffile.little_endian:
        return Endianness.Little
    else:
        return Endianness.Big


def get_typename_from_die(die: DIE) -> str:
    """Reads the name out of a base type DIE"""
    if die.tag == Tags.DW_TAG_base_type:
        return cast(bytes, die.attributes[Attrs.DW_AT_name].value).decode('ascii')
    raise ElfParsingError(f"Cannot extract type name from die {die}")


def get_size_from_type_die(die: DIE) -> int:
    """Return the size in multiple of 8 bits bytes of a given type DIE"""
    if Attrs.DW_AT_byte_size not in die.attributes:
        raise ElfParsingError(f'Missing DW_AT_byte_size on type die {die}')
    val = cast(int, die.attributes[Attrs.DW_AT_byte_size].value)

    return val


def has_member_byte_offset(die: DIE) -> bool:
    """Tells if an offset relative to the structure base is available on this member die"""
    return Attrs.DW_AT_data_member_location in die.attributes


def get_member_byte_offset(die: DIE) -> int:
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

        if val[0] != DW_OP_plus_uconst:
            raise ElfParsingError(f"Does not know how to read member location for die {die}. Operator is unsupported")

        return tools.uleb128_decode(bytes(val[1:]))

    raise ElfParsingError(f"Does not know how to read member location for die {die}")


def is_forward_declaration(die: DIE) -> bool:
    return Attrs.DW_AT_declaration in die.attributes and bool(die.attributes[Attrs.DW_AT_declaration].value) == True


def make_ptr_typename(bytesize: int) -> str:
    return f'ptr{bytesize * 8}'


def is_supported_base_type(die:DIE) -> bool:
    try:
        bytesize = get_size_from_type_die(die)
    except ElfParsingError:
        return False

    if bytesize == 0:   # IAR can do that with void*
        return False
    return True


def find_parent_die_of_type(die: DIE, tag: str) -> Optional[DIE]:

    parent = die.get_parent()
    if parent is None:
        return None
    else:
        if die.tag == tag:
            return die
        else:
            return find_parent_die_of_type(parent, tag)
