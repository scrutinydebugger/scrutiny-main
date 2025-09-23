#    test_makevarmap_aurixtc334_tasking_11r8.py
#        A test suite testing Tasking compiler V1.1r8 on a Aurix TC334
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

import unittest

from scrutiny.core.basic_types import *
from scrutiny.core.variable import *
from test.artifacts import get_artifact
from test import ScrutinyUnitTest
from test.cli.base_varmap_test import BaseVarmapTest, KnownEnumTypedDict

from scrutiny.tools.typing import *


KNOWN_ENUMS: KnownEnumTypedDict = {
    "IfxPort_OutputIdx": {
        "name": "IfxPort_OutputIdx",
        "values": {
            "IfxPort_OutputIdx_general": 128,
            "IfxPort_OutputIdx_alt1": 136,
            "IfxPort_OutputIdx_alt2": 144,
            "IfxPort_OutputIdx_alt3": 152,
            "IfxPort_OutputIdx_alt4": 160,
            "IfxPort_OutputIdx_alt5": 168,
            "IfxPort_OutputIdx_alt6": 176,
            "IfxPort_OutputIdx_alt7": 184
        }
    },
    "Ifx_RxSel": {
        "name": "Ifx_RxSel",
        "values": {
            "Ifx_RxSel_a": 0,
            "Ifx_RxSel_b": 1,
            "Ifx_RxSel_c": 2,
            "Ifx_RxSel_d": 3,
            "Ifx_RxSel_e": 4,
            "Ifx_RxSel_f": 5,
            "Ifx_RxSel_g": 6,
            "Ifx_RxSel_h": 7
        }
    },
    "EnumA": {
        'name': 'EnumA',
        'values': {
            'eVal1': 0,
            'eVal2': 1,
            'eVal3': 100,
            'eVal4': 101
        }
    },
    "IfxScuCcu_PllInputClockSelection": {
        "name": "IfxScuCcu_PllInputClockSelection",
        "values": {
            "IfxScuCcu_PllInputClockSelection_fOsc1": 0,
            "IfxScuCcu_PllInputClockSelection_fOsc0": 1,
            "IfxScuCcu_PllInputClockSelection_fSysclk": 2
        }
    },
    "IfxScuCcu_ModEn": {
        "name": "IfxScuCcu_ModEn",
        "values": {
            "IfxScuCcu_ModEn_disabled": 0,
            "IfxScuCcu_ModEn_enabled": 1
        }
    },
    "IfxScuCcu_ModulationAmplitude": {
        "name": "IfxScuCcu_ModulationAmplitude",
        "values": {
            "IfxScuCcu_ModulationAmplitude_0p5": 0,
            "IfxScuCcu_ModulationAmplitude_1p0": 1,
            "IfxScuCcu_ModulationAmplitude_1p25": 2,
            "IfxScuCcu_ModulationAmplitude_1p5": 3,
            "IfxScuCcu_ModulationAmplitude_2p0": 4,
            "IfxScuCcu_ModulationAmplitude_2p5": 5,
            "IfxScuCcu_ModulationAmplitude_count": 6
        }
    },
    "IfxAsclin_DataBufferMode": {
        "name": "IfxAsclin_DataBufferMode",
        "values": {
            "IfxAsclin_DataBufferMode_normal": 0,
            "IfxAsclin_DataBufferMode_timeStampSingle": 1
        }
    },
    "_dbg_nr_t": {
        "name": "_dbg_nr_t",
        "values": {
            "_DBG_EXIT": 1,
            "_DBG_CLOCK": 2,
            "_DBG_OPEN": 3,
            "_DBG_READ": 4,
            "_DBG_WRITE": 5,
            "_DBG_LSEEK": 6,
            "_DBG_CLOSE": 7,
            "_DBG_RENAME": 8,
            "_DBG_UNLINK": 9,
            "_DBG_ACCESS": 10,
            "_DBG_GETCWD": 11,
            "_DBG_CHDIR": 12,
            "_DBG_STAT": 13,
            "_DBG_ARGCV": 14
        }
    }
}


class TestMakeVarMap_AurixTC334_Tasking_v11r8(BaseVarmapTest, ScrutinyUnitTest):
    bin_filename = get_artifact('customtest_20250716_tricore_taskking_1_1r8.elf')
    memdump_filename = get_artifact('customtest_20250716_tricore_taskking_1_1r8.memdump')
    known_enums = KNOWN_ENUMS

    # _CPP_FILT = 'c++filt'
    _CPP_FILT = 'tricore-elf-c++filt'

    def test_file1_globals_basic_types(self):
        self.assert_var('/global/file1GlobalChar', EmbeddedDataType.sint8, value_at_loc=-10)
        self.assert_var('/global/file1GlobalInt', EmbeddedDataType.sint32, value_at_loc=-1000)
        self.assert_var('/global/file1GlobalShort', EmbeddedDataType.sint16, value_at_loc=-999)
        self.assert_var('/global/file1GlobalLong', EmbeddedDataType.sint32, value_at_loc=-100000)
        self.assert_var('/global/file1GlobalUnsignedChar', EmbeddedDataType.uint8, value_at_loc=55)
        self.assert_var('/global/file1GlobalUnsignedInt', EmbeddedDataType.uint32, value_at_loc=100001)
        self.assert_var('/global/file1GlobalUnsignedShort', EmbeddedDataType.uint16, value_at_loc=50000)
        self.assert_var('/global/file1GlobalUnsignedLong', EmbeddedDataType.uint32, value_at_loc=100002)
        self.assert_var('/global/file1GlobalFloat', EmbeddedDataType.float32, value_at_loc=3.1415926)
        self.assert_var('/global/file1GlobalDouble', EmbeddedDataType.float32, value_at_loc=1.71)
        self.assert_var('/global/file1GlobalBool', EmbeddedDataType.sint8, value_at_loc=1)  # bool are char with tasking

    def test_file2_globals_basic_types(self):
        self.assert_var('/global/file2GlobalChar', EmbeddedDataType.sint8, value_at_loc=20)
        self.assert_var('/global/file2GlobalInt', EmbeddedDataType.sint32, value_at_loc=2000)
        self.assert_var('/global/file2GlobalShort', EmbeddedDataType.sint16, value_at_loc=998)
        self.assert_var('/global/file2GlobalLong', EmbeddedDataType.sint32, value_at_loc=555555)
        self.assert_var('/global/file2GlobalUnsignedChar', EmbeddedDataType.uint8, value_at_loc=254)
        self.assert_var('/global/file2GlobalUnsignedInt', EmbeddedDataType.uint32, value_at_loc=123456)
        self.assert_var('/global/file2GlobalUnsignedShort', EmbeddedDataType.uint16, value_at_loc=12345)
        self.assert_var('/global/file2GlobalUnsignedLong', EmbeddedDataType.uint32, value_at_loc=1234567)
        self.assert_var('/global/file2GlobalFloat', EmbeddedDataType.float32, value_at_loc=0.1)
        self.assert_var('/global/file2GlobalDouble', EmbeddedDataType.float32, value_at_loc=0.11111111111111)
        self.assert_var('/global/file2GlobalBool', EmbeddedDataType.sint8, value_at_loc=0)  # bool are char with tasking

    def test_file1_static_basic_types(self):
        self.assert_var('/static/file1.cpp/file1StaticChar', EmbeddedDataType.sint8, value_at_loc=99)
        self.assert_var('/static/file1.cpp/file1StaticInt', EmbeddedDataType.sint32, value_at_loc=987654)
        self.assert_var('/static/file1.cpp/file1StaticShort', EmbeddedDataType.sint16, value_at_loc=-666)
        self.assert_var('/static/file1.cpp/file1StaticLong', EmbeddedDataType.sint32, value_at_loc=-55555)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedChar', EmbeddedDataType.uint8, value_at_loc=44)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedInt', EmbeddedDataType.uint32, value_at_loc=3333)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedShort', EmbeddedDataType.uint16, value_at_loc=22222)
        self.assert_var('/static/file1.cpp/file1StaticUnsignedLong', EmbeddedDataType.uint32, value_at_loc=321321)
        self.assert_var('/static/file1.cpp/file1StaticFloat', EmbeddedDataType.float32, value_at_loc=1.23456789)
        self.assert_var('/static/file1.cpp/file1StaticDouble', EmbeddedDataType.float32, value_at_loc=9.87654321)
        self.assert_var('/static/file1.cpp/file1StaticBool', EmbeddedDataType.sint8, value_at_loc=1)    # bool are char with tasking

    def test_file2_static_basic_types(self):
        self.assert_var('/static/file2.cpp/file2StaticChar', EmbeddedDataType.sint8, value_at_loc=-66)
        self.assert_var('/static/file2.cpp/file2StaticInt', EmbeddedDataType.sint32, value_at_loc=-8745)
        self.assert_var('/static/file2.cpp/file2StaticShort', EmbeddedDataType.sint16, value_at_loc=-9876)
        self.assert_var('/static/file2.cpp/file2StaticLong', EmbeddedDataType.sint32, value_at_loc=-12345678)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedChar', EmbeddedDataType.uint8, value_at_loc=12)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedInt', EmbeddedDataType.uint32, value_at_loc=34)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedShort', EmbeddedDataType.uint16, value_at_loc=56)
        self.assert_var('/static/file2.cpp/file2StaticUnsignedLong', EmbeddedDataType.uint32, value_at_loc=78)
        self.assert_var('/static/file2.cpp/file2StaticFloat', EmbeddedDataType.float32, value_at_loc=2.22222)
        self.assert_var('/static/file2.cpp/file2StaticDouble', EmbeddedDataType.float32, value_at_loc=3.3333)
        self.assert_var('/static/file2.cpp/file2StaticBool', EmbeddedDataType.sint8, value_at_loc=1)

    def test_func_static(self):
        pass
        # Those are not part of the debugging symbol!?
        # Built with -O0, can't be optimized. It looks like the compiler doesn't tell us!

        # self.assert_var('/static/file2.cpp/file2func1()/file2func1Var', EmbeddedDataType.sint32, value_at_loc=-88778877)
        # self.assert_var('/static/file2.cpp/file2func1(int)/file2func1Var', EmbeddedDataType.float64, value_at_loc=963258741.123)
        # self.assert_var('/static/main.cpp/main/staticIntInMainFunc', EmbeddedDataType.sint32, value_at_loc=22222)
        # self.assert_var('/static/main.cpp/mainfunc1()/mainfunc1Var', EmbeddedDataType.sint32, value_at_loc=7777777)
        # self.assert_var('/static/main.cpp/mainfunc1(int)/mainfunc1Var', EmbeddedDataType.float64, value_at_loc=8888888.88)
        # self.assert_var('/static/file1.cpp/funcInFile1(int, int)/staticLongInFuncFile1',
        #                EmbeddedDataType.sint64, value_at_loc=-0x123456789abcdef)  # long long

    def test_namespace(self):
        self.assert_var('/global/NamespaceInFile1/NamespaceInFile1Nested1/file1GlobalNestedVar1', EmbeddedDataType.uint32, value_at_loc=1111111111)
        self.assert_var('/static/file1.cpp/NamespaceInFile1/NamespaceInFile1Nested1/file1StaticNestedVar1',
                        EmbeddedDataType.uint32, value_at_loc=945612345)

    def test_structA(self):
        v = self.assert_var('/global/file1StructAInstance/structAMemberInt', EmbeddedDataType.sint32, value_at_loc=-654)
        self.assert_var('/global/file1StructAInstance/structAMemberUInt', EmbeddedDataType.uint32, addr=v.get_address() + 4, value_at_loc=258147)
        self.assert_var('/global/file1StructAInstance/structAMemberFloat', EmbeddedDataType.float32, addr=v.get_address() + 8, value_at_loc=77.77)
        self.assert_var('/global/file1StructAInstance/structAMemberDouble', EmbeddedDataType.float32, addr=v.get_address() + 12, value_at_loc=66.66)
        self.assert_var('/global/file1StructAInstance/structAMemberBool', EmbeddedDataType.sint8, addr=v.get_address() + 16, value_at_loc=0)

    def test_structB(self):
        v = self.assert_var('/global/file1StructBInstance/structBMemberInt', EmbeddedDataType.sint32, value_at_loc=55555)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberInt',
                        EmbeddedDataType.sint32, addr=v.get_address() + 4, value_at_loc=-199999)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberUInt',
                        EmbeddedDataType.uint32, addr=v.get_address() + 8, value_at_loc=33333)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberFloat',
                        EmbeddedDataType.float32, addr=v.get_address() + 12, value_at_loc=33.33)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberDouble',
                        EmbeddedDataType.float32, addr=v.get_address() + 16, value_at_loc=22.22)
        self.assert_var('/global/file1StructBInstance/structBMemberStructA/structAMemberBool',
                        EmbeddedDataType.sint8, addr=v.get_address() + 20, value_at_loc=1)

    def test_structC(self):
        v = self.assert_var('/global/file1StructCInstance/structCMemberInt', EmbeddedDataType.sint32, value_at_loc=888874)
        self.assert_var('/global/file1StructCInstance/nestedStructInstance/nestedStructMemberInt',
                        EmbeddedDataType.sint32, addr=v.get_address() + 4, value_at_loc=2298744)
        self.assert_var('/global/file1StructCInstance/nestedStructInstance/nestedStructMemberFloat',
                        EmbeddedDataType.float32, addr=v.get_address() + 8, value_at_loc=-147.55)
        self.assert_var('/global/file1StructCInstance/nestedStructInstance/nestedStructInstance2/nestedStructInstance2MemberDouble',
                        EmbeddedDataType.float32, addr=v.get_address() + 12, value_at_loc=654.654)

    def test_structD(self):
        # We do not validate the bitoffset nor the address.
        # Tasking changes the type to take the smallest fit.
        self.assert_var('/global/file1StructDInstance/bitfieldA', bitsize=4, value_at_loc=13)
        self.assert_var('/global/file1StructDInstance/bitfieldB', bitsize=13, value_at_loc=4100)
        self.assert_var('/global/file1StructDInstance/bitfieldC', bitsize=8, value_at_loc=222)
        self.assert_var('/global/file1StructDInstance/bitfieldD', value_at_loc=1234567)
        self.assert_var('/global/file1StructDInstance/bitfieldE', bitsize=10, value_at_loc=777)

    def test_array1(self):
        self.assert_var('/global/file2GlobalArray1Int5[0]', EmbeddedDataType.sint32, value_at_loc=1111)
        self.assert_var('/global/file2GlobalArray1Int5[1]', EmbeddedDataType.sint32, value_at_loc=2222)
        self.assert_var('/global/file2GlobalArray1Int5[2]', EmbeddedDataType.sint32, value_at_loc=3333)
        self.assert_var('/global/file2GlobalArray1Int5[3]', EmbeddedDataType.sint32, value_at_loc=4444)
        self.assert_var('/global/file2GlobalArray1Int5[4]', EmbeddedDataType.sint32, value_at_loc=5555)

    @unittest.skip("Tasking makes array of array. Not supported")
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

        # Cannot validate enum. Not even part of the dwarf symbols
        self.assert_var('/global/file3_test_class/m_file3testclass_inclassenum', EmbeddedDataType.uint32, value_at_loc=1)

        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field1', EmbeddedDataType.uint32, value_at_loc=0x11223344)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field2', EmbeddedDataType.uint32, value_at_loc=0x55667788)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_u8/p3', EmbeddedDataType.uint8, value_at_loc=0xAA)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_u16/p0', EmbeddedDataType.uint16, value_at_loc=0xBCC2)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_u32', EmbeddedDataType.uint32, value_at_loc=0xAA34BCC2)

        # We do not validate bitoffset nor the type. Tasking plays on those 2. Multiple valid combination
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_enum_bitfields/p0', value_at_loc=2, bitsize=5)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_enum_bitfields/p1', value_at_loc=0x66, bitsize=7)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_enum_bitfields/p2', value_at_loc=0x34B, bitsize=10)
        self.assert_var('/global/file3_test_class/m_file3_complex_struct/field3/field3_enum_bitfields/p3', value_at_loc=0x2A8, bitsize=10)


if __name__ == '__main__':
    import unittest
    unittest.main()
