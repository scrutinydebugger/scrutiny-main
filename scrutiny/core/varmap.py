#    varmap.py
#        A VarMap list all variables in a firmware file along with their types, address, bit
#        offset, etc
#        . I is a simplified version of the DWARF debugging symbols.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['VarMap']

import json
import logging
from pathlib import Path

from scrutiny.core.variable import Variable, VariableLocation, Array
from scrutiny.core.basic_types import EmbeddedDataType, Endianness
from scrutiny.core.embedded_enum import EmbeddedEnum, EmbeddedEnumDef
from scrutiny.tools.typing import *
from scrutiny.tools import validation


class TypeEntry(TypedDict):
    name: str
    type: str


class ArrayDef(TypedDict):
    dims: List[int]
    byte_size: int


class VariableEntry(TypedDict, total=False):
    type_id: str  # integer as string because of json format that can't have a dict key as int
    addr: int
    bitoffset: int
    bitsize: int
    enum: int
    array_segments: Dict[str, ArrayDef]


class VarMap:

    class SerializableContentDict(TypedDict):
        version: int
        endianness: str
        type_map: Dict[str, TypeEntry]
        variables: Dict[str, VariableEntry]
        enums: Dict[str, EmbeddedEnumDef]

    class SerializableContent:
        __slots__ = ('endianness', 'typemap', 'variables', 'enums')
        VERSION = 1

        endianness: Endianness
        typemap: Dict[str, TypeEntry]
        variables: Dict[str, VariableEntry]
        enums: Dict[str, EmbeddedEnumDef]

        def __init__(self) -> None:
            self.endianness = Endianness.Little
            self.typemap = {}
            self.variables = {}
            self.enums = {}

        def to_dict(self) -> "VarMap.SerializableContentDict":
            if self.endianness == Endianness.Little:
                endianness_str = 'little'
            elif self.endianness == Endianness.Big:
                endianness_str = 'big'
            else:
                raise ValueError('Unknown endianness')

            return {
                'version': self.VERSION,
                'endianness': endianness_str,
                'type_map': self.typemap,
                'variables': self.variables,
                'enums': self.enums,
            }

        def load_dict(self, d: "VarMap.SerializableContentDict") -> None:
            validation.assert_dict_key(d, 'endianness', str)
            validation.assert_dict_key(d, 'type_map', dict)
            validation.assert_dict_key(d, 'variables', dict)
            validation.assert_dict_key(d, 'enums', dict)

            endinaness_str = d['endianness'].lower().strip()
            if endinaness_str == 'little':
                endianness = Endianness.Little
            elif endinaness_str == 'big':
                endianness = Endianness.Big
            else:
                raise ValueError(f"Unknown endianness {d['endianness']}")

            self.endianness = endianness
            self.typemap = d['type_map']
            self.variables = d['variables']
            self.enums = d['enums']

    _logger: logging.Logger
    _content: SerializableContent
    _next_type_id: int
    _next_enum_id: int
    _typename2typeid_map: Dict[str, str]      # name to numeric id as string
    _enums_to_id_map: Dict[EmbeddedEnum, int]

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._content = self.SerializableContent()
        self._build_content_indexes()   # Initialize all the index variables.

    @classmethod
    def from_file(cls, filename: Union[Path, str]) -> Self:
        varmap = cls()
        with open(filename, 'r') as f:
            content = json.loads(f.read())
        varmap.load_dict(content)
        return varmap

    @classmethod
    def from_file_content(cls, data: bytes) -> Self:
        varmap = cls()
        content = json.loads(data.decode('utf8'))
        varmap.load_dict(content)
        return varmap

    def load_dict(self, content: Dict[str, Any]) -> None:
        self._content.load_dict(cast(VarMap.SerializableContentDict, content))
        self._build_content_indexes()

    def _build_content_indexes(self) -> None:
        self._next_type_id = 0
        self._next_enum_id = 0
        self._typename2typeid_map = {}   # Maps the type id of this VarMap to the original name inside the binary.
        self._enums_to_id_map = {}       # Maps a EmbeddedEnum object to it's internal id

        # Build _typename2typeid_map
        for typeid_str in self._content.typemap:
            typeid_int = int(typeid_str)
            if typeid_int > self._next_type_id:
                self._next_type_id = typeid_int

            typename = self._content.typemap[str(typeid_int)]['name']
            self._typename2typeid_map[typename] = typeid_str

        # Build _enums_to_id_map
        for enum_id_str in self._content.enums:
            enum_id_int = int(enum_id_str)
            if enum_id_int > self._next_enum_id:
                self._next_enum_id = enum_id_int

            enum = EmbeddedEnum.from_def(self._content.enums[str(enum_id_int)])
            self._enums_to_id_map[enum] = enum_id_int

    def set_endianness(self, endianness: Endianness) -> None:
        if endianness not in [Endianness.Little, Endianness.Big]:
            raise ValueError(f'Invalid endianness {endianness}')
        self._content.endianness = endianness

    def get_endianness(self) -> Endianness:
        return self._content.endianness

    def write(self, filename: str, indent: int = 4) -> None:
        with open(filename, 'w') as f:
            f.write(self.get_json(indent))

    def get_json(self, indent: int = 4) -> str:
        return json.dumps(self._content.to_dict(), indent=indent)

    def add_variable(self,
                     path_segments: List[str],
                     name: str,
                     location: VariableLocation,
                     original_type_name: str,
                     bitsize: Optional[int] = None,
                     bitoffset: Optional[int] = None,
                     enum: Optional[EmbeddedEnum] = None,
                     array_segments: Optional[Dict[str, Array]] = None
                     ) -> None:
        fullname = self.make_fullname(path_segments, name)

        if self._logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
            self._logger.debug(f"Adding {fullname}")

        if not self.is_known_type(original_type_name):
            raise ValueError(f'Cannot add variable of type {original_type_name}. Type has not been registered yet')

        if location.is_null():
            raise ValueError('Cannot add variable at address 0')

        if fullname in self._content.variables:
            self._logger.warning('Duplicate entry %s' % fullname)

        entry: VariableEntry = {
            'type_id': self.get_type_id(original_type_name),
            'addr': location.get_address()
        }

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

        if array_segments is not None:
            entry['array_segments'] = {}
            for path, array in array_segments.items():
                entry['array_segments'][path] = {
                    'byte_size': array.element_byte_size,
                    'dims': list(array.dims)
                }

        self._content.variables[fullname] = entry

    def register_base_type(self, original_name: str, vartype: EmbeddedDataType) -> None:
        validation.assert_type(vartype, 'vartype', EmbeddedDataType)

        if self.is_known_type(original_name):
            assigned_vartype = self.get_vartype_from_binary_name(original_name)
            if assigned_vartype != vartype:
                raise Exception(f'Cannot assign type {vartype} to  "{original_name}". Scrutiny type already assigned: {assigned_vartype}')
        else:
            typeid = self._next_type_id
            self._next_type_id += 1
            self._typename2typeid_map[original_name] = str(typeid)
            self._content.typemap[str(typeid)] = {
                'name': original_name, 
                'type': vartype.name
            }

    def get_vartype_from_binary_name(self, binary_type_name: str) -> EmbeddedDataType:
        typeid = self._typename2typeid_map[binary_type_name]
        vartype_name = self._content.typemap[typeid]['type']
        return EmbeddedDataType[vartype_name]    # Enums supports square brackets to get enum from name

    def is_known_type(self, binary_type_name: str) -> bool:
        return (binary_type_name in self._typename2typeid_map)

    def get_type_id(self, binary_type_name: str) -> str:
        if binary_type_name not in self._typename2typeid_map:
            raise Exception('Type name %s does not exist in the Variable Description File' % (binary_type_name))

        return self._typename2typeid_map[binary_type_name]   # Type is an integer as string

    def get_var(self, fullname: str) -> Variable:
        segments, name = self.make_segments(fullname)
        vardef = self.get_var_def(fullname)
        # Todo : Handles array here
        return Variable(
            name=name,
            vartype=self.get_type(vardef),
            path_segments=segments,
            location=self.get_addr(vardef),
            endianness=self.get_endianness(),
            bitsize=self.get_bitsize(vardef),
            bitoffset=self.get_bitoffset(vardef),
            enum=self.get_enum(vardef)
        )

    def has_var(self, fullname: str) -> bool:
        return fullname in self._content.variables

    def make_segments(self, fullname: str) -> Tuple[List[str], str]:
        pieces = fullname.split('/')
        segments = [segment for segment in pieces[0:-1] if segment]
        name = pieces[-1]
        return (segments, name)

    def make_fullname(self, path_segments: List[str], name: str) -> str:
        fullname = '/'
        for segment in path_segments:
            fullname += segment + '/'
        fullname += name
        return fullname

    def get_type(self, vardef: VariableEntry) -> EmbeddedDataType:
        type_id = str(vardef['type_id'])
        if type_id not in self._content.typemap:
            raise AssertionError(f'Type "{type_id}" refer to a type not in type map')
        typename = self._content.typemap[type_id]['type']
        return EmbeddedDataType[typename]  # Enums support square brackets

    def get_addr(self, vardef: VariableEntry) -> int:
        return vardef['addr']

    def get_var_def(self, fullname: str) -> VariableEntry:
        if not self.has_var(fullname):
            raise ValueError(f'{fullname} not in Variable Description File')
        return self._content.variables[fullname]

    def get_bitsize(self, vardef: VariableEntry) -> Optional[int]:
        if 'bitsize' in vardef:
            return vardef['bitsize']
        return None

    def get_bitoffset(self, vardef: VariableEntry) -> Optional[int]:
        if 'bitoffset' in vardef:
            return vardef['bitoffset']
        return None

    def get_enum(self, vardef: VariableEntry) -> Optional[EmbeddedEnum]:
        if 'enum' in vardef:
            enum_id = str(vardef['enum'])
            if enum_id not in self._content.enums:
                raise Exception("Unknown enum ID %s" % enum_id)
            enum_def = self._content.enums[enum_id]
            return EmbeddedEnum.from_def(enum_def)
        return None

    def get_enum_by_name(self, name: str) -> Generator[EmbeddedEnum, None, None]:
        found = False
        for enumdef in self._content.enums.values():
            if name == enumdef['name']:
                found = True
                yield EmbeddedEnum.from_def(enumdef)

        if not found:
            raise KeyError(f"No enum with name {name}")

    def iterate_vars(self) -> Generator[Tuple[str, Variable], None, None]:
        for fullname in self._content.variables:
            yield (fullname, self.get_var(fullname))

    def validate(self) -> None:
        pass
