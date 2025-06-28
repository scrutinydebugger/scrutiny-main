import unittest
from test.artifacts import get_artifact
from test.cli.base_customtest_arm32_r52_arm_none_eabi_gcc_10_2 import BaseCustomeTestArm32R52_ArmNoneEabiGcc10_2
from test import ScrutinyUnitTest


class TestCustomeTestArm32R52_ArmNoneEabiGcc10_2_Dwarf3(BaseCustomeTestArm32R52_ArmNoneEabiGcc10_2, ScrutinyUnitTest):
    bin_filename = get_artifact('customtest_20240628_Arm32CortexR52_ArmNoneEabiGcc10_2-dwarf3')
    memdump_filename = get_artifact('customtest_20240628_Arm32CortexR52_ArmNoneEabiGcc10_2-dwarf3.memdump')

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 3)

if __name__ == '__main__':
    import unittest
    unittest.main()
