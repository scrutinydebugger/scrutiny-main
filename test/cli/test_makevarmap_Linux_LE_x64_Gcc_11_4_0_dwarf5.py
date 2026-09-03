#    test_makevarmap_Linux_LE_x64_Gcc_11_4_0_dwarf5.py
#        Test suite for symbol extraction. GCC dwarf V3
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import unittest
from test.artifacts import get_artifact
from test.cli.base_testapp_makevarmap_test import BaseTestAppMakeVarmapTest
from test.cli.base_ctestapp_makevarmap_test import BaseCTestAppMakeVarmapTest
from test import ScrutinyUnitTest


class TestMakeVarMap_CPP_LinuxLEx64_Gcc11_4_0_Dwarf5(BaseTestAppMakeVarmapTest, ScrutinyUnitTest):
    bin_filename = get_artifact('testapp20260824_UbuntuLEx64_gcc11_4_0-dwarf5')
    memdump_filename = get_artifact('testapp20260824_UbuntuLEx64_gcc11_4_0-dwarf5.memdump')

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 5)

class TestMakeVarMap_C_LinuxLEx64_Gcc11_4_0_Dwarf5(BaseCTestAppMakeVarmapTest, ScrutinyUnitTest):
    bin_filename = get_artifact('ctestapp20260824_UbuntuLEx64_gcc11_4_0-dwarf5')
    memdump_filename = get_artifact('ctestapp20260824_UbuntuLEx64_gcc11_4_0-dwarf5.memdump')

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 5)

if __name__ == '__main__':
    import unittest
    unittest.main()
