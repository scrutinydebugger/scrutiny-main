#    test_csv_logger.py
#        Test suite for the CSVLogger class
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import os
import csv
import unittest
from tempfile import TemporaryDirectory
from datetime import datetime, timedelta
from pathlib import Path

from scrutiny.core.basic_types import EmbeddedDataType
import scrutiny.sdk
from scrutiny.sdk.listeners import ValueUpdate
from scrutiny.sdk.listeners.csv_logger import CSVLogger, CSVConfig
from scrutiny.sdk.watchable_handle import WatchableHandle, WatchableType
from scrutiny.sdk.client import ScrutinyClient
from test import ScrutinyUnitTest

sdk = scrutiny.sdk


class TestCSVLogger(ScrutinyUnitTest):

    def setUp(self) -> None:
        self.dummy_client = ScrutinyClient()
        self.dt_zero = datetime.now()
        self.dt_format = r'%Y-%m-%d %H:%M:%S.%f'

        self.w1 = WatchableHandle(self.dummy_client, '/var/speed')
        self.w2 = WatchableHandle(self.dummy_client, '/var/temperature')
        self.w3 = WatchableHandle(self.dummy_client, '/var/active')

        self.w1._configure(sdk.BaseDetailedWatchableConfiguration(
            watchable_type=WatchableType.Variable, datatype=EmbeddedDataType.float32,
            server_id='id_w1', enum=None, server_path=self.w1.server_path))
        self.w2._configure(sdk.BaseDetailedWatchableConfiguration(
            watchable_type=WatchableType.Variable, datatype=EmbeddedDataType.sint32,
            server_id='id_w2', enum=None, server_path=self.w2.server_path))
        self.w3._configure(sdk.BaseDetailedWatchableConfiguration(
            watchable_type=WatchableType.Variable, datatype=EmbeddedDataType.boolean,
            server_id='id_w3', enum=None, server_path=self.w3.server_path))

    def _make_update(self, watchable: WatchableHandle, value, dt: datetime) -> ValueUpdate:
        watchable._update_value(value, timestamp=dt)
        return ValueUpdate(watchable=watchable, value=value, update_timestamp=dt)

    def _make_logger(self, folder: str, **kwargs) -> CSVLogger:
        defaults = dict(
            folder=folder,
            filename='test_output',
            datetime_zero_sec=self.dt_zero,
            datetime_format=self.dt_format,
        )
        defaults.update(kwargs)
        return CSVLogger(**defaults)

    def _read_csv(self, filepath: str, csv_config: CSVConfig = CSVConfig()) :
        with open(filepath, 'r', encoding=csv_config.encoding, newline=csv_config.newline) as f:
            reader = csv.reader(f, delimiter=csv_config.delimiter, quotechar=csv_config.quotechar, quoting=csv_config.quoting)
            return list(reader)

    # --- Constructor validation ---

    def test_bad_folder_raises(self):
        with self.assertRaises(FileNotFoundError):
            CSVLogger(folder='/nonexistent/path', filename='test')

    def test_filename_with_directory_raises(self):
        with TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                CSVLogger(folder=d, filename=os.path.join('subdir', 'test'))

    def test_empty_filename_raises(self):
        with TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                CSVLogger(folder=d, filename='.csv')

    def test_bad_types_raise(self):
        with TemporaryDirectory() as d:
            with self.assertRaises(TypeError):
                CSVLogger(folder=123, filename='test')
            with self.assertRaises(TypeError):
                CSVLogger(folder=d, filename=123)
            with self.assertRaises(TypeError):
                CSVLogger(folder=d, filename='test', convert_bool_to_int='yes')
            with self.assertRaises(TypeError):
                CSVLogger(folder=d, filename='test', datetime_format=123)
            with self.assertRaises(TypeError):
                CSVLogger(folder=d, filename='test', csv_config='bad')

    def test_lines_per_file_validation(self):
        with TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                CSVLogger(folder=d, filename='test', lines_per_file=10)  # below 100
            with self.assertRaises(ValueError):
                CSVLogger(folder=d, filename='test', lines_per_file=-1)

    def test_file_part_0pad_validation(self):
        with TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                CSVLogger(folder=d, filename='test', file_part_0pad=-1)
            with self.assertRaises(ValueError):
                CSVLogger(folder=d, filename='test', file_part_0pad=21)

    def test_conflicting_files_raises(self):
        with TemporaryDirectory() as d:
            open(os.path.join(d, 'test_0001.csv'), 'w').close()
            with self.assertRaises(FileExistsError):
                CSVLogger(folder=d, filename='test', lines_per_file=100)

    def test_conflicting_files_ignored_when_no_split(self):
        with TemporaryDirectory() as d:
            open(os.path.join(d, 'test_0001.csv'), 'w').close()
            logger = CSVLogger(folder=d, filename='test', lines_per_file=None)
            self.assertIsNotNone(logger)

    def test_extension_stripped_from_filename(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d, filename='test_output.csv')
            logger.define_columns([CSVLogger.ColumnDescriptor(signal_id='s1', name='col1', fullpath=None)])
            logger.start()
            self.assertEqual(logger.get_actual_filename(), Path(os.path.join(d, 'test_output.csv')))
            logger.stop()

    # --- State machine ---

    def test_start_without_columns_raises(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            with self.assertRaises(ValueError):
                logger.start()

    def test_define_columns_while_started_raises(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            logger.define_columns([CSVLogger.ColumnDescriptor(signal_id='s1', name='col1', fullpath=None)])
            logger.start()
            with self.assertRaises(RuntimeError):
                logger.define_columns([CSVLogger.ColumnDescriptor(signal_id='s2', name='col2', fullpath=None)])
            logger.stop()

    def test_set_file_headers_while_started_raises(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            logger.define_columns([CSVLogger.ColumnDescriptor(signal_id='s1', name='col1', fullpath=None)])
            logger.start()
            with self.assertRaises(RuntimeError):
                logger.set_file_headers([["header"]])
            logger.stop()

    def test_started_flag(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            self.assertFalse(logger.started())
            logger.define_columns([CSVLogger.ColumnDescriptor(signal_id='s1', name='col1', fullpath=None)])
            logger.start()
            self.assertTrue(logger.started())
            logger.stop()
            self.assertFalse(logger.started())

    def test_get_actual_filename_none_when_not_started(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            self.assertIsNone(logger.get_actual_filename())

    def test_get_folder(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            self.assertEqual(logger.get_folder(), Path(os.path.normpath(os.path.abspath(d))))

    # --- Single file output ---

    def test_single_file_basic_write(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            logger.define_columns_from_handles([self.w1, self.w2])
            logger.start()

            t0 = self.dt_zero
            updates = [
                self._make_update(self.w1, 1.5, t0 + timedelta(seconds=0)),
                self._make_update(self.w2, 100, t0 + timedelta(seconds=0)),
            ]
            logger.write(updates)

            updates2 = [
                self._make_update(self.w1, 2.5, t0 + timedelta(seconds=1)),
                self._make_update(self.w2, 200, t0 + timedelta(seconds=1)),
            ]
            logger.write(updates2)

            logger.stop()

            filepath = os.path.join(d, 'test_output.csv')
            self.assertTrue(os.path.exists(filepath))
            rows = self._read_csv(filepath)

            # Row 0: fullpath header
            # Row 1: column headers
            # Row 2+: data
            headers = rows[1]
            self.assertIn(CSVLogger.DATETIME_HEADER, headers)
            self.assertIn(CSVLogger.RELTIME_HEADER, headers)
            self.assertIn(self.w1.name, headers)
            self.assertIn(self.w2.name, headers)
            self.assertIn(CSVLogger.UPDATE_FLAG_HEADER, headers)

            # Should have 2 data rows (from stop() flushing the last one + the flush at t=1)
            data_rows = rows[2:]
            self.assertEqual(len(data_rows), 2)

    def test_fullpath_row_present(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            logger.define_columns_from_handles([self.w1])
            logger.start()

            updates = [self._make_update(self.w1, 1.0, self.dt_zero)]
            logger.write(updates)
            logger.stop()

            rows = self._read_csv(os.path.join(d, 'test_output.csv'))
            # First row should contain fullpath info
            self.assertIn(self.w1.server_path, rows[0])

    def test_no_fullpath_row_when_all_none(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            logger.define_columns([
                CSVLogger.ColumnDescriptor(signal_id='s1', name='col1', fullpath=None),
                CSVLogger.ColumnDescriptor(signal_id='s2', name='col2', fullpath=None),
            ])
            logger.start()

            updates = [self._make_update(self.w1, 1.0, self.dt_zero)]
            logger.write(updates, signal_id_list=['s1'])
            logger.stop()

            rows = self._read_csv(os.path.join(d, 'test_output.csv'))
            # First row should be the table headers directly
            self.assertEqual(rows[0][0], CSVLogger.DATETIME_HEADER)

    # --- Boolean conversion ---

    def test_bool_to_int_conversion(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d, convert_bool_to_int=True)
            logger.define_columns_from_handles([self.w3])
            logger.start()

            t0 = self.dt_zero
            updates = [self._make_update(self.w3, True, t0)]
            logger.write(updates)

            updates2 = [self._make_update(self.w3, False, t0 + timedelta(seconds=1))]
            logger.write(updates2)

            logger.stop()

            rows = self._read_csv(os.path.join(d, 'test_output.csv'))
            data_rows = rows[2:]  # skip fullpath + headers
            self.assertEqual(data_rows[0][2], 1)  # True -> 1
            self.assertEqual(data_rows[1][2], 0)  # False -> 0

    def test_bool_no_conversion(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d, convert_bool_to_int=False)
            logger.define_columns_from_handles([self.w3])
            logger.start()

            updates = [self._make_update(self.w3, True, self.dt_zero)]
            logger.write(updates)

            updates2 = [self._make_update(self.w3, False, self.dt_zero + timedelta(seconds=1))]
            logger.write(updates2)

            logger.stop()

            rows = self._read_csv(os.path.join(d, 'test_output.csv'), csv_config=CSVConfig(quoting=csv.QUOTE_ALL))
            data_rows = rows[2:]
            self.assertEqual(data_rows[0][2], 'True')
            self.assertEqual(data_rows[1][2], 'False')

    def test_relative_time_zero_is_picked(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            logger.define_columns_from_handles([self.w3])
            logger.start()

            updates = [self._make_update(self.w3, 1.23, self.dt_zero)]
            updates = [self._make_update(self.w3, 1.23, self.dt_zero + timedelta(seconds=1))]
            logger.write(updates)

            logger.stop()

            rows = self._read_csv(os.path.join(d, 'test_output.csv'))
            data_rows = rows[2:]
            self.assertEqual(data_rows[0][1], 0)
            self.assertEqual(data_rows[0][2], 1)

    # --- Update flags ---

    def test_update_flags(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            logger.define_columns_from_handles([self.w1, self.w2])
            logger.start()

            t0 = self.dt_zero
            # Only update w1
            updates = [self._make_update(self.w1, 1.0, t0)]
            logger.write(updates)

            # Move to next timestamp so that first row is flushed
            updates2 = [self._make_update(self.w1, 2.0, t0 + timedelta(seconds=1))]
            logger.write(updates2)

            logger.stop()

            rows = self._read_csv(os.path.join(d, 'test_output.csv'))
            data_rows = rows[2:]
            # First data row: only w1 was updated -> flags should be "1,0"
            flags_col = len(rows[1]) - 1  # last column
            self.assertEqual(data_rows[0][flags_col], '1,0')

    # --- Signal ID list ---

    def test_write_with_signal_id_list(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            logger.define_columns([
                CSVLogger.ColumnDescriptor(signal_id='sig_a', name='Signal A', fullpath=None),
                CSVLogger.ColumnDescriptor(signal_id='sig_b', name='Signal B', fullpath=None),
            ])
            logger.start()

            t0 = self.dt_zero
            updates = [
                self._make_update(self.w1, 10.0, t0),
                self._make_update(self.w2, 20, t0),
            ]
            logger.write(updates, signal_id_list=['sig_a', 'sig_b'])

            logger.stop()

            rows = self._read_csv(os.path.join(d, 'test_output.csv'))
            # headers (no fullpath row since all None)
            self.assertIn('Signal A', rows[0])
            self.assertIn('Signal B', rows[0])

    def test_write_with_mismatched_signal_id_list_raises(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            logger.define_columns([
                CSVLogger.ColumnDescriptor(signal_id='sig_a', name='Signal A', fullpath=None),
            ])
            logger.start()

            updates = [self._make_update(self.w1, 10.0, self.dt_zero)]
            with self.assertRaises(ValueError):
                logger.write(updates, signal_id_list=['sig_a', 'sig_b'])
            logger.stop()

    # --- File splitting ---

    def test_file_splitting(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d, lines_per_file=100, file_part_0pad=4)
            logger.define_columns_from_handles([self.w1])
            logger.start()

            t0 = self.dt_zero
            # Write 250 updates at distinct timestamps to trigger file splits
            for i in range(250):
                updates = [self._make_update(self.w1, float(i), t0 + timedelta(seconds=i + 1))]
                logger.write(updates)

            logger.stop()

            self.assertTrue(os.path.exists(os.path.join(d, 'test_output_0000.csv')))
            self.assertTrue(os.path.exists(os.path.join(d, 'test_output_0001.csv')))
            self.assertTrue(os.path.exists(os.path.join(d, 'test_output_0002.csv')))
            self.assertFalse(os.path.exists(os.path.join(d, 'test_output_0003.csv')))

    def test_file_split_naming_pad(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d, lines_per_file=100, file_part_0pad=6)
            logger.define_columns_from_handles([self.w1])
            logger.start()
            logger.stop()

            self.assertTrue(os.path.exists(os.path.join(d, 'test_output_000000.csv')))

    def test_single_file_naming(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d, lines_per_file=None)
            logger.define_columns_from_handles([self.w1])
            logger.start()
            self.assertEqual(logger.get_actual_filename(), Path(os.path.join(d, 'test_output.csv')))
            logger.stop()

    # --- File headers ---

    def test_file_headers(self):
        with TemporaryDirectory() as d:
            headers = [["Project", "My Project"], ["Date", "2025-01-01"]]
            logger = self._make_logger(d, file_headers=headers)
            logger.define_columns_from_handles([self.w1])
            logger.start()

            updates = [self._make_update(self.w1, 1.0, self.dt_zero)]
            logger.write(updates)
            logger.stop()

            rows = self._read_csv(os.path.join(d, 'test_output.csv'))
            self.assertEqual(rows[0][0], 'Project')
            self.assertEqual(rows[0][1], 'My Project')
            self.assertEqual(rows[1][0], 'Date')
            self.assertEqual(rows[1][1], '2025-01-01')
            # Row 2 is empty separator
            self.assertEqual(rows[2], [])

    def test_file_headers_written_in_each_split_file(self):
        with TemporaryDirectory() as d:
            headers = [["Info", "Test"]]
            logger = self._make_logger(d, lines_per_file=100, file_headers=headers)
            logger.define_columns_from_handles([self.w1])
            logger.start()

            t0 = self.dt_zero
            for i in range(150):
                logger.write([self._make_update(self.w1, float(i), t0 + timedelta(seconds=i + 1))])
            logger.stop()

            for fname in ['test_output_0000.csv', 'test_output_0001.csv']:
                rows = self._read_csv(os.path.join(d, fname))
                self.assertEqual(rows[0][0], 'Info')

    # --- Relative time ---

    def test_relative_time_increases(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            logger.define_columns_from_handles([self.w1])
            logger.start()

            t0 = self.dt_zero
            for i in range(5):
                logger.write([self._make_update(self.w1, float(i), t0 + timedelta(seconds=i + 1))])
            logger.stop()

            rows = self._read_csv(os.path.join(d, 'test_output.csv'))
            data_rows = rows[2:]  # skip fullpath + headers
            prev_t = -1.0
            for row in data_rows:
                t = row[1]  # reltime column
                self.assertGreater(t, prev_t)
                prev_t = t

    # --- Same-timestamp updates coalesce into one row ---

    def test_same_timestamp_updates_coalesce(self):
        with TemporaryDirectory() as d:
            logger = self._make_logger(d)
            logger.define_columns_from_handles([self.w1, self.w2])
            logger.start()

            t0 = self.dt_zero
            updates = [
                self._make_update(self.w1, 1.0, t0 + timedelta(seconds=1)),
                self._make_update(self.w2, 2, t0 + timedelta(seconds=1)),
            ]
            logger.write(updates)

            # Write another timestamp to flush the first
            logger.write([self._make_update(self.w1, 3.0, t0 + timedelta(seconds=2))])
            logger.stop()

            rows = self._read_csv(os.path.join(d, 'test_output.csv'))
            data_rows = rows[2:]
            # First data row should have both w1 and w2 values
            self.assertEqual(data_rows[0][2], 1.0)
            self.assertEqual(data_rows[0][3], 2)

    # --- Conflicting files detection ---

    def test_get_conflicting_files(self):
        with TemporaryDirectory() as d:
            # Create some files that match
            open(os.path.join(d, 'data_0000.csv'), 'w').close()
            open(os.path.join(d, 'data_0001.csv'), 'w').close()
            # Files that should NOT match
            open(os.path.join(d, 'data.csv'), 'w').close()
            open(os.path.join(d, 'other_0000.csv'), 'w').close()

            conflicts = list(CSVLogger.get_conflicting_files(Path(d), 'data'))
            self.assertEqual(len(conflicts), 2)

    def test_get_conflicting_files_no_partial_match(self):
        with TemporaryDirectory() as d:
            # Should not match because of extra suffix
            open(os.path.join(d, 'data_0001.csv_extra'), 'w').close()
            conflicts = list(CSVLogger.get_conflicting_files(Path(d), 'data'))
            self.assertEqual(len(conflicts), 0)

    # --- File already exists ---

    def test_start_fails_if_file_exists(self):
        with TemporaryDirectory() as d:
            open(os.path.join(d, 'test_output.csv'), 'w').close()
            logger = self._make_logger(d)
            logger.define_columns_from_handles([self.w1])
            with self.assertRaises(FileExistsError):
                logger.start()

    # --- CSV config ---

    def test_custom_csv_config(self):
        with TemporaryDirectory() as d:
            config = CSVConfig(delimiter=';', quotechar="'", quoting=csv.QUOTE_ALL)
            logger = self._make_logger(d, csv_config=config)
            logger.define_columns_from_handles([self.w1])
            logger.start()

            logger.write([self._make_update(self.w1, 42.0, self.dt_zero)])
            logger.stop()

            filepath = os.path.join(d, 'test_output.csv')
            rows = self._read_csv(filepath, config)
            self.assertTrue(len(rows) >= 2)


if __name__ == '__main__':
    unittest.main()
