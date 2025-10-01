__all__ = ['ScrutinyPath']

from dataclasses import dataclass
import re
from scrutiny.tools.typing import *
from scrutiny.core.variable import UntypedArray, Array



@dataclass
class ScrutinyPath:
    _complex_path_segment_regex = re.compile(r'(.+?)((\[\d+\])+)$')
    __slots__ = ('segments', 'raw_segments', 'array_pos')

    segments:List[str]
    raw_segments: List[str]
    array_pos: List[Optional[Tuple[int, ...]]]

    def __str__(self) -> str:
        return self.to_str()
    
    def to_str(self) -> str:
        return self.join_segments(self.segments)

    def to_raw_str(self) -> str:
        return self.join_segments(self.raw_segments)

    @staticmethod
    def make_segments(path: str) -> List[str]:
        pieces = path.split('/')
        return [segment for segment in pieces if segment]

    @staticmethod
    def join_segments(segments: List[str]) -> str:
        return '/' + '/'.join(segments)
    
    def get_segments(self) -> List[str]:
        return self.segments.copy()

    def get_name_segment(self) -> str:
        return self.segments[-1]
    
    def get_segments_without_name(self) -> List[str]:
        return self.segments[:-1]

    def get_raw_segments(self) -> List[str]:
        return self.raw_segments.copy()

    def get_raw_name_segment(self) -> str:
        return self.raw_segments[-1]
    
    def get_raw_segments_without_name(self) -> List[str]:
        return self.raw_segments[:-1]
    
    def has_array_information(self) -> bool:
        for v in self.array_pos:
            if v is not None:
                return True
        return False

    def get_path_to_array_pos_dict(self) -> Dict[str, Tuple[int, ...]]:
        outdict: Dict[str, Tuple[int, ...]] = {}
        for i in range(len(self.array_pos)):
            pos = self.array_pos[i]
            if pos is not None:
                outdict[self.join_segments(self.raw_segments[:i + 1])] = pos

        return outdict

    @classmethod
    def from_string(cls, path: str) -> Self:
        """Parse a path with information encoded and extract it
        ex: /aaa/bbb[2][3]/ccc = /aaa/bbb/ccc + {array: /aaa/bbb, (2,3)}"""
        segments = cls.make_segments(path)
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
            segments = segments,
            raw_segments=raw_segments,
            array_pos=array_pos
        )

    def compute_address_offset(self, array_segments_dict:Mapping[str, Array]) -> int:
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
