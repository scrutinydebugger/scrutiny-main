#    test_serializable_value_set.py
#        A test suite for the value set fil
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from test import ScrutinyUnitTest
from scrutiny.gui.core.serializable_value_set import SerializableValueSet, InvalidFileFormatError
import tempfile
from pathlib import Path


class TestSerializableValueTest(ScrutinyUnitTest):
    def test_save_reload(self):
        valueset = SerializableValueSet()
        valueset.add('var:/aaa/bbb/ccc', 1.2)
        valueset.add('var:/aaa/bbb/ddd', True)
        valueset.add('var:/aaa/bbb/eee', 123)

        with tempfile.TemporaryDirectory() as d:
            filepath = Path(d) / 'temp1'
            valueset.to_file(filepath)
            valueset2 = SerializableValueSet.from_file(filepath)

        d = valueset2.to_dict()

        self.assertIn('var:/aaa/bbb/ccc', d)
        self.assertIn('var:/aaa/bbb/ddd', d)
        self.assertIn('var:/aaa/bbb/eee', d)

        self.assertAlmostEqual(d['var:/aaa/bbb/ccc'], 1.2)
        self.assertEqual(d['var:/aaa/bbb/ddd'], True)
        self.assertEqual(d['var:/aaa/bbb/eee'], 123)

    def test_bad_inputs(self):

        valueset = SerializableValueSet()

        with self.assertRaises(Exception):
            valueset.add(1, 1)

        with self.assertRaises(Exception):
            valueset.add('not_a_valid_fqn', 1)

        with self.assertRaises(Exception):
            valueset.add('xxx:/aaa/bb/cc', 1)

        with self.assertRaises(Exception):
            valueset.add('var:/aaa/bb/cc', 'asd')

    def test_bad_dict(self):

        with self.assertRaises(InvalidFileFormatError):
            SerializableValueSet.from_dict({
                'aaa': 1
            })

        with self.assertRaises(InvalidFileFormatError):
            SerializableValueSet.from_dict({
                1: 1
            })

        with self.assertRaises(InvalidFileFormatError):
            SerializableValueSet.from_dict('aaaa')

        with self.assertRaises(InvalidFileFormatError):
            SerializableValueSet.from_dict({
                'var:/aaa/bbb': 'aaa'
            })

        with self.assertRaises(InvalidFileFormatError):
            SerializableValueSet.from_dict({
                'var:/aaa/bbb': None
            })
