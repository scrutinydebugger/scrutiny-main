#    path_tools.py
#        Tools for scrutiny path manipulation
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from scrutiny.tools.typing import *


def make_segments(path: str) -> List[str]:
    """Splits a path string into an list of string segments"""
    pieces = path.split('/')
    return [segment for segment in pieces if segment]


def join_segments(segments: List[str]) -> str:
    """Joins a list of string segments into a path string"""
    return '/' + '/'.join(segments)
