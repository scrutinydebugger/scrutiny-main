import abc

from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.core.server_manager import ServerManager

class AbstractComponentAppInterface(abc.ABC):

    @abc.abstractmethod
    def reveal_varlist_fqn(self, fqn:str) -> None:
        pass
