#    dummy_command.py
#        Fake Scrutiny protocol command for unit test purpose
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['DummyCommand']

from .base_command import BaseCommand
from enum import Enum

# For testing purpose.


class DummyCommand(BaseCommand):
    """Dummy command for testing purpose"""
    _cmd_id = 0

    class Subfunction(Enum):
        SubFn1 = 1
        SubFn2 = 2
        SubFn3 = 3
