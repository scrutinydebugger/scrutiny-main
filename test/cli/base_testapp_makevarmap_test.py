#    base_testapp_makevarmap_test.py
#        Base test for symbol extraction based on C++ TestApp
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
    },
    'File3EnumInClass': {
        "name": "File3EnumInClass",
        "values": {
            "AAA": 0,
            "BBB": 1,
            "CCC": 2
        }
    }
}


class BaseTestAppMakeVarmapTest(BaseVarmapTest):
    known_enums = KNOWN_ENUMS

    def test_env(self):
        self.assertEqual(self.varmap.get_endianness(), Endianness.Little)

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
        self.assert_var('/global/file1GlobalBool', EmbeddedDataType.boolean, value_at_loc=True)

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
        self.assert_var('/global/file2GlobalBool', EmbeddedDataType.boolean, value_at_loc=False)

    def test_file1_static_basic_types(self):
        self.assert_var('/static/file1.cpp/file1StaticChar', EmbeddedDataType.sint8, value_at_loc=99)
        self.assert_var('/static/file1.cpp/file1StaticInt', EmbeddedDataType.sint32, value_at_loc=987654)
        self.assert_var('/static/file1.cpp/file1StaticShort', EmbeddedDataType.sint16, value_at_loc=-666)
        self.assert_var('/static/file1.cpp/file1StaticLong', EmbeddedDataType.sint64, value_at_loc=-55555)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedChar', EmbeddedDataType.uint8, value_at_loc=44)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedInt', EmbeddedDataType.uint32, value_at_loc=3333)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedShort', EmbeddedDataType.uint16, value_at_loc=22222)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedLong', EmbeddedDataType.uint64, value_at_loc=321321)
        self.assert_var('/static/file1.cpp/file1StaticFloat', EmbeddedDataType.float32, value_at_loc=1.23456789)
        self.assert_var('/static/file1.cpp/file1StaticDouble', EmbeddedDataType.float64, value_at_loc=9.87654321)
        self.assert_var('/static/file1.cpp/file1StaticBool', EmbeddedDataType.boolean, value_at_loc=True)

    def test_file2_static_basic_types(self):
        self.assert_var('/static/file2.cpp/file2StaticChar', EmbeddedDataType.sint8, value_at_loc=-66)
        self.assert_var('/static/file2.cpp/file2StaticInt', EmbeddedDataType.sint32, value_at_loc=-8745)
        self.assert_var('/static/file2.cpp/file2StaticShort', EmbeddedDataType.sint16, value_at_loc=-9876)
        self.assert_var('/static/file2.cpp/file2StaticLong', EmbeddedDataType.sint64, value_at_loc=-12345678)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedChar', EmbeddedDataType.uint8, value_at_loc=12)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedInt', EmbeddedDataType.uint32, value_at_loc=34)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedShort', EmbeddedDataType.uint16, value_at_loc=56)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedLong', EmbeddedDataType.uint64, value_at_loc=78)
        self.assert_var('/static/file2.cpp/file2StaticFloat', EmbeddedDataType.float32, value_at_loc=2.22222)
        self.assert_var('/static/file2.cpp/file2StaticDouble', EmbeddedDataType.float64, value_at_loc=3.3333)
        self.assert_var('/static/file2.cpp/file2StaticBool', EmbeddedDataType.boolean, value_at_loc=True)

    def test_func_static(self):
        self.assert_var('/static/file2.cpp/file2func1()/file2func1Var', EmbeddedDataType.sint32, value_at_loc=-88778877)
        self.assert_var('/static/file2.cpp/file2func1(int)/file2func1Var', EmbeddedDataType.float64, value_at_loc=963258741.123)
        self.assert_var('/static/main.cpp/main/staticIntInMainFunc', EmbeddedDataType.sint32, value_at_loc=22222)
        self.assert_var('/static/main.cpp/mainfunc1()/mainfunc1Var', EmbeddedDataType.sint32, value_at_loc=7777777)
        self.assert_var('/static/main.cpp/mainfunc1(int)/mainfunc1Var', EmbeddedDataType.float64, value_at_loc=8888888.88)
        self.assert_var('/static/file1.cpp/funcInFile1(int, int)/staticLongInFuncFile1', EmbeddedDataType.sint64, value_at_loc=-0x123456789abcdef)

    def test_namespace(self):
        self.assert_var('/global/NamespaceInFile1/NamespaceInFile1Nested1/file1GlobalNestedVar1', EmbeddedDataType.uint64, value_at_loc=1111111111)
        self.assert_var('/static/file1.cpp/NamespaceInFile1/NamespaceInFile1Nested1/file1StaticNestedVar1',
                        EmbeddedDataType.uint64, value_at_loc=945612345)

    def assert_is_enumA(self, fullpath, value_at_loc=None):
        return self.assert_var(fullpath, EmbeddedDataType.uint32, value_at_loc=value_at_loc, enum='EnumA')

    def test_enum(self):
        self.assert_is_enumA('/global/NamespaceInFile2/instance_enumA', value_at_loc=1)
        self.assert_is_enumA('/global/instance2_enumA', value_at_loc=101)
        self.assert_is_enumA('/static/file2.cpp/staticInstance2_enumA', value_at_loc=0)
        self.assert_is_enumA('/static/file2.cpp/NamespaceInFile2/staticInstance_enumA', value_at_loc=100)

    def test_structA(self):
        v = self.assert_var('/global/file1StructAInstance/structAMemberInt', EmbeddedDataType.sint32, value_at_loc=-654)
        self.assert_var('/global/file1StructAInstance/structAMemberUInt', EmbeddedDataType.uint32, addr=v.get_address() + 4, value_at_loc=258147)
        self.assert_var('/global/file1StructAInstance/structAMemberFloat', EmbeddedDataType.float32, addr=v.get_address() + 8, value_at_loc=77.77)
        self.assert_var('/global/file1StructAInstance/structAMemberDouble', EmbeddedDataType.float64, addr=v.get_address() + 12, value_at_loc=66.66)
        self.assert_var('/global/file1StructAInstance/structAMemberBool', EmbeddedDataType.boolean, addr=v.get_address() + 20, value_at_loc=False)

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
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberBool',
                        EmbeddedDataType.boolean, addr=v.get_address() + 24, value_at_loc=True)

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

    def test_class_file2(self):
        self.assert_var('/global/file2ClassBInstance/intInClassB', EmbeddedDataType.sint32, value_at_loc=-11111)
        self.assert_var('/global/file2ClassBInstance/nestedClassInstance/intInClassBA', EmbeddedDataType.sint32, value_at_loc=-22222)
        self.assert_var('/global/file2ClassBInstance/nestedClassInstance/classAInstance/intInClassA', EmbeddedDataType.sint32, value_at_loc=-33333)

        self.assert_var('/static/file2.cpp/file2ClassBStaticInstance/intInClassB', EmbeddedDataType.sint32, value_at_loc=-44444)
        self.assert_var('/static/file2.cpp/file2ClassBStaticInstance/nestedClassInstance/intInClassBA', EmbeddedDataType.sint32, value_at_loc=-55555)
        self.assert_var('/static/file2.cpp/file2ClassBStaticInstance/nestedClassInstance/classAInstance/intInClassA',
                        EmbeddedDataType.sint32, value_at_loc=-66666)

    def test_file3_union(self):
        vu8 = self.assert_var('/global/file3_union/u8_var', EmbeddedDataType.uint8, value_at_loc=0x99)
        vu16 = self.assert_var('/global/file3_union/u16_var', EmbeddedDataType.uint16, value_at_loc=0xAA99)
        vu32 = self.assert_var('/global/file3_union/u32_var', EmbeddedDataType.uint32, value_at_loc=0x1234AA99)
        self.assertEqual(vu8.get_address(), vu16.get_address())
        self.assertEqual(vu16.get_address(), vu32.get_address())

        v1 = self.assert_var('/global/file3_anonbitfield_in_union/bits/bit5_8', EmbeddedDataType.uint8, bitoffset=4, bitsize=4, value_at_loc=7)
        v2 = self.assert_var('/global/file3_anonbitfield_in_union/bits/bit1', EmbeddedDataType.uint8, bitoffset=0, bitsize=1, value_at_loc=0)
        v3 = self.assert_var('/global/file3_anonbitfield_in_union/val', EmbeddedDataType.uint8, value_at_loc=0x74)
        self.assertEqual(v1.get_address(), v2.get_address())
        self.assertEqual(v1.get_address(), v3.get_address())

        self.assert_var('/global/file3_test_class/m_file3testclass_inclassenum', EmbeddedDataType.uint32, value_at_loc=1, enum='File3EnumInClass')

        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field1', EmbeddedDataType.uint32, value_at_loc=0x11223344)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field2', EmbeddedDataType.uint32, value_at_loc=0x55667788)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_u8/p3', EmbeddedDataType.uint8, value_at_loc=0xAA)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_u16/p0', EmbeddedDataType.uint16, value_at_loc=0xBCC2)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_u32', EmbeddedDataType.uint32, value_at_loc=0xAA34BCC2)

        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_enum_bitfields/p0', EmbeddedDataType.uint32,
                        value_at_loc=2, bitoffset=0, bitsize=5, enum='File3EnumInClass')
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_enum_bitfields/p1', EmbeddedDataType.uint32,
                        value_at_loc=0x66, bitoffset=5, bitsize=7, enum='File3EnumInClass')
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_enum_bitfields/p2', EmbeddedDataType.uint32,
                        value_at_loc=0x34B, bitoffset=12, bitsize=10, enum='File3EnumInClass')
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_enum_bitfields/p3', EmbeddedDataType.uint32,
                        value_at_loc=0x2A8, bitoffset=22, bitsize=10, enum='File3EnumInClass')
