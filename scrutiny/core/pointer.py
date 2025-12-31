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

from scrutiny.tools.typing import *

if TYPE_CHECKING:
    from scrutiny.core.struct import Struct


@dataclass(slots=True)
class Pointer:
    size: int
    pointed_type: Union[EmbeddedDataType, "Struct"]

    def get_size(self) -> int:
        return self.size
