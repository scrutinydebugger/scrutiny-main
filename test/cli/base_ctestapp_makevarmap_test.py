#    base_ctestapp_makevarmap_test.py
#        Base test for make varmap tests based on the C TestApp
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

import unittest

from scrutiny.core.basic_types import *
from scrutiny.core.variable import *

from scrutiny.tools.typing import *
from test.cli.base_varmap_test import BaseVarmapTest, KnownEnumTypedDict

KNOWN_ENUMS: KnownEnumTypedDict = {
    'EnumA': {
        'name': 'EnumA',
        'values': {
            "eVal1": 0,
            "eVal2": 1,
            "eVal3": 100,
            "eVal4": 101
        }
    }
}


class BaseCTestAppMakeVarmapTest(BaseVarmapTest):
    known_enums = KNOWN_ENUMS

    def test_file1_globals_basic_types(self):
        self.assert_var('/global/file1GlobalChar', EmbeddedDataType.sint8, value_at_loc=-10)
        self.assert_var('/global/file1GlobalInt', EmbeddedDataType.sint32, value_at_loc=-1000)
        self.assert_var('/global/file1GlobalShort', EmbeddedDataType.sint16, value_at_loc=-999)
        self.assert_var('/global/file1GlobalLong', EmbeddedDataType.sint64, value_at_loc=-100000)
        self.assert_var('/global/file1GlobalUnsignedChar', EmbeddedDataType.uint8, value_at_loc=55)
        self.assert_var('/global/file1GlobalUnsignedInt', EmbeddedDataType.uint32, value_at_loc=100001)
        self.assert_var('/global/file1GlobalUnsignedShort', EmbeddedDataType.uint16, value_at_loc=50000)
        self.assert_var('/global/file1GlobalUnsignedLong', EmbeddedDataType.uint64, value_at_loc=100002)
        self.assert_var('/global/file1GlobalFloat', EmbeddedDataType.float32, value_at_loc=3.1415926)
        self.assert_var('/global/file1GlobalDouble', EmbeddedDataType.float64, value_at_loc=1.71)

    def test_file2_globals_basic_types(self):
        self.assert_var('/global/file2GlobalChar', EmbeddedDataType.sint8, value_at_loc=20)
        self.assert_var('/global/file2GlobalInt', EmbeddedDataType.sint32, value_at_loc=2000)
        self.assert_var('/global/file2GlobalShort', EmbeddedDataType.sint16, value_at_loc=998)
        self.assert_var('/global/file2GlobalLong', EmbeddedDataType.sint64, value_at_loc=555555)
        self.assert_var('/global/file2GlobalUnsignedChar', EmbeddedDataType.uint8, value_at_loc=254)
        self.assert_var('/global/file2GlobalUnsignedInt', EmbeddedDataType.uint32, value_at_loc=123456)
        self.assert_var('/global/file2GlobalUnsignedShort', EmbeddedDataType.uint16, value_at_loc=12345)
        self.assert_var('/global/file2GlobalUnsignedLong', EmbeddedDataType.uint64, value_at_loc=1234567)
        self.assert_var('/global/file2GlobalFloat', EmbeddedDataType.float32, value_at_loc=0.1)
        self.assert_var('/global/file2GlobalDouble', EmbeddedDataType.float64, value_at_loc=0.11111111111111)

    def test_file1_static_basic_types(self):
        self.assert_var('/static/file1.c/file1StaticChar', EmbeddedDataType.sint8, value_at_loc=99)
        self.assert_var('/static/file1.c/file1StaticInt', EmbeddedDataType.sint32, value_at_loc=987654)
        self.assert_var('/static/file1.c/file1StaticShort', EmbeddedDataType.sint16, value_at_loc=-666)
        self.assert_var('/static/file1.c/file1StaticLong', EmbeddedDataType.sint64, value_at_loc=-55555)
        self.assert_var('/static/file1.c/file1StaticUnsignedChar', EmbeddedDataType.uint8, value_at_loc=44)
        self.assert_var('/static/file1.c/file1StaticUnsignedInt', EmbeddedDataType.uint32, value_at_loc=3333)
        self.assert_var('/static/file1.c/file1StaticUnsignedShort', EmbeddedDataType.uint16, value_at_loc=22222)
        self.assert_var('/static/file1.c/file1StaticUnsignedLong', EmbeddedDataType.uint64, value_at_loc=321321)
        self.assert_var('/static/file1.c/file1StaticFloat', EmbeddedDataType.float32, value_at_loc=1.23456789)
        self.assert_var('/static/file1.c/file1StaticDouble', EmbeddedDataType.float64, value_at_loc=9.87654321)

    def test_file2_static_basic_types(self):
        self.assert_var('/static/file2.c/file2StaticChar', EmbeddedDataType.sint8, value_at_loc=-66)
        self.assert_var('/static/file2.c/file2StaticInt', EmbeddedDataType.sint32, value_at_loc=-8745)
        self.assert_var('/static/file2.c/file2StaticShort', EmbeddedDataType.sint16, value_at_loc=-9876)
        self.assert_var('/static/file2.c/file2StaticLong', EmbeddedDataType.sint64, value_at_loc=-12345678)
        self.assert_var('/static/file2.c/file2StaticUnsignedChar', EmbeddedDataType.uint8, value_at_loc=12)
        self.assert_var('/static/file2.c/file2StaticUnsignedInt', EmbeddedDataType.uint32, value_at_loc=34)
        self.assert_var('/static/file2.c/file2StaticUnsignedShort', EmbeddedDataType.uint16, value_at_loc=56)
        self.assert_var('/static/file2.c/file2StaticUnsignedLong', EmbeddedDataType.uint64, value_at_loc=78)
        self.assert_var('/static/file2.c/file2StaticFloat', EmbeddedDataType.float32, value_at_loc=2.22222)
        self.assert_var('/static/file2.c/file2StaticDouble', EmbeddedDataType.float64, value_at_loc=3.3333)

    def test_func_static(self):
        self.assert_var('/static/file2.c/file2func1/file2func1Var', EmbeddedDataType.float64, value_at_loc=963258741.123 + 123)
        self.assert_var('/static/main.c/main/staticIntInMainFunc', EmbeddedDataType.sint32, value_at_loc=22222)
        self.assert_var('/static/main.c/mainfunc1/mainfunc1Var', EmbeddedDataType.sint32, value_at_loc=7777777)
        self.assert_var('/static/file1.c/funcInFile1/staticLongInFuncFile1', EmbeddedDataType.sint64, value_at_loc=-0x123456789abcdef)

    def assert_is_enumA(self, fullpath, value_at_loc=None):
        return self.assert_var(fullpath, EmbeddedDataType.uint32, value_at_loc=value_at_loc, enum='EnumA')

    def test_enum(self):
        self.assert_is_enumA('/global/instance_enumA', value_at_loc=101)
        self.assert_is_enumA('/static/file2.c/staticInstance_enumA', value_at_loc=0)

    def test_struct_with_enumA(self):
        self.assert_var('/global/instance_structWithEnumA/a', EmbeddedDataType.sint32, value_at_loc=123)
        self.assert_var('/global/instance_structWithEnumA/b', EmbeddedDataType.sint32, value_at_loc=456)
        self.assert_is_enumA('/global/instance_structWithEnumA/instance_enumA', value_at_loc=1)
        self.assert_var('/static/file2.c/static_instance_structWithEnumA/a', EmbeddedDataType.sint32, value_at_loc=135)
        self.assert_var('/static/file2.c/static_instance_structWithEnumA/b', EmbeddedDataType.sint32, value_at_loc=246)
        self.assert_is_enumA('/static/file2.c/static_instance_structWithEnumA/instance_enumA', value_at_loc=100)

    def test_structA(self):
        v = self.assert_var('/global/file1StructAInstance/structAMemberInt', EmbeddedDataType.sint32, value_at_loc=-654)
        self.assert_var('/global/file1StructAInstance/structAMemberUInt', EmbeddedDataType.uint32, addr=v.get_address() + 4, value_at_loc=258147)
        self.assert_var('/global/file1StructAInstance/structAMemberFloat', EmbeddedDataType.float32, addr=v.get_address() + 8, value_at_loc=77.77)
        self.assert_var('/global/file1StructAInstance/structAMemberDouble', EmbeddedDataType.float64, addr=v.get_address() + 12, value_at_loc=66.66)

    def test_structB(self):
        v = self.assert_var('/global/file1StructBInstance/structBMemberInt', EmbeddedDataType.sint32, value_at_loc=55555)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberInt',
                        EmbeddedDataType.sint32, addr=v.get_address() + 4, value_at_loc=-199999)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberUInt',
                        EmbeddedDataType.uint32, addr=v.get_address() + 8, value_at_loc=33333)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberFloat',
                        EmbeddedDataType.float32, addr=v.get_address() + 12, value_at_loc=33.33)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberDouble',
                        EmbeddedDataType.float64, addr=v.get_address() + 16, value_at_loc=22.22)

    def test_structC(self):
        v = self.assert_var('/global/file1StructCInstance/structCMemberInt', EmbeddedDataType.sint32, value_at_loc=888874)
        self.assert_var('/global/file1StructCInstance/nestedStructInstance/nestedStructMemberInt',
                        EmbeddedDataType.sint32, addr=v.get_address() + 4, value_at_loc=2298744)
        self.assert_var('/global/file1StructCInstance/nestedStructInstance/nestedStructMemberFloat',
                        EmbeddedDataType.float32, addr=v.get_address() + 8, value_at_loc=-147.55)
        self.assert_var('/global/file1StructCInstance/nestedStructInstance/nestedStructInstance2/nestedStructInstance2MemberDouble',
                        EmbeddedDataType.float64, addr=v.get_address() + 12, value_at_loc=654.654)

    def test_structD(self):
        v = self.assert_var('/global/file1StructDInstance/bitfieldA', EmbeddedDataType.uint32, bitoffset=0, bitsize=4, value_at_loc=13)
        self.assert_var('/global/file1StructDInstance/bitfieldB', EmbeddedDataType.uint32,
                        bitoffset=4, bitsize=13, value_at_loc=4100, addr=v.get_address())
        self.assert_var('/global/file1StructDInstance/bitfieldC', EmbeddedDataType.uint32,
                        bitoffset=13 + 4, bitsize=8, value_at_loc=222, addr=v.get_address())
        self.assert_var('/global/file1StructDInstance/bitfieldD', EmbeddedDataType.uint32, value_at_loc=1234567, addr=v.get_address() + 4)
        self.assert_var('/global/file1StructDInstance/bitfieldE', EmbeddedDataType.uint32,
                        bitoffset=0, bitsize=10, value_at_loc=777, addr=v.get_address() + 8)

    def test_array1(self):
        self.assert_var('/global/file2GlobalArray1Int5[0]', EmbeddedDataType.sint32, value_at_loc=1111)
        self.assert_var('/global/file2GlobalArray1Int5[1]', EmbeddedDataType.sint32, value_at_loc=2222)
        self.assert_var('/global/file2GlobalArray1Int5[2]', EmbeddedDataType.sint32, value_at_loc=3333)
        self.assert_var('/global/file2GlobalArray1Int5[3]', EmbeddedDataType.sint32, value_at_loc=4444)
        self.assert_var('/global/file2GlobalArray1Int5[4]', EmbeddedDataType.sint32, value_at_loc=5555)

    def test_array_2d(self):
        self.assert_var('/global/file2GlobalArray2x2Float[0][0]', EmbeddedDataType.float32, value_at_loc=1.1)
        self.assert_var('/global/file2GlobalArray2x2Float[0][1]', EmbeddedDataType.float32, value_at_loc=2.2)
        self.assert_var('/global/file2GlobalArray2x2Float[1][0]', EmbeddedDataType.float32, value_at_loc=3.3)
        self.assert_var('/global/file2GlobalArray2x2Float[1][1]', EmbeddedDataType.float32, value_at_loc=4.4)


if __name__ == '__main__':
    import unittest
    unittest.main()
