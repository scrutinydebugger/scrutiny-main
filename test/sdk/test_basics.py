#    test_basics.py
#        Test basic classes of the SDK
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

import unittest
from scrutiny import sdk
from test import ScrutinyUnitTest


class TestDatalogging(ScrutinyUnitTest):
    def test_variable_factory_interface(self):
        factory_interface = sdk.VariableFactoryInterface(
            access_path="/aa/bb/cc/dd",
            datatype=sdk.EmbeddedDataType.float32,
            array_dims={
                '/aa/bb': (2, 3),
                '/aa/bb/cc/dd': (5,)
            },
            enum=sdk.EmbeddedEnum('SomeEnum', {'aaa': 100, 'bbb': 200})
        )

        self.assertEqual(factory_interface.count_possible_paths(), 30)
        all_paths = []
        for path, config in factory_interface.iterate_possible_paths():
            all_paths.append(path)
            self.assertEqual(config.datatype, sdk.EmbeddedDataType.float32)
            self.assertEqual(config.watchable_type, sdk.WatchableType.Variable)
            self.assertIsNotNone(config.enum)
            self.assertEqual(config.enum.name, 'SomeEnum')
            
        all_paths_unique = set(all_paths)
        self.assertEqual(len(all_paths), len(all_paths_unique))
        self.assertEqual(len(all_paths_unique), factory_interface.count_possible_paths())

        self.assertIn('/aa/bb[0][0]/cc/dd[0]', all_paths_unique)
        self.assertIn('/aa/bb[0][0]/cc/dd[1]', all_paths_unique)
        self.assertIn('/aa/bb[0][0]/cc/dd[2]', all_paths_unique)
        self.assertIn('/aa/bb[0][0]/cc/dd[3]', all_paths_unique)
        self.assertIn('/aa/bb[0][0]/cc/dd[4]', all_paths_unique)

        self.assertIn('/aa/bb[0][1]/cc/dd[0]', all_paths_unique)
        self.assertIn('/aa/bb[0][1]/cc/dd[1]', all_paths_unique)
        self.assertIn('/aa/bb[0][1]/cc/dd[2]', all_paths_unique)
        self.assertIn('/aa/bb[0][1]/cc/dd[3]', all_paths_unique)
        self.assertIn('/aa/bb[0][1]/cc/dd[4]', all_paths_unique)

        self.assertIn('/aa/bb[0][2]/cc/dd[0]', all_paths_unique)
        self.assertIn('/aa/bb[0][2]/cc/dd[1]', all_paths_unique)
        self.assertIn('/aa/bb[0][2]/cc/dd[2]', all_paths_unique)
        self.assertIn('/aa/bb[0][2]/cc/dd[3]', all_paths_unique)
        self.assertIn('/aa/bb[0][2]/cc/dd[4]', all_paths_unique)

        self.assertIn('/aa/bb[1][0]/cc/dd[0]', all_paths_unique)
        self.assertIn('/aa/bb[1][0]/cc/dd[1]', all_paths_unique)
        self.assertIn('/aa/bb[1][0]/cc/dd[2]', all_paths_unique)
        self.assertIn('/aa/bb[1][0]/cc/dd[3]', all_paths_unique)
        self.assertIn('/aa/bb[1][0]/cc/dd[4]', all_paths_unique)

        self.assertIn('/aa/bb[1][1]/cc/dd[0]', all_paths_unique)
        self.assertIn('/aa/bb[1][1]/cc/dd[1]', all_paths_unique)
        self.assertIn('/aa/bb[1][1]/cc/dd[2]', all_paths_unique)
        self.assertIn('/aa/bb[1][1]/cc/dd[3]', all_paths_unique)
        self.assertIn('/aa/bb[1][1]/cc/dd[4]', all_paths_unique)

        self.assertIn('/aa/bb[1][2]/cc/dd[0]', all_paths_unique)
        self.assertIn('/aa/bb[1][2]/cc/dd[1]', all_paths_unique)
        self.assertIn('/aa/bb[1][2]/cc/dd[2]', all_paths_unique)
        self.assertIn('/aa/bb[1][2]/cc/dd[3]', all_paths_unique)
        self.assertIn('/aa/bb[1][2]/cc/dd[4]', all_paths_unique)


if __name__ == '__main__':
    unittest.main()
