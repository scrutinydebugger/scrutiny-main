#    demangled_name_parser.py
#        Converts demangled linkage names to a list of path segments
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['CppDemangledNameParser', 'RustDemangledNameParser']

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


class RustDemangledNameParser:
    """Parse names demangled from the Rust schemes"""

    # Crate disambiguator, ex: rust_testapp[3f7a14bcb36fbfb0]. Only an identifier can precede it. Arrays/slices are always preceded by a non-word char.
    CRATE_HASH_REGEX: re.Pattern[str] = re.compile(r'(?<=\w)\[[a-fA-F0-9]+\]')

    @staticmethod
    def parse_demangled_name(name: str) -> List[str]:
        """Transform a Rust demangled path to a path like structure.
        crate[hash]::module::func::STATIC                     --> crate/module/func/STATIC
        <crate[hash]::module::Type>::method::STATIC           --> crate/module/Type/method/STATIC
        <crate[hash]::module::Type as crate[hash]::Trait>::method::STATIC --> crate/module/Type/Trait/method/STATIC
        """
        name = RustDemangledNameParser.CRATE_HASH_REGEX.sub('', name)
        segments = RustDemangledNameParser._split_top_level(name, '::')
        first_segment = segments[0]
        # rustc only emits a qualified path <Type> or <Type as Trait> as the first segment. It identifies the impl block.
        if first_segment.startswith('<') and first_segment.endswith('>'):
            root_segments = RustDemangledNameParser._expand_qualified_root(first_segment[1:-1])
            segments = root_segments + segments[1:]
        return segments

    @staticmethod
    def _expand_qualified_root(root: str) -> List[str]:
        """Converts the content of a <Type> or <Type as Trait> root to a list of segments"""
        as_parts = RustDemangledNameParser._split_top_level(root, ' as ')
        self_type = as_parts[0]

        if RustDemangledNameParser._is_path_type(self_type):
            segments = RustDemangledNameParser._split_top_level(self_type, '::')
        else:
            segments = [self_type]  # Arrays, tuples, references, dyn, fn pointers, etc. are kept as a single segment

        if len(as_parts) > 1:
            trait_path_segments = RustDemangledNameParser._split_top_level(as_parts[1], '::')
            segments.append(trait_path_segments[-1])

        return segments

    @staticmethod
    def _is_path_type(type_str: str) -> bool:
        """Tells if a demangled Rust type is a path (crate::module::Type<T>) as opposed to a structural type ([T; N], (A, B), &T, dyn T, fn(), etc.)"""
        if len(type_str) == 0:
            return False

        if type_str[0] in '[(&*<!':
            return False

        for prefix in ('dyn ', 'fn(', 'unsafe ', 'extern ', 'for<', 'impl '):
            if type_str.startswith(prefix):
                return False

        return True

    @staticmethod
    def _split_top_level(text: str, separator: str) -> List[str]:
        """Split a string on a separator, ignoring the occurrences that are inside brackets of any kind"""
        parts: List[str] = []
        depth = 0
        start = 0
        i = 0
        while i < len(text):
            if text.startswith('->', i):  # Return type of a fn pointer. Not a closing bracket
                i += 2
                continue

            c = text[i]
            if c in '<([{':
                depth += 1
            elif c in '>)]}':
                depth -= 1
            elif depth == 0 and text.startswith(separator, i):
                parts.append(text[start:i])
                i += len(separator)
                start = i
                continue
            i += 1

        parts.append(text[start:])
        return parts
