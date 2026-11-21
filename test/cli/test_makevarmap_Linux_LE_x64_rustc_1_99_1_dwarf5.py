#    test_makevarmap_Linux_LE_x64_rustc_1_99_1_dwarf5.py
#        Test suite for symbol extraction. rustc dwarf V5
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import unittest
from test.artifacts import get_artifact
from test.cli.base_makevarmap_rust_testapp import BaseMakeVarmapRustTestApp
from test import ScrutinyUnitTest


class TestMakeVarMap_LinuxLEx64_Rustc_1_99_1_Dwarf5(BaseMakeVarmapRustTestApp, ScrutinyUnitTest):
    bin_filename = get_artifact('rust-testapp/20261119_rust-testapp-rustc_v1.99.1_dwarf-v5')
    memdump_filename = get_artifact('rust-testapp/20261119_rust-testapp-rustc_v1.99.1_dwarf-v5.memdump')

    def test_dwarf_version(self):
        self.assert_rust_dwarf_version(self.bin_filename, 5)


if __name__ == '__main__':
    import unittest
    unittest.main()
