#    test_makevarmap_demo_stm32f4_gcc10_3.py
#        Test suite parse the debug symbols of the STM32F4 demo
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import os
from scrutiny.core.basic_types import *
from scrutiny.core.variable import *

from test.cli.base_varmap_test import BaseVarmapTest, KnownEnumTypedDict
from test import ScrutinyUnitTest
from test.artifacts import get_artifact


class TestMakeVarMap_Demo_STM32F4_GCC10_3_Dwarf4(BaseVarmapTest, ScrutinyUnitTest):
    dereference_pointer = True
    memdump_filename = None
    bin_filename = get_artifact(os.path.join('demos_prebuilt', 'stm32f4_cmake', 'stm32f4_demo.elf'))

    # TODO : Add tests.  Just scanning the file without error is already good!
