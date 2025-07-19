import unittest

from scrutiny.core.basic_types import *
from scrutiny.core.variable import *
from test.artifacts import get_artifact
from test import ScrutinyUnitTest
from test.cli.base_varmap_test import BaseVarmapTest, KnownEnumTypedDict

from scrutiny.tools.typing import *


KNOWN_ENUMS:KnownEnumTypedDict = {
    "IfxPort_OutputIdx" : {
        "name" : "IfxPort_OutputIdx",
        "values" : {
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
    "Ifx_RxSel" : {
        "name" : "Ifx_RxSel",
        "values" : {
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
   # "_ZN16NamespaceInFile25EnumAE" : {
#
   # },
    "IfxScuCcu_PllInputClockSelection" : {
        "name" : "IfxScuCcu_PllInputClockSelection",
        "values" : {
            "IfxScuCcu_PllInputClockSelection_fOsc1": 0,
            "IfxScuCcu_PllInputClockSelection_fOsc0": 1,
            "IfxScuCcu_PllInputClockSelection_fSysclk": 2
        }
    },
    "IfxScuCcu_ModEn" : {
        "name" : "IfxScuCcu_ModEn",
        "values" : {
            "IfxScuCcu_ModEn_disabled": 0,
            "IfxScuCcu_ModEn_enabled": 1
        }
    },
    "IfxScuCcu_ModulationAmplitude" : {
        "name" : "IfxScuCcu_ModulationAmplitude",
        "values" : {
            "IfxScuCcu_ModulationAmplitude_0p5": 0,
            "IfxScuCcu_ModulationAmplitude_1p0": 1,
            "IfxScuCcu_ModulationAmplitude_1p25": 2,
            "IfxScuCcu_ModulationAmplitude_1p5": 3,
            "IfxScuCcu_ModulationAmplitude_2p0": 4,
            "IfxScuCcu_ModulationAmplitude_2p5": 5,
            "IfxScuCcu_ModulationAmplitude_count": 6
        }
    },
    "IfxAsclin_DataBufferMode" : {
        "name" : "IfxAsclin_DataBufferMode",
        "values" : {
            "IfxAsclin_DataBufferMode_normal": 0,
            "IfxAsclin_DataBufferMode_timeStampSingle": 1
        }
    },
    "_dbg_nr_t" : {
        "name" : "_dbg_nr_t",
        "values" : {
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

    _CPP_FILT = 'c++filt'
    #_CPP_FILT = 'c++filt'
   
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
        

if __name__ == '__main__':
    import unittest
    unittest.main()
