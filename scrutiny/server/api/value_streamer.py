#    value_streamer.py
#        Take the data from the Datastore and sends it to all clients by respecting bitrate
#        limits and avoiding duplicate date.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

__all__ = ['ValueStreamer']

from scrutiny.server.datastore.datastore_entry import DatastoreEntry
from scrutiny.server.datastore.datastore import Datastore, BatchEditCallback, BatchState
from scrutiny import tools

from scrutiny.tools.typing import *


class ValueStreamer:
    """
    This class get notified when a value changes in the datastore and decides
    when to actually flush the update to the client handler. It keeps track of the
    client connection ID so that rules are applied per client.

    It avoid duplicates updates and can also apply some rules such as throttling
    """

    entry_to_publish: Dict[str, Set[DatastoreEntry]]
    entry_to_publish_on_batch_end: Dict[str, Set[DatastoreEntry]]
    batch_state_per_conn_id: Dict[str, BatchState]
    frozen_connections: Set[str]
    datastore: Datastore

    def __init__(self, datastore:Datastore) -> None:
        self.entry_to_publish = {}
        self.entry_to_publish_on_batch_end = {}
        self.batch_state_per_conn_id = {}
        self.frozen_connections = set()
        self.datastore = datastore

        self.datastore.add_batch_edit_callback(self._batch_edit_callback)

    def _batch_edit_callback(self, source:str, state:BatchState) -> None:

        if state == BatchState.INACTIVE:    # Flush  entry_to_publish_on_batch_end --> entry_to_publish
            for conn_id, entry_set in self.entry_to_publish_on_batch_end.items():
                for entry in entry_set:
                    self.entry_to_publish[conn_id].add(entry)
                self.entry_to_publish_on_batch_end[conn_id].clear()

        if state == BatchState.ACTIVE:
            for conn_id in self.entry_to_publish_on_batch_end.keys():
                self.entry_to_publish_on_batch_end[conn_id].clear()

        for conn_id in self.batch_state_per_conn_id.keys():
            self.batch_state_per_conn_id[conn_id] = state

    def publish(self, entry: DatastoreEntry, conn_id: str) -> None:
        # inform the value streamer that a new value should be published.
        # This is called by the datastore set_value callback
        with tools.SuppressException():
            if self.batch_state_per_conn_id[conn_id] == BatchState.ACTIVE:
                self.entry_to_publish_on_batch_end[conn_id].add(entry)
            else:
                self.entry_to_publish[conn_id].add(entry)

    def get_stream_chunk(self, conn_id: str) -> List[DatastoreEntry]:
        # Returns a list of entry to be flushed per connection
        chunk: List[DatastoreEntry] = []
        if conn_id not in self.entry_to_publish:
            return chunk

        if conn_id in self.frozen_connections:
            return chunk

        for entry in self.entry_to_publish[conn_id]:
            chunk.append(entry)

        for entry in chunk:
            self.entry_to_publish[conn_id].remove(entry)

        return chunk

    def is_still_waiting_stream(self, entry: DatastoreEntry) -> bool:
        # Tells if an entry update is pending to be sent to a client
        for conn_id in self.entry_to_publish:
            if entry in self.entry_to_publish[conn_id]:
                return True
        return False

    def new_connection(self, conn_id: str) -> None:
        # Called when the API gets a new connection
        if conn_id not in self.entry_to_publish:
            self.entry_to_publish[conn_id] = set()
            self.entry_to_publish_on_batch_end[conn_id] = set()
            self.batch_state_per_conn_id[conn_id] = BatchState.INACTIVE

    def clear_connection(self, conn_id: str) -> None:
        # Called when the API looses a connection
        if conn_id in self.entry_to_publish:
            del self.entry_to_publish[conn_id]
        if conn_id in self.entry_to_publish_on_batch_end:
            del self.entry_to_publish_on_batch_end[conn_id]
        if conn_id in self.batch_state_per_conn_id:
            del self.batch_state_per_conn_id[conn_id]

    def process(self) -> None:
        pass
