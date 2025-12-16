#    test_firmware_description.py
#        A test suite to test the FirmwareDescription class
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from test import ScrutinyUnitTest
from scrutiny.core.varmap import VarMap
from scrutiny.core.alias import Alias
from scrutiny.core.variable import *
from scrutiny.core.basic_types import EmbeddedDataType
from scrutiny.core.firmware_description import FirmwareDescription
from io import BytesIO
from scrutiny.sdk import WatchableType


class TestFirmwareDescription(ScrutinyUnitTest):
    def test_alias_save_and_read(self):
        varmap = VarMap()
        varmap.register_base_type(original_name='float', vartype=EmbeddedDataType.float32)

        varmap.add_variable(
            path_segments=['a', 'b', 'c'],
            location=AbsoluteLocation(0x1000),
            original_type_name='float'
        )

        alias1 = Alias('/x/y/z', '/a/b/c')
        bio = BytesIO(FirmwareDescription.serialize_aliases([alias1]))
        alias_readback = FirmwareDescription.read_aliases(bio, varmap)
        self.assertIn('/x/y/z', alias_readback)
        alias1_readback = alias_readback['/x/y/z']
        self.assertEqual(alias1.target, alias1_readback.target)
        self.assertEqual(alias1_readback.target, '/a/b/c')
        self.assertEqual(alias1_readback.target_type, WatchableType.Variable)

        alias2 = Alias('/x/y/z', '/i/dont/exist')
        bio = BytesIO(FirmwareDescription.serialize_aliases([alias2]))
        alias_readback = FirmwareDescription.read_aliases(bio, varmap, suppress_errors=True)
        alias2_readback = alias_readback['/x/y/z']
        self.assertEqual(alias2.target, alias2_readback.target)
        self.assertEqual(alias2_readback.target, '/i/dont/exist')
        self.assertEqual(alias2_readback.target_type, None)

        bio = BytesIO(FirmwareDescription.serialize_aliases([alias2]))
        with self.assertRaises(Exception):
            alias_readback = FirmwareDescription.read_aliases(bio, varmap, suppress_errors=False)
