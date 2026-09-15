#    errors.py
#        Watchable Registry related errors
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = [
    'WatchableRegistryError',
    'WatchableRegistryNodeNotFoundError',
    'WatcherNotFoundError'
]


class WatchableRegistryError(Exception):
    pass


class WatchableRegistryNodeNotFoundError(WatchableRegistryError):
    pass


class WatcherNotFoundError(Exception):
    pass
