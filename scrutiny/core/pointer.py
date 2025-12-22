#    pointer.py
#        Represent a pointer
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['Pointer']


from dataclasses import dataclass

from scrutiny.core.variable_location import AbsoluteLocation
from scrutiny.core.basic_types import EmbeddedDataType


@dataclass(slots=True, frozen=True)
class Pointer:
    location: AbsoluteLocation
    pointed_type: EmbeddedDataType
