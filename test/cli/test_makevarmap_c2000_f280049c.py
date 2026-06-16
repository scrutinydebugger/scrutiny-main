#    test_makevarmap_c2000_f280049c.py
#        A test suite that check the ability to make a varmap that correctly represent a .elf
#        built with TI C2000 compiler
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from test import ScrutinyUnitTest
from test.artifacts import get_artifact
from scrutiny.tools.c2000_memdump_parser import C2000MemdumpParser
from scrutiny.core.bintools.elf_dwarf_var_extractor import ElfDwarfVarExtractor
from scrutiny.core.basic_types import *

from scrutiny.tools.typing import *


class KnownEnumTypedDictEntry(TypedDict):
    name: str
    values: Dict[str, int]


KnownEnumTypedDict: TypeAlias = Dict[str, KnownEnumTypedDictEntry]


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
    'File3Enum': {
        "name": "File3Enum",
        "values": {
            "AAA": 0,
            "BBB": 1,
            "CCC": 2
        }
    },
    'File4EnumA': {
        "name": "File4EnumA",
        "values": {
            "XXX": 123,
            "YYY": 456
        }
    }
}


class TestMakeVarMap_C2000_f280049C(ScrutinyUnitTest):
    ELF_FILE = get_artifact('20260604_ti_c2000_f280049c_test.elf')
    MEMDUMP_FILE = get_artifact('20260604_ti_c2000_f280049c_test.elf.memdump')

    @classmethod
    def setUpClass(cls) -> None:
        cls.extractor = ElfDwarfVarExtractor(cls.ELF_FILE)
        cls.memdump_parser = C2000MemdumpParser(cls.MEMDUMP_FILE)
        cls.varmap = cls.extractor.get_varmap()
        return super().setUpClass()

    def setUp(self) -> None:
        errors = self.extractor.get_errors()
        self.assertEqual(errors.total_count(), 0, f"Errors while parsing {errors.get_first_exc()}")
        return super().setUp()

    def assert_var(self,
                   fullname,
                   thetype: Optional[EmbeddedDataType] = None,
                   addr: Optional[int] = None,
                   bitsize=None,
                   bitoffset=None,
                   value_at_loc=None,
                   float_tol: Optional[float] = None,
                   enum: Optional[str] = None):
        v = self.varmap.get_var(fullname)
        self.assertTrue(v.get_size() % 2 == 0, "variable size not a multiple of 16bits")  # C2000 has a byte of 16bits.

        if thetype is not None:
            self.assertEqual(thetype, v.get_type())
            if thetype in [EmbeddedDataType.float32, EmbeddedDataType.float64] and float_tol is None:
                float_tol = 0.00001

        if bitsize is not None:
            self.assertEqual(v.bitsize, bitsize)

        if bitoffset is not None:
            self.assertEqual(v.bitoffset, bitoffset)

        if addr is not None:
            self.assertEqual(v.get_address(), addr)

        if enum is not None:
            self.assertIn(enum, KNOWN_ENUMS)
            self.assertIsNotNone(v.enum)
            self.assertEqual(KNOWN_ENUMS[enum]['name'], v.enum.get_name())
            for key, value in KNOWN_ENUMS[enum]['values'].items():
                value2 = v.enum.get_value(key)
                self.assertIsNotNone(value2)
                self.assertEqual(value2, value)
        else:
            self.assertIsNone(v.enum)

        if value_at_loc is not None:
            if v.has_absolute_address():
                data = self.memdump_parser.read_little_endian(v.get_address(), v.get_size() // 2)
            else:
                raise NotImplementedError("todo")

            val = v.decode(data)

            if float_tol is not None:
                self.assertAlmostEqual(val, value_at_loc, delta=float_tol)
            else:
                self.assertEqual(val, value_at_loc)
        return v

    def test_char_16bits(self):
        uchar_type = self.varmap.get_vartype_from_base_type('unsigned char')
        self.assertEqual(uchar_type, EmbeddedDataType.uint16),

    def test_file1(self):
        self.assert_var('/global/file1GlobalChar', EmbeddedDataType.sint16, value_at_loc=-10)
        self.assert_var('/global/file1GlobalInt', EmbeddedDataType.sint16, value_at_loc=-1000)
        self.assert_var('/global/file1GlobalShort', EmbeddedDataType.sint16, value_at_loc=-999)
        self.assert_var('/global/file1GlobalLong', EmbeddedDataType.sint32, value_at_loc=-100000)
        self.assert_var('/global/file1GlobalUnsignedChar', EmbeddedDataType.uint16, value_at_loc=55)
        self.assert_var('/global/file1GlobalUnsignedInt', EmbeddedDataType.uint16, value_at_loc=10001)
        self.assert_var('/global/file1GlobalUnsignedShort', EmbeddedDataType.uint16, value_at_loc=50000)
        self.assert_var('/global/file1GlobalUnsignedLong', EmbeddedDataType.uint32, value_at_loc=100002)
        self.assert_var('/global/file1GlobalFloat', EmbeddedDataType.float32, value_at_loc=3.1415926)
        self.assert_var('/global/file1GlobalDouble', EmbeddedDataType.float64, value_at_loc=1.71)
        self.assert_var('/global/file1GlobalBool', EmbeddedDataType.bool16, value_at_loc=True)

        self.assert_var('/static/file1.cpp/file1StaticChar', EmbeddedDataType.sint16, value_at_loc=99)
        self.assert_var('/static/file1.cpp/file1StaticInt', EmbeddedDataType.sint16, value_at_loc=9876)
        self.assert_var('/static/file1.cpp/file1StaticShort', EmbeddedDataType.sint16, value_at_loc=-666)
        self.assert_var('/static/file1.cpp/file1StaticLong', EmbeddedDataType.sint32, value_at_loc=-55555)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedChar', EmbeddedDataType.uint16, value_at_loc=44)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedInt', EmbeddedDataType.uint16, value_at_loc=3333)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedShort', EmbeddedDataType.uint16, value_at_loc=22222)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedLong', EmbeddedDataType.uint32, value_at_loc=321321)
        self.assert_var('/static/file1.cpp/file1StaticFloat', EmbeddedDataType.float32, value_at_loc=1.23456789)
        self.assert_var('/static/file1.cpp/file1StaticDouble', EmbeddedDataType.float64, value_at_loc=9.87654321)
        self.assert_var('/static/file1.cpp/file1StaticBool', EmbeddedDataType.bool16, value_at_loc=True)

        self.assert_var('/static/file1.cpp/file1StructAStaticInstance/structAMemberInt', EmbeddedDataType.sint16, value_at_loc=-789)
        self.assert_var('/static/file1.cpp/file1StructAStaticInstance/structAMemberUInt', EmbeddedDataType.uint16, value_at_loc=1472)
        self.assert_var('/static/file1.cpp/file1StructAStaticInstance/structAMemberFloat', EmbeddedDataType.float32, value_at_loc=88.88)
        self.assert_var('/static/file1.cpp/file1StructAStaticInstance/structAMemberDouble', EmbeddedDataType.float64, value_at_loc=99.99)
        self.assert_var('/static/file1.cpp/file1StructAStaticInstance/structAMemberBool', EmbeddedDataType.bool16, value_at_loc=True)

        self.assert_var('/static/file1.cpp/NamespaceInFile1/NamespaceInFile1Nested1/file1StaticNestedVar1',
                        EmbeddedDataType.uint32, value_at_loc=945612345)

        self.assert_var('/global/file1StructAInstance/structAMemberInt', EmbeddedDataType.sint16, value_at_loc=-654)
        self.assert_var('/global/file1StructAInstance/structAMemberUInt', EmbeddedDataType.uint16, value_at_loc=25814)
        self.assert_var('/global/file1StructAInstance/structAMemberFloat', EmbeddedDataType.float32, value_at_loc=77.77)
        self.assert_var('/global/file1StructAInstance/structAMemberDouble', EmbeddedDataType.float64, value_at_loc=66.66)
        self.assert_var('/global/file1StructAInstance/structAMemberBool', EmbeddedDataType.bool16, value_at_loc=False)

        self.assert_var('/global/file1StructBInstance/structBMemberInt', EmbeddedDataType.sint16, value_at_loc=5555)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberInt', EmbeddedDataType.sint16, value_at_loc=-19999)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberUInt', EmbeddedDataType.uint16, value_at_loc=33333)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberFloat', EmbeddedDataType.float32, value_at_loc=33.33)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberDouble', EmbeddedDataType.float64, value_at_loc=22.22)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberBool', EmbeddedDataType.bool16, value_at_loc=True)

        self.assert_var('/global/file1StructCInstance/structCMemberInt', EmbeddedDataType.sint16, value_at_loc=8887)
        self.assert_var('/global/file1StructCInstance/nestedStructInstance/nestedStructMemberInt', EmbeddedDataType.sint16, value_at_loc=22987)
        self.assert_var('/global/file1StructCInstance/nestedStructInstance/nestedStructMemberFloat', EmbeddedDataType.float32, value_at_loc=-147.55)
        self.assert_var('/global/file1StructCInstance/nestedStructInstance/nestedStructInstance2/nestedStructInstance2MemberDouble',
                        EmbeddedDataType.float64, value_at_loc=654.654)

        self.assert_var('/global/file1StructDInstance/bitfieldA', EmbeddedDataType.uint16, value_at_loc=13, bitoffset=0, bitsize=4)
        address_A = self.varmap.get_var('/global/file1StructDInstance/bitfieldA').get_address()
        self.assert_var('/global/file1StructDInstance/bitfieldB', EmbeddedDataType.uint16,
                        value_at_loc=4100, addr=address_A + 1, bitoffset=0, bitsize=13)
        self.assert_var('/global/file1StructDInstance/bitfieldC', EmbeddedDataType.uint16,
                        value_at_loc=222, addr=address_A + 2, bitoffset=0, bitsize=8)
        self.assert_var('/global/file1StructDInstance/bitfieldD', EmbeddedDataType.uint16, value_at_loc=12345, addr=address_A + 3)
        self.assert_var('/global/file1StructDInstance/bitfieldE', EmbeddedDataType.uint16,
                        value_at_loc=777, addr=address_A + 4, bitoffset=0, bitsize=10)

        self.assert_var('/global/NamespaceInFile1/NamespaceInFile1Nested1/file1GlobalNestedVar1', EmbeddedDataType.uint32, value_at_loc=1111111111)
        self.assert_var('/static/file1.cpp/funcInFile1(int, int)/staticLongInFuncFile1', EmbeddedDataType.sint64, value_at_loc=-0x123456789abcdef)

    def test_file2(self):
        self.assert_var('/global/file2GlobalChar', EmbeddedDataType.sint16, value_at_loc=20)
        self.assert_var('/global/file2GlobalInt', EmbeddedDataType.sint16, value_at_loc=2000)
        self.assert_var('/global/file2GlobalShort', EmbeddedDataType.sint16, value_at_loc=998)
        self.assert_var('/global/file2GlobalLong', EmbeddedDataType.sint32, value_at_loc=555555)
        self.assert_var('/global/file2GlobalUnsignedChar', EmbeddedDataType.uint16, value_at_loc=254)
        self.assert_var('/global/file2GlobalUnsignedInt', EmbeddedDataType.uint16, value_at_loc=1234)
        self.assert_var('/global/file2GlobalUnsignedShort', EmbeddedDataType.uint16, value_at_loc=12345)
        self.assert_var('/global/file2GlobalUnsignedLong', EmbeddedDataType.uint32, value_at_loc=1234567)
        self.assert_var('/global/file2GlobalFloat', EmbeddedDataType.float32, value_at_loc=0.1)
        self.assert_var('/global/file2GlobalDouble', EmbeddedDataType.float64, value_at_loc=0.11111111111111)
        self.assert_var('/global/file2GlobalBool', EmbeddedDataType.bool16, value_at_loc=False)

        self.assert_var('/static/file2.cpp/file2StaticChar', EmbeddedDataType.sint16, value_at_loc=-66)
        self.assert_var('/static/file2.cpp/file2StaticInt', EmbeddedDataType.sint16, value_at_loc=-8745)
        self.assert_var('/static/file2.cpp/file2StaticShort', EmbeddedDataType.sint16, value_at_loc=-9876)
        self.assert_var('/static/file2.cpp/file2StaticLong', EmbeddedDataType.sint32, value_at_loc=-12345678)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedChar', EmbeddedDataType.uint16, value_at_loc=12)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedInt', EmbeddedDataType.uint16, value_at_loc=34)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedShort', EmbeddedDataType.uint16, value_at_loc=56)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedLong', EmbeddedDataType.uint32, value_at_loc=78)
        self.assert_var('/static/file2.cpp/file2StaticFloat', EmbeddedDataType.float32, value_at_loc=2.22222)
        self.assert_var('/static/file2.cpp/file2StaticDouble', EmbeddedDataType.float64, value_at_loc=3.3333)
        self.assert_var('/static/file2.cpp/file2StaticBool', EmbeddedDataType.bool16, value_at_loc=True)

        self.assert_var('/global/NamespaceInFile2/instance_enumA', EmbeddedDataType.uint16, enum='EnumA', value_at_loc=1)
        self.assert_var('/static/file2.cpp/NamespaceInFile2/staticInstance_enumA', EmbeddedDataType.uint16, enum='EnumA', value_at_loc=100)
        self.assert_var('/global/instance2_enumA', EmbeddedDataType.uint16, enum='EnumA', value_at_loc=101)
        self.assert_var('/static/file2.cpp/staticInstance2_enumA', EmbeddedDataType.uint16, enum='EnumA', value_at_loc=0)

        self.assert_var('/global/file2GlobalArray1Int5/file2GlobalArray1Int5[0]', EmbeddedDataType.sint16, value_at_loc=1111)
        self.assert_var('/global/file2GlobalArray1Int5/file2GlobalArray1Int5[1]', EmbeddedDataType.sint16, value_at_loc=2222)
        self.assert_var('/global/file2GlobalArray1Int5/file2GlobalArray1Int5[2]', EmbeddedDataType.sint16, value_at_loc=3333)
        self.assert_var('/global/file2GlobalArray1Int5/file2GlobalArray1Int5[3]', EmbeddedDataType.sint16, value_at_loc=4444)
        self.assert_var('/global/file2GlobalArray1Int5/file2GlobalArray1Int5[4]', EmbeddedDataType.sint16, value_at_loc=5555)

        self.assert_var('/global/file2GlobalArray2x2Float/file2GlobalArray2x2Float[0][0]', EmbeddedDataType.float32, value_at_loc=1.1)
        self.assert_var('/global/file2GlobalArray2x2Float/file2GlobalArray2x2Float[0][1]', EmbeddedDataType.float32, value_at_loc=2.2)
        self.assert_var('/global/file2GlobalArray2x2Float/file2GlobalArray2x2Float[1][0]', EmbeddedDataType.float32, value_at_loc=3.3)
        self.assert_var('/global/file2GlobalArray2x2Float/file2GlobalArray2x2Float[1][1]', EmbeddedDataType.float32, value_at_loc=4.4)

        self.assert_var('/global/file2ClassBInstance/intInClassB', EmbeddedDataType.sint16, value_at_loc=-11111)
        self.assert_var('/global/file2ClassBInstance/nestedClassInstance/intInClassBA', EmbeddedDataType.sint16, value_at_loc=-22222)
        self.assert_var('/global/file2ClassBInstance/nestedClassInstance/classAInstance/intInClassA', EmbeddedDataType.sint16, value_at_loc=-3333)

        self.assert_var('/static/file2.cpp/file2ClassBStaticInstance/intInClassB', EmbeddedDataType.sint16, value_at_loc=-4444)
        self.assert_var('/static/file2.cpp/file2ClassBStaticInstance/nestedClassInstance/intInClassBA', EmbeddedDataType.sint16, value_at_loc=-5555)
        self.assert_var('/static/file2.cpp/file2ClassBStaticInstance/nestedClassInstance/classAInstance/intInClassA',
                        EmbeddedDataType.sint16, value_at_loc=-6666)

        self.assert_var('/static/file2.cpp/file2func1()/file2func1Var', EmbeddedDataType.sint16, value_at_loc=-8877)
        self.assert_var('/static/file2.cpp/file2func1(int)/file2func1Var', EmbeddedDataType.float64, value_at_loc=963258741.123)

    def test_file3(self):
        self.assert_var('/global/file3_union/u64_var', EmbeddedDataType.uint64, value_at_loc=0x012345679988AABB)
        self.assert_var('/global/file3_union/u32_var', EmbeddedDataType.uint32, value_at_loc=0x9988AABB)
        self.assert_var('/global/file3_union/u16_var', EmbeddedDataType.uint16, value_at_loc=0xAABB)

        # 0x0055 -> 0x0054 -> 0x0074
        self.assert_var('/global/file3_anonbitfield_in_union/val', EmbeddedDataType.uint16, value_at_loc=0x0074)
        self.assert_var('/global/file3_anonbitfield_in_union/bits/bit1', EmbeddedDataType.uint16, value_at_loc=0)
        self.assert_var('/global/file3_anonbitfield_in_union/bits/bit5_8', EmbeddedDataType.uint16, value_at_loc=7)
        self.assert_var('/global/file3_anonbitfield_in_union/bits/bit9_13', EmbeddedDataType.uint16, value_at_loc=0)

        self.assert_var('/global/file3_test_class/m_file3testclass_inclassenum', EmbeddedDataType.uint16, value_at_loc=1, enum='File3Enum')

        # 0x123456789abcdef0 -> 0x12345678AABBCCDD ->  0x123456787766CCDD -> 0x123456787766CCC2
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field1', EmbeddedDataType.uint32, value_at_loc=0x11223344)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field2', EmbeddedDataType.uint32, value_at_loc=0x55667788)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_u64', EmbeddedDataType.uint64, value_at_loc=0x123456787766CCC2)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_u32/p0', EmbeddedDataType.uint32, value_at_loc=0x7766CCC2)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_u16/p1', EmbeddedDataType.uint16, value_at_loc=0x7766)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_enum_bitfields/p0',
                        EmbeddedDataType.uint16, value_at_loc=2, enum='File3Enum')

    def test_file4(self):
        self.assert_var('/global/file4classB/some_bool', EmbeddedDataType.bool16, value_at_loc=True)
        self.assert_var('/global/file4classB/array_of_A2/array_of_A2[2][0]/xxx', EmbeddedDataType.uint32, value_at_loc=0xdeadbeef)
        self.assert_var('/global/file4classB/array_of_A2/array_of_A2[2][0]/yyy/yyy[0][0]', EmbeddedDataType.sint32, value_at_loc=0x10001111)
        self.assert_var('/global/file4classB/array_of_A2/array_of_A2[2][0]/yyy/yyy[0][1]', EmbeddedDataType.sint32, value_at_loc=0x20002222)
        self.assert_var('/global/file4classB/array_of_A2/array_of_A2[2][0]/yyy/yyy[0][2]', EmbeddedDataType.sint32, value_at_loc=0x30003333)
        self.assert_var('/global/file4classB/array_of_A2/array_of_A2[2][0]/yyy/yyy[1][2]', EmbeddedDataType.sint32, value_at_loc=0x40004444)
        self.assert_var('/global/file4classB/array_of_A2/array_of_A2[2][0]/zzz/zzz[0][0][0]', EmbeddedDataType.uint16, value_at_loc=0x5566)
        self.assert_var('/global/file4classB/array_of_A2/array_of_A2[2][0]/zzz/zzz[1][2][3]', EmbeddedDataType.uint16, value_at_loc=0x6789)
        self.assert_var('/global/file4classB/array_of_A2/array_of_A2[2][0]/A2enum', EmbeddedDataType.uint16, enum='File4EnumA', value_at_loc=456)

        self.assert_var('/global/file4classB_array/file4classB_array[0]/some_bool', EmbeddedDataType.bool16, value_at_loc=True)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[0]/array_of_A2/array_of_A2[2][0]/xxx', EmbeddedDataType.uint32, value_at_loc=0xdeadbeef + 1)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[0]/array_of_A2/array_of_A2[2][0]/yyy/yyy[0][0]', EmbeddedDataType.sint32, value_at_loc=0x10001111 + 1)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[0]/array_of_A2/array_of_A2[2][0]/yyy/yyy[0][1]', EmbeddedDataType.sint32, value_at_loc=0x20002222 + 1)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[0]/array_of_A2/array_of_A2[2][0]/yyy/yyy[0][2]', EmbeddedDataType.sint32, value_at_loc=0x30003333 + 1)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[0]/array_of_A2/array_of_A2[2][0]/yyy/yyy[1][2]', EmbeddedDataType.sint32, value_at_loc=0x40004444 + 1)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[0]/array_of_A2/array_of_A2[2][0]/zzz/zzz[0][0][0]', EmbeddedDataType.uint16, value_at_loc=0x5566 + 1)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[0]/array_of_A2/array_of_A2[2][0]/zzz/zzz[1][2][3]', EmbeddedDataType.uint16, value_at_loc=0x6789 + 1)
        self.assert_var('/global/file4classB_array/file4classB_array[0]/array_of_A2/array_of_A2[2][0]/A2enum',
                        EmbeddedDataType.uint16, enum='File4EnumA', value_at_loc=123)

        self.assert_var('/global/file4classB_array/file4classB_array[1]/some_bool', EmbeddedDataType.bool16, value_at_loc=True)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[1]/array_of_A2/array_of_A2[2][0]/xxx', EmbeddedDataType.uint32, value_at_loc=0xdeadbeef + 2)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[1]/array_of_A2/array_of_A2[2][0]/yyy/yyy[0][0]', EmbeddedDataType.sint32, value_at_loc=0x10001111 + 2)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[1]/array_of_A2/array_of_A2[2][0]/yyy/yyy[0][1]', EmbeddedDataType.sint32, value_at_loc=0x20002222 + 2)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[1]/array_of_A2/array_of_A2[2][0]/yyy/yyy[0][2]', EmbeddedDataType.sint32, value_at_loc=0x30003333 + 2)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[1]/array_of_A2/array_of_A2[2][0]/yyy/yyy[1][2]', EmbeddedDataType.sint32, value_at_loc=0x40004444 + 2)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[1]/array_of_A2/array_of_A2[2][0]/zzz/zzz[0][0][0]', EmbeddedDataType.uint16, value_at_loc=0x5566 + 2)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[1]/array_of_A2/array_of_A2[2][0]/zzz/zzz[1][2][3]', EmbeddedDataType.uint16, value_at_loc=0x6789 + 2)
        self.assert_var('/global/file4classB_array/file4classB_array[1]/array_of_A2/array_of_A2[2][0]/A2enum',
                        EmbeddedDataType.uint16, enum='File4EnumA', value_at_loc=123)

        self.assert_var('/global/file4classB_array/file4classB_array[2]/some_bool', EmbeddedDataType.bool16, value_at_loc=False)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[2]/array_of_A2/array_of_A2[2][0]/xxx', EmbeddedDataType.uint32, value_at_loc=0xdeadbeef + 3)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[2]/array_of_A2/array_of_A2[2][0]/yyy/yyy[0][0]', EmbeddedDataType.sint32, value_at_loc=0x10001111 + 3)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[2]/array_of_A2/array_of_A2[2][0]/yyy/yyy[0][1]', EmbeddedDataType.sint32, value_at_loc=0x20002222 + 3)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[2]/array_of_A2/array_of_A2[2][0]/yyy/yyy[0][2]', EmbeddedDataType.sint32, value_at_loc=0x30003333 + 3)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[2]/array_of_A2/array_of_A2[2][0]/yyy/yyy[1][2]', EmbeddedDataType.sint32, value_at_loc=0x40004444 + 3)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[2]/array_of_A2/array_of_A2[2][0]/zzz/zzz[0][0][0]', EmbeddedDataType.uint16, value_at_loc=0x5566 + 3)
        self.assert_var(
            '/global/file4classB_array/file4classB_array[2]/array_of_A2/array_of_A2[2][0]/zzz/zzz[1][2][3]', EmbeddedDataType.uint16, value_at_loc=0x6789 + 3)
        self.assert_var('/global/file4classB_array/file4classB_array[2]/array_of_A2/array_of_A2[2][0]/A2enum',
                        EmbeddedDataType.uint16, enum='File4EnumA', value_at_loc=456)

        self.assert_var('/global/file4classA3_array/file4classA3_array[0][0]/the_union/u32', EmbeddedDataType.uint32, value_at_loc=0x12345678)
        self.assert_var('/global/file4classA3_array/file4classA3_array[0][1]/the_union/u32', EmbeddedDataType.uint32, value_at_loc=0xAABBCCDD)
        self.assert_var('/global/file4classA3_array/file4classA3_array[1][0]/the_union/u32', EmbeddedDataType.uint32, value_at_loc=0x11223344)
        self.assert_var('/global/file4classA3_array/file4classA3_array[1][1]/the_union/u32', EmbeddedDataType.uint32, value_at_loc=0x55667788)
