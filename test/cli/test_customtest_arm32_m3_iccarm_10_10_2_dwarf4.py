
import unittest
from test.artifacts import get_artifact
from test.cli.base_customtest_arm32_m3_iccarm_10_10_2_dwarf4 import BaseCustomTestArm32M3Iccarm_10_10_2_Dwarf4
from test import ScrutinyUnitTest


class TestCustomtestArm32M3Iccarm_10_10_2_dwarf4(BaseCustomTestArm32M3Iccarm_10_10_2_Dwarf4, ScrutinyUnitTest):
    bin_filename = get_artifact('customtest_20261014_Arm32CortexM3_iccarm_v10_10_2-dwarf4.elf')
    memdump_filename = get_artifact('customtest_20261014_Arm32CortexM3_iccarm_v10_10_2-dwarf4.memdump')

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 4)


if __name__ == '__main__':
    import unittest
    unittest.main()
