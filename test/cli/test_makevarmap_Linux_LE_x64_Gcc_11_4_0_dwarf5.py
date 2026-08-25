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

if __name__ == '__main__':
    import unittest
    unittest.main()
