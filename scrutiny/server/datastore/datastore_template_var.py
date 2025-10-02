#    datastore_template_var.py
#        A definition of a tempalte that can generate DatastoreVariableEntries from additional
#        information encoded in a path
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['DatastoreTemplateVar']

from scrutiny.server.datastore.datastore_entry import DatastoreVariableEntry
from scrutiny.core.variable import *
from scrutiny.core.array import *
from scrutiny.core.basic_types import *
from scrutiny.core.embedded_enum import EmbeddedEnum
from scrutiny.core.scrutiny_path import *
from scrutiny.tools.typing import *


class DatastoreTemplateVar:
    __slots__ = ['_access_name', '_array_nodes', '_base_address', '_vartype', '_bitoffset', '_bitsize', '_endianness', '_enum']

    _access_name: str
    _array_nodes: Dict[str, UntypedArray]
    _base_address: int
    _vartype: EmbeddedDataType
    _bitoffset: Optional[int]
    _bitsize: Optional[int]
    _endianness: Endianness
    _enum: Optional[EmbeddedEnum]

    def __init__(self,
                 access_name: str,
                 vartype: EmbeddedDataType,
                 base_address: int,
                 endianness: Endianness,
                 bitoffset: Optional[int],
                 bitsize: Optional[int],
                 enum: Optional[EmbeddedEnum] = None
                 ) -> None:
        self._access_name = access_name
        self._array_nodes = {}
        self._base_address = base_address
        self._endianness = endianness
        self._vartype = vartype
        self._bitoffset = bitoffset
        self._bitsize = bitsize
        self._enum = enum

    def get_access_name(self) -> str:
        return self._access_name

    def add_array_node(self, path: str, array: UntypedArray) -> None:
        if path in self._array_nodes:
            raise KeyError(f"Duplicate array node at {path}")
        self._array_nodes[path] = array

    def instantiate(self, path: ScrutinyPath) -> DatastoreVariableEntry:
        byte_offset = path.compute_address_offset(self._array_nodes)

        var = Variable(
            vartype=self._vartype,
            path_segments=path.get_segments(),
            location=self._base_address + byte_offset,
            endianness=self._endianness,
            bitsize=self._bitsize,
            bitoffset=self._bitoffset,
            enum=self._enum
        )

        return DatastoreVariableEntry(path.to_str(), var)
