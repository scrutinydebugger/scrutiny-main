#    base_varmap_test.py
#        A base class shared amongst all test suites that test a varmap
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

import elftools.elf
import elftools.elf.elffile
from scrutiny.core.varmap import VarMap
from scrutiny.exceptions import EnvionmentNotSetUpException
from test import SkipOnException
from scrutiny.core.bintools.elf_dwarf_var_extractor import ElfDwarfVarExtractor
from scrutiny.core.memory_content import MemoryContent


from scrutiny.core.basic_types import *
from scrutiny.core.variable import *
from scrutiny.core.embedded_enum import *
from scrutiny.tools.typing import *


class KnownEnumTypedDictEntry(TypedDict):
    name: str
    values: Dict[str, int]


KnownEnumTypedDict: TypeAlias = Dict[str, KnownEnumTypedDictEntry]


class BaseVarmapTest:
    varmap: VarMap
    bin_filename: str
    memdump_filename: Optional[str]
    memdump: Optional[MemoryContent]
    known_enums: Optional[KnownEnumTypedDict]

    _CPP_FILT = 'c++filt'   # Can be overriden

    @classmethod
    def setUpClass(cls):
        cls.init_exception = None
        try:
            if not hasattr(cls, "known_enums"):
                cls.known_enums = None
            extractor = ElfDwarfVarExtractor(cls.bin_filename, cppfilt=cls._CPP_FILT)
            error_ignore = [NotImplementedError]
            first_error = extractor.get_errors().get_first_exc(error_ignore)
            if first_error is not None:
                raise RuntimeError("Parsing errors occured") from first_error
            varmap = extractor.get_varmap()
            cls.varmap = VarMap.from_file_content(varmap.get_json().encode('utf8'))
            cls.memdump = None
            if cls.memdump_filename is not None:
                cls.memdump = MemoryContent(cls.memdump_filename)
        except Exception as e:
            cls.init_exception = e  # Let's remember the exception and throw it for each test for good logging.

    @SkipOnException(EnvionmentNotSetUpException)
    def setUp(self) -> None:
        if self.init_exception is not None:
            raise self.init_exception

    def load_var(self, fullname: str):
        return self.varmap.get_var_from_complex_name(fullname)

    def assert_var(self,
                   fullname,
                   thetype: Optional[EmbeddedDataType] = None,
                   addr=None,
                   bitsize=None,
                   bitoffset=None,
                   value_at_loc=None,
                   float_tol: Optional[float] = None,
                   enum: Optional[str] = None):
        v = self.load_var(fullname)
        if thetype is not None:
            self.assertEqual(thetype, v.get_type())
            if thetype in [EmbeddedDataType.float32, EmbeddedDataType.float64] and float_tol is None:
                float_tol = 0.00001

        if bitsize is not None:
            self.assertEqual(v.bitsize, bitsize)

        if bitoffset is not None:
            self.assertEqual(v.bitoffset, bitoffset)

        if addr is not None:
            self.assertEqual(addr, v.get_address())

        if enum is not None:
            self.assertIn(enum, self.known_enums)
            self.assertIsNotNone(v.enum)
            self.assertEqual(self.known_enums[enum]['name'], v.enum.get_name())
            for key, value in self.known_enums[enum]['values'].items():
                value2 = v.enum.get_value(key)
                self.assertIsNotNone(value2)
                self.assertEqual(value2, value)
        else:
            self.assertIsNone(v.enum)

        if value_at_loc is not None:
            if self.memdump is None:
                raise ValueError("No memdump available")
            data = self.memdump.read(v.get_address(), v.get_size())
            val = v.decode(data)
            if float_tol is not None:
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

    def assert_is_enum(self, v: Variable):
        self.assertIsNotNone(v.enum)

    def assert_has_enum(self, v: Variable, name: str, value: int):
        self.assert_is_enum(v)
        venum = v.get_enum()
        self.assertIsNotNone(venum)
        value2 = venum.get_value(name)
        self.assertIsNotNone(value2)
        self.assertEqual(value2, value)

    def _compare_known_enum(self, known_enum: KnownEnumTypedDictEntry, embedded_enum: EmbeddedEnum) -> bool:
        if known_enum['name'] != embedded_enum.get_name():
            return False

        if sorted(list(known_enum['values'].keys())) != sorted(list(embedded_enum.vals.keys())):
            return False

        for name, val in known_enum['values'].items():
            if not embedded_enum.has_value(name):
                return False
            if embedded_enum.get_value(name) != val:
                return False

        return True

    def test_all_enums(self):
        if self.known_enums is None:
            return

        for unique_id, known_enum in self.known_enums.items():
            enum_found_and_ok = False
            enum_name = known_enum['name']
            for candidate in self.varmap.get_enum_by_name(enum_name):
                if self._compare_known_enum(known_enum, candidate):
                    enum_found_and_ok = True
                    break

            if not enum_found_and_ok:
                self.assertTrue(enum_found_and_ok, f"Enum {unique_id} (name={enum_name}) not found in varmap with the same definition")
