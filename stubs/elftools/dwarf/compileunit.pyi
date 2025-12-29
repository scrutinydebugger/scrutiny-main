#    compileunit.pyi
#        A stub file for the pyelftools package
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from elftools.dwarf.die import DIE
from elftools.dwarf.dwarfinfo import DWARFInfo

class CompileUnitHeader:
    debug_abbrev_offset:int
    address_size:int
    unit_length:int
    version :int

class CompileUnit:
    cu_offset: int
    header:CompileUnitHeader
    dwarfinfo:DWARFInfo

    def get_top_DIE(self) -> DIE: ...
