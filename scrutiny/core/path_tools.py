
from scrutiny.tools.typing import *

def make_segments(path: str) -> List[str]:
    """Splits a path string into an list of string segments"""
    pieces = path.split('/')
    return [segment for segment in pieces if segment]

def join_segments(segments: List[str]) -> str:
    """Joins a list of string segments into a path string"""
    return '/' + '/'.join(segments)
