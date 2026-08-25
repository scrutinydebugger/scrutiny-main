import unittest
from test.artifacts import get_artifact
from test.cli.base_testapp_makevarmap_test import BaseTestAppMakeVarmapTest
from test import ScrutinyUnitTest


class TestMakeVarMap_LinuxLEx64_Clang_14_0_0_Dwarf5(BaseTestAppMakeVarmapTest, ScrutinyUnitTest):
    bin_filename = get_artifact('testapp20260824_UbuntuLEx64_clang14_0_0-dwarf5')
    memdump_filename = get_artifact('testapp20260824_UbuntuLEx64_clang14_0_0-dwarf5.memdump')

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 5)

if __name__ == '__main__':
    import unittest
    unittest.main()
