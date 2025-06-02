#    test_makevarmap_Linux_LE_x64_Clang_14_0_0_dwarf2.py
#        Test suite for symbol extraction. clang dwarf V2
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

import unittest
from test.artifacts import get_artifact
from test.cli.base_testapp_makevarmap_test import BaseTestAppMakeVarmapTest
from test import ScrutinyUnitTest


class TestMakeVarMap_LinuxLEx64_Clang_14_0_0_Dwarf2(BaseTestAppMakeVarmapTest, ScrutinyUnitTest):
    bin_filename = get_artifact('testapp20240505_UbuntuLEx64_clang14_0_0-dwarf2')
    memdump_filename = get_artifact('testapp20240505_UbuntuLEx64_clang14_0_0-dwarf2.memdump')

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 2)

if __name__ == '__main__':
    import unittest
    unittest.main()
