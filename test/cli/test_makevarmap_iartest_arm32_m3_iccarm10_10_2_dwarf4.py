#    test_makevarmap_iartest_arm32_m3_iccarm10_10_2_dwarf4.py
#        Test suite for symbol extraction. IAR 10.10.2 on ARM Cortex-M3, dwarf V4
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import unittest
from test.artifacts import get_artifact
from test.cli.base_makevarmap_iar import BaseMakeVarmapIAR
from test import ScrutinyUnitTest


class TestMakevarmapIartestArm32M3_iccarm10_10_2_dwarf4(BaseMakeVarmapIAR, ScrutinyUnitTest):
    bin_filename = get_artifact('20261015_iartest_iccarm_10_10_2_arm32_m3-dwarf4.elf')
    memdump_filename = get_artifact('20261015_iartest_iccarm_10_10_2_arm32_m3-dwarf4.memdump')

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 4)


if __name__ == '__main__':
    import unittest
    unittest.main()
