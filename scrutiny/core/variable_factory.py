#    variable_factory.py
#        A class that can instantiate variables based on a base variable and additional information.
#        Mainly to instantiate array items
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2025 Scrutiny Debugger

__all__ = ['VariableFactory']

from scrutiny.core import path_tools
from scrutiny.core.array import UntypedArray, Array
from scrutiny.core.scrutiny_path import ScrutinyPath
from scrutiny.core.variable_location import AbsoluteLocation, UnresolvedPathPointedLocation, ResolvedPathPointedLocation
from scrutiny.core.variable import Variable, VariableLayout
from scrutiny.tools.typing import *


class VariableFactory:
    """Class able to instantiate Variables following a pattern. Mostly used for instantiating array elements from an array definition."""
    __slots__ = ['_layout', '_access_name', '_base_location', '_array_nodes']

    _layout: VariableLayout
    """The memory layout to apply to each variable created"""
    _access_name: str
    """The path used to access this factory. All encoded information is striped from this path. e.g. array indices"""
    _base_location: Union[AbsoluteLocation, UnresolvedPathPointedLocation]
    """A location used to generate a new location when instantiating variables"""
    _array_nodes: Dict[str, UntypedArray]
    """A dict mapping path to array definitions"""

    def __init__(self,
                 access_name: str,
                 base_location: Union[AbsoluteLocation, UnresolvedPathPointedLocation, ResolvedPathPointedLocation, int],
                 layout: VariableLayout
                 ) -> None:
        self._access_name = access_name
        self._layout = layout
        if isinstance(base_location, ResolvedPathPointedLocation):  # Convenience for the varmap
            # An unresolved path is the same as a resolved path, but it contains array information to instantiate.
            base_location = base_location.make_unresolved()
        if isinstance(base_location, int):
            base_location = AbsoluteLocation(base_location)
        self._base_location = base_location
        self._array_nodes = {}

    def get_base_location(self) -> Union[AbsoluteLocation, UnresolvedPathPointedLocation]:
        """Return the base location used to generate locations when instantiating variables"""
        return self._base_location

    def get_array_nodes(self) -> Mapping[str, Array]:
        """Returns the array node of the dereferenced part of the path (after the pointer, if any)."""
        return self._array_nodes

    def get_pointer_array_nodes(self) -> Mapping[str, Array]:
        """Returns the array node of the pointer part of the path."""
        if isinstance(self._base_location, AbsoluteLocation):
            return {}

        return self._base_location.array_segments

    def get_all_array_nodes_flat(self) -> Mapping[str, Array]:
        """Returns the array node of the pointer part of the path. Make sure the path are consistent"""
        all_nodes: Dict[str, Array] = {}

        for path, array in self.get_array_nodes().items():
            all_nodes[path] = array

        if self.has_array_in_pointed_address():
            parsed_access_name = ScrutinyPath.from_string(self.get_access_name())
            for path, array in self.get_pointer_array_nodes().items():
                parsed_path = ScrutinyPath.from_string(path)
                if parsed_access_name.segments_count() < parsed_path.segments_count():
                    raise ValueError("Invalid factory structure. Pointer arrays path longer than access name")

                # Add the * in the path if needed.
                # This could probably be less hacky, but it is also a one time deal and hidden under an api.. leaving as is for now.
                if parsed_access_name.has_pointer_dereferencer() and not parsed_path.has_pointer_dereferencer():
                    path_segments = parsed_path.get_segments()  # makes a copy
                    star_index = parsed_access_name.get_pointer_dereferencer_index()
                    if star_index < len(path_segments):
                        path_segments[star_index] = '*' + path_segments[star_index]
                        path = path_tools.join_segments(path_segments)
                parsed_access_name.has_pointer_dereferencer()
                all_nodes[path] = array

        return all_nodes

    def get_variable_layout(self) -> VariableLayout:
        """Return the layout applied to each variable instantiated"""
        return self._layout

    def get_access_name(self) -> str:
        """The path without encoded information"""
        return self._access_name

    def add_array_node(self, path: str, array: UntypedArray) -> None:
        """Add the definition of the arrays nodes in the non-pointer part of the path (last part)"""
        if path in self._array_nodes:
            raise KeyError(f"Duplicate array node at {path}")

        if not path_tools.is_subpath(subpath=path, path=self._access_name):
            raise ValueError(f"Cannot add an array node at {path} for access name {self._access_name}")
        self._array_nodes[path] = array

    def has_absolute_address(self) -> bool:
        """Return ``True`` if the variable instantiated will have an absolute address in memory. ``False`` if pointed"""
        return isinstance(self._base_location, AbsoluteLocation)

    def has_pointed_address(self) -> bool:
        """Return ``True`` if the variable instantiated will have a pointed address. ``False`` if absolute"""
        return isinstance(self._base_location, UnresolvedPathPointedLocation)

    def has_array_in_pointed_address(self) -> bool:
        """Return ``True`` if the location is pointed and there are array segments in the pointer part of the path"""
        if not isinstance(self._base_location, UnresolvedPathPointedLocation):
            return False
        return len(self._base_location.array_segments) > 0

    def instantiate(self, path: Union[ScrutinyPath, str]) -> Variable:
        """Instantiate a Variable from a path that matches this factory"""
        if isinstance(path, str):
            path = ScrutinyPath.from_string(path)

        location: Union[int, AbsoluteLocation, ResolvedPathPointedLocation]
        if isinstance(self._base_location, AbsoluteLocation):
            byte_offset = path.compute_address_offset(self._array_nodes)
            location = self._base_location.get_address() + byte_offset
        elif isinstance(self._base_location, UnresolvedPathPointedLocation):
            unresolved_path = self._base_location.pointer_path
            nb_pointer_segments = len(path_tools.make_segments(unresolved_path))
            byte_offset = path.compute_address_offset(self._array_nodes, ignore_leading_segments=nb_pointer_segments)

            resolved_pointer_path = ScrutinyPath.resolve_pointer_path(unresolved_path, path, self._base_location.array_segments)
            if resolved_pointer_path is None:
                raise ValueError("Cannot instantiate variable from factory. Pointer path not resolvable from given path")
            location = ResolvedPathPointedLocation(
                pointer_path=resolved_pointer_path.to_str(),
                pointer_offset=self._base_location.pointer_offset + byte_offset  # Add the array offset to the dereferencing offset
            )
        else:
            raise NotImplementedError("Unsupported type of base var location for instantiation")

        return Variable.from_layout(
            path_segments=path.get_segments(),
            location=location,
            layout=self._layout.copy()
        )
