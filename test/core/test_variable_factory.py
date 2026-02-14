#    test_variable_factory.py
#        A test suite for the VariableFactory
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from test import ScrutinyUnitTest
from scrutiny.core.array import UntypedArray
from scrutiny.core.variable_factory import VariableFactory
from scrutiny.core.scrutiny_path import ScrutinyPath
from scrutiny.core.variable import Variable, VariableLayout
from scrutiny.core.basic_types import *
from scrutiny.core.variable_location import UnresolvedPathPointedLocation, AbsoluteLocation


class TestVariableFactory(ScrutinyUnitTest):
    def test_factory_instantiation(self):
        factory = VariableFactory(
            layout=VariableLayout(
                vartype=EmbeddedDataType.float32,
                endianness=Endianness.Little,
                bitoffset=None,
                bitsize=None,
                enum=None
            ),
            base_location=AbsoluteLocation(1000),
            access_name="/aaa/bbb/ccc/ddd",
        )

        factory.add_array_node('/aaa/bbb', UntypedArray((2, 3), 100))
        factory.add_array_node('/aaa/bbb/ccc/ddd', UntypedArray((4, 5), 4))

        v = factory.instantiate(ScrutinyPath.from_string('/aaa/bbb[1][0]/ccc/ddd[2][3]'))
        self.assertEqual(v.get_address(), 1000 + (1 * 3 + 0) * 100 + (2 * 5 + 3) * 4)
        self.assertEqual(v.get_fullname(), "/aaa/bbb[1][0]/ccc/ddd[2][3]")
        self.assertEqual(v.get_type(), EmbeddedDataType.float32)

    def test_instantiate_out_of_bounds(self):
        factory = VariableFactory(
            base_location=AbsoluteLocation(1000),
            layout=VariableLayout(
                vartype=EmbeddedDataType.float32,
                endianness=Endianness.Little,
                bitoffset=None,
                bitsize=None,
                enum=None
            ),
            access_name="/aaa/bbb/ccc/ddd",
        )
        factory.add_array_node('/aaa/bbb', UntypedArray((2, 3), 100))
        factory.add_array_node('/aaa/bbb/ccc/ddd', UntypedArray((4, 5), 4))

        factory.instantiate('/aaa/bbb[0][0]/ccc/ddd[0][0]')

        for v in [
            '/aaa/bbb/ccc/ddd',
            '/aaa/bbb[0]/ccc/ddd[0][0]',
            '/aaa/bbb[0][0]/ccc/ddd[0]',
            '/aaa/bbb[0][0]/ccc/ddd[0][0][0]',
            '/aaa/bbb[0][3]/ccc/ddd[0][0]',
            '/aaa/bbb[2][0]/ccc/ddd[0][0]',
            '/aaa/bbb[2][0]/ccc/ddd[4][0]',
            '/aaa/bbb[0][0]/ccc/ddd[0][5]',
            '/aaa/bbb[-1][0]/ccc/ddd[0][0]',
            '/aaa/bbb[0][-1]/ccc/ddd[0][0]',
            '/aaa/bbb[0][0]/ccc/ddd[-1][0]',
            '/aaa/bbb[0][0]/ccc/ddd[0][-1]',
        ]:
            with self.assertRaises(Exception):
                factory.instantiate(v)

    def test_instantiate_array_of_pointers_of_arrays_coool(self):

        location = UnresolvedPathPointedLocation(
            '/aaa/bbb/ccc/ddd',
            123,
            array_segments={
                '/aaa/bbb': UntypedArray((2, 3), 4),
                '/aaa/bbb/ccc': UntypedArray((3, 4), 32)
            })

        factory = VariableFactory(
            base_location=location,
            layout=VariableLayout(
                vartype=EmbeddedDataType.float32,
                endianness=Endianness.Little,
                bitoffset=None,
                bitsize=None,
                enum=None
            ),
            access_name="/aaa/bbb/ccc/*ddd/xxx/yyy/zzz",
        )

        factory.add_array_node('/aaa/bbb/ccc/*ddd/xxx/', UntypedArray((4, 5), 100))
        factory.add_array_node('/aaa/bbb/ccc/*ddd/xxx/yyy', UntypedArray((6, 7), 4))
