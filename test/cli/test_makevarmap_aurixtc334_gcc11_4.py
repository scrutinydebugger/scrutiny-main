#    test_makevarmap_aurixtc334_gcc11_4.py
#        Tries to extract var from the Aurix demo
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


class TestMakeVarMap_AurixTC334_GCC11_4_Dwarf4(BaseVarmapTest, ScrutinyUnitTest):
    dereference_pointer = True  # This adds some significant testing time. ~1min vs 2 sec
    memdump_filename = None
    bin_filename = get_artifact(os.path.join('demos_prebuilt', 'aurix_tc334_cmake', 'scrutiny-aurix-tc334-asclin0.elf'))

    # TODO : Add tests.  Just scanning the file without error is already good!
