#    test_makevarmap_qemu_leon3_Gcc_13_3_0_dwarf4.py
#        A test suite to test elf2varmap against Leon3 CPU (Big Endian)
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

import unittest
from test.artifacts import get_artifact
from test import ScrutinyUnitTest
from scrutiny.core.basic_types import *
from test.cli.base_makevarmap_qemu_leon3 import BaseTestMakeVarMap_CPP_QEMU_LEON3
import os

class TestMakeVarMap_CPP_QEMU_LEON3_Gcc_13_3_0_Dwarf4(BaseTestMakeVarMap_CPP_QEMU_LEON3, ScrutinyUnitTest):
    bin_filename = get_artifact(os.path.join('qemu_memdump_test', 'memdump_testapp_leon3_gcc_13_3_0_dwarfv4.elf'))
    memdump_filename = get_artifact(os.path.join('qemu_memdump_test', 'memdump_testapp_leon3_gcc_13_3_0_dwarfv4.memdump'))

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 4)

class TestMakeVarMap_CPP_QEMU_LEON3_Gcc_13_3_0_Dwarf5(BaseTestMakeVarMap_CPP_QEMU_LEON3, ScrutinyUnitTest):
    bin_filename = get_artifact(os.path.join('qemu_memdump_test', 'memdump_testapp_leon3_gcc_13_3_0_dwarfv5.elf'))
    memdump_filename = get_artifact(os.path.join('qemu_memdump_test', 'memdump_testapp_leon3_gcc_13_3_0_dwarfv5.memdump'))

    def test_dwarf_version(self):
        self.assert_dwarf_version(self.bin_filename, 5)
