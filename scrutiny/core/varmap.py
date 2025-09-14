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
import re
from pathlib import Path
from dataclasses import dataclass

from scrutiny.core.variable import Variable, VariableLocation, Array, UntypedArray
from scrutiny.core.basic_types import EmbeddedDataType, Endianness
from scrutiny.core.embedded_enum import EmbeddedEnum, EmbeddedEnumDef
from scrutiny.tools.typing import *
from scrutiny.tools import validation

_complex_path_segment_regex = re.compile(r'(.+?)((\[\d+\])+)$')


class TypeEntry(TypedDict):
    name: str
    type: str


class ArrayDef(TypedDict):
    dims: List[int]
    byte_size: int


def make_segments(path: str) -> List[str]:
    pieces = path.split('/')
    return [segment for segment in pieces if segment]


def join_segments(segments: List[str]) -> str:
    return '/' + '/'.join(segments)


@dataclass
class ComplexPath:
    __slots__ = ('raw_segments', 'array_pos')

    raw_segments: List[str]
    array_pos: List[Optional[Tuple[int, ...]]]

    def get_path_to_array_pos_dict(self) -> Dict[str, Tuple[int, ...]]:
        outdict: Dict[str, Tuple[int, ...]] = {}
        for i in range(len(self.array_pos)):
            pos = self.array_pos[i]
            if pos is not None:
                outdict[join_segments(self.raw_segments[:i + 1])] = pos

        return outdict

    @classmethod
    def from_string(cls, path: str) -> Self:
        """Parse a path with information encoded and extract it
        ex: /aaa/bbb[2][3]/ccc = /aaa/bbb/ccc + {array: /aaa/bbb, (2,3)}"""
        segments = make_segments(path)
        raw_segments: List[str] = []
        array_pos: List[Optional[Tuple[int, ...]]] = []
        for i in range(len(segments)):
            m = _complex_path_segment_regex.match(segments[i])
            if m:
                name_part = m.group(1)
                raw_segments.append(name_part)
                array_part = m.group(2)
                pos = tuple([int(x) for x in re.findall(r'\d+', array_part)])
                array_pos.append(pos)
            else:
                raw_segments.append(segments[i])
                array_pos.append(None)

        return cls(
            raw_segments=raw_segments,
            array_pos=array_pos
        )


class VariableEntry(TypedDict, total=False):
    type_id: str  # integer as string because of json format that can't have a dict key as int
    addr: int
    bitoffset: int
    bitsize: int
    enum: int
    array_segments: Dict[str, ArrayDef]


SupportedVersionKeys: TypeAlias = Literal['v1']
VariableDict: TypeAlias = Dict[SupportedVersionKeys, Dict[str, VariableEntry]]


class VarMap:

    class SerializableContentDict(TypedDict):
        endianness: str
        type_map: Dict[str, TypeEntry]
        variables: VariableDict
        enums: Dict[str, EmbeddedEnumDef]

    class SerializableContent:
        __slots__ = ('endianness', 'typemap', 'variables', 'enums')
        endianness: Endianness
        typemap: Dict[str, TypeEntry]
        variables: VariableDict
        enums: Dict[str, EmbeddedEnumDef]

        def __init__(self) -> None:
            self.endianness = Endianness.Little
            self.typemap = {}
            self.variables = {"v1": {}}
            self.enums = {}

        def to_dict(self) -> "VarMap.SerializableContentDict":
            return {
                'endianness': self.endianness.to_str(),
                'type_map': self.typemap,
                'variables': self.variables,
                'enums': self.enums,
            }

        def load_dict(self, d: "VarMap.SerializableContentDict") -> None:
            validation.assert_dict_key(d, 'endianness', str)
            validation.assert_dict_key(d, 'type_map', dict)
            validation.assert_dict_key(d, 'variables', dict)
            validation.assert_dict_key(d, 'enums', dict)

            self.endianness = Endianness.from_str(d['endianness'])
            self.typemap = d['type_map']
            self.enums = d['enums']

            variables = d['variables']
            if 'v1' not in variables:   # Backward compatibility with unversioned files
                variables = {'v1': cast(Dict[str, VariableEntry], variables)}

            self.variables = {
                'v1': variables['v1']  # Cherry pick the versions we know. Will drop unsupported stuff from the future
            }

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
        return cls.from_json(data.decode('utf8'))

    @classmethod
    def from_json(cls, data: str) -> Self:
        varmap = cls()
        content = json.loads(data)
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
            if enum_id_int >= self._next_enum_id:
                self._next_enum_id = enum_id_int + 1

            enum = EmbeddedEnum.from_def(self._content.enums[str(enum_id_int)])
            self._enums_to_id_map[enum] = enum_id_int

    def _get_type_id(self, binary_type_name: str) -> str:
        if binary_type_name not in self._typename2typeid_map:
            raise ValueError(f'Type name {binary_type_name} does not exist in the Variable Description File')

        return self._typename2typeid_map[binary_type_name]   # Type is an integer as string

    def _get_type(self, vardef: VariableEntry) -> EmbeddedDataType:
        type_id = str(vardef['type_id'])    # type_id is a required field
        if type_id not in self._content.typemap:
            raise KeyError(f'Type "{type_id}" refer to a type not in type map')
        typename = self._content.typemap[type_id]['type']
        return EmbeddedDataType[typename]  # Enums support square brackets

    def _get_addr(self, vardef: VariableEntry) -> int:
        return vardef['addr']   # addr is a required field

    def _get_var_def(self, fullname: str, version_key: SupportedVersionKeys) -> VariableEntry:
        if not self.has_var(fullname):
            raise ValueError(f'{fullname} not in Variable Description File')
        return self._content.variables[version_key][fullname]

    def _get_bitsize(self, vardef: VariableEntry) -> Optional[int]:
        if 'bitsize' in vardef:
            return vardef['bitsize']
        return None

    def _get_bitoffset(self, vardef: VariableEntry) -> Optional[int]:
        if 'bitoffset' in vardef:
            return vardef['bitoffset']
        return None

    def _get_enum(self, vardef: VariableEntry) -> Optional[EmbeddedEnum]:
        if 'enum' in vardef:
            enum_id = str(vardef['enum'])
            if enum_id not in self._content.enums:
                raise ValueError(f"Unknown enum ID {enum_id}")
            enum_def = self._content.enums[enum_id]
            return EmbeddedEnum.from_def(enum_def)
        return None

    def set_endianness(self, endianness: Endianness) -> None:
        if endianness not in [Endianness.Little, Endianness.Big]:
            raise ValueError(f'Invalid endianness {endianness}')    # pragma: no cover
        self._content.endianness = endianness

    def get_endianness(self) -> Endianness:
        return self._content.endianness

    def write(self, filename: str, indent: int = 4) -> None:
        with open(filename, 'wb') as f:
            f.write(self.get_json(indent).encode('utf8'))

    def get_json(self, indent: int = 4) -> str:
        return json.dumps(self._content.to_dict(), indent=indent)

    def add_variable(self,
                     path_segments: List[str],
                     location: VariableLocation,
                     original_type_name: str,
                     bitsize: Optional[int] = None,
                     bitoffset: Optional[int] = None,
                     enum: Optional[EmbeddedEnum] = None,
                     array_segments: Optional[Dict[str, Array]] = None
                     ) -> None:
        fullname = join_segments(path_segments)

        if self._logger.isEnabledFor(logging.DEBUG):  # pragma: no cover
            self._logger.debug(f"Adding {fullname}")

        if not self.is_known_type(original_type_name):
            raise ValueError(f'Cannot add variable of type {original_type_name}. Type has not been registered yet')

        if location.is_null():
            raise ValueError('Cannot add variable at address 0')

        if fullname in self._content.variables:
            self._logger.warning(f'Duplicate entry {fullname}')

        entry: VariableEntry = {
            'type_id': self._get_type_id(original_type_name),
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

        if array_segments is not None and len(array_segments) > 0:
            entry['array_segments'] = {}
            for path, array in array_segments.items():
                entry['array_segments'][path] = {
                    'byte_size': array.get_element_byte_size(),
                    'dims': list(array.dims)
                }

        version_container: SupportedVersionKeys = 'v1'    # Can add logic in the future to decide based on features above
        self._content.variables[version_container][fullname] = entry

    def register_base_type(self, original_name: str, vartype: EmbeddedDataType) -> None:
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
        typeid = self._typename2typeid_map[binary_type_name]
        vartype_name = self._content.typemap[typeid]['type']
        return EmbeddedDataType[vartype_name]    # Enums supports square brackets to get enum from name

    def is_known_type(self, binary_type_name: str) -> bool:
        return (binary_type_name in self._typename2typeid_map)

    def get_var(self, fullname: str) -> Variable:
        segments = make_segments(fullname)
        vardef = self._get_var_def(fullname, 'v1')
        # Todo : Handles array here
        return Variable(
            name=segments[-1],
            vartype=self._get_type(vardef),
            path_segments=segments[:-1],
            location=self._get_addr(vardef),
            endianness=self.get_endianness(),
            bitsize=self._get_bitsize(vardef),
            bitoffset=self._get_bitoffset(vardef),
            enum=self._get_enum(vardef)
        )

    def has_var(self, fullname: str) -> bool:
        v = False
        if fullname in self._content.variables['v1']:
            v = True
        return v

    def get_enum_by_name(self, name: str) -> List[EmbeddedEnum]:
        outlist = []
        for enumdef in self._content.enums.values():
            if name == enumdef['name']:
                outlist.append(EmbeddedEnum.from_def(enumdef))

        if len(outlist) == 0:
            raise KeyError(f"No enum with name {name}")

        return outlist

    def iterate_vars(self) -> Generator[Tuple[str, Variable], None, None]:
        for fullname in self._content.variables['v1']:
            yield (fullname, self.get_var(fullname))

    def validate(self) -> None:
        pass

    def get_var_from_complex_name(self, path: str) -> Variable:
        parsed = ComplexPath.from_string(path)
        raw_path = join_segments(parsed.raw_segments)
        vardef = self._get_var_def(raw_path, 'v1')
        path2pos = parsed.get_path_to_array_pos_dict()

        array_segments_def = {}
        if 'array_segments' in vardef:
            array_segments_def = vardef['array_segments']

        if len(array_segments_def) != len(path2pos):
            raise ValueError("The array identifiers does not match the variable definition")

        path_by_length = sorted(list(array_segments_def.keys()), key=lambda x: len(x))
        byte_multiplier = 1
        byte_offset = 0
        for k in reversed(path_by_length):
            if k not in path2pos:
                raise ValueError("The array identifiers does not match the variable definition. Array not indexed")
            pos = path2pos[k]
            array = array_segments_def[k]
            dims = tuple(array['dims'])
            bytesize = array['byte_size']
            try:
                arr = UntypedArray(dims, '', bytesize)
                byte_offset += arr.byte_position_of(pos) * byte_multiplier
                byte_multiplier *= arr.get_total_byte_size()
            except Exception as e:
                raise ValueError(f'The array identifiers does not match the variable definition. {e}')

        new_address = self._get_addr(vardef) + byte_offset

        segments = make_segments(path)
        return Variable(
            name=segments[-1],
            vartype=self._get_type(vardef),
            path_segments=segments[:-1],
            location=new_address,
            endianness=self.get_endianness(),
            bitsize=self._get_bitsize(vardef),
            bitoffset=self._get_bitoffset(vardef),
            enum=self._get_enum(vardef)
        )
