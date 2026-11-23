#    base_makevarmap_rust_testapp.py
#        Base test for symbol extraction based on the Rust TestApp
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import elftools.elf.elffile

from scrutiny.core.basic_types import *
from scrutiny.core.variable import *
from scrutiny.tools.typing import *
from test.cli.base_varmap_test import BaseVarmapTest, KnownEnumTypedDict
from scrutiny.core.variable_location import ResolvedPathPointedLocation

KNOWN_ENUMS: KnownEnumTypedDict = {
    'EnumA': {
        'name': 'EnumA',
        'values': {
            "EVal1": 0,
            "EVal2": 1,
            "EVal3": 100,
            "EVal4": 101
        }
    },
    'File3EnumInClass': {
        "name": "File3EnumInClass",
        "values": {
            "Aaa": 0,
            "Bbb": 1,
            "Ccc": 2
        }
    },
    'File4EnumA': {
        "name": "File4EnumA",
        "values": {
            "Xxx": 123,
            "Yyy": 456
        }
    },
    'File6ReprU8Enum': {
        "name": "File6ReprU8Enum",
        "values": {
            "First": 1,
            "Second": 2,
            "Third": 200
        }
    }
}

# Compilation units of the precompiled Rust sysroot (std, core, alloc, ...) keep the DWARF version they were shipped with
PRECOMPILED_CU_PREFIXES = ['/rustc/', '/rust/deps/']


class BaseMakeVarmapRustTestApp(BaseVarmapTest):
    known_enums = KNOWN_ENUMS

    def assert_rust_dwarf_version(self, binname: str, version: int):
        with open(binname, 'rb') as f:
            elffile = elftools.elf.elffile.ELFFile(f)
            self.assertTrue(elffile.has_dwarf_info())

            dwarfinfo = elffile.get_dwarf_info()
            nb_cu_checked = 0
            for cu in dwarfinfo.iter_CUs():
                top_die = cu.get_top_DIE()
                cu_name = ''
                if 'DW_AT_name' in top_die.attributes:
                    cu_name = top_die.attributes['DW_AT_name'].value.decode('utf8')

                is_precompiled = False
                for prefix in PRECOMPILED_CU_PREFIXES:
                    if cu_name.startswith(prefix):
                        is_precompiled = True

                if is_precompiled:
                    continue

                self.assertEqual(cu.header['version'], version, f"CU {cu_name}")
                nb_cu_checked += 1

            self.assertGreater(nb_cu_checked, 0)

    def test_env(self):
        self.assertEqual(self.varmap.get_endianness(), Endianness.Little)

    def test_file1_globals_basic_types(self):
        self.assert_var('/static/rust_testapp/file1/FILE1_GLOBAL_CHAR', EmbeddedDataType.sint8, value_at_loc=-10)
        self.assert_var('/static/rust_testapp/file1/FILE1_GLOBAL_INT', EmbeddedDataType.sint32, value_at_loc=-1000)
        self.assert_var('/static/rust_testapp/file1/FILE1_GLOBAL_SHORT', EmbeddedDataType.sint16, value_at_loc=-999)
        self.assert_var('/static/rust_testapp/file1/FILE1_GLOBAL_LONG', EmbeddedDataType.sint64, value_at_loc=-100000)
        self.assert_var('/static/rust_testapp/file1/FILE1_GLOBAL_UNSIGNED_CHAR', EmbeddedDataType.uint8, value_at_loc=55)
        self.assert_var('/static/rust_testapp/file1/FILE1_GLOBAL_UNSIGNED_INT', EmbeddedDataType.uint32, value_at_loc=100001)
        self.assert_var('/static/rust_testapp/file1/FILE1_GLOBAL_UNSIGNED_SHORT', EmbeddedDataType.uint16, value_at_loc=50000)
        self.assert_var('/static/rust_testapp/file1/FILE1_GLOBAL_UNSIGNED_LONG', EmbeddedDataType.uint64, value_at_loc=100002)
        self.assert_var('/static/rust_testapp/file1/FILE1_GLOBAL_FLOAT', EmbeddedDataType.float32, value_at_loc=3.1415926)
        self.assert_var('/static/rust_testapp/file1/FILE1_GLOBAL_DOUBLE', EmbeddedDataType.float64, value_at_loc=1.71)
        self.assert_var('/static/rust_testapp/file1/FILE1_GLOBAL_BOOL', EmbeddedDataType.bool8, value_at_loc=True)

    def test_file2_globals_basic_types(self):
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_CHAR', EmbeddedDataType.sint8, value_at_loc=20)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_INT', EmbeddedDataType.sint32, value_at_loc=2000)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_SHORT', EmbeddedDataType.sint16, value_at_loc=998)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_LONG', EmbeddedDataType.sint64, value_at_loc=555555)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_UNSIGNED_CHAR', EmbeddedDataType.uint8, value_at_loc=254)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_UNSIGNED_INT', EmbeddedDataType.uint32, value_at_loc=123456)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_UNSIGNED_SHORT', EmbeddedDataType.uint16, value_at_loc=12345)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_UNSIGNED_LONG', EmbeddedDataType.uint64, value_at_loc=1234567)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_FLOAT', EmbeddedDataType.float32, value_at_loc=0.1)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_DOUBLE', EmbeddedDataType.float64, value_at_loc=0.11111111111111)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_BOOL', EmbeddedDataType.bool8, value_at_loc=False)

    def test_file1_static_basic_types(self):
        self.assert_var('/static/rust_testapp/file1/FILE1_STATIC_CHAR', EmbeddedDataType.sint8, value_at_loc=99)
        self.assert_var('/static/rust_testapp/file1/FILE1_STATIC_INT', EmbeddedDataType.sint32, value_at_loc=987654)
        self.assert_var('/static/rust_testapp/file1/FILE1_STATIC_SHORT', EmbeddedDataType.sint16, value_at_loc=-666)
        self.assert_var('/static/rust_testapp/file1/FILE1_STATIC_LONG', EmbeddedDataType.sint64, value_at_loc=-55555)
        self.assert_var('/static/rust_testapp/file1/FILE1_STATIC_UNSIGNED_CHAR', EmbeddedDataType.uint8, value_at_loc=44)
        self.assert_var('/static/rust_testapp/file1/FILE1_STATIC_UNSIGNED_INT', EmbeddedDataType.uint32, value_at_loc=3333)
        self.assert_var('/static/rust_testapp/file1/FILE1_STATIC_UNSIGNED_SHORT', EmbeddedDataType.uint16, value_at_loc=22222)
        self.assert_var('/static/rust_testapp/file1/FILE1_STATIC_UNSIGNED_LONG', EmbeddedDataType.uint64, value_at_loc=321321)
        self.assert_var('/static/rust_testapp/file1/FILE1_STATIC_FLOAT', EmbeddedDataType.float32, value_at_loc=1.23456789)
        self.assert_var('/static/rust_testapp/file1/FILE1_STATIC_DOUBLE', EmbeddedDataType.float64, value_at_loc=9.87654321)
        self.assert_var('/static/rust_testapp/file1/FILE1_STATIC_BOOL', EmbeddedDataType.bool8, value_at_loc=True)

    def test_file2_static_basic_types(self):
        self.assert_var('/static/rust_testapp/file2/FILE2_STATIC_CHAR', EmbeddedDataType.sint8, value_at_loc=-66)
        self.assert_var('/static/rust_testapp/file2/FILE2_STATIC_INT', EmbeddedDataType.sint32, value_at_loc=-8745)
        self.assert_var('/static/rust_testapp/file2/FILE2_STATIC_SHORT', EmbeddedDataType.sint16, value_at_loc=-9876)
        self.assert_var('/static/rust_testapp/file2/FILE2_STATIC_LONG', EmbeddedDataType.sint64, value_at_loc=-12345678)
        self.assert_var('/static/rust_testapp/file2/FILE2_STATIC_UNSIGNED_CHAR', EmbeddedDataType.uint8, value_at_loc=12)
        self.assert_var('/static/rust_testapp/file2/FILE2_STATIC_UNSIGNED_INT', EmbeddedDataType.uint32, value_at_loc=34)
        self.assert_var('/static/rust_testapp/file2/FILE2_STATIC_UNSIGNED_SHORT', EmbeddedDataType.uint16, value_at_loc=56)
        self.assert_var('/static/rust_testapp/file2/FILE2_STATIC_UNSIGNED_LONG', EmbeddedDataType.uint64, value_at_loc=78)
        self.assert_var('/static/rust_testapp/file2/FILE2_STATIC_FLOAT', EmbeddedDataType.float32, value_at_loc=2.22222)
        self.assert_var('/static/rust_testapp/file2/FILE2_STATIC_DOUBLE', EmbeddedDataType.float64, value_at_loc=3.3333)
        self.assert_var('/static/rust_testapp/file2/FILE2_STATIC_BOOL', EmbeddedDataType.bool8, value_at_loc=True)

    def test_func_static(self):
        self.assert_var('/static/rust_testapp/file2/file2func1/FILE2FUNC1_VAR', EmbeddedDataType.sint32, value_at_loc=-88778877)
        self.assert_var('/static/rust_testapp/file2/file2func1_with_arg/FILE2FUNC1_VAR', EmbeddedDataType.float64, value_at_loc=963258741.123)
        self.assert_var('/static/rust_testapp/main/STATIC_INT_IN_MAIN_FUNC', EmbeddedDataType.sint32, value_at_loc=22222)
        self.assert_var('/static/rust_testapp/mainfunc1/MAINFUNC1_VAR', EmbeddedDataType.sint32, value_at_loc=7777777)
        self.assert_var('/static/rust_testapp/mainfunc1_with_arg/MAINFUNC1_VAR', EmbeddedDataType.float64, value_at_loc=8888888.88)
        self.assert_var('/static/rust_testapp/file1/func_in_file1/STATIC_LONG_IN_FUNC_FILE1', EmbeddedDataType.sint64, value_at_loc=-0x123456789abcdef)

    def test_method_static(self):
        # Expected path is an assumption: impl block treated like a module level
        self.assert_var('/static/rust_testapp/file6/{impl#0}/method_with_static/STATIC_IN_METHOD', EmbeddedDataType.uint32, value_at_loc=0x600DF00D)

    def test_interactive_data(self):
        # Memdump is taken before the main loop runs. Initial values are expected
        self.assert_var('/static/rust_testapp/process_interactive_data/ENABLE', EmbeddedDataType.bool8, value_at_loc=False)
        self.assert_var('/static/rust_testapp/process_interactive_data/COUNTER', EmbeddedDataType.sint16, value_at_loc=0)
        self.assert_var('/static/rust_testapp/process_interactive_data/STEP', EmbeddedDataType.sint16, value_at_loc=1)

    def test_namespace(self):
        self.assert_var('/static/rust_testapp/file1/namespace_in_file1/namespace_in_file1_nested1/FILE1_GLOBAL_NESTED_VAR1',
                        EmbeddedDataType.uint64, value_at_loc=1111111111)
        self.assert_var('/static/rust_testapp/file1/namespace_in_file1/namespace_in_file1_nested1/FILE1_STATIC_NESTED_VAR1',
                        EmbeddedDataType.uint64, value_at_loc=945612345)
        self.assert_var('/static/rust_testapp/file6/file6_outer/file6_inner/FILE6_DEEP_VAR', EmbeddedDataType.uint16, value_at_loc=0xD00D)

    def assert_is_enumA(self, fullpath, value_at_loc=None):
        return self.assert_var(fullpath, EmbeddedDataType.uint32, value_at_loc=value_at_loc, enum='EnumA')

    def test_enum(self):
        self.assert_is_enumA('/static/rust_testapp/file2/namespace_in_file2/INSTANCE_ENUM_A', value_at_loc=1)
        self.assert_is_enumA('/static/rust_testapp/file2/INSTANCE2_ENUM_A', value_at_loc=101)
        self.assert_is_enumA('/static/rust_testapp/file2/STATIC_INSTANCE2_ENUM_A', value_at_loc=0)
        self.assert_is_enumA('/static/rust_testapp/file2/namespace_in_file2/STATIC_INSTANCE_ENUM_A', value_at_loc=100)

    def test_structA(self):
        # repr(C, packed)
        v = self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_A_INSTANCE/struct_a_member_int', EmbeddedDataType.sint32, value_at_loc=-654)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_A_INSTANCE/struct_a_member_uint',
                        EmbeddedDataType.uint32, addr=v.get_address() + 4, value_at_loc=258147)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_A_INSTANCE/struct_a_member_float',
                        EmbeddedDataType.float32, addr=v.get_address() + 8, value_at_loc=77.77)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_A_INSTANCE/struct_a_member_double',
                        EmbeddedDataType.float64, addr=v.get_address() + 12, value_at_loc=66.66)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_A_INSTANCE/struct_a_member_bool',
                        EmbeddedDataType.bool8, addr=v.get_address() + 20, value_at_loc=False)

        v = self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_A_STATIC_INSTANCE/struct_a_member_int', EmbeddedDataType.sint32, value_at_loc=-789)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_A_STATIC_INSTANCE/struct_a_member_uint',
                        EmbeddedDataType.uint32, addr=v.get_address() + 4, value_at_loc=147258)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_A_STATIC_INSTANCE/struct_a_member_float',
                        EmbeddedDataType.float32, addr=v.get_address() + 8, value_at_loc=88.88)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_A_STATIC_INSTANCE/struct_a_member_double',
                        EmbeddedDataType.float64, addr=v.get_address() + 12, value_at_loc=99.99)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_A_STATIC_INSTANCE/struct_a_member_bool',
                        EmbeddedDataType.bool8, addr=v.get_address() + 20, value_at_loc=True)

    def test_structB(self):
        v = self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_B_INSTANCE/struct_b_member_int', EmbeddedDataType.sint32, value_at_loc=55555)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_B_INSTANCE/struct_b_member_struct_a/struct_a_member_int',
                        EmbeddedDataType.sint32, addr=v.get_address() + 4, value_at_loc=-199999)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_B_INSTANCE/struct_b_member_struct_a/struct_a_member_uint',
                        EmbeddedDataType.uint32, addr=v.get_address() + 8, value_at_loc=33333)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_B_INSTANCE/struct_b_member_struct_a/struct_a_member_float',
                        EmbeddedDataType.float32, addr=v.get_address() + 12, value_at_loc=33.33)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_B_INSTANCE/struct_b_member_struct_a/struct_a_member_double',
                        EmbeddedDataType.float64, addr=v.get_address() + 16, value_at_loc=22.22)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_B_INSTANCE/struct_b_member_struct_a/struct_a_member_bool',
                        EmbeddedDataType.bool8, addr=v.get_address() + 24, value_at_loc=True)

    def test_structC(self):
        v = self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_C_INSTANCE/struct_c_member_int', EmbeddedDataType.sint32, value_at_loc=888874)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_C_INSTANCE/nested_struct_instance/nested_struct_member_int',
                        EmbeddedDataType.sint32, addr=v.get_address() + 4, value_at_loc=2298744)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_C_INSTANCE/nested_struct_instance/nested_struct_member_float',
                        EmbeddedDataType.float32, addr=v.get_address() + 8, value_at_loc=-147.55)
        self.assert_var('/static/rust_testapp/file1/FILE1_STRUCT_C_INSTANCE/nested_struct_instance/nested_struct_instance2/nested_struct_instance2_member_double',
                        EmbeddedDataType.float64, addr=v.get_address() + 12, value_at_loc=654.654)

    def test_array1(self):
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_ARRAY1_INT5/FILE2_GLOBAL_ARRAY1_INT5[0]', EmbeddedDataType.sint32, value_at_loc=1111)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_ARRAY1_INT5/FILE2_GLOBAL_ARRAY1_INT5[1]', EmbeddedDataType.sint32, value_at_loc=2222)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_ARRAY1_INT5/FILE2_GLOBAL_ARRAY1_INT5[2]', EmbeddedDataType.sint32, value_at_loc=3333)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_ARRAY1_INT5/FILE2_GLOBAL_ARRAY1_INT5[3]', EmbeddedDataType.sint32, value_at_loc=4444)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_ARRAY1_INT5/FILE2_GLOBAL_ARRAY1_INT5[4]', EmbeddedDataType.sint32, value_at_loc=5555)

    def test_array_2d(self):
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_ARRAY2X2_FLOAT/FILE2_GLOBAL_ARRAY2X2_FLOAT[0][0]', EmbeddedDataType.float32, value_at_loc=1.1)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_ARRAY2X2_FLOAT/FILE2_GLOBAL_ARRAY2X2_FLOAT[0][1]', EmbeddedDataType.float32, value_at_loc=2.2)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_ARRAY2X2_FLOAT/FILE2_GLOBAL_ARRAY2X2_FLOAT[1][0]', EmbeddedDataType.float32, value_at_loc=3.3)
        self.assert_var('/static/rust_testapp/file2/FILE2_GLOBAL_ARRAY2X2_FLOAT/FILE2_GLOBAL_ARRAY2X2_FLOAT[1][1]', EmbeddedDataType.float32, value_at_loc=4.4)

    def test_class_file2(self):
        self.assert_var('/static/rust_testapp/file2/FILE2_CLASS_B_INSTANCE/int_in_class_b', EmbeddedDataType.sint32, value_at_loc=-11111)
        self.assert_var('/static/rust_testapp/file2/FILE2_CLASS_B_INSTANCE/nested_class_instance/int_in_class_ba', EmbeddedDataType.sint32, value_at_loc=-22222)
        self.assert_var('/static/rust_testapp/file2/FILE2_CLASS_B_INSTANCE/nested_class_instance/class_a_instance/int_in_class_a',
                        EmbeddedDataType.sint32, value_at_loc=-33333)

        self.assert_var('/static/rust_testapp/file2/FILE2_CLASS_B_STATIC_INSTANCE/int_in_class_b', EmbeddedDataType.sint32, value_at_loc=-44444)
        self.assert_var('/static/rust_testapp/file2/FILE2_CLASS_B_STATIC_INSTANCE/nested_class_instance/int_in_class_ba',
                        EmbeddedDataType.sint32, value_at_loc=-55555)
        self.assert_var('/static/rust_testapp/file2/FILE2_CLASS_B_STATIC_INSTANCE/nested_class_instance/class_a_instance/int_in_class_a',
                        EmbeddedDataType.sint32, value_at_loc=-66666)

    def test_file3_union(self):
        vu8 = self.assert_var('/static/rust_testapp/file3/FILE3_UNION/u8_var', EmbeddedDataType.uint8, value_at_loc=0x99)
        vu16 = self.assert_var('/static/rust_testapp/file3/FILE3_UNION/u16_var', EmbeddedDataType.uint16, value_at_loc=0xAA99)
        vu32 = self.assert_var('/static/rust_testapp/file3/FILE3_UNION/u32_var', EmbeddedDataType.uint32, value_at_loc=0x1234AA99)
        self.assertEqual(vu8.get_address(), vu16.get_address())
        self.assertEqual(vu16.get_address(), vu32.get_address())

        self.assert_var('/static/rust_testapp/file3/FILE3_TEST_CLASS/m_file3testclass_inclassenum',
                        EmbeddedDataType.uint32, value_at_loc=1, enum='File3EnumInClass')

        v1 = self.assert_var('/static/rust_testapp/file3/FILE3_TEST_CLASS/m_file3_complex_struct/field1', EmbeddedDataType.uint32, value_at_loc=0x11223344)
        self.assert_var('/static/rust_testapp/file3/FILE3_TEST_CLASS/m_file3_complex_struct/field2',
                        EmbeddedDataType.uint32, addr=v1.get_address() + 4, value_at_loc=0x55667788)
        field3_addr = v1.get_address() + 8
        self.assert_var('/static/rust_testapp/file3/FILE3_TEST_CLASS/m_file3_complex_struct/field3/field3_u32',
                        EmbeddedDataType.uint32, addr=field3_addr, value_at_loc=0xAA34BCDE)
        self.assert_var('/static/rust_testapp/file3/FILE3_TEST_CLASS/m_file3_complex_struct/field3/field3_u16/p0',
                        EmbeddedDataType.uint16, addr=field3_addr, value_at_loc=0xBCDE)
        self.assert_var('/static/rust_testapp/file3/FILE3_TEST_CLASS/m_file3_complex_struct/field3/field3_u16/p1',
                        EmbeddedDataType.uint16, addr=field3_addr + 2, value_at_loc=0xAA34)
        self.assert_var('/static/rust_testapp/file3/FILE3_TEST_CLASS/m_file3_complex_struct/field3/field3_u8/p0',
                        EmbeddedDataType.uint8, addr=field3_addr, value_at_loc=0xDE)
        self.assert_var('/static/rust_testapp/file3/FILE3_TEST_CLASS/m_file3_complex_struct/field3/field3_u8/p1',
                        EmbeddedDataType.uint8, addr=field3_addr + 1, value_at_loc=0xBC)
        self.assert_var('/static/rust_testapp/file3/FILE3_TEST_CLASS/m_file3_complex_struct/field3/field3_u8/p2',
                        EmbeddedDataType.uint8, addr=field3_addr + 2, value_at_loc=0x34)
        self.assert_var('/static/rust_testapp/file3/FILE3_TEST_CLASS/m_file3_complex_struct/field3/field3_u8/p3',
                        EmbeddedDataType.uint8, addr=field3_addr + 3, value_at_loc=0xAA)

    def assert_file4_class_b(self, path: str, some_bool: bool, offset: int, a2enum: int):
        a2_path = f'{path}/array_of_a2/array_of_a2[2][0]'
        self.assert_var(f'{path}/some_bool', EmbeddedDataType.bool8, value_at_loc=some_bool)
        self.assert_var(f'{a2_path}/base/xxx', EmbeddedDataType.uint32, value_at_loc=0xdeadbeef + offset)
        self.assert_var(f'{a2_path}/base/yyy/yyy[0][0]', EmbeddedDataType.sint32, value_at_loc=0x10001111 + offset)
        self.assert_var(f'{a2_path}/base/yyy/yyy[0][1]', EmbeddedDataType.sint32, value_at_loc=0x20002222 + offset)
        self.assert_var(f'{a2_path}/base/yyy/yyy[0][2]', EmbeddedDataType.sint32, value_at_loc=0x30003333 + offset)
        self.assert_var(f'{a2_path}/base/yyy/yyy[1][2]', EmbeddedDataType.sint32, value_at_loc=0x40004444 + offset)
        self.assert_var(f'{a2_path}/zzz/zzz[0][0][0]', EmbeddedDataType.uint16, value_at_loc=0x5566 + offset)
        self.assert_var(f'{a2_path}/zzz/zzz[1][2][3]', EmbeddedDataType.uint16, value_at_loc=0x6789 + offset)
        self.assert_var(f'{a2_path}/a2enum', EmbeddedDataType.uint16, value_at_loc=a2enum, enum='File4EnumA')

    def test_file4(self):
        self.assert_file4_class_b('/static/rust_testapp/file4/FILE4_CLASS_B', some_bool=True, offset=0, a2enum=456)
        self.assert_file4_class_b('/static/rust_testapp/file4/FILE4_CLASS_B_ARRAY/FILE4_CLASS_B_ARRAY[0]', some_bool=True, offset=1, a2enum=123)
        self.assert_file4_class_b('/static/rust_testapp/file4/FILE4_CLASS_B_ARRAY/FILE4_CLASS_B_ARRAY[1]', some_bool=True, offset=2, a2enum=123)
        self.assert_file4_class_b('/static/rust_testapp/file4/FILE4_CLASS_B_ARRAY/FILE4_CLASS_B_ARRAY[2]', some_bool=False, offset=3, a2enum=456)

        a3_path = '/static/rust_testapp/file4/FILE4_CLASS_A3_ARRAY/FILE4_CLASS_A3_ARRAY'
        self.assert_var(f'{a3_path}[0][0]/the_union/u32', EmbeddedDataType.uint32, value_at_loc=0x12345678)
        self.assert_var(f'{a3_path}[0][0]/the_union/u8/u8[0]', EmbeddedDataType.uint8, value_at_loc=0x78)
        self.assert_var(f'{a3_path}[0][0]/the_union/u8/u8[1]', EmbeddedDataType.uint8, value_at_loc=0x56)
        self.assert_var(f'{a3_path}[0][0]/the_union/u8/u8[2]', EmbeddedDataType.uint8, value_at_loc=0x34)
        self.assert_var(f'{a3_path}[0][0]/the_union/u8/u8[3]', EmbeddedDataType.uint8, value_at_loc=0x12)

        self.assert_var(f'{a3_path}[0][1]/the_union/u32', EmbeddedDataType.uint32, value_at_loc=0xAABBCCDD)
        self.assert_var(f'{a3_path}[0][1]/the_union/u8/u8[0]', EmbeddedDataType.uint8, value_at_loc=0xDD)
        self.assert_var(f'{a3_path}[0][1]/the_union/u8/u8[1]', EmbeddedDataType.uint8, value_at_loc=0xCC)
        self.assert_var(f'{a3_path}[0][1]/the_union/u8/u8[2]', EmbeddedDataType.uint8, value_at_loc=0xBB)
        self.assert_var(f'{a3_path}[0][1]/the_union/u8/u8[3]', EmbeddedDataType.uint8, value_at_loc=0xAA)

        self.assert_var(f'{a3_path}[1][0]/the_union/u32', EmbeddedDataType.uint32, value_at_loc=0x11223344)
        self.assert_var(f'{a3_path}[1][0]/the_union/u8/u8[0]', EmbeddedDataType.uint8, value_at_loc=0x44)
        self.assert_var(f'{a3_path}[1][0]/the_union/u8/u8[1]', EmbeddedDataType.uint8, value_at_loc=0x33)
        self.assert_var(f'{a3_path}[1][0]/the_union/u8/u8[2]', EmbeddedDataType.uint8, value_at_loc=0x22)
        self.assert_var(f'{a3_path}[1][0]/the_union/u8/u8[3]', EmbeddedDataType.uint8, value_at_loc=0x11)

        self.assert_var(f'{a3_path}[1][1]/the_union/u32', EmbeddedDataType.uint32, value_at_loc=0x55667788)
        self.assert_var(f'{a3_path}[1][1]/the_union/u8/u8[0]', EmbeddedDataType.uint8, value_at_loc=0x88)
        self.assert_var(f'{a3_path}[1][1]/the_union/u8/u8[1]', EmbeddedDataType.uint8, value_at_loc=0x77)
        self.assert_var(f'{a3_path}[1][1]/the_union/u8/u8[2]', EmbeddedDataType.uint8, value_at_loc=0x66)
        self.assert_var(f'{a3_path}[1][1]/the_union/u8/u8[3]', EmbeddedDataType.uint8, value_at_loc=0x55)

    def test_file5(self):
        ns_a = '/static/rust_testapp/file5/file5_namespace_a'
        ns_b = '/static/rust_testapp/file5/file5_namespace_b'

        # Both structs are repr(C, packed)
        class StructAOffsets:
            i32 = 0
            i32_ptr = i32 + 4
            u16_array = i32_ptr + 8

        class StructBOffsets:
            u32 = 0
            struct_a_ptr = u32 + 4

        struct_a_base = self.varmap.get_var(f'{ns_a}/FILE5_STRUCT_A/i32').get_address()
        struct_b_base = self.varmap.get_var(f'{ns_a}/FILE5_STRUCT_B/u32').get_address()
        file5_i32_addr = self.varmap.get_var(f'{ns_a}/FILE5_I32').get_address()

        self.assert_var(f'{ns_a}/FILE5_I64', EmbeddedDataType.sint64, value_at_loc=-0x123456789abcdef)
        self.assert_var(f'{ns_a}/FILE5_I32', EmbeddedDataType.sint32, value_at_loc=-0x77553311)
        self.assert_var(f'{ns_a}/FILE5_I16', EmbeddedDataType.sint16, value_at_loc=-0x2A3C)
        self.assert_var(f'{ns_a}/FILE5_I8', EmbeddedDataType.sint8, value_at_loc=-0x35)

        self.assert_var(f'{ns_a}/FILE5_U64', EmbeddedDataType.uint64, value_at_loc=0x98765432123456)
        self.assert_var(f'{ns_a}/FILE5_U32', EmbeddedDataType.uint32, value_at_loc=0xaabbccdd)
        self.assert_var(f'{ns_a}/FILE5_U16', EmbeddedDataType.uint16, value_at_loc=0xFDCE)
        self.assert_var(f'{ns_a}/FILE5_U8', EmbeddedDataType.uint8, value_at_loc=0xBD)

        self.assert_var(f'{ns_a}/FILE5_STRUCT_A/i32', EmbeddedDataType.sint32, addr=struct_a_base + StructAOffsets.i32, value_at_loc=31415926)
        self.assert_var(f'{ns_a}/FILE5_STRUCT_A/i32_ptr', EmbeddedDataType.ptr64,
                        addr=struct_a_base + StructAOffsets.i32_ptr, value_at_loc=file5_i32_addr)
        self.assert_var(f'{ns_a}/FILE5_STRUCT_A/u16_array/u16_array[0]', EmbeddedDataType.uint16,
                        addr=struct_a_base + StructAOffsets.u16_array, value_at_loc=0x121)
        self.assert_var(f'{ns_a}/FILE5_STRUCT_A/u16_array/u16_array[1]', EmbeddedDataType.uint16, value_at_loc=0x122)
        self.assert_var(f'{ns_a}/FILE5_STRUCT_A/u16_array/u16_array[2]', EmbeddedDataType.uint16, value_at_loc=0x123)
        self.assert_var(f'{ns_a}/FILE5_STRUCT_A/u16_array/u16_array[3]', EmbeddedDataType.uint16, value_at_loc=0x124)
        self.assert_var(f'{ns_a}/FILE5_STRUCT_A/u16_array/u16_array[4]', EmbeddedDataType.uint16, value_at_loc=0x125)

        self.assert_var(f'{ns_a}/FILE5_STRUCT_B/u32', EmbeddedDataType.uint32, addr=struct_b_base + StructBOffsets.u32, value_at_loc=0x97461346)
        self.assert_var(f'{ns_a}/FILE5_STRUCT_B/struct_a_ptr', EmbeddedDataType.ptr64,
                        addr=struct_b_base + StructBOffsets.struct_a_ptr, value_at_loc=struct_a_base)

        self.assert_var(f'{ns_a}/FILE5_STRUCTB_ARRAY/FILE5_STRUCTB_ARRAY[0]/u32', EmbeddedDataType.uint32, value_at_loc=0x1195735)
        self.assert_var(f'{ns_a}/FILE5_STRUCTB_ARRAY/FILE5_STRUCTB_ARRAY[1]/u32', EmbeddedDataType.uint32, value_at_loc=0x1284629)
        self.assert_var(f'{ns_a}/FILE5_STRUCTB_ARRAY/FILE5_STRUCTB_ARRAY[0]/struct_a_ptr', EmbeddedDataType.ptr64, value_at_loc=struct_a_base)
        self.assert_var(f'{ns_a}/FILE5_STRUCTB_ARRAY/FILE5_STRUCTB_ARRAY[1]/struct_a_ptr', EmbeddedDataType.ptr64, value_at_loc=struct_a_base)

        # Test addresses
        self.assert_var(f'{ns_b}/FILE5_I64_PTR', EmbeddedDataType.ptr64, value_at_loc=self.varmap.get_var(f'{ns_a}/FILE5_I64').get_address())
        self.assert_var(f'{ns_b}/FILE5_I32_PTR', EmbeddedDataType.ptr64, value_at_loc=self.varmap.get_var(f'{ns_a}/FILE5_I32').get_address())
        self.assert_var(f'{ns_b}/FILE5_I16_PTR', EmbeddedDataType.ptr64, value_at_loc=self.varmap.get_var(f'{ns_a}/FILE5_I16').get_address())
        self.assert_var(f'{ns_b}/FILE5_I8_PTR', EmbeddedDataType.ptr64, value_at_loc=self.varmap.get_var(f'{ns_a}/FILE5_I8').get_address())

        self.assert_var(f'{ns_b}/FILE5_U64_PTR', EmbeddedDataType.ptr64, value_at_loc=self.varmap.get_var(f'{ns_a}/FILE5_U64').get_address())
        self.assert_var(f'{ns_b}/FILE5_U32_PTR', EmbeddedDataType.ptr64, value_at_loc=self.varmap.get_var(f'{ns_a}/FILE5_U32').get_address())
        self.assert_var(f'{ns_b}/FILE5_U16_PTR', EmbeddedDataType.ptr64, value_at_loc=self.varmap.get_var(f'{ns_a}/FILE5_U16').get_address())
        self.assert_var(f'{ns_b}/FILE5_U8_PTR', EmbeddedDataType.ptr64, value_at_loc=self.varmap.get_var(f'{ns_a}/FILE5_U8').get_address())

        self.assert_var(f'{ns_b}/FILE5_STRUCT_A_PTR', EmbeddedDataType.ptr64, value_at_loc=struct_a_base)
        self.assert_var(f'{ns_b}/FILE5_STRUCT_B_PTR', EmbeddedDataType.ptr64, value_at_loc=struct_b_base)

        # == Test dereferencing ==
        # base types
        self.assert_var(f'{ns_b}/*FILE5_I64_PTR', EmbeddedDataType.sint64,
                        addr=ResolvedPathPointedLocation(f'{ns_b}/FILE5_I64_PTR', 0), value_at_loc=-0x123456789abcdef)
        self.assert_var(f'{ns_b}/*FILE5_I32_PTR', EmbeddedDataType.sint32,
                        addr=ResolvedPathPointedLocation(f'{ns_b}/FILE5_I32_PTR', 0), value_at_loc=-0x77553311)
        self.assert_var(f'{ns_b}/*FILE5_I16_PTR', EmbeddedDataType.sint16,
                        addr=ResolvedPathPointedLocation(f'{ns_b}/FILE5_I16_PTR', 0), value_at_loc=-0x2A3C)
        self.assert_var(f'{ns_b}/*FILE5_I8_PTR', EmbeddedDataType.sint8,
                        addr=ResolvedPathPointedLocation(f'{ns_b}/FILE5_I8_PTR', 0), value_at_loc=-0x35)

        self.assert_var(f'{ns_b}/*FILE5_U64_PTR', EmbeddedDataType.uint64,
                        addr=ResolvedPathPointedLocation(f'{ns_b}/FILE5_U64_PTR', 0), value_at_loc=0x98765432123456)
        self.assert_var(f'{ns_b}/*FILE5_U32_PTR', EmbeddedDataType.uint32,
                        addr=ResolvedPathPointedLocation(f'{ns_b}/FILE5_U32_PTR', 0), value_at_loc=0xaabbccdd)
        self.assert_var(f'{ns_b}/*FILE5_U16_PTR', EmbeddedDataType.uint16,
                        addr=ResolvedPathPointedLocation(f'{ns_b}/FILE5_U16_PTR', 0), value_at_loc=0xFDCE)
        self.assert_var(f'{ns_b}/*FILE5_U8_PTR', EmbeddedDataType.uint8,
                        addr=ResolvedPathPointedLocation(f'{ns_b}/FILE5_U8_PTR', 0), value_at_loc=0xBD)

        # Struct A
        struct_a_ptr_path = f'{ns_b}/FILE5_STRUCT_A_PTR'
        self.assert_var(f'{ns_b}/*FILE5_STRUCT_A_PTR/i32', EmbeddedDataType.sint32,
                        addr=ResolvedPathPointedLocation(struct_a_ptr_path, StructAOffsets.i32), value_at_loc=31415926)
        self.assert_var(f'{ns_b}/*FILE5_STRUCT_A_PTR/i32_ptr', EmbeddedDataType.ptr64,
                        addr=ResolvedPathPointedLocation(struct_a_ptr_path, StructAOffsets.i32_ptr), value_at_loc=file5_i32_addr)
        self.assert_var(f'{ns_b}/*FILE5_STRUCT_A_PTR/u16_array/u16_array[0]', EmbeddedDataType.uint16,
                        addr=ResolvedPathPointedLocation(struct_a_ptr_path, StructAOffsets.u16_array), value_at_loc=0x121)
        self.assert_var(f'{ns_b}/*FILE5_STRUCT_A_PTR/u16_array/u16_array[1]', EmbeddedDataType.uint16,
                        addr=ResolvedPathPointedLocation(struct_a_ptr_path, StructAOffsets.u16_array + 2), value_at_loc=0x122)
        self.assert_var(f'{ns_b}/*FILE5_STRUCT_A_PTR/u16_array/u16_array[2]', EmbeddedDataType.uint16,
                        addr=ResolvedPathPointedLocation(struct_a_ptr_path, StructAOffsets.u16_array + 4), value_at_loc=0x123)
        self.assert_var(f'{ns_b}/*FILE5_STRUCT_A_PTR/u16_array/u16_array[3]', EmbeddedDataType.uint16,
                        addr=ResolvedPathPointedLocation(struct_a_ptr_path, StructAOffsets.u16_array + 6), value_at_loc=0x124)
        self.assert_var(f'{ns_b}/*FILE5_STRUCT_A_PTR/u16_array/u16_array[4]', EmbeddedDataType.uint16,
                        addr=ResolvedPathPointedLocation(struct_a_ptr_path, StructAOffsets.u16_array + 8), value_at_loc=0x125)

        # Struct A pointed by an array of struct B
        for i in range(2):
            struct_a_ptr_path = f'{ns_a}/FILE5_STRUCTB_ARRAY/FILE5_STRUCTB_ARRAY[{i}]/struct_a_ptr'
            pointed_path = f'{ns_a}/FILE5_STRUCTB_ARRAY/FILE5_STRUCTB_ARRAY[{i}]/*struct_a_ptr'
            self.assert_var(f'{pointed_path}/i32', EmbeddedDataType.sint32,
                            addr=ResolvedPathPointedLocation(struct_a_ptr_path, StructAOffsets.i32), value_at_loc=31415926)
            self.assert_var(f'{pointed_path}/i32_ptr', EmbeddedDataType.ptr64,
                            addr=ResolvedPathPointedLocation(struct_a_ptr_path, StructAOffsets.i32_ptr), value_at_loc=file5_i32_addr)
            self.assert_var(f'{pointed_path}/u16_array/u16_array[0]', EmbeddedDataType.uint16,
                            addr=ResolvedPathPointedLocation(struct_a_ptr_path, StructAOffsets.u16_array), value_at_loc=0x121)
            self.assert_var(f'{pointed_path}/u16_array/u16_array[4]', EmbeddedDataType.uint16,
                            addr=ResolvedPathPointedLocation(struct_a_ptr_path, StructAOffsets.u16_array + 8), value_at_loc=0x125)

        # Struct B
        struct_b_ptr_path = f'{ns_b}/FILE5_STRUCT_B_PTR'
        self.assert_var(f'{ns_b}/*FILE5_STRUCT_B_PTR/u32', EmbeddedDataType.uint32,
                        addr=ResolvedPathPointedLocation(struct_b_ptr_path, StructBOffsets.u32), value_at_loc=0x97461346)
        self.assert_var(f'{ns_b}/*FILE5_STRUCT_B_PTR/struct_a_ptr', EmbeddedDataType.ptr64,
                        addr=ResolvedPathPointedLocation(struct_b_ptr_path, StructBOffsets.struct_a_ptr), value_at_loc=struct_a_base)

        # Pointer to the first element of an array. Seen as a simple pointer
        self.assert_var(f'{ns_b}/*FILE5_STRUCT_B_ARRAY_PTR/u32', EmbeddedDataType.uint32, value_at_loc=0x1195735)
        self.assert_var(f'{ns_b}/*FILE5_STRUCT_B_ARRAY_PTR/struct_a_ptr', EmbeddedDataType.ptr64, value_at_loc=struct_a_base)

    def test_file6_primitives(self):
        # Rust char is a 32 bits unicode scalar value. 'é' = U+00E9
        self.assert_var('/static/rust_testapp/file6/FILE6_CHAR', EmbeddedDataType.uint32, value_at_loc=0xE9)
        self.assert_var('/static/rust_testapp/file6/FILE6_U128', EmbeddedDataType.uint128, value_at_loc=0x0123456789ABCDEF_FEDCBA9876543210)
        self.assert_var('/static/rust_testapp/file6/FILE6_I128', EmbeddedDataType.sint128, value_at_loc=-0x0123456789ABCDEF_0EDCBA9876543210)
        self.assert_var('/static/rust_testapp/file6/FILE6_USIZE', EmbeddedDataType.uint64, value_at_loc=0x1122334455667788)
        self.assert_var('/static/rust_testapp/file6/FILE6_ISIZE', EmbeddedDataType.sint64, value_at_loc=-0x1122334455667788)
        self.assert_var('/static/rust_testapp/file6/FILE6_CONST_U32', EmbeddedDataType.uint32, value_at_loc=0x13572468)

    def test_file6_bool_array(self):
        self.assert_var('/static/rust_testapp/file6/FILE6_BOOL_ARRAY/FILE6_BOOL_ARRAY[0]', EmbeddedDataType.bool8, value_at_loc=True)
        self.assert_var('/static/rust_testapp/file6/FILE6_BOOL_ARRAY/FILE6_BOOL_ARRAY[1]', EmbeddedDataType.bool8, value_at_loc=False)
        self.assert_var('/static/rust_testapp/file6/FILE6_BOOL_ARRAY/FILE6_BOOL_ARRAY[2]', EmbeddedDataType.bool8, value_at_loc=True)
        self.assert_var('/static/rust_testapp/file6/FILE6_BOOL_ARRAY/FILE6_BOOL_ARRAY[3]', EmbeddedDataType.bool8, value_at_loc=True)

    def test_file6_tuples(self):
        # Default repr: field order in memory is decided by the compiler. Only values are checked
        self.assert_var('/static/rust_testapp/file6/FILE6_TUPLE/__0', EmbeddedDataType.uint8, value_at_loc=0xAB)
        self.assert_var('/static/rust_testapp/file6/FILE6_TUPLE/__1', EmbeddedDataType.sint32, value_at_loc=-123456)
        self.assert_var('/static/rust_testapp/file6/FILE6_TUPLE/__2', EmbeddedDataType.float64, value_at_loc=2.5)

        self.assert_var('/static/rust_testapp/file6/FILE6_TUPLE_STRUCT/__0', EmbeddedDataType.uint16, value_at_loc=0xBEEF)
        self.assert_var('/static/rust_testapp/file6/FILE6_TUPLE_STRUCT/__1', EmbeddedDataType.sint16, value_at_loc=-1234)

    def test_file6_structs(self):
        # Default repr: field order in memory is decided by the compiler. Only values are checked
        self.assert_var('/static/rust_testapp/file6/FILE6_RUST_REPR_STRUCT/a_u8', EmbeddedDataType.uint8, value_at_loc=0x11)
        self.assert_var('/static/rust_testapp/file6/FILE6_RUST_REPR_STRUCT/b_u32', EmbeddedDataType.uint32, value_at_loc=0x22222222)
        self.assert_var('/static/rust_testapp/file6/FILE6_RUST_REPR_STRUCT/c_u16', EmbeddedDataType.uint16, value_at_loc=0x3333)
        self.assert_var('/static/rust_testapp/file6/FILE6_RUST_REPR_STRUCT/d_u64', EmbeddedDataType.uint64, value_at_loc=0x4444444444444444)

        v = self.assert_var('/static/rust_testapp/file6/FILE6_REPR_C_STRUCT/a_u8', EmbeddedDataType.uint8, value_at_loc=0x55)
        self.assert_var('/static/rust_testapp/file6/FILE6_REPR_C_STRUCT/b_u32', EmbeddedDataType.uint32, addr=v.get_address() + 4, value_at_loc=0x66666666)
        self.assert_var('/static/rust_testapp/file6/FILE6_REPR_C_STRUCT/c_u16', EmbeddedDataType.uint16, addr=v.get_address() + 8, value_at_loc=0x7777)
        self.assert_var('/static/rust_testapp/file6/FILE6_REPR_C_STRUCT/d_u64', EmbeddedDataType.uint64,
                        addr=v.get_address() + 16, value_at_loc=0x8888888888888888)

    def test_file6_generics(self):
        self.assert_var('/static/rust_testapp/file6/FILE6_GENERIC_U32/value', EmbeddedDataType.uint32, value_at_loc=0x12121212)
        self.assert_var('/static/rust_testapp/file6/FILE6_GENERIC_U32/count', EmbeddedDataType.uint8, value_at_loc=3)
        self.assert_var('/static/rust_testapp/file6/FILE6_GENERIC_F32/value', EmbeddedDataType.float32, value_at_loc=-1.5)
        self.assert_var('/static/rust_testapp/file6/FILE6_GENERIC_F32/count', EmbeddedDataType.uint8, value_at_loc=7)

    def test_file6_repr_u8_enum(self):
        self.assert_var('/static/rust_testapp/file6/FILE6_REPR_U8_ENUM', EmbeddedDataType.uint8, value_at_loc=200, enum='File6ReprU8Enum')

    def test_file6_str(self):
        # "Hello Scrutiny ✓" : 15 ASCII bytes + 3 bytes for the UTF-8 check mark
        self.assert_var('/static/rust_testapp/file6/FILE6_STR/length', EmbeddedDataType.uint64, value_at_loc=18)
        self.assert_var('/static/rust_testapp/file6/FILE6_STR/*data_ptr', EmbeddedDataType.uint8,
                        addr=ResolvedPathPointedLocation('/static/rust_testapp/file6/FILE6_STR/data_ptr', 0), value_at_loc=ord('H'))

    def test_file6_no_mangle(self):
        self.assert_var('/global/rust_testapp/file6/file6_no_mangle_u32', EmbeddedDataType.uint32, value_at_loc=0x5A5A5A5A)

    def test_rpv_storage(self):
        self.assert_var('/static/rust_testapp/rpv/RPV_STORAGE/rpv_id_1000', EmbeddedDataType.sint8, value_at_loc=-10)
        self.assert_var('/static/rust_testapp/rpv/RPV_STORAGE/rpv_id_1001', EmbeddedDataType.sint16, value_at_loc=-30000)
        self.assert_var('/static/rust_testapp/rpv/RPV_STORAGE/rpv_id_1002', EmbeddedDataType.sint32, value_at_loc=0xABCDEF)
        self.assert_var('/static/rust_testapp/rpv/RPV_STORAGE/rpv_id_1003', EmbeddedDataType.sint64, value_at_loc=0xAABBCCDDEEFF)
        self.assert_var('/static/rust_testapp/rpv/RPV_STORAGE/rpv_id_2000', EmbeddedDataType.uint8, value_at_loc=0xAB)
        self.assert_var('/static/rust_testapp/rpv/RPV_STORAGE/rpv_id_2001', EmbeddedDataType.uint16, value_at_loc=0x1234)
        self.assert_var('/static/rust_testapp/rpv/RPV_STORAGE/rpv_id_2002', EmbeddedDataType.uint32, value_at_loc=0x12345678)
        self.assert_var('/static/rust_testapp/rpv/RPV_STORAGE/rpv_id_2003', EmbeddedDataType.uint64, value_at_loc=0x111111111111)
        self.assert_var('/static/rust_testapp/rpv/RPV_STORAGE/rpv_id_3000', EmbeddedDataType.float32, value_at_loc=3.1415926)
        self.assert_var('/static/rust_testapp/rpv/RPV_STORAGE/rpv_id_3001', EmbeddedDataType.float64, value_at_loc=2.71828)
        self.assert_var('/static/rust_testapp/rpv/RPV_STORAGE/rpv_id_4000', EmbeddedDataType.bool8, value_at_loc=True)
        self.assert_var('/static/rust_testapp/rpv/RPV_STORAGE/rpv_id_5000', EmbeddedDataType.bool8, value_at_loc=False)
        self.assert_var('/static/rust_testapp/rpv/RPV_STORAGE/rpv_id_5001', EmbeddedDataType.uint16, value_at_loc=0)
