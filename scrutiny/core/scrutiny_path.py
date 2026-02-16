#    scrutiny_path.py
#        A class that can manipulate and interpret a path refering to a watchable in the server
#        and cli toolchains.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2025 Scrutiny Debugger

__all__ = ['ScrutinyPath']

from dataclasses import dataclass
import re
from scrutiny.tools.typing import *
from scrutiny.core.array import Array
from scrutiny.core import path_tools


@dataclass(slots=True)
class AddressOffset:
    pointer_part_offset: int
    non_pointer_part_offset: int


@dataclass(slots=True)
class ScrutinyPath:
    """A class to manipulate and interpret paths used to refer to watchable elements across the project"""

    _complex_path_segment_regex = re.compile(r'((\*?)(.+?))((\[\d+\])*)$')
    _segments: List[str]
    _raw_segments: List[str]
    _array_pos: List[Optional[Tuple[int, ...]]]
    _dereference_index: Optional[int]

    def __str__(self) -> str:
        return self.to_str()

    def to_str(self) -> str:
        """Return the path as a string with the encoded location information, if any"""
        return path_tools.join_segments(self._segments)

    def to_raw_str(self) -> str:
        """Return the path as a string without the encoded location information"""
        return path_tools.join_segments(self._raw_segments)

    def get_segments(self) -> List[str]:
        """Get all path segments"""
        return self._segments.copy()

    def get_name_segment(self) -> str:
        """Get only the last path segments, corresponding to its name"""
        return self._segments[-1]

    def get_segments_without_name(self) -> List[str]:
        """Get all path segments except the last one (the name)"""
        return self._segments[:-1]

    def get_raw_segments(self) -> List[str]:
        """Get all path segments, without encoded information"""
        return self._raw_segments.copy()

    def get_raw_name_segment(self) -> str:
        """Get only the last path segments without encoded information, corresponding to its name"""
        return self._raw_segments[-1]

    def get_raw_segments_without_name(self) -> List[str]:
        """Get all path segments without encoded information except the last one (the name)"""
        return self._raw_segments[:-1]

    def has_array_information(self) -> bool:
        """Tells if there is array information encoded in the path"""
        for v in self._array_pos:
            if v is not None:
                return True
        return False

    def has_pointer_dereferencer(self) -> bool:
        return self._dereference_index is not None

    def get_pointer_dereferencer_index(self) -> int:
        if self._dereference_index is not None:
            return self._dereference_index
        raise ValueError("No dereferencing segment in path")

    def get_path_to_array_pos_dict(self, skip_first_segments: int = 0) -> Dict[str, Tuple[int, ...]]:
        """Extract the array information from the path and return it in a format easier to work with. 
        Returns a dict mapping the subpath to a position.

        /aaa[2]/bbb/ccc[3][4] 
        becomes:
        {
            '/aaa':(2,), 
            '/aaa/bbb/ccc':(3,4)
        }

        """
        outdict: Dict[str, Tuple[int, ...]] = {}
        for i in range(skip_first_segments, len(self._array_pos)):
            pos = self._array_pos[i]
            if pos is not None:
                outdict[path_tools.join_segments(self._raw_segments[:i + 1])] = pos

        return outdict

    @classmethod
    def from_string(cls, path: str) -> Self:
        """Parse a path with information encoded and extract it
        ex: /aaa/bbb[2][3]/ccc = /aaa/bbb/ccc + {array: /aaa/bbb, (2,3)}"""
        segments = path_tools.make_segments(path)
        raw_segments: List[str] = []
        array_pos: List[Optional[Tuple[int, ...]]] = []
        dereference_index: Optional[int] = None
        for i in range(len(segments)):
            m = cls._complex_path_segment_regex.match(segments[i])
            if not m:
                raise ValueError(f"Invalid path segment {i} in path {path}")
            dereferencer_part = m.group(2)
            if len(dereferencer_part) > 0:
                if dereference_index is not None:
                    raise ValueError("More than one dereference symbol in path")
                dereference_index = i
            name_part = m.group(1)
            raw_segments.append(name_part)
            array_part = m.group(4)
            if len(array_part) > 0:
                pos = tuple([int(x) for x in re.findall(r'\d+', array_part)])
                array_pos.append(pos)
            else:
                array_pos.append(None)

        return cls(
            _segments=segments,
            _raw_segments=raw_segments,
            _array_pos=array_pos,
            _dereference_index=dereference_index
        )

    def compute_address_offset(self, array_segments_dict: Mapping[str, Array], ignore_leading_segments: int = 0) -> int:
        """Tells by how many bytes an address should be shifted to find the referenced element
        based of the information encoded in the path"""
        path2pos = self.get_path_to_array_pos_dict(skip_first_segments=ignore_leading_segments)

        if len(path2pos) != len(array_segments_dict):
            raise ValueError(f"Cannot compute array offset. Array nodes count does not match for path: {self.to_str()}.")

        path_by_length = sorted(list(array_segments_dict.keys()), key=lambda x: len(x))
        byte_offset = 0
        for k in reversed(path_by_length):
            if k not in path2pos:
                raise ValueError("The array identifiers does not match the variable definition. Array not indexed")
            pos = path2pos[k]
            array = array_segments_dict[k]
            try:
                byte_offset += array.byte_position_of(pos)
            except Exception as e:
                raise ValueError(f'The array identifiers does not match the variable definition. {e}')

        return byte_offset

    @staticmethod
    def resolve_pointer_path(unresolved_path: str, input_path: "ScrutinyPath", pointer_array_segments: Mapping[str, Array]) -> Optional["ScrutinyPath"]:
        unresolved_segments = path_tools.make_segments(unresolved_path)
        resolved_segments = input_path.get_segments()

        if len(resolved_segments) < len(unresolved_segments):
            return None

        resolved_segments = resolved_segments[0:len(unresolved_segments)]
        if resolved_segments[-1].startswith('*'):
            resolved_segments[-1] = resolved_segments[-1][1:]

        resolved_path = path_tools.join_segments(resolved_segments)
        resolved_path_parsed = ScrutinyPath.from_string(resolved_path)
        resolved_path_parsed.compute_address_offset(pointer_array_segments)   # We use this just for validation

        return resolved_path_parsed
