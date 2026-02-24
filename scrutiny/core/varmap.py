#    varmap.py
#        A VarMap list all variables in a firmware file along with their types, address, bit
#        offset, etc
#        . It is a simplified version of the DWARF debugging symbols.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

__all__ = ['VarMap']

import json
import enum
import logging
from pathlib import Path

from scrutiny.core.variable import Variable, VariableLayout
from scrutiny.core.variable_location import AbsoluteLocation, ResolvedPathPointedLocation, UnresolvedPathPointedLocation
from scrutiny.core.variable_factory import VariableFactory
from scrutiny.core.array import Array, UntypedArray
from scrutiny.core.basic_types import EmbeddedDataType, Endianness
from scrutiny.core.embedded_enum import EmbeddedEnum, EmbeddedEnumDef
from scrutiny.core.scrutiny_path import ScrutinyPath
from scrutiny.core import path_tools
from scrutiny.tools.typing import *
from scrutiny.tools import validation


class TypeEntry(TypedDict):
    """Representation of type description in the VarMap storage"""

    name: str
    """Original type name as it appears in the binary's debug information"""
    type: str
    """Scrutiny ``EmbeddedDataType`` name associated with this type"""


class ArrayDef(TypedDict):
    """Representation of an array in the VarMap storage"""

    dims: List[int]
    """List of sizes for each dimension of the array"""
    byte_size: int
    """Size in bytes of a single array element"""


class PointerInfo(TypedDict, total=False):
    """Representation of a pointer in the VarMap storage"""

    path: str
    """Path to the pointer variable in the variable map"""
    offset: int
    """Byte offset applied after pointer dereferencing to reach the target variable"""
    array_segments: Dict[str, ArrayDef]
    """Array segment definitions for the pointer path, keyed by sub-path string"""


class VariableEntry(TypedDict, total=False):
    """Representation of a variable in the VarMap storage"""

    type_id: str
    """Numeric type ID encoded as a string (required by JSON, which only allows string keys)"""
    addr: int
    """Absolute address of the variable in embedded memory. Can be omitted if a pointer is available"""
    bitoffset: int
    """Optional Bit-level offset within the byte, used for bit-field variables"""
    bitsize: int
    """Optional Size in bits for bit-field variables"""
    enum: int
    """Optional ID of the ``EmbeddedEnum`` associated with this variable"""
    array_segments: Dict[str, ArrayDef]
    """Optional Array segment definitions for variables that are elements of an array, keyed by sub-path"""
    pointer: PointerInfo
    """Pointer location information, present when the variable is accessed through a pointer. Can be omitted if an absolute address is available"""


VariableDict: TypeAlias = Dict[str, VariableEntry]


class VarMap:
    """Variable map listing all variables in a firmware binary along with their types, addresses,
    bit offsets, array layouts, and pointer information.

    It is a simplified, serializable representation of DWARF debugging symbols, stored as JSON.
    """

    class LocationType(enum.Enum):
        """Discriminant for the kind of memory location a variable occupies"""

        ABSOLUTE = enum.auto()
        POINTED = enum.auto()

    class SerializableContentDict(TypedDict):
        """Typed dictionary representing the JSON-serializable form of a ``VarMap``"""

        endianness: str
        """Endianness string (e.g. ``'little'`` or ``'big'``)"""
        type_map: Dict[str, TypeEntry]
        """Mapping of type ID strings to ``TypeEntry`` records"""
        variables: VariableDict
        """Mapping of full variable path strings to ``VariableEntry`` records"""
        enums: Dict[str, EmbeddedEnumDef]
        """Mapping of enum ID strings to ``EmbeddedEnumDef`` records"""

    class SerializableContent:
        """Mutable container holding the in-memory representation of a ``VarMap``'s data,
        with helpers for serialization and deserialization"""

        __slots__ = ('endianness', 'typemap', 'variables', 'enums')
        endianness: Endianness
        """Target device endianness"""
        typemap: Dict[str, TypeEntry]
        """Mapping of type ID strings to ``TypeEntry`` records"""
        variables: VariableDict
        """Mapping of full variable path strings to ``VariableEntry`` records"""
        enums: Dict[str, EmbeddedEnumDef]
        """Mapping of enum ID strings to ``EmbeddedEnumDef`` records"""

        def __init__(self) -> None:
            self.endianness = Endianness.Little
            self.typemap = {}
            self.variables = {}
            self.enums = {}

        def to_dict(self) -> "VarMap.SerializableContentDict":
            """Serialize this content object to a JSON-compatible dictionary"""
            return {
                'endianness': self.endianness.to_str(),
                'type_map': self.typemap,
                'variables': self.variables,
                'enums': self.enums,
            }

        def load_dict(self, d: "VarMap.SerializableContentDict") -> None:
            """Populate this content object from a JSON-compatible dictionary.

            :param d: Dictionary in ``SerializableContentDict`` format.
            :raises KeyError: If any required key is missing from ``d``.
            """
            validation.assert_dict_key(d, 'endianness', str)
            validation.assert_dict_key(d, 'type_map', dict)
            validation.assert_dict_key(d, 'variables', dict)
            validation.assert_dict_key(d, 'enums', dict)

            self.endianness = Endianness.from_str(d['endianness'])
            self.typemap = d['type_map']
            self.enums = d['enums']
            self.variables = d['variables']

    _logger: logging.Logger
    """Logger for this class"""
    _content: SerializableContent
    """In-memory representation of the variable map's serializable content"""
    _next_type_id: int
    """Counter used to generate unique numeric type IDs"""
    _next_enum_id: int
    """Counter used to generate unique numeric enum IDs"""
    _typename2typeid_map: Dict[str, str]
    """Mapping from original binary type name to the string-encoded numeric type ID"""
    _enums_to_id_map: Dict[EmbeddedEnum, int]
    """Mapping from ``EmbeddedEnum`` instances to their integer IDs in ``_content.enums``"""

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._content = self.SerializableContent()
        self._build_content_indexes()   # Initialize all the index variables.

    @classmethod
    def from_file(cls, filename: Union[Path, str]) -> Self:
        """Construct a ``VarMap`` by loading and parsing a JSON file on disk.

        :param filename: Path to the JSON file to read.
        """
        varmap = cls()
        with open(filename, 'r') as f:
            content = json.loads(f.read())
        varmap.load_dict(content)
        return varmap

    @classmethod
    def from_file_content(cls, data: bytes) -> Self:
        """Construct a ``VarMap`` from raw bytes containing UTF-8-encoded JSON content.

        :param data: Raw bytes of the JSON-encoded variable map.
        """
        return cls.from_json(data.decode('utf8'))

    @classmethod
    def from_json(cls, data: str) -> Self:
        """Construct a ``VarMap`` from a JSON-encoded string.

        :param data: JSON string representing the variable map.
        """
        varmap = cls()
        content = json.loads(data)
        varmap.load_dict(content)
        return varmap

    def load_dict(self, content: Dict[str, Any]) -> None:
        """Populate the variable map from a plain dictionary (e.g. parsed from JSON).

        :param content: Dictionary in ``SerializableContentDict`` format.
        """
        self._content.load_dict(cast(VarMap.SerializableContentDict, content))
        self._build_content_indexes()

    def _build_content_indexes(self) -> None:
        """Rebuild all internal index structures from the current ``_content``.

        Resets and recomputes ``_next_type_id``, ``_next_enum_id``,
        ``_typename2typeid_map``, and ``_enums_to_id_map``.
        """
        self._next_type_id = 0
        self._next_enum_id = 0
        self._typename2typeid_map = {}   # Maps the type id of this VarMap to the original name inside the binary.
        self._enums_to_id_map = {}       # Maps a EmbeddedEnum object to it's internal id

        # Build _typename2typeid_map
        for typeid_str in self._content.typemap:
            typeid_int = int(typeid_str)
            if typeid_int >= self._next_type_id:
                self._next_type_id = typeid_int + 1

            typename = self._content.typemap[str(typeid_int)]['name']
            self._typename2typeid_map[typename] = typeid_str

        # Build _enums_to_id_map
        for enum_id_str in self._content.enums:
            enum_id_int = int(enum_id_str)
            if enum_id_int >= self._next_enum_id:
                self._next_enum_id = enum_id_int + 1

            enum = EmbeddedEnum.from_def(self._content.enums[str(enum_id_int)])
            self._enums_to_id_map[enum] = enum_id_int

    def _get_type_id(self, binary_type_name: str) -> str:
        """Return the string-encoded numeric type ID for the given original binary type name.

        :param binary_type_name: Original type name as registered in the type map.
        :raises ValueError: If ``binary_type_name`` is not in the type map.
        """
        if binary_type_name not in self._typename2typeid_map:
            raise ValueError(f'Type name {binary_type_name} does not exist in the Variable Map')

        return self._typename2typeid_map[binary_type_name]   # Type is an integer as string

    def _get_type(self, vardef: VariableEntry) -> EmbeddedDataType:
        """Return the ``EmbeddedDataType`` for the given variable entry.

        :param vardef: Variable entry whose type is to be resolved.
        :raises KeyError: If the entry's ``type_id`` is not found in the type map.
        """
        type_id = str(vardef['type_id'])    # type_id is a required field
        if type_id not in self._content.typemap:
            raise KeyError(f'Type "{type_id}" refer to a type not in type map')
        typename = self._content.typemap[type_id]['type']
        return EmbeddedDataType[typename]  # Enums support square brackets

    @classmethod
    def _has_addr(cls, vardef: VariableEntry) -> bool:
        """Return ``True`` if the variable entry has an absolute address field.

        :param vardef: Variable entry to inspect.
        """
        return 'addr' in vardef

    @classmethod
    def _has_pointed_location(cls, vardef: VariableEntry) -> bool:
        """Return ``True`` if the variable entry has a pointer-based location field.

        :param vardef: Variable entry to inspect.
        """
        return 'pointer' in vardef

    @classmethod
    def _get_addr(cls, vardef: VariableEntry) -> int:
        """Return the absolute address from the variable entry. Performs no availability check

        :param vardef: Variable entry containing an ``addr`` field.
        """
        return vardef['addr']   # addr is a required field

    @classmethod
    def _get_pointer_path(cls, vardef: VariableEntry) -> str:
        """Return the pointer path string from the variable entry. Performs no availability check

        :param vardef: Variable entry containing a ``pointer`` field.
        """
        return vardef['pointer']['path']

    @classmethod
    def _get_pointer_offset(cls, vardef: VariableEntry) -> int:
        """Return the pointer byte offset from the variable entry. Performs no availability check

        :param vardef: Variable entry containing a ``pointer`` field.
        """
        return vardef['pointer']['offset']

    @classmethod
    def _has_pointer_array_segments(cls, vardef: VariableEntry) -> bool:
        """Return ``True`` if the variable entry has non-empty array segments for its pointer path.

        :param vardef: Variable entry to inspect.
        """
        if 'pointer' not in vardef:
            return False
        return 'array_segments' in vardef['pointer'] and len(vardef['pointer']['array_segments']) > 0

    @classmethod
    def _get_pointer_array_segments(cls, vardef: VariableEntry) -> Dict[str, ArrayDef]:
        """Return the pointer array segments dict from the variable entry. Performs no availability check

        :param vardef: Variable entry containing a ``pointer.array_segments`` field.
        """
        return vardef['pointer']['array_segments']

    @classmethod
    def _has_array_segments(cls, vardef: VariableEntry) -> bool:
        """Return ``True`` if the variable entry has an ``array_segments`` field.

        :param vardef: Variable entry to inspect.
        """
        return 'array_segments' in vardef

    @classmethod
    def _array_segments_to_untyped_array(cls, array_segments: Dict[str, ArrayDef]) -> Dict[str, UntypedArray]:
        """Convert an ``ArrayDef`` dict to a dict of ``UntypedArray`` instances.

        :param array_segments: Mapping of sub-path strings to ``ArrayDef`` records.
        :returns: Mapping of sub-path strings to ``UntypedArray`` instances.
        """
        dout: Dict[str, UntypedArray] = {}
        for path, array_def in array_segments.items():
            dout[path] = UntypedArray(
                dims=tuple(array_def['dims']),
                element_type_name='',
                element_byte_size=array_def['byte_size']
            )
        return dout

    def _get_var_def(self, fullname: str) -> VariableEntry:
        """Return the variable entry for the given full variable path.

        :param fullname: Full path string of the variable.
        :raises ValueError: If the variable is not present in the map.
        """
        if not self.has_var(fullname):
            raise ValueError(f'{fullname} not in Variable Map')
        return self._content.variables[fullname]

    def _get_bitsize(self, vardef: VariableEntry) -> Optional[int]:
        """Return the bit size from the variable entry, or ``None`` if not set.

        :param vardef: Variable entry to inspect.
        """
        if 'bitsize' in vardef:
            return vardef['bitsize']
        return None

    def _get_array_segments(self, vardef: VariableEntry) -> Dict[str, ArrayDef]:
        """Return the array segments dict from the variable entry, or an empty dict if not set.

        :param vardef: Variable entry to inspect.
        """
        return vardef.get('array_segments', {})

    def _get_bitoffset(self, vardef: VariableEntry) -> Optional[int]:
        """Return the bit offset from the variable entry, or ``None`` if not set.

        :param vardef: Variable entry to inspect.
        """
        if 'bitoffset' in vardef:
            return vardef['bitoffset']
        return None

    def _get_enum(self, vardef: VariableEntry) -> Optional[EmbeddedEnum]:
        """Return the ``EmbeddedEnum`` for the variable entry, or ``None`` if not set.

        :param vardef: Variable entry to inspect.
        :raises ValueError: If the entry references an unknown enum ID.
        """
        if 'enum' in vardef:
            enum_id = str(vardef['enum'])
            if enum_id not in self._content.enums:
                raise ValueError(f"Unknown enum ID {enum_id}")
            enum_def = self._content.enums[enum_id]
            return EmbeddedEnum.from_def(enum_def)
        return None

    def set_endianness(self, endianness: Endianness) -> None:
        """Set the target device endianness for this variable map.

        :param endianness: ``Endianness.Little`` or ``Endianness.Big``.
        :raises ValueError: If ``endianness`` is not a recognized ``Endianness`` value.
        """
        if endianness not in [Endianness.Little, Endianness.Big]:
            raise ValueError(f'Invalid endianness {endianness}')    # pragma: no cover
        self._content.endianness = endianness

    def get_endianness(self) -> Endianness:
        """Return the target device endianness"""
        return self._content.endianness

    def write(self, filename: str, indent: Optional[Union[int, str]] = '\t') -> None:
        """Serialize the variable map to a UTF-8-encoded JSON file on disk.

        :param filename: Destination file path.
        :param indent: JSON indentation passed to ``json.dumps``.
        """
        with open(filename, 'wb') as f:
            f.write(self.get_json(indent).encode('utf8'))

    def get_json(self, indent: Optional[Union[int, str]] = 4) -> str:
        """Return the variable map serialized as a JSON string.

        :param indent: JSON indentation passed to ``json.dumps``.
        """
        return json.dumps(self._content.to_dict(), indent=indent)

    def add_variable(self,
                     path_segments: List[str],
                     location: Union[AbsoluteLocation, UnresolvedPathPointedLocation, ResolvedPathPointedLocation],
                     original_type_name: str,
                     bitsize: Optional[int] = None,
                     bitoffset: Optional[int] = None,
                     enum: Optional[EmbeddedEnum] = None,
                     array_segments: Optional[Dict[str, Array]] = None
                     ) -> None:
        """Add a variable in the VarMap

        :param path_segments: List of path segments forming the full variable path.
        :param location: Memory location of the variable (absolute, resolved pointer, or unresolved pointer).
        :param original_type_name: Original binary type name, must already be registered via ``register_base_type``.
        :param bitsize: Optional size in bits for bit-field variables, or ``None`` for regular variables.
        :param bitoffset: Optional bit-level offset within the byte for bit-field variables, or ``None``.
        :param enum: Optional ``EmbeddedEnum`` to associate with this variable.
        :param array_segments: Optional mapping of sub-path strings to ``Array`` instances for array variables.
        :raises ValueError: If ``original_type_name`` is not registered, or if the location is at address 0.
        :raises TypeError: If ``location`` is not a recognized location type.
        """
        fullname = path_tools.join_segments(path_segments)

        if self._logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
            enum_debug_str = "[enum]" if enum is not None else ""
            self._logger.debug(f"Adding {fullname} ({original_type_name}) {enum_debug_str}")

        if not self.is_known_type(original_type_name):
            raise ValueError(f'Cannot add variable of type {original_type_name}. Type has not been registered yet')

        if fullname in self._content.variables:
            self._logger.warning(f'Duplicate entry {fullname}')

        entry: VariableEntry = {
            'type_id': self._get_type_id(original_type_name),
        }
        if isinstance(location, AbsoluteLocation):
            if location.is_null():
                raise ValueError('Cannot add variable at address 0')

            entry['addr'] = location.get_address()

        elif isinstance(location, (UnresolvedPathPointedLocation, ResolvedPathPointedLocation)):
            entry['pointer'] = {
                'path': location.pointer_path,
                'offset': location.pointer_offset
            }

            if isinstance(location, UnresolvedPathPointedLocation):
                if len(location.array_segments) > 0:
                    entry['pointer']['array_segments'] = cast(Dict[str, ArrayDef], {})
                    for path, array in location.array_segments.items():
                        entry['pointer']['array_segments'][path] = {
                            'byte_size': array.get_element_byte_size(),
                            'dims': list(array.dims)
                        }

        else:
            raise TypeError("Invalid location type")

        if bitoffset is not None:
            entry['bitoffset'] = bitoffset

        if bitsize is not None:
            entry['bitsize'] = bitsize

        if enum is not None:
            if enum not in self._enums_to_id_map:
                self._content.enums[str(self._next_enum_id)] = enum.get_def()
                self._enums_to_id_map[enum] = self._next_enum_id
                self._next_enum_id += 1

            entry['enum'] = self._enums_to_id_map[enum]

        if array_segments is not None and len(array_segments) > 0:
            entry['array_segments'] = {}
            for path, array in array_segments.items():
                entry['array_segments'][path] = {
                    'byte_size': array.get_element_byte_size(),
                    'dims': list(array.dims)
                }

        self._content.variables[fullname] = entry

    def register_base_type(self, original_name: str, vartype: EmbeddedDataType) -> None:
        """Register a mapping from an original binary type name to a Scrutiny ``EmbeddedDataType``.

        If the name is already registered with the same type, the call is a no-op.

        :param original_name: Original type name from the binary's debug information.
        :param vartype: Corresponding Scrutiny ``EmbeddedDataType``.
        :raises ValueError: If ``original_name`` is already registered with a different ``EmbeddedDataType``.
        """
        validation.assert_type(vartype, 'vartype', EmbeddedDataType)

        if self.is_known_type(original_name):
            assigned_vartype = self.get_vartype_from_base_type(original_name)
            if assigned_vartype != vartype:
                raise ValueError(f'Cannot assign type {vartype} to  "{original_name}". Scrutiny type already assigned: {assigned_vartype}')
        else:
            typeid = self._next_type_id
            self._next_type_id += 1
            self._typename2typeid_map[original_name] = str(typeid)
            self._content.typemap[str(typeid)] = {
                'name': original_name,
                'type': vartype.name
            }

    def get_vartype_from_base_type(self, binary_type_name: str) -> EmbeddedDataType:
        """Return the Scrutiny ``EmbeddedDataType`` for the given original binary type name.

        :param binary_type_name: Original type name as registered via ``register_base_type``.
        """
        typeid = self._typename2typeid_map[binary_type_name]
        vartype_name = self._content.typemap[typeid]['type']
        return EmbeddedDataType[vartype_name]    # Enums supports square brackets to get enum from name

    def is_known_type(self, binary_type_name: str) -> bool:
        """Return ``True`` if the given original binary type name has been registered.

        :param binary_type_name: Original type name to look up.
        """
        return (binary_type_name in self._typename2typeid_map)

    def has_var(self, fullname: str) -> bool:
        """Return ``True`` if a variable with the given full path is present in the map.

        :param fullname: Full variable path string, may include array index notation.
        """
        try:
            parsed_path = ScrutinyPath.from_string(fullname)
        except Exception:
            return False
        raw_path = parsed_path.to_raw_str()
        return raw_path in self._content.variables

    def has_array_segments(self, fullname: str) -> bool:
        """Return ``True`` if the given variable has array segments defined in the map.

        :param fullname: Full variable path string.
        """
        vardef = self._get_var_def(fullname)
        return len(vardef.get('array_segments', {})) > 0

    def has_pointer_array_segments(self, fullname: str) -> bool:
        """Return ``True`` if the given variable has array segments defined for its pointer path.

        :param fullname: Full variable path string.
        """
        vardef = self._get_var_def(fullname)
        return self._has_pointer_array_segments(vardef)

    def get_pointer_array_segments(self, fullname: str) -> Dict[str, UntypedArray]:
        """Return the pointer array segments for the given variable path as ``UntypedArray`` instances.

        :param fullname: Full variable path string.
        :raises ValueError: If the variable has no pointer array segments.
        """
        vardef = self._get_var_def(fullname)
        if not self._has_pointer_array_segments(vardef):
            raise ValueError(f"No pointer array segments available for {fullname}")
        return self._array_segments_to_untyped_array(self._get_pointer_array_segments(vardef))

    def has_enum(self, fullname: str) -> bool:
        """Return ``True`` if the given variable has an associated ``EmbeddedEnum``.

        :param fullname: Full variable path string.
        """
        return self.get_enum(fullname) is not None

    def get_array_segments(self, fullname: str) -> Dict[str, UntypedArray]:
        """Return the array segments for the given variable path as ``UntypedArray`` instances.

        :param fullname: Full variable path string.
        :raises ValueError: If the variable has no array segments.
        """
        vardef = self._get_var_def(fullname)

        if not self._has_array_segments(vardef):
            raise ValueError(f"No array segments available for {fullname}")
        return self._array_segments_to_untyped_array(self._get_array_segments(vardef))

    def get_enum(self, fullname: str) -> Optional[EmbeddedEnum]:
        """Return the ``EmbeddedEnum`` associated with the given variable path, or ``None`` if not set.

        :param fullname: Full variable path string.
        """
        vardef = self._get_var_def(fullname)
        return self._get_enum(vardef)

    def get_enum_by_name(self, name: str) -> List[EmbeddedEnum]:
        """Return all ``EmbeddedEnum`` instances registered under the given name.

        :param name: Enum name to look up.
        :raises KeyError: If no enum with the given name is found.
        """
        outlist = []
        for enumdef in self._content.enums.values():
            if name == enumdef['name']:
                outlist.append(EmbeddedEnum.from_def(enumdef))

        if len(outlist) == 0:
            raise KeyError(f"No enum with name {name}")

        return outlist

    def iterate_vars(self, wanted_location_type: Sequence[LocationType]) -> Generator[Tuple[str, Union[Variable, VariableFactory]], None, None]:
        """Yield all variable entries as ``(path, Variable)`` or ``(path, VariableFactory)`` tuples.

        Variables with array segments are yielded as ``VariableFactory`` instances; scalar variables
        are yielded as fully resolved ``Variable`` instances. Only entries whose location type is
        present in ``wanted_location_type`` are yielded.

        :param wanted_location_type: Sequence of ``LocationType`` values to include. (ABSOLUTE or POINTED)
        :returns: Generator of ``(full_path, Variable | VariableFactory)`` tuples.
        """
        for fullname, vardef in self._content.variables.items():
            parsed_path = ScrutinyPath.from_string(fullname)

            if self._has_addr(vardef):
                location_type = self.LocationType.ABSOLUTE
            elif self._has_pointed_location(vardef):
                location_type = self.LocationType.POINTED
            else:
                self._logger.warning(f'Unknown location type for {fullname}')
                continue

            if location_type not in wanted_location_type:
                continue

            array_segments = vardef.get('array_segments', None)
            pointer_array_segments: Optional[Dict[str, ArrayDef]] = None
            if self._has_pointer_array_segments(vardef):
                pointer_array_segments = self._get_pointer_array_segments(vardef)

            location: Union[AbsoluteLocation, UnresolvedPathPointedLocation, ResolvedPathPointedLocation]
            if location_type == self.LocationType.ABSOLUTE:
                location = AbsoluteLocation(self._get_addr(vardef))

            elif location_type == self.LocationType.POINTED:
                pointer_path = self._get_pointer_path(vardef)
                pointer_offset = self._get_pointer_offset(vardef)
                if pointer_array_segments is not None:
                    ptr_array_segments: Dict[str, Array] = {}
                    for path, array_def in pointer_array_segments.items():
                        ptr_array_segments[path] = UntypedArray(
                            dims=tuple(array_def['dims']),
                            element_byte_size=array_def['byte_size']
                        )

                    location = UnresolvedPathPointedLocation(
                        pointer_path=pointer_path,
                        pointer_offset=pointer_offset,
                        array_segments=ptr_array_segments
                    )
                else:
                    location = ResolvedPathPointedLocation(
                        pointer_path=pointer_path,
                        pointer_offset=pointer_offset,
                    )

            else:
                raise NotImplementedError("Unsupported location type")

            varlayout = VariableLayout(
                vartype=self._get_type(vardef),
                endianness=self.get_endianness(),
                bitsize=self._get_bitsize(vardef),
                bitoffset=self._get_bitoffset(vardef),
                enum=self._get_enum(vardef)
            )

            if array_segments is not None or pointer_array_segments is not None:
                array_segments = self._get_array_segments(vardef)
                factory = VariableFactory(
                    layout=varlayout,
                    access_name=fullname,
                    base_location=location
                )
                if array_segments is not None:
                    for path, array_def in array_segments.items():
                        arr = UntypedArray(
                            dims=tuple(array_def['dims']),
                            element_byte_size=array_def['byte_size']
                        )
                        factory.add_array_node(path, arr)
                yield (fullname, factory)
            else:
                assert not isinstance(location, UnresolvedPathPointedLocation)
                v = Variable.from_layout(
                    path_segments=parsed_path.get_segments(),
                    location=location,
                    layout=varlayout
                )
                yield (fullname, v)

    def validate(self) -> None:
        """Validate the variable map contents. Currently a no-op placeholder"""
        pass

    def get_var(self, path: str) -> Variable:
        """Return a fully resolved ``Variable`` object for the given path.

        Resolves array index notation in ``path`` to compute the correct byte offset, and resolves
        pointer paths when applicable.

        :param path: Full variable path string, may include array index notation.
        :raises ValueError: If the variable is not found, or if its location cannot be resolved.
        """
        parsed_path = ScrutinyPath.from_string(path)
        raw_path = parsed_path.to_raw_str()
        vardef = self._get_var_def(raw_path)

        var_array_segments: Dict[str, Array] = {}
        pointer_array_segments: Dict[str, Array] = {}

        def fill_array_segments_from_vardef_content(array_segments: Dict[str, Array], array_def_dict: Dict[str, ArrayDef]) -> None:
            for segment_path, array_def in array_def_dict.items():
                array_segments[segment_path] = UntypedArray(
                    dims=tuple(array_def['dims']),
                    element_byte_size=array_def['byte_size'],
                    element_type_name=''
                )

        if self._has_array_segments(vardef):
            fill_array_segments_from_vardef_content(var_array_segments, self._get_array_segments(vardef))

        if self._has_pointer_array_segments(vardef):
            fill_array_segments_from_vardef_content(pointer_array_segments, self._get_pointer_array_segments(vardef))

        location: Union[ResolvedPathPointedLocation, AbsoluteLocation]
        if self._has_addr(vardef):
            byte_offset = parsed_path.compute_address_offset(var_array_segments)
            location = AbsoluteLocation(self._get_addr(vardef) + byte_offset)
        elif self._has_pointed_location(vardef):
            unresolved_path = self._get_pointer_path(vardef)
            nb_pointer_segments = len(path_tools.make_segments(unresolved_path))
            byte_offset = parsed_path.compute_address_offset(var_array_segments, ignore_leading_segments=nb_pointer_segments)

            if self._has_pointer_array_segments(vardef):
                resolved_pointer_path = ScrutinyPath.resolve_pointer_path(unresolved_path, parsed_path, pointer_array_segments)
                if resolved_pointer_path is None:
                    raise ValueError(f"Cannot resolve pointer path from {parsed_path.to_str()}")

                location = ResolvedPathPointedLocation(
                    pointer_path=resolved_pointer_path.to_str(),
                    pointer_offset=self._get_pointer_offset(vardef) + byte_offset  # Add the array offset to the dereferencing offset
                )

            else:   # Simple case - Optimisation to skip parsing
                location = ResolvedPathPointedLocation(
                    pointer_path=unresolved_path,
                    pointer_offset=self._get_pointer_offset(vardef) + byte_offset  # Add the array offset to the dereferencing offset
                )

        else:
            raise ValueError(f"Invalid variable location for {raw_path}")

        return Variable(
            vartype=self._get_type(vardef),
            path_segments=parsed_path.get_segments(),
            location=location,
            endianness=self.get_endianness(),
            bitsize=self._get_bitsize(vardef),
            bitoffset=self._get_bitoffset(vardef),
            enum=self._get_enum(vardef)
        )

    def get_registered_types(self) -> Dict[str, EmbeddedDataType]:
        """Return a dictionary of all the registered variable types mapping original type name to Scrutiny ``EmbeddedDataType``"""
        dout: Dict[str, EmbeddedDataType] = {}
        for type_name in self._typename2typeid_map.keys():
            dout[type_name] = self.get_vartype_from_base_type(type_name)
        return dout

    def get_registered_enums(self) -> List[EmbeddedEnum]:
        """Return a list of all ``EmbeddedEnum`` instances registered in the variable map"""
        outlist: List[EmbeddedEnum] = []
        for enumdef in self._content.enums.values():
            outlist.append(EmbeddedEnum.from_def(enumdef))
        return outlist
