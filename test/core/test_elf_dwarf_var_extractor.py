#    test_elf_dwarf_var_extractor.py
#        Test the extraction of dwarf symbols from a .elf file
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

import re
import unittest
import subprocess
import tempfile
import os
import sys

from test import logger
from test import ScrutinyUnitTest
from scrutiny.core.bintools.elf_dwarf_var_extractor import ElfDwarfVarExtractor
from scrutiny.core.basic_types import *

from scrutiny.tools.typing import *


class TestElf2VarMapBasics(ScrutinyUnitTest):

    def test_unique_cu_name(self):
        unique_name_regex = re.compile(r'cu(\d+)_(.+)')
        path1 = '/aaa/bbb/ccc'
        path2 = '/aaa/bbb/ddd'
        path3 = '/aaa/xxx/ccc'
        path4 = '/aaa/bbb/ccc/ddd/x'
        path5 = '/aaa/bbb/ccc/ddd/x'
        path6 = '/ccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc/ddd/x'

        fullpath_list = [
            path1,
            path2,
            path3,
            path4,
            path5,
            path6,
        ]

        fullpath_2_displaypath_map = ElfDwarfVarExtractor.make_unique_display_name(fullpath_list)

        self.assertEqual(len(fullpath_2_displaypath_map), 5)

        self.assertEqual(fullpath_2_displaypath_map[path1], 'bbb_ccc')
        self.assertEqual(fullpath_2_displaypath_map[path2], 'ddd')
        self.assertEqual(fullpath_2_displaypath_map[path3], 'xxx_ccc')
        self.assertIsNotNone(fullpath_2_displaypath_map[path4], 'ccc_ddd_x')
        self.assertIsNotNone(unique_name_regex.match(fullpath_2_displaypath_map[path6]))

    def test_split_demangled_name(self):
        cases: List[Tuple[str, List[str]]] = [
            ("aaa::bbb::ccc", ['aaa', 'bbb', 'ccc']),
            ("aaa::bbb(qqq::www, yyy::zzz::kkk)::ccc", ['aaa', 'bbb(qqq::www, yyy::zzz::kkk)', 'ccc']),
            ("aaa::bbb<AAA::BBB<CCC::DDD>>(qqq::www<EEE::FFF>, yyy::zzz::kkk)::ccc", [
             'aaa', 'bbb<AAA::BBB<CCC::DDD>>(qqq::www<EEE::FFF>, yyy::zzz::kkk)', 'ccc'])
        ]
        for case in cases:
            strin, expected = case[0], case[1]
            segments = ElfDwarfVarExtractor.split_demangled_name(strin)
            self.assertEqual(segments, expected)


def has_elf_toolchain(compiler, cppfilt) -> bool:
    if sys.platform == 'win32':
        return False

    compiler_check_p = subprocess.Popen(["which", compiler], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    cppfilt_check_p = subprocess.Popen(["which", cppfilt], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    compiler_check_p.communicate()
    cppfilt_check_p.communicate()

    if compiler_check_p.returncode != 0:
        return False

    if cppfilt_check_p.returncode != 0:
        return False

    return True


class TestElf2VarMapFromBuilds(ScrutinyUnitTest):

    def _make_varmap(self, code: str, dwarf_version=4, compiler="g++", cppfilt='c++filt'):
        with tempfile.TemporaryDirectory() as d:
            main_cpp = os.path.join(d, 'main.cpp')
            outbin = os.path.join(d, 'out.bin')
            with open(main_cpp, 'wb') as f:
                f.write(code.encode('utf8'))

            p = subprocess.Popen([compiler, '-no-pie', f'-gdwarf-{dwarf_version}', main_cpp,
                                 '-o', outbin], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()

            logger.debug(stdout.decode('utf8'))
            logger.debug(stderr.decode('utf8'))

            if p.returncode != 0:
                raise RuntimeError("Failed to compile code")

            with open(outbin, 'rb') as f:
                if f.read(4) != b'\x7fELF':
                    raise unittest.SkipTest("Toolchain does not produce an elf.")

            # p = subprocess.Popen(['objdump', '-g', '--dwarf=info', outbin], stdout=subprocess.PIPE)
            # stdout, stderr = p.communicate()
            # print(stdout.decode('utf8'))
            extractor = ElfDwarfVarExtractor(outbin, cppfilt=cppfilt)
            return extractor.get_varmap()

    @unittest.skipIf(
        not has_elf_toolchain(compiler='g++', cppfilt='c++filt')
        or not has_elf_toolchain(compiler='clang++', cppfilt='c++filt'),
        "No toolchain available")
    def test_extract_arrays(self):
        code = """
#include <cstdint>
#pragma pack(push, 1)
enum class EnumA : int32_t
{
    AAA,BBB,CCC
};
struct A
{
    EnumA x;
    int16_t y[2][3];
};

struct B
{
    int32_t x2;
    A y2[4][5];
};

struct C {
    uint32_t a;
    EnumA b;
};

typedef int32_t arr1[5];
typedef arr1 arr2[4];

#pragma pack(pop)

A my_global_A;
B my_global_B;
C my_global_C;
A my_global_array_of_A[3];
B my_global_array_of_B[4];
C my_global_array_of_C[5];
int32_t my_global_int32_array[10][20];
EnumA my_global_enum_array[11][12];
arr2 my_global_array_of_array345[3];

int main(int argc, char* argv[])
{
    static volatile A my_static_A;
    static volatile B my_static_B;
    static volatile C my_static_C;
    static volatile A my_static_array_of_A[5];
    static volatile B my_static_array_of_B[6];
    static volatile C my_static_array_of_C[7];
    static volatile int32_t my_static_int32_array[15][10];
    return 0;
}
"""

        for compiler in ['g++', 'clang++']:
            for dwarf_version in [2, 3, 4]:
                with self.subTest(f"{compiler}-dwarf{dwarf_version}"):
                    varmap = self._make_varmap(code, dwarf_version=dwarf_version, compiler=compiler, cppfilt='c++filt')

                    enum_list = varmap.get_enum_by_name('EnumA')
                    self.assertEqual(len(enum_list), 1)
                    enumA = enum_list[0]
                    self.assertEqual(enumA.get_value('AAA'), 0)
                    self.assertEqual(enumA.get_value('BBB'), 1)
                    self.assertEqual(enumA.get_value('CCC'), 2)

                    # === my_global_int32_array ===
                    v = '/global/my_global_int32_array/my_global_int32_array'
                    self.assertTrue(varmap.has_var(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 1)
                    self.assertIn(v, array_segments)
                    self.assertEqual(array_segments[v].dims, (10, 20))
                    self.assertEqual(array_segments[v].element_byte_size, 4)

                    # === my_static_int32_array ===
                    v = '/static/main.cpp/main/my_static_int32_array/my_static_int32_array'
                    self.assertTrue(varmap.has_var(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 1)
                    self.assertIn(v, array_segments)
                    self.assertEqual(array_segments[v].dims, (15, 10))
                    self.assertEqual(array_segments[v].element_byte_size, 4)

                    # === my_global_enum_array ===
                    v = '/global/my_global_enum_array/my_global_enum_array'
                    self.assertTrue(varmap.has_var(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    enum = varmap.get_enum(v)
                    self.assertEqual(enum, enumA)
                    self.assertEqual(len(array_segments), 1)
                    self.assertIn(v, array_segments)
                    self.assertEqual(array_segments[v].dims, (11, 12))
                    self.assertEqual(array_segments[v].element_byte_size, 4)

    # region struct A
                    # == my_global_A ===
                    v = '/global/my_global_A/x'
                    self.assertTrue(varmap.has_var(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assertFalse(varmap.has_array_segments(v))

                    v = '/global/my_global_A/y/y'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertIn(v, array_segments)
                    self.assertEqual(array_segments[v].dims, (2, 3))
                    self.assertEqual(array_segments[v].element_byte_size, 2)

                    # === my_static_A ===
                    v = '/static/main.cpp/main/my_static_A/x'
                    self.assertTrue(varmap.has_var(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assertFalse(varmap.has_array_segments(v))

                    v = '/static/main.cpp/main/my_static_A/y/y'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertIn(v, array_segments)
                    self.assertEqual(array_segments[v].dims, (2, 3))
                    self.assertEqual(array_segments[v].element_byte_size, 2)

                    # ===   my_global_array_of_A ====
                    v = '/global/my_global_array_of_A/my_global_array_of_A/x'
                    self.assertTrue(varmap.has_var(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    p1 = '/global/my_global_array_of_A/my_global_array_of_A'
                    self.assertEqual(len(array_segments), 1)
                    self.assertEqual(array_segments[p1].dims, (3,))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 2 * 3 * 2)

                    v = '/global/my_global_array_of_A/my_global_array_of_A/y/y'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 2)
                    p1 = '/global/my_global_array_of_A/my_global_array_of_A'
                    self.assertEqual(array_segments[p1].dims, (3,))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 2 * 3 * 2)
                    p2 = '/global/my_global_array_of_A/my_global_array_of_A/y/y'
                    self.assertEqual(array_segments[p2].dims, (2, 3))
                    self.assertEqual(array_segments[p2].element_byte_size, 2)

                    # ===   my_static_array_of_A ====
                    v = '/static/main.cpp/main/my_static_array_of_A/my_static_array_of_A/x'
                    self.assertTrue(varmap.has_var(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    p1 = '/static/main.cpp/main/my_static_array_of_A/my_static_array_of_A'
                    self.assertEqual(len(array_segments), 1)
                    self.assertEqual(array_segments[p1].dims, (5,))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 2 * 3 * 2)

                    v = '/static/main.cpp/main/my_static_array_of_A/my_static_array_of_A/y/y'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 2)
                    p1 = '/static/main.cpp/main/my_static_array_of_A/my_static_array_of_A'
                    self.assertEqual(array_segments[p1].dims, (5,))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 2 * 3 * 2)
                    p2 = '/static/main.cpp/main/my_static_array_of_A/my_static_array_of_A/y/y'
                    self.assertEqual(array_segments[p2].dims, (2, 3))
                    self.assertEqual(array_segments[p2].element_byte_size, 2)
    # endregion

    # region struct B
                    # === my_global_B ===
                    v = '/global/my_global_B/x2'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertFalse(varmap.has_array_segments(v))

                    v = '/global/my_global_B/y2/y2/x'
                    self.assertTrue(varmap.has_var(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/global/my_global_B/y2/y2"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (4, 5))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 2 * 3 * 2)

                    v = '/global/my_global_B/y2/y2/y/y'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 2)
                    p1 = "/global/my_global_B/y2/y2"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (4, 5))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 2 * 3 * 2)
                    p2 = "/global/my_global_B/y2/y2/y/y"
                    self.assertIn(p2, array_segments)
                    self.assertEqual(array_segments[p2].dims, (2, 3))
                    self.assertEqual(array_segments[p2].element_byte_size, 2)

                    # === my_static_B ===
                    v = '/static/main.cpp/main/my_static_B/x2'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertFalse(varmap.has_array_segments(v))

                    v = '/static/main.cpp/main/my_static_B/y2/y2/x'
                    self.assertTrue(varmap.has_var(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/static/main.cpp/main/my_static_B/y2/y2"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (4, 5))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 2 * 3 * 2)

                    v = '/static/main.cpp/main/my_static_B/y2/y2/y/y'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 2)
                    p1 = "/static/main.cpp/main/my_static_B/y2/y2"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (4, 5))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 2 * 3 * 2)
                    p2 = "/static/main.cpp/main/my_static_B/y2/y2/y/y"
                    self.assertIn(p2, array_segments)
                    self.assertEqual(array_segments[p2].dims, (2, 3))
                    self.assertEqual(array_segments[p2].element_byte_size, 2)

                    # === my_global_array_of_B ===
                    v = '/global/my_global_array_of_B/my_global_array_of_B/x2'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/global/my_global_array_of_B/my_global_array_of_B"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (4, ))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 4 * 5 * (4 + 2 * 3 * 2))

                    v = '/global/my_global_array_of_B/my_global_array_of_B/y2/y2/x'
                    self.assertTrue(varmap.has_var(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 2)
                    p1 = "/global/my_global_array_of_B/my_global_array_of_B"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (4, ))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 4 * 5 * (4 + 2 * 3 * 2))
                    p2 = "/global/my_global_array_of_B/my_global_array_of_B/y2/y2"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p2].dims, (4, 5))
                    self.assertEqual(array_segments[p2].element_byte_size, 4 + 2 * 3 * 2)

                    v = '/global/my_global_array_of_B/my_global_array_of_B/y2/y2/y/y'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 3)
                    p1 = "/global/my_global_array_of_B/my_global_array_of_B"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (4, ))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 4 * 5 * (4 + 2 * 3 * 2))
                    p2 = "/global/my_global_array_of_B/my_global_array_of_B/y2/y2"
                    self.assertIn(p2, array_segments)
                    self.assertEqual(array_segments[p2].dims, (4, 5))
                    self.assertEqual(array_segments[p2].element_byte_size, 4 + 2 * 3 * 2)
                    p3 = "/global/my_global_array_of_B/my_global_array_of_B/y2/y2/y/y"
                    self.assertIn(p3, array_segments)
                    self.assertEqual(array_segments[p3].dims, (2, 3))
                    self.assertEqual(array_segments[p3].element_byte_size, 2)

                    # === my_static_array_of_B ===
                    v = '/static/main.cpp/main/my_static_array_of_B/my_static_array_of_B/x2'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/static/main.cpp/main/my_static_array_of_B/my_static_array_of_B"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (6, ))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 4 * 5 * (4 + 2 * 3 * 2))

                    v = '/static/main.cpp/main/my_static_array_of_B/my_static_array_of_B/y2/y2/x'
                    self.assertTrue(varmap.has_var(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 2)
                    p1 = "/static/main.cpp/main/my_static_array_of_B/my_static_array_of_B"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (6, ))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 4 * 5 * (4 + 2 * 3 * 2))
                    p2 = "/static/main.cpp/main/my_static_array_of_B/my_static_array_of_B/y2/y2"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p2].dims, (4, 5))
                    self.assertEqual(array_segments[p2].element_byte_size, 4 + 2 * 3 * 2)

                    v = '/static/main.cpp/main/my_static_array_of_B/my_static_array_of_B/y2/y2/y/y'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 3)
                    p1 = "/static/main.cpp/main/my_static_array_of_B/my_static_array_of_B"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (6, ))
                    self.assertEqual(array_segments[p1].element_byte_size, 4 + 4 * 5 * (4 + 2 * 3 * 2))
                    p2 = "/static/main.cpp/main/my_static_array_of_B/my_static_array_of_B/y2/y2"
                    self.assertIn(p2, array_segments)
                    self.assertEqual(array_segments[p2].dims, (4, 5))
                    self.assertEqual(array_segments[p2].element_byte_size, 4 + 2 * 3 * 2)
                    p3 = "/static/main.cpp/main/my_static_array_of_B/my_static_array_of_B/y2/y2/y/y"
                    self.assertIn(p3, array_segments)
                    self.assertEqual(array_segments[p3].dims, (2, 3))
                    self.assertEqual(array_segments[p3].element_byte_size, 2)

    # endregion

    # region struct C

                    # === my_global_C ===
                    v = '/global/my_global_C/a'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_array_segments(v))
                    self.assertIsNone(varmap.get_enum(v))

                    v = '/global/my_global_C/b'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_array_segments(v))
                    self.assertEqual(varmap.get_enum(v), enumA)

                    # === my_global_array_of_C ===
                    v = '/global/my_global_array_of_C/my_global_array_of_C/a'
                    self.assertTrue(varmap.has_var(v))
                    self.assertIsNone(varmap.get_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/global/my_global_array_of_C/my_global_array_of_C"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (5, ))
                    self.assertEqual(array_segments[p1].element_byte_size, 8)

                    v = '/global/my_global_array_of_C/my_global_array_of_C/b'
                    self.assertTrue(varmap.has_var(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/global/my_global_array_of_C/my_global_array_of_C"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (5, ))
                    self.assertEqual(array_segments[p1].element_byte_size, 8)

                    # === my_static_C ===
                    v = '/static/main.cpp/main/my_static_C/a'
                    self.assertTrue(varmap.has_var(v))
                    self.assertIsNone(varmap.get_enum(v))
                    self.assertFalse(varmap.has_array_segments(v))

                    v = '/static/main.cpp/main/my_static_C/b'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_array_segments(v))
                    self.assertEqual(varmap.get_enum(v), enumA)

                    # === my_static_array_of_C ===
                    v = '/static/main.cpp/main/my_static_array_of_C/my_static_array_of_C/a'
                    self.assertTrue(varmap.has_var(v))
                    self.assertIsNone(varmap.get_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/static/main.cpp/main/my_static_array_of_C/my_static_array_of_C"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (7, ))
                    self.assertEqual(array_segments[p1].element_byte_size, 8)

                    v = '/static/main.cpp/main/my_static_array_of_C/my_static_array_of_C/b'
                    self.assertTrue(varmap.has_var(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/static/main.cpp/main/my_static_array_of_C/my_static_array_of_C"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (7, ))
                    self.assertEqual(array_segments[p1].element_byte_size, 8)
    # endregion

    # region my_global_array_of_array345
                    # Clang makes array of array in the dwarf structure instead of a single array with multiple subranges
                    v = '/global/my_global_array_of_array345/my_global_array_of_array345'
                    self.assertTrue(varmap.has_var(v))
                    self.assertIsNone(varmap.get_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 1)
                    self.assertEqual(array_segments[v].dims, (3, 4, 5))
                    self.assertEqual(array_segments[v].element_byte_size, 4)

    # endregion

    @unittest.skipIf(
        not has_elf_toolchain(compiler='g++', cppfilt='c++filt')
        or not has_elf_toolchain(compiler='clang++', cppfilt='c++filt'),
        "No toolchain available")
    def test_extract_pointers(self):
        code = """
#include <cstdint>

volatile uint32_t gu32;
volatile uint32_t *gu32_ptr = &gu32;
int main(int argc, char* argv[])
{
    return 0;
}
"""

        for compiler in ['g++', 'clang++']:
            for dwarf_version in [2, 3, 4]:
                with self.subTest(f"{compiler}-dwarf{dwarf_version}"):
                    varmap = self._make_varmap(code, dwarf_version=dwarf_version, compiler=compiler, cppfilt='c++filt')
                    vpath = '/global/gu32_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.pointer)
                    self.assertTrue(v.has_absolute_address())
                    self.assertFalse(v.has_pointed_address())

                    vpath = '/global/*gu32_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.uint32)
                    self.assertTrue(v.has_pointed_address())
                    self.assertFalse(v.has_absolute_address())


if __name__ == '__main__':
    import unittest
    unittest.main()
