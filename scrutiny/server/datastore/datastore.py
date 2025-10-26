#    datastore.py
#        This class is a container that will hold all the data read from a device (e.g. the
#        variables).
#        It's the meeting point of the API (with ValueStreamer) and the DeviceHandler
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

__all__ = ['Datastore']

import logging
import functools
from scrutiny.core.basic_types import WatchableType
from scrutiny.core.scrutiny_path import ScrutinyPath
from scrutiny.server.datastore.datastore_entry import *
from scrutiny.core.variable_factory import VariableFactory
from scrutiny import tools

from scrutiny.tools.typing import *

WatchCallback = Callable[[str], None]


class Datastore:
    """
    Class at the center of the server. It contains the value of all watched items.
    the device handler writes variable and RPV (Runtime Published Values) into the datastore
    and the user subscribe to value change by setting a callback in the datastore through the API.

    The datastore manages entries per type. There is 3 types : Variable, RPV, Alias.
    We can do most operation on all entries of one type. This per-type management is required because
    from the outside, there are differences. Mainly, RPV are added and removed to the datastore by the device
    handler when a connection is made. Aliases and variables are added when a Firmware Description is loaded. 
    It's the same as having 3 datastore, one for each type.
    """

    _logger: logging.Logger
    _entries: Dict[WatchableType, Dict[str, DatastoreEntry]]
    _displaypath2idmap: Dict[WatchableType, Dict[str, str]]
    _watcher_map: Dict[WatchableType, Dict[str, Set[str]]]
    _global_watch_callbacks: List[WatchCallback]
    _global_unwatch_callbacks: List[WatchCallback]
    _target_update_request_queue: "List[UpdateTargetRequest]"
    _var_factories: Dict[str, VariableFactory]
    _display_path_to_templated_entries_map: Dict[str, DatastoreEntry]

    MAX_ENTRY: int = 1000000

    def __init__(self) -> None:
        self._logger = logging.getLogger(self.__class__.__name__)
        self._global_watch_callbacks = []    # When somebody starts watching an entry,m these callbacks are called
        self._global_unwatch_callbacks = []  # When somebody stops watching an entry, these callbacks are called

        self._entries = {}
        self._watcher_map = {}
        self._displaypath2idmap = {}
        self._var_factories = {}
        self._display_path_to_templated_entries_map = {}
        self._target_update_request_queue = []
        for watchable_type in WatchableType.all():
            self._entries[watchable_type] = {}
            self._watcher_map[watchable_type] = {}
            self._displaypath2idmap[watchable_type] = {}

    def clear(self, watchable_type: Optional[WatchableType] = None) -> None:
        """ Deletes all entries of a given type. All types if None"""
        if watchable_type is None:
            type_to_clear_list = WatchableType.all()
        else:
            type_to_clear_list = [watchable_type]

        for type_to_clear in type_to_clear_list:
            self._entries[type_to_clear] = {}
            self._watcher_map[type_to_clear] = {}
            self._displaypath2idmap[type_to_clear] = {}

        self._display_path_to_templated_entries_map.clear()
        self._var_factories.clear()

    def add_entries_quiet(self, entries: List[DatastoreEntry]) -> None:
        """ Add many entries without raising exceptions. Silently remove failing ones"""
        for entry in entries:
            self.add_entry_quiet(entry)

    def add_entry_quiet(self, entry: DatastoreEntry) -> None:
        """ Add a single entry without raising exception. Silently remove failing ones"""
        try:
            self.add_entry(entry)
        except Exception as e:
            self._logger.debug(str(e))

    def add_entries(self, entries: List[DatastoreEntry]) -> None:
        """ Add multiple entries to the datastore"""
        for entry in entries:
            self.add_entry(entry)

    def add_entry(self, entry: DatastoreEntry) -> None:
        """ Add a single entry to the datastore."""
        entry_id = entry.get_id()
        for watchable_type in WatchableType.all():
            if entry_id in self._entries[watchable_type]:
                raise ValueError('Duplicate datastore entry')

        if self.get_entries_count() >= self.MAX_ENTRY:
            raise RuntimeError('Datastore cannot have more than %d entries' % self.MAX_ENTRY)

        if isinstance(entry, DatastoreAliasEntry):
            resolved_entry = entry.resolve()
            if resolved_entry.get_id() not in self._entries[resolved_entry.get_type()]:
                raise KeyError('Alias ID %s (%s) refer to entry ID %s (%s) that is not in the datastore' %
                               (entry.get_id(), entry.get_display_path(), resolved_entry.get_id(), resolved_entry.get_display_path()))

        self._entries[entry.get_type()][entry.get_id()] = entry
        self._displaypath2idmap[entry.get_type()][entry.get_display_path()] = entry.get_id()

    def remove_entry(self, entry_or_entryid: Union[DatastoreEntry, str]) -> None:
        for watcher in self.get_watchers(entry_or_entryid):
            self.stop_watching(entry_or_entryid, watcher)

        entry_id = self._get_entry_id(entry_or_entryid)
        entry = self.get_entry(entry_id)

        with tools.SuppressException(KeyError):
            del self._display_path_to_templated_entries_map[entry.display_path]

        for watchable_type in WatchableType.all():
            if entry_id in self._entries[watchable_type]:
                del self._entries[watchable_type][entry_id]

    def get_entry(self, entry_id: str) -> DatastoreEntry:
        """ Fetch a datastore entry by its ID"""
        for watchable_type in WatchableType.all():
            if entry_id in self._entries[watchable_type]:
                return self._entries[watchable_type][entry_id]
        raise KeyError('Entry with ID %s not found in datastore' % entry_id)

    def get_entry_by_display_path(self, display_path: str) -> DatastoreEntry:
        """ Find an entry by its display path, which is supposed to be unique"""
        parsed_path = ScrutinyPath.from_string(display_path)

        display_path = parsed_path.to_str()
        for watchable_type in WatchableType.all():
            if display_path in self._displaypath2idmap[watchable_type]:
                entry_id = self._displaypath2idmap[watchable_type][display_path]
                if entry_id in self._entries[watchable_type]:
                    return self._entries[watchable_type][entry_id]

        if parsed_path.has_encoded_information():
            factory_path = parsed_path.to_raw_str()
            if factory_path in self._var_factories:
                factory = self._var_factories[factory_path]
                new_entry = DatastoreVariableEntry(parsed_path.to_str(), factory.instantiate(parsed_path))
                self._display_path_to_templated_entries_map[display_path] = new_entry
                self.add_entry(new_entry)
                return new_entry

        raise KeyError(f'Entry with display path {display_path} not found in datastore')

    def get_var_factory_by_access_path(self, access_path: str) -> VariableFactory:
        if access_path not in self._var_factories:
            raise KeyError(f"No Variable Factory located at {access_path}")
        return self._var_factories[access_path]

    def add_watch_callback(self, callback: WatchCallback) -> None:
        """ Mainly used to notify device handler that a new variable is to be polled"""
        self._global_watch_callbacks.append(callback)

    def add_unwatch_callback(self, callback: WatchCallback) -> None:
        self._global_unwatch_callbacks.append(callback)

    def start_watching_by_display_path(self,
                                       display_path: str,
                                       watcher: str,
                                       value_change_callback: Optional[UserValueChangeCallback] = None) -> DatastoreEntry:
        entry = self.get_entry_by_display_path(display_path)    # Invoke the factory if needed
        return self.start_watching(entry, watcher, value_change_callback)

    def start_watching(self,
                       entry_or_entryid: Union[DatastoreEntry, str],
                       watcher: str,
                       value_change_callback: Optional[UserValueChangeCallback] = None
                       ) -> DatastoreEntry:
        """ 
        Register a new callback on the entry identified by the given entry_id.
        The watcher parameter will be given back when calling the callback.
        We ensure to call the callback for each watcher.
        """

        entry_id = self._get_entry_id(entry_or_entryid)
        entry = self.get_entry(entry_id)

        if entry_id not in self._watcher_map[entry.get_type()]:
            self._watcher_map[entry.get_type()][entry.get_id()] = set()
        self._watcher_map[entry.get_type()][entry_id].add(watcher)

        if not entry.has_value_change_callback(watcher):
            if value_change_callback is not None:
                entry.register_value_change_callback(owner=watcher, callback=value_change_callback)

        # Mainly used to notify device handler that a new variable is to be polled
        for callback in self._global_watch_callbacks:
            callback(entry_id)

        if isinstance(entry, DatastoreAliasEntry):
            # Alias are tricky. When we subscribe to them, another hidden subscription to the referenced entry is made here
            alias_value_change_callback = functools.partial(self._alias_value_change_callback, watching_entry=entry)
            self.start_watching(
                entry_or_entryid=entry.resolve(),
                watcher=self._make_owner_from_alias_entry(entry),
                value_change_callback=alias_value_change_callback
            )

        return entry

    def is_watching(self, entry_or_entryid: Union[DatastoreEntry, str], watcher: str) -> bool:
        """ Tell if the given watcher is actually watching an entry"""
        entry_id = self._get_entry_id(entry_or_entryid)
        entry = self.get_entry(entry_id)
        if entry_id not in self._watcher_map[entry.get_type()]:
            return False
        return watcher in self._watcher_map[entry.get_type()][entry_id]

    def get_watchers(self, entry_or_entryid: Union[DatastoreEntry, str]) -> List[str]:
        """ Get the list of watchers on a given entry"""
        entry_id = self._get_entry_id(entry_or_entryid)
        entry = self.get_entry(entry_id)
        if entry_id not in self._watcher_map[entry.get_type()]:
            return []
        return list(self._watcher_map[entry.get_type()][entry_id])

    def has_watchers(self, entry_or_entryid: Union[DatastoreEntry, str]) -> bool:
        """Tells if the entry has at least one watcher"""
        if isinstance(entry_or_entryid, str):
            entry = self.get_entry(entry_or_entryid)
        else:
            entry = entry_or_entryid

        entry_id = entry.get_id()
        if entry_id not in self._watcher_map[entry.get_type()]:
            return False

        return len(self._watcher_map[entry.get_type()][entry_id]) > 0

    def stop_watching(self, entry_or_entryid: Union[DatastoreEntry, str], watcher: str) -> None:
        """Indicates that a watcher does not want to watch an entry anymore.
        Mainly removes the callback for that watcher for that given entry. 
        Also notifies the rest of the application through callback (mostly MemoryReader/MemoryWriter)

        :param entry_or_entryid: The entry to stop watching
        :watcher: The name of the watcher
        """
        entry_id = self._get_entry_id(entry_or_entryid)
        entry = self.get_entry(entry_id)

        with tools.SuppressException():
            self._watcher_map[entry.get_type()][entry_id].remove(watcher)

        with tools.SuppressException():
            if len(self._watcher_map[entry.get_type()][entry_id]) == 0:
                del self._watcher_map[entry.get_type()][entry_id]

                if isinstance(entry, DatastoreAliasEntry):
                    # Special handling for Aliases.
                    # If nobody watches this alias, then we can remove the internal subscription to the referenced entry
                    self.stop_watching(entry.resolve(), self._make_owner_from_alias_entry(entry))

        entry.unregister_value_change_callback(watcher)

        for callback in self._global_unwatch_callbacks:
            callback(entry_id)  # Mainly used by the device handler to know it can stop polling that entry

        # If that was a templated entry (generated by a template) and nobody's watching it anymore, we can delete it
        # avoid bloating the datastore on the long run if a client starts watching a huge array for a short period of time
        if entry.display_path in self._display_path_to_templated_entries_map:
            if not self.has_watchers(entry):
                self.remove_entry(entry)

    def stop_watching_all(self, watcher: str) -> None:
        """Stop watching every entries for a given watcher."""
        for watchable_type in WatchableType.all():
            watched_entries_id = self.get_watched_entries_id(watchable_type)    # Make a copy of the list
            for entry_id in watched_entries_id:
                self.stop_watching(entry_id, watcher)

    def get_all_entries(self, watchable_type: Optional[WatchableType] = None) -> Generator[DatastoreEntry, None, None]:
        """ Fetch all entries of a given type. All types if None"""
        watchable_types = WatchableType.all() if watchable_type is None else [watchable_type]
        for watchable_type in watchable_types:
            for entry_id in self._entries[watchable_type]:
                yield self._entries[watchable_type][entry_id]

    def get_entries_count(self, watchable_type: Optional[WatchableType] = None) -> int:
        """ Returns the number of entries of a given type. All types if None"""
        val = 0
        typelist = [watchable_type] if watchable_type is not None else WatchableType.all()
        for thetype in typelist:
            val += len(self._entries[thetype])

        return val

    def set_value(self, entry_or_entryid: Union[DatastoreEntry, str], value: Any) -> None:
        """ Sets the value on an entry"""
        entry_id = self._get_entry_id(entry_or_entryid)
        entry = self.get_entry(entry_id)
        entry.set_value(value)

    def update_target_value(self, entry_or_entryid: Union[DatastoreEntry, str], value: Any, callback: UpdateTargetRequestCallback) -> UpdateTargetRequest:
        """Enqueue a write request on the datastore entry. Will be picked up by the device side to be executed"""
        if isinstance(entry_or_entryid, DatastoreEntry):
            entry = entry_or_entryid
        else:
            entry = self.get_entry(entry_or_entryid)
        update_request = UpdateTargetRequest(value, entry=entry, callback=callback)

        if isinstance(entry, DatastoreAliasEntry):
            new_value = entry.aliasdef.compute_user_to_device(value)
            nested_callback = functools.partial(self._alias_target_update_callback, update_request)
            new_request = self.update_target_value(entry.resolve(), new_value, callback=nested_callback)
            if new_request.is_complete():  # Edge case if failed to enqueue request.
                new_request.complete(success=update_request.is_complete())
            return update_request
        else:
            self._target_update_request_queue.append(update_request)

        return update_request

    def pop_target_update_request(self) -> Optional[UpdateTargetRequest]:
        """ Returns the next write request to be processed and removes it form the queue"""
        try:
            return self._target_update_request_queue.pop(0)
        except IndexError:
            return None

    def peek_target_update_request(self) -> Optional[UpdateTargetRequest]:
        """ Returns the next write request to be processed without removing it from the queue"""
        try:
            return self._target_update_request_queue[0]
        except IndexError:
            return None

    def has_pending_target_update(self) -> bool:
        return len(self._target_update_request_queue) > 0

    def get_pending_target_update_count(self) -> int:
        return len(self._target_update_request_queue)

    def get_watched_entries_id(self, watchable_type: WatchableType) -> List[str]:
        """ Get a list of all watched entries ID of a given type."""
        return list(self._watcher_map[watchable_type].keys())

    @classmethod
    def is_rpv_path(cls, path: str) -> bool:
        """Returns True if the tree-like path matches the expected RPV default path (i.e. /rpv/x1234)"""
        return DatastoreRPVEntry.is_valid_path(path)

    def register_var_factories(self, factories: Iterable[VariableFactory]) -> None:
        for factory in factories:
            self.register_var_factory(factory)

    def register_var_factory(self, factory: VariableFactory) -> None:
        key = factory.get_access_name()
        if key in self._var_factories:
            raise KeyError("Duplicate datastore variable factory")

        self._var_factories[key] = factory

    def get_var_factory_count(self) -> int:
        return len(self._var_factories)

    def get_all_variable_factory(self) -> Generator[VariableFactory, None, None]:
        for factory in self._var_factories.values():
            yield factory

# region Private

    def _prune_unwatched_templated_entries(self) -> None:
        for entry in list(self._display_path_to_templated_entries_map.values()):
            if not self.has_watchers(entry):
                self.remove_entry(entry)

    def _get_entry_id(self, entry_or_entryid: Union[DatastoreEntry, str]) -> str:
        """ Get the entry ID of a given entry."""
        if isinstance(entry_or_entryid, DatastoreEntry):
            return entry_or_entryid.get_id()
        else:
            return entry_or_entryid

    def _make_owner_from_alias_entry(self, entry: DatastoreAliasEntry) -> str:
        """ When somebody subscribes to an alias, the datastore starts watching the pointed entry
        This method creates a watcher name based on the alias ID"""
        return 'alias_' + entry.get_id()

    def _alias_value_change_callback(self, owner: str, entry: DatastoreEntry, watching_entry: DatastoreAliasEntry) -> None:
        """ This callback is the one given when the datastore starts watching an entry because somebody wants to watch an alias."""
        watching_entry.set_value_internal(entry.get_value())

    def _alias_target_update_callback(self, alias_request: UpdateTargetRequest, success: bool, entry: DatastoreEntry, timestamp: float) -> None:
        """Callback used by an alias to grab the result of the target update and apply it to its own"""
        # entry is a var or a RPV
        alias_request.complete(success=success)
# endregion
