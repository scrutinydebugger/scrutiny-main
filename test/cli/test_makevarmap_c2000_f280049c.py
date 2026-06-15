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


class TestMakeVarMap_C2000_f280049C(ScrutinyUnitTest):
    ELF_FILE = get_artifact('20260604_ti_c2000_f280049c_test.elf')
    MEMDUMP_FILE = get_artifact('20260604_ti_c2000_f280049c_test.elf.memdump')

    @classmethod
    def setUpClass(cls) -> None:
        cls.memdump_parser = C2000MemdumpParser(cls.MEMDUMP_FILE)
        cls.varmap = ElfDwarfVarExtractor(cls.ELF_FILE).get_varmap()
        return super().setUpClass()

    def assert_var(self,
                   fullname,
                   thetype: Optional[EmbeddedDataType] = None,
                   bitsize=None,
                   bitoffset=None,
                   value_at_loc=None,
                   float_tol: Optional[float] = None):
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

        self.assert_var('/global/NamespaceInFile1/NamespaceInFile1Nested1/file1GlobalNestedVar1', EmbeddedDataType.uint32, value_at_loc=1111111111)

        self.assert_var('/static/file1.cpp/funcInFile1(int, int)/staticLongInFuncFile1', EmbeddedDataType.sint64, value_at_loc=-0x123456789abcdef)
