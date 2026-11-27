#    demangler.py
#        Converts mangled linkage names to readable symbols names
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

__all__ = ['BaseDemangler', 'GccDemangler']

import subprocess
import shutil
import abc
import enum

from scrutiny.tools.typing import *


class BaseDemangler(abc.ABC):
    class Format(enum.Enum):
        GnuV3 = 'gnu-v3'
        Rust = 'rust'

    def can_run(self) -> bool:
        return False

    def get_error(self) -> str:
        return "virtual class"

    def demangle(self, mangled: str, format:Format) -> str:
        raise NotImplementedError('Trying to demangle with base class')


class GccDemangler(BaseDemangler):
    """Class capable of demangling symbols names mangled by GCC. It uses the provided GCC c++filt utility"""

    _default_binary_name: str = "c++filt"

    binary_name: str
    error_details: str
    binary_found: bool

    def __init__(self, binary_name: Optional[str] = None) -> None:
        if binary_name is None:
            binary_name = self._default_binary_name
        self.binary_name = binary_name
        self.error_details = ""
        self.binary_found = shutil.which(self.binary_name) is not None

    def can_run(self) -> bool:
        """Returns True if c++filt is found on the system"""
        can_run = True
        if not self.binary_found:
            can_run = False
            self.error_details = 'Demangler binary "%s" is not in the path' % self.binary_name

        return can_run

    def get_error(self) -> str:
        """Returns why the demangler cannot run"""
        return self.error_details

    def demangle(self, mangled: str, format:BaseDemangler.Format) -> str:
        """Perform demangling on a mangled symbol name"""
        if not self.can_run():
            raise Exception('Cannot run demangler. %s' % self.get_error())

        format_args = []
        if format==self.Format.GnuV3:
            format_args = ['--format', 'gnu-v3']
        elif format==self.Format.Rust:
            format_args = ['--format', 'rust']

        self.process = subprocess.Popen([self.binary_name, '-n'] + format_args,
                                        stdout=subprocess.PIPE, stdin=subprocess.PIPE, universal_newlines=True, encoding='utf8')
        return self.process.communicate(input=mangled)[0]
