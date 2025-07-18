
import elftools.elf
import elftools.elf.elffile
from scrutiny.core.varmap import VarMap
from scrutiny.exceptions import EnvionmentNotSetUpException
from test import SkipOnException
from scrutiny.core.bintools.elf_dwarf_var_extractor import ElfDwarfVarExtractor
from scrutiny.core.memory_content import MemoryContent


from scrutiny.core.basic_types import *
from scrutiny.core.variable import *
from scrutiny.tools.typing import *

class BaseVarmapTest:
    varmap:VarMap
    bin_filename:str
    memdump_filename:Optional[str]
    memdump:Optional[MemoryContent]

    _CPP_FILT = 'c++filt'   # Can be overriden

    @classmethod
    def setUpClass(cls):
        cls.init_exception = None
        try:
            extractor = ElfDwarfVarExtractor(cls.bin_filename, cppfilt=cls._CPP_FILT)
            varmap = extractor.get_varmap()
            cls.varmap = VarMap(varmap.get_json())
            cls.memdump = None
            if cls.memdump_filename is not None:
                cls.memdump = MemoryContent(cls.memdump_filename)
        except Exception as e:
            cls.init_exception = e  # Let's remember the exception and throw it for each test for good logging.

    @SkipOnException(EnvionmentNotSetUpException)
    def setUp(self) -> None:
        if self.init_exception is not None:
            raise self.init_exception
        
    def load_var(self, fullname:str):
        return self.varmap.get_var(fullname)

    def assert_var(self, fullname, thetype, addr=None, bitsize=None, bitoffset=None, value_at_loc=None, float_tol=0.00001):
        v = self.load_var(fullname)
        self.assertEqual(thetype, v.get_type())

        if bitsize is not None:
            self.assertEqual(v.bitsize, bitsize)

        if bitoffset is not None:
            self.assertEqual(v.bitoffset, bitoffset)

        if addr is not None:
            self.assertEqual(addr, v.get_address())

        if value_at_loc is not None:
            if self.memdump is None:
                raise ValueError("No memdump available")
            data = self.memdump.read(v.get_address(), v.get_size())
            val = v.decode(data)
            if thetype in [EmbeddedDataType.float32, EmbeddedDataType.float64]:
                self.assertAlmostEqual(val, value_at_loc, delta=float_tol)
            else:
                self.assertEqual(val, value_at_loc)
        return v

    def assert_dwarf_version(self, binname: str, version: int):
        with open(binname, 'rb') as f:
            elffile = elftools.elf.elffile.ELFFile(f)

            self.assertTrue(elffile.has_dwarf_info())

            dwarfinfo = elffile.get_dwarf_info()
            for cu in dwarfinfo.iter_CUs():
                self.assertEqual(cu.header['version'], version)

    def assert_is_enum(self, v):
        self.assertIsNotNone(v.enum)

    def assert_has_enum(self, v, name: str, value: int):
        self.assert_is_enum(v)
        value2 = v.enum.get_value(name)
        self.assertIsNotNone(value2)
        self.assertEqual(value2, value)
