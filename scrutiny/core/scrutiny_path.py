#    scrutiny_path.py
#        A class that can manipulate and interpret a path refering to a watchable in the server
#        and cli toolchains.
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['ScrutinyPath']

from dataclasses import dataclass
import re
from scrutiny.tools.typing import *
from scrutiny.core.array import Array
from scrutiny.core import path_tools


@dataclass(slots=True)
class ScrutinyPath:
    """A class to manipulate and interpret paths used to refer to watchable elements across the project"""

    _complex_path_segment_regex = re.compile(r'(.+?)((\[\d+\])+)$')
    _segments: List[str]
    _raw_segments: List[str]
    _array_pos: List[Optional[Tuple[int, ...]]]

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

    def has_encoded_information(self) -> bool:
        """Tells if there is any information encoded in the path. Including arrays"""
        # Future proofing in case we encode more than just arrays
        return self.has_array_information()

    def get_path_to_array_pos_dict(self) -> Dict[str, Tuple[int, ...]]:
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
        for i in range(len(self._array_pos)):
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
        for i in range(len(segments)):
            m = cls._complex_path_segment_regex.match(segments[i])
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
            _segments=segments,
            _raw_segments=raw_segments,
            _array_pos=array_pos
        )

    def compute_address_offset(self, array_segments_dict: Mapping[str, Array]) -> int:
        """Tells by how many bytes an address should be shifted to find the referenced element
        based of the information encoded in the path"""
        path2pos = self.get_path_to_array_pos_dict()

        if len(path2pos) != len(array_segments_dict):
            raise ValueError("Cannot compute array offset. Array nodes count does not match.")

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
