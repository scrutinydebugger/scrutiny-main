
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

    def test_char16bits(self):
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
