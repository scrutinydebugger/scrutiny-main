#    watchable_registry.py
#        A storage object that keeps a local copy of all the watchable (Variable/Alias/RPV)
#        available on the server.
#        Lots of overlapping feature with the server datastore, with few fundamentals differences.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2024 Scrutiny Debugger

__all__ = [
    'WatchableRegistry',
]


from dataclasses import dataclass
import logging

from scrutiny import sdk
from scrutiny.sdk.listeners import ValueUpdate
from scrutiny.gui.core.threads import QT_THREAD_NAME
from scrutiny import tools
from scrutiny.tools.thread_enforcer import enforce_thread
from scrutiny.tools.typing import *
from scrutiny.core import path_tools
from scrutiny.gui.core.watchable_registry.server_registry_bidirectional_map import ServerRegistryBidirectionalMap
from scrutiny.gui.core.watchable_registry.common import WatcherIdType
from scrutiny.gui.core.watchable_registry.errors import WatchableRegistryNodeNotFoundError, WatcherNotFoundError
from scrutiny.gui.core.watchable_registry.common import (RegistryValueUpdate, GlobalWatchCallback, GlobalUnwatchCallback,
                                                         WatcherValueUpdateCallback, UnwatchCallback, GlobalWatchCallbackData,
                                                         RegistryNodeConfiguration, RegistryNodeType)
from scrutiny.gui.core.watchable_registry.nodes import WatchableRegistryEntryNode, WatchableRegistryIntermediateNode
from scrutiny.gui.core.watchable_registry.watcher import Watcher
from scrutiny.gui.core.watchable_registry.errors import WatchableRegistryError
from scrutiny.gui.core.watchable_registry.fqn import FQN


class WatchableRegistry:
    """Contains a copy of the watchable list available on the server side
    Act as a relay to dispatch value update event to the internal widgets"""

    @dataclass(frozen=True, slots=True)
    class Statistics:
        """(Immutable struct) Internal metrics for debugging and diagnostics"""
        watched_entries_count: int
        registered_watcher_count: int
        alias_count: int
        rpv_count: int
        var_count: int
        math_count: int

    _trees: Dict[RegistryNodeType, Any]
    """The main storage of the registry, implemented with recursive dicts"""
    _watchable_count: Dict[RegistryNodeType, int]
    """A summary count of the number of watchables in the registry, grouped by type"""
    _global_watch_callbacks: Optional[GlobalWatchCallback]
    """A callback to be called whenever any watcher starts watching a node """
    _global_unwatch_callbacks: Optional[GlobalUnwatchCallback]
    """A callback to be called whenever any watcher stops watching a node """
    _logger: logging.Logger
    """The logger object"""
    _tree_change_counters: Dict[RegistryNodeType, int]
    """Counter keeping track how many times the tree is being modified, grouped by watchable entry. Mostly used to trigger "change" event from the server manager"""
    _watchers: Dict[WatcherIdType, Watcher]
    """A dict mapping a watcher ID to its watcher object"""
    _watched_entries: Dict[int, WatchableRegistryEntryNode]
    """Dict mapping a registry ID to a node being watched"""
    _node_counter: int
    """Used to generate incrementing registry IDs to assign on watchables"""
    _serverid_map: Dict[RegistryNodeType, ServerRegistryBidirectionalMap]
    """Bidirectional maps, mapping Server ID to Registry ID, grouped by watchable types"""

    def __init__(self) -> None:
        self._trees = {}
        self._tree_change_counters = {}
        self._watchable_count = {}
        self._serverid_map = {}

        for watchable_type in RegistryNodeType:
            self._trees[watchable_type] = {}
            self._tree_change_counters[watchable_type] = 0
            self._watchable_count[watchable_type] = 0
            self._serverid_map[watchable_type] = ServerRegistryBidirectionalMap()

        self._watchers = {}
        self._watched_entries = {}
        self._global_watch_callbacks = None
        self._global_unwatch_callbacks = None
        self._logger = logging.getLogger(self.__class__.__name__)
        self._node_counter = 0

    @enforce_thread(QT_THREAD_NAME)
    def _make_node_id(self) -> int:
        """Create a unique registry ID"""
        v = self._node_counter
        self._node_counter += 1
        return v

    @enforce_thread(QT_THREAD_NAME)
    def _add_watchable(self, path: str, config: Union[sdk.BriefWatchableConfiguration, RegistryNodeConfiguration]) -> WatchableRegistryEntryNode:
        """Adds a single watchable to the tree storage

        :param path: Path to add the node to
        :param config: Watchable config object. Represent a set of watchable properties

        """
        parts = path_tools.make_segments(path)
        if len(parts) == 0:
            raise WatchableRegistryError(f"Empty path : {path}")
        if isinstance(config, sdk.BriefWatchableConfiguration):
            config = RegistryNodeConfiguration.from_sdk(config)
        node = self._trees[config.node_type]
        for i in range(len(parts) - 1):
            part = parts[i]
            if part not in node:
                node[part] = {}
            node = node[part]
        if parts[-1] in node:
            raise WatchableRegistryError(f"Cannot insert a watchable at location {path}. Another watchable already uses that path.")

        created_node = WatchableRegistryEntryNode(
            self._make_node_id(),
            server_path=path,  # Required for proper error messages.
            config=config
        )
        node[parts[-1]] = created_node
        self._watchable_count[config.node_type] += 1

        return created_node

    @enforce_thread(QT_THREAD_NAME)
    def _get_node(self, node_type: RegistryNodeType, path: str) -> Union[WatchableRegistryIntermediateNode, WatchableRegistryEntryNode]:
        """Read a node in the tree and locks the tree while doing it."""
        parts = path_tools.make_segments(path)
        node = self._trees[node_type]
        for part in parts:
            if part not in node:
                raise WatchableRegistryNodeNotFoundError(f"Inexistent path : {path} ")
            node = node[part]

        if isinstance(node, dict):
            return WatchableRegistryIntermediateNode(
                watchables=dict((name, val) for name, val in node.items() if isinstance(val, WatchableRegistryEntryNode)),
                subtree=[name for name, val in node.items() if isinstance(val, dict)]
            )
        elif isinstance(node, WatchableRegistryEntryNode):
            return node
        else:
            raise WatchableRegistryError(f"Unexpected item of type {node.__class__.__name__} inside the registry")

    @enforce_thread(QT_THREAD_NAME)
    def assign_serverid_to_node_by_registry_id(self, node_type: Union[sdk.WatchableType, RegistryNodeType], registry_id: int, server_id: str) -> None:
        """Assign a server ID to a watchable node so it can be looked up later when a value update must be broadcast.

        :param node_type: The type of watchable node
        :param registry_id: The registry ID of the node
        :param server_id: The server ID to assign
        """
        if isinstance(node_type, sdk.WatchableType):
            node_type = RegistryNodeType.from_sdk(node_type)
        self._serverid_map[node_type].map(registry_id, server_id)

    @enforce_thread(QT_THREAD_NAME)
    def assign_serverid_to_node(self, node_type: RegistryNodeType, path: str, server_id: str) -> None:
        """Assign a server ID to a watchable node so it can be looked up later when a value update must be broadcast

        :param node_type: The type of watchable node
        :param path: The tree path of the targeted node. Must point to a watchable node
        :param server_id: The server ID to assign
        """
        node = self.get_watchable_node(node_type, path)
        if node is None:
            self._logger.error(f"Failed to assign a server ID to {path}")
            return

        self.assign_serverid_to_node_by_registry_id(node_type, node.registry_id, server_id)

    def assign_serverid_to_node_fqn(self, fqn: str, server_id: str) -> None:
        """Assign a server ID to a watchable node so it can be looked up later when a value update must be broadcast.

        :param fqn: The node Fully Qualified Name
        :param server_id: The server ID to assign
        """
        parsed = FQN.parse(fqn)
        self.assign_serverid_to_node(parsed.node_type, parsed.path, server_id)

    @enforce_thread(QT_THREAD_NAME)
    def clear_serverid_from_node_by_registry_id(self, node_type: RegistryNodeType, registry_id: int) -> None:
        """Removes the server ID associated with a registry node."""
        self._serverid_map[node_type].unmap_by_registry_id(registry_id)

    @enforce_thread(QT_THREAD_NAME)
    def clear_serverid_from_node(self, node_type: Union[sdk.WatchableType, RegistryNodeType], path: str) -> None:
        if isinstance(node_type, sdk.WatchableType):
            node_type = RegistryNodeType.from_sdk(node_type)
        node = self.get_watchable_node(node_type, path)
        if node is None:
            self._logger.error(f"Failed to clear the server ID onto {path}")
            return

        self.clear_serverid_from_node_by_registry_id(node_type, node.registry_id)

    @enforce_thread(QT_THREAD_NAME)
    def broadcast_value_updates_to_watchers(self, updates: List[ValueUpdate]) -> None:
        """Broadcast a list of SDK ValueUpdates created by a listener to all the registry watchers.
        This method will use the ValueUpdate server ID property to find the corresponding registry entry, then
        forward to every watchers of that entry

        :param updates: List of ValueUpdates
        """
        update_by_watchers: Dict[Union[str, int], List[RegistryValueUpdate]] = {}
        for update in updates:
            node_type = RegistryNodeType.from_sdk(update.watchable.type)
            registry_id = self._serverid_map[node_type].get_registry_id_or_none(update.watchable.server_id)
            try:
                if registry_id is None:  # Ignore the update if there is no server ID associated
                    continue
                node = self._watched_entries[registry_id]
            except KeyError:
                continue

            for watcher_id in node.iterate_watchers():
                if watcher_id not in update_by_watchers:
                    update_by_watchers[watcher_id] = []

                registry_update = RegistryValueUpdate(
                    sdk_update=update,
                    registry_id=registry_id,
                    node_type=RegistryNodeType.from_sdk(update.watchable.type))
                update_by_watchers[watcher_id].append(registry_update)

        for watcher_id, filtered_updates in update_by_watchers.items():
            self._watchers[watcher_id].value_update_callback(watcher_id, filtered_updates)

    @enforce_thread(QT_THREAD_NAME)
    def register_watcher(self,
                         watcher_id: WatcherIdType,
                         value_update_callback: WatcherValueUpdateCallback,
                         unwatch_callback: UnwatchCallback,
                         ignore_duplicate: bool = False) -> None:
        """Register a watcher to the registry. A watcher must be registered prior to watching an element.

        :param watcher_id: A string identifying the watcher
        :param value_update_callback: The callback to be called when a ValueUpdate is received
        :param unwatch_callback: A callback to be called when the watcher unwatch an element. Can be triggered by :meth:`unwatch<scrutiny.gui.core.watchable_registry.WatchableRegistry.unwatch>`
            or by the element being watched becoming unavailable
        :param ignore_duplicate: A string identifying the watcher

        """
        # Create the Watcher first to validate the args
        watcher = Watcher(
            watcher_id=watcher_id,
            value_update_callback=value_update_callback,
            unwatch_callback=unwatch_callback
        )

        if watcher_id in self._watchers:
            if ignore_duplicate:
                return
            raise WatchableRegistryError(f"Duplicate watcher with ID {watcher_id}")

        self._watchers[watcher_id] = watcher

    @enforce_thread(QT_THREAD_NAME)
    def unregister_watcher(self, watcher_id: WatcherIdType) -> None:
        self.unwatch_all(watcher_id)

        with tools.SuppressException(KeyError):
            del self._watchers[watcher_id]

    def registered_watcher_count(self) -> int:
        """Return the number of active registered watchers"""
        return len(self._watchers)

    def watch_fqn(self, watcher_id: WatcherIdType, fqn: str, update_rate: Optional[float] = None) -> int:
        """Adds a watcher on the given watchable and register a callback to be
        invoked when its value is updated

        :param watcher_id: A string/int that identifies the owner of the callback. Passed back when the callback is invoked
        :param fqn: The watchable fully qualified name
        :param update_rate: The update rate to request the server with. ``None`` means as fast as possible
        :return: The registry ID assigned to the value updates that will be broadcast for that item
        """
        parsed = FQN.parse(fqn)
        return self.watch(watcher_id, parsed.node_type, parsed.path, update_rate)

    @enforce_thread(QT_THREAD_NAME)
    def watch(self, watcher_id: WatcherIdType, node_type: RegistryNodeType, path: str, update_rate: Optional[float] = None) -> int:
        """Adds a watcher on the given watchable and register a callback to be
        invoked when its value is updated

        :param watcher_id: A string/int that identifies the owner of the callback. Passed back when the callback is invoked
        :param node_type: The watchable type
        :param path: The watchable tree path
        :param update_rate: The update rate to request the server with. ``None`` means as fast as possible

        :return: The registry ID assigned to the value updates that will be broadcast for that item
        """
        watcher: Optional[Watcher] = None
        with tools.SuppressException(KeyError):
            watcher = self._watchers[watcher_id]

        if watcher is None:
            raise WatcherNotFoundError(f"No watchers with ID {watcher_id}")

        node = self._get_node(node_type, path)
        if not isinstance(node, WatchableRegistryEntryNode):
            raise WatchableRegistryError("Cannot watch something that is not a Watchable")

        self._watched_entries[node.registry_id] = node
        added = False
        if node.registry_id not in watcher.subscribed_registry_id:
            watcher.subscribed_registry_id.add(node.registry_id)
            node.add_watcher(watcher.watcher_id, update_rate=update_rate)
            added = True

        if added and self._global_watch_callbacks is not None:
            data = GlobalWatchCallbackData(
                watcher_id=watcher_id,
                server_path=node.server_path,
                node_config=node.configuration,
                registry_id=node.registry_id,
                watcher_count=node.get_watcher_count(),
                highest_update_rate=node.get_highest_update_rate()
            )
            self._global_watch_callbacks(data)

        return node.registry_id

    @enforce_thread(QT_THREAD_NAME)
    def _unwatch_node_list(self, nodes: Iterable[WatchableRegistryEntryNode], watcher: Watcher) -> None:
        """Make a watcher unwatch multiple registry elements

        :param nodes: List of element to unwatch
        :param watcher: The target watcher
        """
        removed_list: List[WatchableRegistryEntryNode] = []
        for node in nodes:
            if node.registry_id in watcher.subscribed_registry_id:
                fqn = FQN.make(node.configuration.node_type, node.server_path)
                try:
                    watcher.unwatch_callback(watcher.watcher_id, fqn, node.configuration, node.registry_id)
                except Exception as e:
                    msg = f"Error in unwatch_callback callback for watcher ID {watcher.watcher_id} while unwatching {fqn}"
                    tools.log_exception(self._logger, e, msg)

                watcher.subscribed_registry_id.remove(node.registry_id)
                removed_list.append(node)
                node.remove_watcher(watcher.watcher_id)
                if node.get_watcher_count() == 0:
                    with tools.SuppressException(KeyError):
                        del self._watched_entries[node.registry_id]

        # Callback is outside of lock on purpose to allow it to access the registry too. Deadlock will happen otherwise
        if self._global_unwatch_callbacks is not None:
            for node in removed_list:
                data = GlobalWatchCallbackData(
                    watcher_id=watcher.watcher_id,
                    server_path=node.server_path,
                    node_config=node.configuration,
                    registry_id=node.registry_id,
                    watcher_count=node.get_watcher_count(),
                    highest_update_rate=node.get_highest_update_rate()
                )
                self._global_unwatch_callbacks(data)

    @enforce_thread(QT_THREAD_NAME)
    def unwatch_all(self, watcher_id: WatcherIdType) -> None:
        """Unwatch every registry entry presently watched by the given watcher

        :param watcher_id: The unique ID of the watcher
        """
        try:
            watcher = self._watchers[watcher_id]
        except KeyError:
            raise WatcherNotFoundError(f"No watchers with ID {watcher_id}")

        nodes: List[WatchableRegistryEntryNode] = []
        for registry_id in watcher.subscribed_registry_id:
            with tools.LogException(self._logger, KeyError, "Missing node in watched_entry", str_level=logging.WARNING):
                nodes.append(self._watched_entries[registry_id])

        self._unwatch_node_list(nodes, watcher)

    @enforce_thread(QT_THREAD_NAME)
    def unwatch(self, watcher_id: WatcherIdType, node_type: RegistryNodeType, path: str) -> None:
        """Remove a the given watcher from the watcher list of the given node.

        :param watcher_id: A string/int that identifies the owner of the callback. Passed back when the callback is invoked
        :param node_type: The watchable type
        :param path: The watchable tree path
        """
        try:
            watcher = self._watchers[watcher_id]
        except KeyError:
            raise WatcherNotFoundError(f"No watchers with ID {watcher_id}")

        node = self._get_node(node_type, path)
        if not isinstance(node, WatchableRegistryEntryNode):
            raise WatchableRegistryError("Cannot unwatch something that is not a Watchable")

        self._unwatch_node_list([node], watcher)

    def unwatch_fqn(self, watcher_id: WatcherIdType, fqn: str) -> None:
        """Remove a the given watcher from the watcher list of the given node.

        :param watcher_id: A string/int that identifies the owner of the callback. Passed back when the callback is invoked
        :param fqn: The fully qualified name
        """
        parsed = FQN.parse(fqn)
        self.unwatch(watcher_id, parsed.node_type, parsed.path)

    def watcher_count_by_registry_id(self, registry_id: int) -> int:
        """Return the number of watcher on a node, identified by its registry_id

        :param registry_id: The watchable registry_id
        :return: The number of watchers
        """
        try:
            entry = self._watched_entries[registry_id]
        except KeyError:
            return 0
        return entry.get_watcher_count()

    def node_watcher_count_fqn(self, fqn: str) -> Optional[int]:
        """Return the number of watcher on a node

        :param fqn: The watchable fully qualified name
        :return: The number of watchers
        """
        parsed = FQN.parse(fqn)
        return self.node_watcher_count(parsed.node_type, parsed.path)

    def node_watcher_count(self, node_type: RegistryNodeType, path: str) -> Optional[int]:
        """Return the number of watcher on a node

        :param node_type: The registry node type
        :param path: The watchable tree path
        :return: The number of watchers
        """
        node = self._get_node(node_type, path)
        if not isinstance(node, WatchableRegistryEntryNode):
            self._logger.debug("Cannot get the watcher count of something that is not a Watchable")
            return None
        return node.get_watcher_count()

    def watched_entries_count(self) -> int:
        """Return the total number of watchable being watched"""
        return len(self._watched_entries)

    @enforce_thread(QT_THREAD_NAME)
    def read(self, node_type: RegistryNodeType, path: str) -> Optional[Union[WatchableRegistryIntermediateNode, WatchableRegistryEntryNode]]:
        """Read a node inside the registry.

        :node_type: The type of node to read
        :path: The tree path of the node

        :return: The node content. Either a watchable or a description of the subnodes
        """
        try:
            return self._get_node(node_type, path)
        except WatchableRegistryNodeNotFoundError:
            return None
        except WatchableRegistryError as e:
            tools.log_exception(self._logger, e)
            return None

    def read_fqn(self, fqn: str) -> Optional[Union[WatchableRegistryIntermediateNode, WatchableRegistryEntryNode]]:
        """Read a node inside the registry using a fully qualified name.

        :param fqn: The fully qualified name created using ``make_fqn()``

        :return: The node content. Either a watchable or a description of the subnodes
        """
        parsed = FQN.parse(fqn)
        return self.read(parsed.node_type, parsed.path)

    def get_watchable_node_fqn(self, fqn: str) -> Optional[WatchableRegistryEntryNode]:
        """Access a node from the registry and return it if it is a watchable node. Returns ``None`` if no node exist or if the accessed node is not a Watchable

        :param fqn: The node Fully Qualified Name
        :return: The node referred to by the given FQN
        """
        node = self.read_fqn(fqn)
        if not isinstance(node, WatchableRegistryEntryNode):
            return None
        return node

    def get_watchable_node(self, node_type: RegistryNodeType, path: str) -> Optional[WatchableRegistryEntryNode]:
        """Access a node from the registry and return it if it is a watchable node. Returns ``None`` if no node exist or if the accessed node is not a Watchable

        :node_type: The type of node to read
        :path: The tree path of the node
        :return: The node referred to by the given path
        """

        node = self.read(node_type, path)
        if not isinstance(node, WatchableRegistryEntryNode):
            return None
        return node

    def get_server_id_fqn(self, fqn: str) -> Optional[str]:
        """Reads the associated Server ID of a node. Returns ``None`` if :
          - The node does not exist
          - The node is not a watchable
          - There is no Server ID associated with that node

          :param fqn: The node Fully Qualified Name
          :return: The server ID of the node or ``None`` if not available
          """
        parsed = FQN.parse(fqn)
        return self.get_server_id(parsed.node_type, parsed.path)

    def get_server_id(self, node_type: RegistryNodeType, path: str) -> Optional[str]:
        """Reads the associated Server ID of a node. Returns ``None`` if :
          - The node does not exist
          - The node is not a watchable
          - There is no Server ID associated with that node

        :node_type: The type of node to read
        :path: The tree path of the node

        :return: The server ID of the node or ``None`` if not available
        """

        node = self.get_watchable_node(node_type, path)
        if node is None:
            return None
        return self._serverid_map[node.configuration.node_type].get_server_id_or_none(node.registry_id)

    def is_watchable_fqn(self, fqn: str) -> bool:
        """Tells if the item referred to by the Fully Qualified Name exists and is a watchable.

        :param fqn: The fully qualified name created using ``make_fqn()``

        :return: ``True`` if exists and is a watchable
        """
        node = self.read_fqn(fqn)
        return isinstance(node, WatchableRegistryEntryNode)

    @enforce_thread(QT_THREAD_NAME)
    def write_content(self, data: Dict[RegistryNodeType, Dict[str, sdk.BriefWatchableConfiguration]]) -> None:
        """Write content of the given types.
        Triggers ``changed``.  May trigger ``filled`` if all types have data after calling this function.

        :param data: The data to add. Classified in dict[watchable_type][path].
        """
        touched: Dict[RegistryNodeType, bool] = {node_type: False for node_type in RegistryNodeType}

        for node_type in data.keys():
            if len(data[node_type]) > 0:
                self.clear_content_by_type(node_type)

        for subdata in data.values():
            for path, wc in subdata.items():
                created_node = self._add_watchable(path, wc)
                touched[created_node.configuration.node_type] = True

        for node_type in touched:
            if touched[node_type]:
                self._tree_change_counters[node_type] += 1

    @enforce_thread(QT_THREAD_NAME)
    def clear_content_by_type(self, node_types: Union[RegistryNodeType, Iterable[RegistryNodeType]]) -> bool:
        """
        Clear the content of the given type from the registry.
        May triggers ``changed`` and ``cleared`` if data was actually removed.

        :return: ``True`` if data was removed. ``False`` if the nothing was removed (already empty)
        """
        if isinstance(node_types, RegistryNodeType):
            node_types = [node_types]
        self._logger.debug(f"Clearing content for types {node_types}")
        changed = False

        for node_type in node_types:
            had_data = len(self._trees[node_type]) > 0

            to_unwatch: List[WatchableRegistryEntryNode] = []
            for entry in self._watched_entries.values():
                if entry.configuration.node_type == node_type:
                    to_unwatch.append(entry)

            to_unwatch_per_watcher: Dict[WatcherIdType, List[WatchableRegistryEntryNode]] = {}
            for entry in to_unwatch:
                for watcher in self._watchers.values():
                    if entry.registry_id in watcher.subscribed_registry_id:
                        if watcher.watcher_id not in to_unwatch_per_watcher:
                            to_unwatch_per_watcher[watcher.watcher_id] = []
                        to_unwatch_per_watcher[watcher.watcher_id].append(entry)

            for watcher_id, node_list in to_unwatch_per_watcher.items():
                self._unwatch_node_list(node_list, self._watchers[watcher_id])

            for entry in to_unwatch:
                if entry.registry_id in self._watched_entries:
                    self._logger.error(f"Inconsistency in Watchable Registry. Entry {entry.server_path} is still watched, but has no watcher")
                    del self._watched_entries[entry.registry_id]    # Resilience on error

            if had_data:
                changed = True
                self._tree_change_counters[node_type] += 1
            self._trees[node_type] = {}
            self._watchable_count[node_type] = 0

        total_remaining_data = 0
        for t in RegistryNodeType:
            total_remaining_data += self.get_watchable_count(t)
        if total_remaining_data == 0:
            self._node_counter = 0  # Avoid growing forever

        return changed

    @enforce_thread(QT_THREAD_NAME)
    def clear(self) -> bool:
        """
        Clear all the content from the registry.

        :return: ``True`` if data was removed. ``False`` if the nothing was removed (already empty)
        """
        had_data = False
        for node_type in RegistryNodeType:  # Enums are iterable
            temp = self.clear_content_by_type(node_type)
            had_data = had_data or temp

        if len(self._watched_entries) > 0:
            self._logger.critical("Failed to clear the registry properly. _watched_entries is not empty")

        for watcher in self._watchers.values():
            if len(watcher.subscribed_registry_id) > 0:
                self._logger.critical(f"Failed to clear the registry properly. watcher {watcher.watcher_id} still have registered nodes")

        return had_data

    def has_data(self, node_type: RegistryNodeType) -> bool:
        """Tells if there is data of the given type inside the registry

        :param watchable_type: The type of watchable to look for
        :return: ``True`` if there is data of that type. ``False otherwise``
        """
        return len(self._trees[node_type]) > 0

    def register_global_watch_callback(self, watch_callback: GlobalWatchCallback, unwatch_callback: GlobalUnwatchCallback) -> None:
        """Register a callback to be called whenever a new watcher is being added or removed on an entry

        :param watch_callback: Callback invoked on ``watch`` invocation
        :param unwatch_callback: Callback invoked on ``unwatch`` invocation
        """
        self._global_watch_callbacks = watch_callback
        self._global_unwatch_callbacks = unwatch_callback

    def get_change_counters(self) -> Dict[RegistryNodeType, int]:
        return self._tree_change_counters.copy()

    def get_watchable_count(self, node_type: RegistryNodeType) -> int:
        return self._watchable_count[node_type]

    def get_stats(self) -> Statistics:
        """Return internal performance metrics for diagnostic and debugging"""
        return self.Statistics(
            alias_count=self.get_watchable_count(RegistryNodeType.Alias),
            rpv_count=self.get_watchable_count(RegistryNodeType.RuntimePublishedValue),
            var_count=self.get_watchable_count(RegistryNodeType.Variable),
            math_count=self.get_watchable_count(RegistryNodeType.Math),
            watched_entries_count=self.watched_entries_count(),
            registered_watcher_count=self.registered_watcher_count()
        )
