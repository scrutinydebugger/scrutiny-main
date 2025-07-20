#    noop.py
#        A command that does nothing. It's sole purpose is to ease the integration with CMake
#        that is picky when using generator statements
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['NoopCommand']

import argparse
from .base_command import BaseCommand
from scrutiny.tools.typing import *


class NoopCommand(BaseCommand):
    _cmd_name_ = 'noop'
    _brief_ = 'A command that does nothing. Convenience for integrating with CMake and generator expressions.'
    _group_ = 'Build Toolchain'

    args: List[str]
    parser: argparse.ArgumentParser

    def __init__(self, args: List[str], requested_log_level: Optional[str] = None):
        self.args = args
        self.parser = argparse.ArgumentParser(prog=self.get_prog())
        self.parser.add_argument('args', nargs='*', help='Sink all arguments')

    def run(self) -> Optional[int]:
        # Do nothing on purpose
        return 0
