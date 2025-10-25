#    path_tools.py
#        Tools for scrutiny path manipulation
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['make_segments', 'join_segments']

from scrutiny.tools.typing import *


def make_segments(path: str) -> List[str]:
    """Splits a path string into an list of string segments"""
    pieces = path.split('/')
    return [segment for segment in pieces if segment]


def join_segments(segments: List[str]) -> str:
    """Joins a list of string segments into a path string"""
    return '/' + '/'.join(segments)


def is_subpath(subpath: str, path: str) -> bool:
    subpath_segments = make_segments(subpath)
    path_segments = make_segments(path)
    if len(subpath_segments) > len(path_segments):
        return False
    if len(subpath_segments) == 0:
        return False

    for i in range(len(subpath_segments)):
        if subpath_segments[i] != path_segments[i]:
            return False
    return True
