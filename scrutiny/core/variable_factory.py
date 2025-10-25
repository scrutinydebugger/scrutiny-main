#    variable_factory.py
#        A class that can instantiate variables based on a base variable and additional information.
#        Mainly to instantiate array items
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['VariableFactory']

from scrutiny.core import path_tools
from scrutiny.core.variable import Variable
from scrutiny.core.array import UntypedArray
from scrutiny.core.scrutiny_path import ScrutinyPath
from scrutiny.core.variable import Variable
from scrutiny.tools.typing import *


class VariableFactory:
    __slots__ = ['_base_var', '_access_name', '_array_nodes', ]

    _base_var: Variable
    _access_name: str
    _array_nodes: Dict[str, UntypedArray]

    def __init__(self,
                 access_name: str,
                 base_var: Variable
                 ) -> None:
        self._access_name = access_name
        self._base_var = base_var
        self._array_nodes = {}

    def get_array_nodes(self) -> Dict[str, UntypedArray]:
        return self._array_nodes

    def get_base_variable(self) -> Variable:
        return self._base_var

    def get_access_name(self) -> str:
        return self._access_name

    def add_array_node(self, path: str, array: UntypedArray) -> None:
        if path in self._array_nodes:
            raise KeyError(f"Duplicate array node at {path}")

        if not path_tools.is_subpath(subpath=path, path=self._access_name):
            raise ValueError(f"Cannot add an array node at {path} for access name {self._access_name}")
        self._array_nodes[path] = array

    def instantiate(self, path: Union[ScrutinyPath, str]) -> Variable:
        if isinstance(path, str):
            path = ScrutinyPath.from_string(path)
        byte_offset = path.compute_address_offset(self._array_nodes)

        return Variable(
            vartype=self._base_var.vartype,
            path_segments=path.get_segments(),
            location=self._base_var.get_address() + byte_offset,
            endianness=self._base_var.endianness,
            bitsize=self._base_var.bitsize,
            bitoffset=self._base_var.bitoffset,
            enum=self._base_var.enum
        )
