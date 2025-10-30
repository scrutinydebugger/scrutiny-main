#    component_app_interface.py
#        The interface to the Scrutiny app seen by the components
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

import abc

from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.core.server_manager import ServerManager


class AbstractComponentAppInterface(abc.ABC):

    watchable_registry: WatchableRegistry
    server_manager: ServerManager

    @abc.abstractmethod
    def reveal_varlist_fqn(self, fqn: str) -> None:
        pass
