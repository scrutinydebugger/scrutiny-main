#    test_alias.py
#        Test Alias basic features
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

from scrutiny.core.alias import Alias
from scrutiny.core.embedded_enum import EmbeddedEnum
from scrutiny.core.basic_types import WatchableType
from test import ScrutinyUnitTest


class TestAlias(ScrutinyUnitTest):
    def test_basics(self):
        with self.assertRaises(Exception):
            Alias.from_dict('aaa', {})

        with self.assertRaises(Exception):
            Alias()

        with self.assertRaises(Exception):
            Alias(fullpath='asd')     # missing target

        with self.assertRaises(Exception):
            Alias(fullpath='asd', target='ssss', target_type=WatchableType.Alias)

        x = Alias(fullpath='aaa', target='asd')
        x.set_target_type(WatchableType.Variable)
        self.assertEqual(x.get_fullpath(), 'aaa')
        self.assertEqual(x.get_target(), 'asd')
        self.assertEqual(x.get_target_type(), WatchableType.Variable)
        self.assertEqual(x.get_min(), float('-inf'))
        self.assertEqual(x.get_max(), float('inf'))
        self.assertEqual(x.get_gain(), 1.0)
        self.assertEqual(x.get_offset(), 0.0)
        self.assertIsNone(x.enum)

        x = Alias.from_dict('aaa', {'target': 'asd', 'target_type': WatchableType.RuntimePublishedValue})
        self.assertEqual(x.get_fullpath(), 'aaa')
        self.assertEqual(x.get_target(), 'asd')
        self.assertEqual(x.get_target_type(), WatchableType.RuntimePublishedValue)
        self.assertEqual(x.get_min(), float('-inf'))
        self.assertEqual(x.get_max(), float('inf'))
        self.assertEqual(x.get_gain(), 1.0)
        self.assertEqual(x.get_offset(), 0.0)
        self.assertIsNone(x.enum)

        x = Alias.from_dict('aaa', {
            'target': 'asd',
            'target_type': WatchableType.RuntimePublishedValue,
            'enum': {
                'name': 'some_enum',
                'values': {
                    'a': 1,
                    'b': 2,
                    'c': 3,
                }
            }
        })
        self.assertEqual(x.get_fullpath(), 'aaa')
        self.assertEqual(x.get_target(), 'asd')
        self.assertEqual(x.get_target_type(), WatchableType.RuntimePublishedValue)
        self.assertEqual(x.get_min(), float('-inf'))
        self.assertEqual(x.get_max(), float('inf'))
        self.assertEqual(x.get_gain(), 1.0)
        self.assertEqual(x.get_offset(), 0.0)
        self.assertIsNotNone(x.enum)
        self.assertEqual(x.enum.name, 'some_enum')
        self.assertEqual(x.enum.vals['a'], 1)
        self.assertEqual(x.enum.vals['b'], 2)
        self.assertEqual(x.enum.vals['c'], 3)

        d = x.to_dict()
        self.assertEqual(d['target'], 'asd')
        self.assertEqual(d['target_type'], WatchableType.RuntimePublishedValue)
        self.assertNotIn('min', d)  # Remove because of default value
        self.assertNotIn('max', d)
        self.assertNotIn('gain', d)
        self.assertNotIn('offset', d)

        with self.assertRaises(Exception):
            x.min = 1.0
            x.max = 0.0
            x.validate()

        x.min = 0.0
        x.max = 100.0
        x.validate()

        with self.assertRaises(Exception):
            x.gain = float('inf')
            x.validate()
        x.gain = 1.0

        with self.assertRaises(Exception):
            x.offset = float('inf')
            x.validate()
        x.offset = 0.0

        with self.assertRaises(Exception):
            x.min = float('nan')
            x.validate()
        x.min = 0.0

        with self.assertRaises(Exception):
            x.max = float('nan')
            x.validate()
        x.max = 100.0

        with self.assertRaises(Exception):
            x.gain = float('nan')
            x.validate()
        x.gain = 1.0

        with self.assertRaises(Exception):
            x.offset = float('nan')
            x.validate()
        x.offset = 0.0

        with self.assertRaises(Exception):
            x.enum = 1
            x.validate()
        x.enum = None

        with self.assertRaises(Exception):
            x.enum = "asdasd"
            x.validate()
        x.enum = None

        x.enum = EmbeddedEnum('asd')

    def test_value_modifiers(self):
        alias = Alias(fullpath='aaa', target='asd', gain=2.0, offset=10, min=0, max=100)
        self.assertEqual(alias.compute_user_to_device(50.0), 20.0)     # (50-10)/2
        self.assertEqual(alias.compute_user_to_device(150), 45)        # (min(150, 100)-10)/2
        self.assertEqual(alias.compute_user_to_device(-100), -5)       # (max(-100, 0)-10)/2
        self.assertEqual(alias.compute_device_to_user(10), 30.0)       # 10*2+10
        self.assertEqual(alias.compute_device_to_user(200), 410)       # 200*2+10. min max ha sno effect in this direction

        alias = Alias(fullpath='aaa', target='asd', gain=None, offset=10, min=0, max=100)
        self.assertEqual(alias.compute_user_to_device(50.0), 40)
        self.assertEqual(alias.compute_user_to_device(150), 90)
        self.assertEqual(alias.compute_user_to_device(-100), -10)
        self.assertEqual(alias.compute_device_to_user(10), 20)
        self.assertEqual(alias.compute_device_to_user(200), 210)

        alias = Alias(fullpath='aaa', target='asd', gain=2.0, offset=None, min=0, max=100)
        self.assertEqual(alias.compute_user_to_device(50.0), 25)
        self.assertEqual(alias.compute_user_to_device(150), 50)
        self.assertEqual(alias.compute_user_to_device(-100), 0)
        self.assertEqual(alias.compute_device_to_user(10), 20)
        self.assertEqual(alias.compute_device_to_user(200), 400)

        alias = Alias(fullpath='aaa', target='asd', gain=2.0, offset=10, min=0, max=None)
        self.assertEqual(alias.compute_user_to_device(50.0), 20.0)
        self.assertEqual(alias.compute_user_to_device(150), 70)
        self.assertEqual(alias.compute_user_to_device(-100), -5)
        self.assertEqual(alias.compute_device_to_user(10), 30.0)
        self.assertEqual(alias.compute_device_to_user(200), 410)

        alias = Alias(fullpath='aaa', target='asd', gain=2.0, offset=10, min=None, max=100)
        self.assertEqual(alias.compute_user_to_device(50.0), 20.0)
        self.assertEqual(alias.compute_user_to_device(150), 45)
        self.assertEqual(alias.compute_user_to_device(-100), -55)
        self.assertEqual(alias.compute_device_to_user(10), 30.0)
        self.assertEqual(alias.compute_device_to_user(200), 410)

        alias = Alias(fullpath='aaa', target='asd')  # No value modifier. Type unchanged
        self.assertIsInstance(alias.compute_user_to_device(50.0), float)
        self.assertIsInstance(alias.compute_user_to_device(50), int)
        self.assertIsInstance(alias.compute_device_to_user(50.0), float)
        self.assertIsInstance(alias.compute_device_to_user(50), int)


if __name__ == '__main__':
    import unittest
    unittest.main()
