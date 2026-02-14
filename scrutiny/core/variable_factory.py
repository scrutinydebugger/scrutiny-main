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
from scrutiny.core.variable_location import AbsoluteLocation, UnresolvedPathPointedLocation, ResolvedPathPointedLocation
from scrutiny.core.variable import Variable, VariableLayout
from scrutiny.tools.typing import *


class VariableFactory:
    __slots__ = ['_layout', '_access_name', '_base_location', '_array_nodes', '_ptr_array_nodes']

    _layout: VariableLayout
    _access_name: str
    _array_nodes: Dict[str, UntypedArray]
    _ptr_array_nodes: Dict[str, UntypedArray]
    _base_location: Union[AbsoluteLocation, UnresolvedPathPointedLocation, ResolvedPathPointedLocation]

    def __init__(self,
                 access_name: str,
                 base_location: Union[AbsoluteLocation, UnresolvedPathPointedLocation, ResolvedPathPointedLocation, int],
                 layout: VariableLayout
                 ) -> None:
        self._access_name = access_name
        self._layout = layout
        if isinstance(base_location, ResolvedPathPointedLocation):
            base_location = base_location.make_unresolved()
        if isinstance(base_location, int):
            base_location = AbsoluteLocation(base_location)
        self._base_location = base_location
        self._array_nodes = {}
        self._ptr_array_nodes = {}

    def get_array_nodes(self) -> Dict[str, UntypedArray]:
        return self._array_nodes

    def get_variable_layout(self) -> VariableLayout:
        return self._layout

    def get_access_name(self) -> str:
        return self._access_name

    def add_array_node(self, path: str, array: UntypedArray) -> None:
        """Add the definition of the arrays nodes in the non-pointer part of the path (last part)"""
        if path in self._array_nodes:
            raise KeyError(f"Duplicate array node at {path}")

        if not path_tools.is_subpath(subpath=path, path=self._access_name):
            raise ValueError(f"Cannot add an array node at {path} for access name {self._access_name}")
        self._array_nodes[path] = array

    def add_pointer_array_node(self, path: str, array: UntypedArray) -> None:
        """Add the definition of the arrays nodes in the pointer part of the path (first part)"""
        if not isinstance(self._base_location, UnresolvedPathPointedLocation):
            raise ValueError("Cannot add a pointer array node on a variable that is not using a pointed address")

        if path in self._ptr_array_nodes:
            raise KeyError(f"Duplicate pointer array node at {path}")

        if not path_tools.is_subpath(subpath=path, path=self._access_name):
            raise ValueError(f"Cannot add a pointer array node at {path} for access name {self._access_name}")
        self._ptr_array_nodes[path] = array

    def instantiate(self, path: Union[ScrutinyPath, str]) -> Variable:
        if isinstance(path, str):
            path = ScrutinyPath.from_string(path)
        byte_offset = path.compute_address_offset(self._array_nodes)
        # pointer_byte_offset = path.compute_address_offset(self._ptr_array_nodes)

        location: Union[int, AbsoluteLocation, UnresolvedPathPointedLocation]
        if isinstance(self._base_location, AbsoluteLocation):
            location = self._base_location.get_address() + byte_offset
        elif isinstance(self._base_location, UnresolvedPathPointedLocation):
            # TODO
            raise NotImplementedError("Instantiating array of pointers not done yet.")
        else:
            raise NotImplementedError("Unsupported type of base var location for instantiation")

        return Variable.from_layout(
            path_segments=path.get_segments(),
            location=location,
            layout=self._layout.copy()
        )
