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
from scrutiny.server.datastore.datastore import Datastore, BatchState
from scrutiny import tools
from scrutiny.tools.throttler import Throttler

from scrutiny.tools.typing import *
from dataclasses import dataclass


@dataclass(slots=True, init=False)
class ConnectionData:
    """State variable for each active connection"""
    to_publish: Set[DatastoreEntry]
    """Entries that are ready to publish"""
    to_publish_on_batch_end: Set[DatastoreEntry]
    """Temporary set of entries that will need to be flushed as soon as the active batch is closed."""
    batch_state: BatchState
    """The actual datastore batch state"""
    stream_rate_throttler: Throttler
    """A low pass filter to keep track of the stream rate in updates/sec"""

    def __init__(self) -> None:
        self.to_publish = set()
        self.to_publish_on_batch_end = set()
        self.batch_state = BatchState.INACTIVE
        self.stream_rate_throttler = Throttler(estimation_window=0.005)

    def process(self) -> None:
        self.stream_rate_throttler.process()


class ValueStreamer:
    """
    This class get notified when a value changes in the datastore and decides
    when to actually flush the update to the client handler. It keeps track of the
    client connection ID so that rules are applied per client.

    It avoid duplicates updates and can also apply some rules such as throttling
    """

    _conn_data: Dict[str, ConnectionData]

    def __init__(self, datastore: Datastore) -> None:
        self._conn_data = {}

        datastore.add_batch_edit_callback(self._batch_edit_callback)

    def _batch_edit_callback(self, source: str, state: BatchState) -> None:
        for conn_data in self._conn_data.values():
            if state == BatchState.INACTIVE:    # Flush  _entry_to_publish_on_batch_end --> _entry_to_publish
                for entry in conn_data.to_publish_on_batch_end:
                    conn_data.to_publish.add(entry)
                conn_data.to_publish_on_batch_end.clear()

            elif state == BatchState.ACTIVE:
                conn_data.to_publish_on_batch_end.clear()

            conn_data.batch_state = state

    def enable_throttling(self, conn_id: str, update_per_sec: float) -> None:
        conn_data = self._conn_data[conn_id]
        if update_per_sec > 0:
            conn_data.stream_rate_throttler.set_rate(update_per_sec)
            conn_data.stream_rate_throttler.enable()
        else:
            self.disable_throttling(conn_id)

    def disable_throttling(self, conn_id: str) -> None:
        self._conn_data[conn_id].stream_rate_throttler.disable()

    def throttling_enabled(self, conn_id: str) -> bool:
        return self._conn_data[conn_id].stream_rate_throttler.is_enabled()

    def get_target_throttling_rate(self, conn_id: str) -> Optional[float]:
        throttler = self._conn_data[conn_id].stream_rate_throttler
        if not throttler.is_enabled():
            return None
        return throttler.get_rate()

    def _set_actual_throttling_measurement(self, conn_id: str, rate: float) -> None:
        """For unit testing"""
        throttler = self._conn_data[conn_id].stream_rate_throttler
        throttler.set_estimated_rate_for_testing(rate)

    def publish(self, entry: DatastoreEntry, conn_id: str) -> None:
        """ inform the value streamer that a new value should be published.
        This is called by the datastore set_value callback"""
        with tools.SuppressException():
            conn_data = self._conn_data[conn_id]
            if conn_data.batch_state == BatchState.ACTIVE:
                conn_data.to_publish_on_batch_end.add(entry)
            else:
                conn_data.to_publish.add(entry)

    def remove_entry_from_pending(self, conn_id: str, entry: DatastoreEntry) -> None:
        """To be called when an entry is unsubscribed"""
        conn_data = self._conn_data[conn_id]
        with tools.SuppressException(KeyError):
            conn_data.to_publish.remove(entry)
        with tools.SuppressException(KeyError):
            conn_data.to_publish_on_batch_end.remove(entry)

    def get_stream_chunk(self, conn_id: str) -> List[DatastoreEntry]:
        """Returns a list of entry to be flushed per connection.
        Entries returned are removed from the internal "to stream" set """

        if conn_id not in self._conn_data:
            return []

        conn_data = self._conn_data[conn_id]

        if not conn_data.stream_rate_throttler.allowed(len(conn_data.to_publish)):
            return []

        chunk = list(conn_data.to_publish)
        conn_data.to_publish.clear()

        conn_data.stream_rate_throttler.consume(len(chunk))
        return chunk

    def new_connection(self, conn_id: str) -> None:
        """Called when the API gets a new connection"""
        if conn_id not in self._conn_data:
            self._conn_data[conn_id] = ConnectionData()

    def clear_connection(self, conn_id: str) -> None:
        """Called when the API looses a connection"""
        if conn_id in self._conn_data:
            del self._conn_data[conn_id]

    def process(self) -> None:
        for conn_data in self._conn_data.values():
            conn_data.process()
