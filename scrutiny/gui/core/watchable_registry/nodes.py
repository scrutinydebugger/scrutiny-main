#    nodes.py
#        Nodes of the tree structure used by the WatchableRegistry
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['ServerStorageEntryNode', 'WatchableRegistryIntermediateNode']


from dataclasses import dataclass
from scrutiny.tools.typing import *
from scrutiny.sdk import listeners
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.core.watchable_registry.common import WatcherIdType, RegistryNodeConfiguration, RegistryNodeType, MathUpdate, RegistryValueUpdate
from scrutiny.gui.core.watchable_registry.watcher import WatcherData, Watcher, WatcherAndDataPair
from scrutiny.gui.core.watchable_registry.errors import WatchableRegistryError
from scrutiny.gui.core.watchable_registry.fqn import FQN

if TYPE_CHECKING:
    from scrutiny.gui.core.watchable_registry.watchable_registry import WatchableRegistry


class BaseRegistryStorable:
    __slots__ = ('registry_id', )

    registry_id: int

    def __init__(self, node_id: int) -> None:
        self.registry_id = node_id


class ServerStorageEntryNode(BaseRegistryStorable):
    """Leaf node in the tree that is a single watchable"""
    __slots__ = ('configuration', 'server_path', '_watcher_data')

    configuration: RegistryNodeConfiguration
    server_path: str
    _watcher_data: Dict[WatcherIdType, WatcherData]

    def __init__(self, node_id: int, server_path: str, config: RegistryNodeConfiguration) -> None:
        super().__init__(node_id)

        self.server_path = server_path
        self.configuration = config
        self._watcher_data = {}

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


class MathProxy(BaseRegistryStorable):
    __slots__ = ('registry', 'math_watchable', '_watchers', '_unwatch_in_progress', '_signature', '__weakref__')

    registry: "WatchableRegistry"
    math_watchable: GUIMathWatchable
    _watchers: Dict[WatcherIdType, WatcherAndDataPair]
    _unwatch_in_progress: bool
    _signature: str

    def __init__(self, node_id: int, registry: "WatchableRegistry", math_watchable: GUIMathWatchable) -> None:
        super().__init__(node_id)
        assert math_watchable.is_fully_configured()
        self.registry = registry
        self._watchers = {}
        self.math_watchable = math_watchable
        self.registry.register_watcher(self.registry_id, self._update_callback, self._unwatch_callback)
        self._unwatch_in_progress = False
        self._signature = math_watchable.signature()

    def notify_registry_insert(self) -> None:
        if len(self._watchers) > 0:
            self._try_watch_all()

    def _compute_highest_update_rate(self) -> Optional[float]:
        rate: Optional[float] = 0.0
        for watcher_id, watcher_and_data in self._watchers.items():
            if watcher_and_data.data.update_rate is None:
                rate = None
                break
            assert rate is not None
            rate = max(rate, watcher_and_data.data.update_rate)
        return rate

    def _unwatch_all(self) -> None:
        self._unwatch_in_progress = True
        for varname, fqn_name_pair in self.math_watchable.get_var_fqn_map().items():
            if fqn_name_pair is None:   # Not supposed to happen. Be safe
                continue
            try:
                self.registry.unwatch_fqn(self.registry_id, fqn_name_pair.fqn)
            except WatchableRegistryError:
                pass
        self._unwatch_in_progress = False

    def _try_watch_all(self) -> bool:
        success = True
        highest_update_rate = self._compute_highest_update_rate()
        for varname, fqn_name_pair in self.math_watchable.get_var_fqn_map().items():
            if fqn_name_pair is None:   # Not supposed to happen. Be safe
                success = False
                break

            try:
                # We have a guarantee that a math element can't watch another math element, therefore
                # preventing infinite circular watch.
                self.registry.watch_fqn(self.registry_id, fqn_name_pair.fqn, highest_update_rate)
            except WatchableRegistryError:
                success = False
                break

        if not success:
            self._unwatch_all()

        return success

    def _update_callback(self, watcher_id: WatcherIdType, updates: List["RegistryValueUpdate"]) -> None:
        new_updates: List["RegistryValueUpdate"] = []
        signature = self.math_watchable.signature()
        for update in updates:
            update_fqn = FQN.make(update.node_type, update.sdk_update.get_source_id())
            self.math_watchable.assign_var_value_by_fqn(update_fqn, update.sdk_update.value)
            val = self.math_watchable.eval()
            if val is not None:
                new_updates.append(RegistryValueUpdate(
                    node_type=RegistryNodeType.Math,
                    registry_id=self.registry_id,
                    sdk_update=MathUpdate(val, signature, update.sdk_update.update_timestamp)
                ))

        if len(new_updates) > 0:
            for watcher_id, pair in self._watchers.items():
                pair.watcher.value_update_callback(watcher_id, new_updates)

    def _unwatch_callback(self, watcher_id: WatcherIdType, server_path: str, registry_id: int) -> None:
        pass

    def add_or_update_watcher(self, watcher: Watcher, update_rate: Optional[float]) -> None:
        self._watchers[watcher.watcher_id] = WatcherAndDataPair(watcher, WatcherData(update_rate=update_rate))
        self._try_watch_all()

    def has_watcher(self, watcher_id: WatcherIdType) -> bool:
        return watcher_id in self._watchers

    def remove_watcher(self, watcher_id: WatcherIdType) -> None:
        if watcher_id in self._watchers:
            del self._watchers[watcher_id]

            if len(self._watchers) == 0:
                self._unwatch_all()

    def get_watcher_count(self) -> int:
        return len(self._watchers)

    def get_signature(self) -> str:
        return self._signature


@dataclass(frozen=True, slots=True)
class WatchableRegistryIntermediateNode:
    """An intermediate node that contains watchable and other subnodes"""

    watchables: Dict[str, ServerStorageEntryNode]
    subtree: List[str]
