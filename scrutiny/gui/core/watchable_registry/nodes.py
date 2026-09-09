
__all__ = ['WatchableRegistryEntryNode', 'WatchableRegistryIntermediateNode']


from dataclasses import dataclass
from scrutiny.tools.typing import *
from scrutiny.gui.core.watchable_registry.common import WatcherIdType, RegistryNodeConfiguration
from scrutiny.gui.core.watchable_registry.watcher import WatcherData
from scrutiny.gui.core.watchable_registry.errors import WatchableRegistryError


@dataclass(init=False, slots=True)
class WatchableRegistryEntryNode:
    """Leaf node in the tree that is a single watchable"""
    configuration: RegistryNodeConfiguration
    server_path: str
    registry_id: int
    _watcher_data: Dict[WatcherIdType, WatcherData]

    def __init__(self, node_id: int, server_path: str, config: RegistryNodeConfiguration) -> None:
        self.server_path = server_path
        self.configuration = config
        self._watcher_data = {}
        self.registry_id = node_id

    def get_watcher_count(self) -> int:
        return len(self._watcher_data)

    def add_watcher(self, watcher_id: WatcherIdType, update_rate: Optional[float]) -> None:
        if watcher_id in self._watcher_data:
            raise WatchableRegistryError(f"Watcher {watcher_id} already added to node {self.server_path}")
        self._watcher_data[watcher_id] = WatcherData(
            update_rate=update_rate
        )

    def remove_watcher(self, watcher_id: WatcherIdType) -> None:
        if watcher_id not in self._watcher_data:
            raise WatchableRegistryError(f"Watcher {watcher_id} not watching node {self.server_path}")
        del self._watcher_data[watcher_id]

    def get_highest_update_rate(self) -> Optional[float]:
        rates = [data.update_rate for data in self._watcher_data.values()]
        if len(rates) == 0:
            return None
        if None in rates:
            return None
        return max(cast(Sequence[float], rates))

    def iterate_watchers(self) -> Generator[WatcherIdType, None, None]:
        for watcher_id in self._watcher_data.keys():
            yield watcher_id


@dataclass(frozen=True, slots=True)
class WatchableRegistryIntermediateNode:
    """An intermediate node that contains watchable and other subnodes"""

    watchables: Dict[str, WatchableRegistryEntryNode]
    subtree: List[str]
