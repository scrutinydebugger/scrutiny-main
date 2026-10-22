
import unittest
from test.artifacts import get_artifact
from test.cli.base_makevarmap_iar import BaseMakeVarmapIAR
from test import ScrutinyUnitTest


class TestMakevarmapIartestRenesasRx600_iccarm5_20_1_dwarf4(BaseMakeVarmapIAR, ScrutinyUnitTest):
    bin_filename = get_artifact('20261015_iartest_iccarm_5_20_1_renesas_rx600-dwarf4.elf')
    memdump_filename = get_artifact('20261015_iartest_iccarm_5_20_1_renesas_rx600-dwarf4.memdump')

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 4)


if __name__ == '__main__':
    import unittest
    unittest.main()
