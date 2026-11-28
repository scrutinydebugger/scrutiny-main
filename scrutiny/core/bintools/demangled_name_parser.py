#    demangled_name_parser.py
#        Converts demangled linkage names to a list of path segments
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['CppDemangledNameParser']

import re

from scrutiny.tools.typing import *


class CppDemangledNameParser:
    """Parse names demangled from the GNU v3 (Itanium C++) scheme"""

    @staticmethod
    def parse_demangled_name(name: str) -> List[str]:
        """Transform a C++ nesting name to a path like structure
        namespace1::class2<T>::enum3::HELLO --> namespace1/class2<T>/enum3/HELLO
        """
        paranthesis_level = 0
        ducky_bracket_level = 0

        outname = ''
        is_in_bracket = False
        bracket_exit_pos = 0
        bracket_enter_pos = 0
        for i in range(len(name)):
            c = name[i]

            was_in_bracket = is_in_bracket
            if c == '(':
                paranthesis_level += 1
            elif c == ')':
                paranthesis_level -= 1
            elif c == '<':
                ducky_bracket_level += 1
            elif c == '>':
                ducky_bracket_level -= 1
            is_in_bracket = (paranthesis_level > 0 or ducky_bracket_level > 0)

            if not was_in_bracket and is_in_bracket:  # entering bracket
                bracket_enter_pos = i
                outname += name[bracket_exit_pos:i].replace('::', ';')

            if was_in_bracket and not is_in_bracket:    # exiting bracket
                bracket_exit_pos = i
                outname += name[bracket_enter_pos:i]    # No replace on purpose

        outname += name[bracket_exit_pos:].replace('::', ';')
        return outname.split(';')

