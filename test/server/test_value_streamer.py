#    test_value_streamer.py
#        Test the ValueStreamer object that reads the datastore and broadcast variables to
#        all clients.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

from test import ScrutinyUnitTest
from scrutiny.server.api.value_streamer import ValueStreamer
from scrutiny.server.datastore.datastore import Datastore
from scrutiny.server.datastore.datastore_entry import DatastoreRPVEntry
from scrutiny.core.basic_types import EmbeddedDataType, RuntimePublishedValue


def make_rpv_entry(path: str, rpv_id: int) -> DatastoreRPVEntry:
    return DatastoreRPVEntry(path, rpv=RuntimePublishedValue(id=rpv_id, datatype=EmbeddedDataType.float32))


class TestValueStreamer(ScrutinyUnitTest):

    def setUp(self) -> None:
        self.datastore = Datastore()
        self.streamer = ValueStreamer(self.datastore)

    def _publish_entries(self, entries, conn_id: str) -> None:
        """Simulate the datastore calling publish() for each entry (mimics the value-change callback pattern)."""
        for entry in entries:
            self.streamer.publish(entry, conn_id)

    def test_batch_updates_held_until_batch_closes(self) -> None:
        conn_id = "conn-batch"
        self.streamer.new_connection(conn_id)

        entry1 = make_rpv_entry("/rpv/x0001", 0x0001)
        entry2 = make_rpv_entry("/rpv/x0002", 0x0002)
        self.datastore.add_entries([entry1, entry2])

        # Open a batch and publish both entries while it is active.
        self.datastore.start_batch("source-a")
        self._publish_entries([entry1, entry2], conn_id)

        # Nothing should be visible yet.
        chunk = self.streamer.get_stream_chunk(conn_id)
        self.assertEqual(chunk, [])

        # Close the batch – the held entries must now be available.
        self.datastore.stop_batch("source-a")

        chunk = self.streamer.get_stream_chunk(conn_id)
        self.assertCountEqual(chunk, [entry1, entry2],
                              "Expected both entries to be flushed after the batch closes")

    def test_non_batch_updates_streamed_immediately(self) -> None:
        # Updates published outside of any batch must be immediately available via get_stream_chunk
        conn_id = "conn-no-batch"
        self.streamer.new_connection(conn_id)

        entry1 = make_rpv_entry("/rpv/x0011", 0x0011)
        entry2 = make_rpv_entry("/rpv/x0012", 0x0012)
        self.datastore.add_entries([entry1, entry2])

        self._publish_entries([entry1, entry2], conn_id)

        chunk = self.streamer.get_stream_chunk(conn_id)
        self.assertCountEqual(chunk, [entry1, entry2])

    def test_duplicate_publishes_within_batch_deduplicated(self) -> None:
        # Publishing the same entry multiple times within a batch must yield only one
        # occurrence in the resulting chunk (set semantics).
        conn_id = "conn-dedup-test"
        self.streamer.new_connection(conn_id)

        entry = make_rpv_entry("/rpv/x0021", 0x0021)
        self.datastore.add_entry(entry)

        self.datastore.start_batch("source-b")
        # Publish same entry multiple times during the batch
        for _ in range(5):
            self._publish_entries([entry], conn_id)
        self.datastore.stop_batch("source-b")

        chunk = self.streamer.get_stream_chunk(conn_id)
        self.assertEqual(len(chunk), 1, "Duplicate publishes must be deduplicated")
        self.assertIn(entry, chunk)

    def test_batch_start_clears_pending_on_batch_end_set(self) -> None:
        # When a new batch starts, the to_publish_on_batch_end set must be cleared.
        # This ensures stale pending data from a previous incomplete sequence is discarded.
        conn_id = "conn-clear"
        self.streamer.new_connection(conn_id)

        entry1 = make_rpv_entry("/rpv/x0031", 0x0031)
        entry2 = make_rpv_entry("/rpv/x0032", 0x0032)
        self.datastore.add_entries([entry1, entry2])

        # First batch: publish entry1 then close → should appear in stream.
        self.datastore.start_batch("source-c")
        self._publish_entries([entry1], conn_id)
        self.datastore.stop_batch("source-c")

        chunk = self.streamer.get_stream_chunk(conn_id)
        self.assertIn(entry1, chunk)

        # Second batch: publish entry2 but do NOT close yet.
        # The internal to_publish_on_batch_end for entry2 is in-flight.
        self.datastore.start_batch("source-c")
        self._publish_entries([entry2], conn_id)

        # Nothing should arrive while batch is open.
        chunk = self.streamer.get_stream_chunk(conn_id)
        self.assertEqual(chunk, [])

        # Close the second batch.
        self.datastore.stop_batch("source-c")
        chunk = self.streamer.get_stream_chunk(conn_id)
        self.assertIn(entry2, chunk)
        self.assertNotIn(entry1, chunk)

    def test_chunk_consumed_after_get(self) -> None:
        # get_stream_chunk must clear the pending set; a second call with no new publishes
        # must return an empty list
        conn_id = "conn-consume"
        self.streamer.new_connection(conn_id)

        entry = make_rpv_entry("/rpv/x0041", 0x0041)
        self.datastore.add_entry(entry)

        self._publish_entries([entry], conn_id)

        first_chunk = self.streamer.get_stream_chunk(conn_id)
        self.assertIn(entry, first_chunk)

        second_chunk = self.streamer.get_stream_chunk(conn_id)
        self.assertEqual(second_chunk, [])  # Chunk must be empty after it has been consumed

    def test_independent_per_connection_batching(self) -> None:
        # Each connection's to_publish set must be managed independently
        conn_a = "conn-a"
        conn_b = "conn-b"
        self.streamer.new_connection(conn_a)
        self.streamer.new_connection(conn_b)

        entry1 = make_rpv_entry("/rpv/x0051", 0x0051)
        entry2 = make_rpv_entry("/rpv/x0052", 0x0052)
        self.datastore.add_entries([entry1, entry2])

        # Publish different entries to different connections (outside any batch).
        self._publish_entries([entry1], conn_a)
        self._publish_entries([entry2], conn_b)

        chunk_a = self.streamer.get_stream_chunk(conn_a)
        chunk_b = self.streamer.get_stream_chunk(conn_b)

        self.assertIn(entry1, chunk_a)
        self.assertNotIn(entry2, chunk_a)

        self.assertIn(entry2, chunk_b)
        self.assertNotIn(entry1, chunk_b)

    def test_throttling(self) -> None:
        """When stream_rate_measurement reports a rate above throttling_target,
        get_stream_chunk must return an empty list instead of the pending entries."""
        conn_id = "conn-throttle"
        self.streamer.new_connection(conn_id)

        entry = make_rpv_entry("/rpv/x0061", 0x0061)
        self.datastore.add_entry(entry)

        # Directly set the internal rate measurement above the target to simulate
        # a situation where the client is already receiving data too fast.
        TARGET = 10.0  # updates / s
        self.streamer.enable_throttling(conn_id, TARGET)
        self.streamer._set_actual_throttling_measurement(conn_id, TARGET + 1)  # above target

        self._publish_entries([entry], conn_id)

        chunk = self.streamer.get_stream_chunk(conn_id)
        self.assertEqual(chunk, [])  # No data when we are throttled

        self.streamer._set_actual_throttling_measurement(conn_id, TARGET - 1)
        chunk = self.streamer.get_stream_chunk(conn_id)
        self.assertEqual(chunk, [entry])  # No data when we are throttled


if __name__ == '__main__':
    import unittest
    unittest.main()
