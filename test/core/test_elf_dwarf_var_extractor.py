#    test_elf_dwarf_var_extractor.py
#        Test the extraction of dwarf symbols from a .elf file
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

import re
import unittest
import subprocess
import tempfile
import os
import sys
from elftools.elf.elffile import ELFFile
from scrutiny.core.memory_content import MemoryContent
from scrutiny.core.varmap import VarMap
from scrutiny.core.codecs import Codecs
from scrutiny.core.embedded_enum import EmbeddedEnum
from scrutiny.core.variable_location import ResolvedPathPointedLocation

from test import logger
from test import ScrutinyUnitTest
from scrutiny.core.bintools.elf_dwarf_var_extractor import ElfDwarfVarExtractor
from scrutiny.core.bintools.elf_dwarf_var_extractor.helpers import make_unique_display_name
from scrutiny.core.bintools.demangled_name_parser import CppDemangledNameParser
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

        fullpath_2_displaypath_map = make_unique_display_name(fullpath_list)

        self.assertEqual(len(fullpath_2_displaypath_map), 5)

        self.assertEqual(fullpath_2_displaypath_map[path1], 'bbb_ccc')
        self.assertEqual(fullpath_2_displaypath_map[path2], 'ddd')
        self.assertEqual(fullpath_2_displaypath_map[path3], 'xxx_ccc')
        self.assertIsNotNone(fullpath_2_displaypath_map[path4], 'ccc_ddd_x')
        self.assertIsNotNone(unique_name_regex.match(fullpath_2_displaypath_map[path6]))

    def test_split_cpp_demangled_name(self):
        cases: List[Tuple[str, List[str]]] = [
            ("aaa::bbb::ccc", ['aaa', 'bbb', 'ccc']),
            ("aaa::bbb(qqq::www, yyy::zzz::kkk)::ccc", ['aaa', 'bbb(qqq::www, yyy::zzz::kkk)', 'ccc']),
            ("aaa::bbb<AAA::BBB<CCC::DDD>>(qqq::www<EEE::FFF>, yyy::zzz::kkk)::ccc", [
             'aaa', 'bbb<AAA::BBB<CCC::DDD>>(qqq::www<EEE::FFF>, yyy::zzz::kkk)', 'ccc'])
        ]
        for case in cases:
            strin, expected = case[0], case[1]
            segments = CppDemangledNameParser.parse_demangled_name(strin)
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


def has_rust_toolchain() -> bool:
    # The extractor needs c++filt even for Rust binaries
    return has_elf_toolchain(compiler='rustc', cppfilt='c++filt')


memdump_declare = """
#include <algorithm>
#include <cstdlib>
#include <string>
#include <iostream>
#include <iomanip>

void memdump(uintptr_t startAddr, uint32_t length)
{
    uintptr_t addr = startAddr;
    while (addr < startAddr + length)
    {
        uint8_t *ptr = reinterpret_cast<uint8_t *>(addr);
        std::cout << "0x" << std::hex << std::setw(16) << std::setfill('0') << addr << ":\t";
        uintptr_t nToPrint = startAddr + length - addr;
        if (nToPrint > 16)
        {
            nToPrint = 16;
        }
        for (unsigned int i = 0; i < nToPrint; i++)
        {
            std::cout << std::hex << std::setw(2) << std::setfill('0') << static_cast<uint32_t>(ptr[i]);
        }
        std::cout << std::endl;
        addr += nToPrint;
    }
}
"""

memdump_invocation = """
int region_index = 0;
for (int i=0; i<(argc-1)/2;i++)
{
    int base1 = 10;
    int base2 = 10;
    std::string start_address(argv[region_index + 1]);
    if (start_address.length() > 2 && start_address.find("0x") == 0)
    {
        start_address = start_address.substr(2);
        base1 = 16;
    }
    std::string length(argv[region_index + 1 + 1]);
    if (length.length() > 2 && length.find("0x") == 0)
    {
        length = length.substr(2);
        base2 = 16;
    }
    memdump(
        static_cast<uintptr_t>(strtoll(start_address.c_str(), NULL, base1)),
        static_cast<uint32_t>(strtol(length.c_str(), NULL, base2))
        );
    region_index+=2;
}

"""


class TestElf2VarMapFromBuilds(ScrutinyUnitTest):

    def _make_varmap_and_memdump(self, code: str, dwarf_version=4, compiler="g++", cppfilt='c++filt') -> Tuple[VarMap, MemoryContent]:
        with tempfile.TemporaryDirectory() as d:
            main_cpp = os.path.join(d, 'main.cpp')
            outbin = os.path.join(d, 'out.bin')
            with open(main_cpp, 'wb') as f:
                f.write(code.encode('utf8'))

            p = subprocess.Popen([compiler, '-no-pie', f'-gdwarf-{dwarf_version}', main_cpp,
                                 '-o', outbin], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()

            stdout_txt = stdout.decode('utf8')
            stderr_txt = stderr.decode('utf8')
            if stdout_txt:
                logger.debug(stdout_txt)
            if stderr_txt:
                logger.debug(stderr_txt)

            if p.returncode != 0:
                raise RuntimeError(f"Failed to compile code. \n {stderr_txt}")
            # Code is compiled. Make sure we produced an elf
            with open(outbin, 'rb') as f:
                if f.read(4) != b'\x7fELF':
                    raise unittest.SkipTest("Toolchain does not produce an elf.")

            # We ahve a valid elf that we should be able to run locally.
            # let's find the location of the interesting sections
            outbin_exec_args = []
            with open(outbin, 'rb') as f:
                ef = ELFFile(f)

                for section_name in ['.text', '.data', '.bss', '.rodata']:
                    section = ef.get_section_by_name(section_name)
                    if section is not None:
                        outbin_exec_args.append(str(section.header['sh_addr']))
                        outbin_exec_args.append(str(section.header['sh_size']))

            # Run the test binary and ask it to dump it's memory to stdout.
            with tempfile.TemporaryDirectory() as d:
                stdout_file = os.path.join(d, "stdout.txt")
                with open(stdout_file, 'wb') as stdout:
                    p = subprocess.Popen([outbin] + outbin_exec_args, stdout=stdout, stderr=subprocess.PIPE)
                    p.communicate()
                    if p.returncode != 0:
                        raise RuntimeError("Failed to run code.")
                # Load the memdump for value testing
                memdump = MemoryContent(stdout_file)

            if False:   # For debugging the test
                p = subprocess.Popen(['objdump', '-g', '--dwarf=info', outbin], stdout=subprocess.PIPE)
                stdout, stderr = p.communicate()
                print(stdout.decode('utf8'))
            extractor = ElfDwarfVarExtractor(outbin, cppfilt=cppfilt)
            return (extractor.get_varmap(), memdump)

    def _make_rust_varmap_and_memdump(self, code: str, crate_name: str, dwarf_version: int) -> Tuple[VarMap, MemoryContent]:
        with tempfile.TemporaryDirectory() as d:
            main_rs = os.path.join(d, 'main.rs')
            outbin = os.path.join(d, 'out.bin')
            with open(main_rs, 'wb') as f:
                f.write(code.encode('utf8'))

            p = subprocess.Popen(['rustc', '--edition', '2021', '--crate-name', crate_name, '-g', f'-Cdwarf-version={dwarf_version}',
                                  '-Crelocation-model=static', '-Copt-level=0', main_rs, '-o', outbin],
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr = p.communicate()

            stdout_txt = stdout.decode('utf8')
            stderr_txt = stderr.decode('utf8')
            if stdout_txt:
                logger.debug(stdout_txt)
            if stderr_txt:
                logger.debug(stderr_txt)

            if p.returncode != 0:
                raise RuntimeError(f"Failed to compile code. \n {stderr_txt}")
            with open(outbin, 'rb') as f:
                if f.read(4) != b'\x7fELF':
                    raise unittest.SkipTest("Toolchain does not produce an elf.")

            # Statics are const-initialized, so their values are read from the ELF instead of running the binary.
            # Running would require a memdump in main(), which pulls core generics first in the CU and makes the extractor skip it.
            memdump = MemoryContent()
            with open(outbin, 'rb') as f:
                ef = ELFFile(f)
                for section_name in ['.data', '.rodata', '.data.rel.ro']:
                    section = ef.get_section_by_name(section_name)
                    if section is not None and section.header['sh_size'] > 0:
                        memdump.write(section.header['sh_addr'], section.data())

            extractor = ElfDwarfVarExtractor(outbin, cppfilt='c++filt')
            return (extractor.get_varmap(), memdump)

    def get_value_at_path(self, path: str, varmap: VarMap, memdump: MemoryContent, allow_pointer: bool = True):
        var = varmap.get_var(path)
        if var.has_absolute_address():
            addr = var.get_address()
        elif var.has_pointed_address():
            if not allow_pointer:
                raise RuntimeError(f"Double dereferencing of {path}")
            ptr_val = cast(int, self.get_value_at_path(var.get_pointer().pointer_path, varmap, memdump, allow_pointer=False))
            ptr_val += var.get_pointer().pointer_offset
            addr = ptr_val
        else:
            raise NotImplementedError("Unsupported address type")
        return var.decode(memdump.read(addr, var.get_type().get_size_8bits()))

    def assert_value_at_path(self, path: str, varmap: VarMap, memdump: MemoryContent, value: Any, msg: Optional[str] = ""):
        self.assertEqual(self.get_value_at_path(path, varmap, memdump), value, msg)

    @unittest.skipIf(
        not has_elf_toolchain(compiler='g++', cppfilt='c++filt')
        or not has_elf_toolchain(compiler='clang++', cppfilt='c++filt'),
        "No toolchain available")
    def test_extract_arrays(self):
        code = """
#include <cstdint>
%s
#pragma pack(push, 1)
enum class EnumA : int32_t
{
    AAA = 10,
    BBB = 20,
    CCC = 30
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

    my_global_int32_array[2][3] = 0x12345678;
    my_static_int32_array[11][6] = 0x18293a4b;
    my_global_enum_array[7][6] = EnumA::BBB;

    my_global_A.x = EnumA::BBB;
    my_global_A.y[1][2] = -0x2233;

    my_static_A.x = EnumA::CCC;
    my_static_A.y[1][2] = -0x3456;

    my_global_B.x2 = 0x55443322;
    my_global_B.y2[3][2].x = EnumA::BBB;
    my_global_B.y2[3][2].y[1][2] = -0x2536;

    my_static_B.x2 = 0x44775588;
    my_static_B.y2[1][2].x = EnumA::CCC;
    my_static_B.y2[1][2].y[1][0] = 0x2143;

    my_global_C.a = 0xaabbccdd;
    my_global_C.b = EnumA::AAA;

    my_static_C.a = 0xa1b2c3d4;
    my_static_C.b = EnumA::BBB;

    my_global_array_of_A[2].x = EnumA::CCC;
    my_global_array_of_A[2].y[1][1] = 0x4567;

    my_static_array_of_A[1].x = EnumA::AAA;
    my_static_array_of_A[1].y[1][0] = 0x3322;

    my_global_array_of_B[3].x2 = 0x77123456;
    my_global_array_of_B[3].y2[2][2].x = EnumA::BBB;
    my_global_array_of_B[3].y2[2][2].y[0][1] = 0x2378;

    my_static_array_of_B[2].x2 = 0x6abcdef0;
    my_static_array_of_B[2].y2[1][2].x = EnumA::AAA;
    my_static_array_of_B[2].y2[1][2].y[0][2] = 0x1829;

    my_global_array_of_C[3].a = 0x99448855;
    my_global_array_of_C[3].b = EnumA::AAA;
    my_static_array_of_C[6].a = 0x66115522;
    my_static_array_of_C[6].b = EnumA::BBB;

    my_global_array_of_array345[1][2][3] = 31415926;


    %s

    return 0;
}
""" % (memdump_declare, memdump_invocation)

        for compiler in ['g++', 'clang++']:
            for dwarf_version in [2, 3, 4]:
                with self.subTest(f"{compiler}-dwarf{dwarf_version}"):
                    varmap, memdump = self._make_varmap_and_memdump(code, dwarf_version=dwarf_version, compiler=compiler, cppfilt='c++filt')

                    enum_list = varmap.get_enum_by_name('EnumA')
                    self.assertEqual(len(enum_list), 1)
                    enumA = enum_list[0]
                    self.assertEqual(enumA.get_value('AAA'), 10)
                    self.assertEqual(enumA.get_value('BBB'), 20)
                    self.assertEqual(enumA.get_value('CCC'), 30)

                    # === my_global_int32_array ===
                    v = '/global/my_global_int32_array/my_global_int32_array'
                    self.assertTrue(varmap.has_var(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 1)
                    self.assertIn(v, array_segments)
                    self.assertEqual(array_segments[v].dims, (10, 20))
                    self.assertEqual(array_segments[v].element_byte_size, 4)
                    self.assert_value_at_path('/global/my_global_int32_array/my_global_int32_array[2][3]', varmap, memdump, 0x12345678)

                    # === my_static_int32_array ===
                    v = '/static/main.cpp/main/my_static_int32_array/my_static_int32_array'
                    self.assertTrue(varmap.has_var(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertEqual(len(array_segments), 1)
                    self.assertIn(v, array_segments)
                    self.assertEqual(array_segments[v].dims, (15, 10))
                    self.assertEqual(array_segments[v].element_byte_size, 4)
                    self.assert_value_at_path(
                        '/static/main.cpp/main/my_static_int32_array/my_static_int32_array[11][6]',
                        varmap, memdump, 0x18293a4b)

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
                    self.assert_value_at_path(
                        '/global/my_global_enum_array/my_global_enum_array[7][6]',
                        varmap, memdump, enumA.get_value('BBB'))

    # region struct A
                    # == my_global_A ===
                    v = '/global/my_global_A/x'
                    self.assertTrue(varmap.has_var(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assertFalse(varmap.has_array_segments(v))
                    self.assert_value_at_path(v, varmap, memdump, enumA.get_value('BBB'))

                    v = '/global/my_global_A/y/y'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertIn(v, array_segments)
                    self.assertEqual(array_segments[v].dims, (2, 3))
                    self.assertEqual(array_segments[v].element_byte_size, 2)
                    self.assert_value_at_path('/global/my_global_A/y/y[1][2]', varmap, memdump, -0x2233)

                    # === my_static_A ===
                    v = '/static/main.cpp/main/my_static_A/x'
                    self.assertTrue(varmap.has_var(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assertFalse(varmap.has_array_segments(v))
                    self.assert_value_at_path(v, varmap, memdump, enumA.get_value('CCC'))

                    v = '/static/main.cpp/main/my_static_A/y/y'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertTrue(varmap.has_array_segments(v))
                    array_segments = varmap.get_array_segments(v)
                    self.assertIn(v, array_segments)
                    self.assertEqual(array_segments[v].dims, (2, 3))
                    self.assertEqual(array_segments[v].element_byte_size, 2)
                    self.assert_value_at_path('/static/main.cpp/main/my_static_A/y/y[1][2]', varmap, memdump, -0x3456)

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
                    self.assert_value_at_path('/global/my_global_array_of_A/my_global_array_of_A[2]/x', varmap, memdump, enumA.get_value('CCC'))

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
                    self.assert_value_at_path('/global/my_global_array_of_A/my_global_array_of_A[2]/y/y[1][1]', varmap, memdump, 0x4567)

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
                    self.assert_value_at_path(
                        '/static/main.cpp/main/my_static_array_of_A/my_static_array_of_A[1]/x',
                        varmap, memdump, enumA.get_value('AAA'))

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
                    self.assert_value_at_path(
                        '/static/main.cpp/main/my_static_array_of_A/my_static_array_of_A[1]/y/y[1][0]',
                        varmap, memdump, 0x3322)
    # endregion

    # region struct B
                    # === my_global_B ===
                    v = '/global/my_global_B/x2'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertFalse(varmap.has_array_segments(v))
                    self.assert_value_at_path('/global/my_global_B/x2', varmap, memdump, 0x55443322)

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
                    self.assert_value_at_path('/global/my_global_B/y2/y2[3][2]/x', varmap, memdump, enumA.get_value('BBB'))

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
                    self.assert_value_at_path('/global/my_global_B/y2/y2[3][2]/y/y[1][2]', varmap, memdump, -0x2536)

                    # === my_static_B ===
                    v = '/static/main.cpp/main/my_static_B/x2'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_enum(v))
                    self.assertFalse(varmap.has_array_segments(v))
                    self.assert_value_at_path(v, varmap, memdump, 0x44775588)

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
                    self.assert_value_at_path('/static/main.cpp/main/my_static_B/y2/y2[1][2]/x', varmap, memdump, enumA.get_value('CCC'))

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
                    self.assert_value_at_path('/static/main.cpp/main/my_static_B/y2/y2[1][2]/y/y[1][0]', varmap, memdump, 0x2143)

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
                    self.assert_value_at_path(
                        '/global/my_global_array_of_B/my_global_array_of_B[3]/x2',
                        varmap, memdump, 0x77123456)

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
                    self.assert_value_at_path(
                        '/global/my_global_array_of_B/my_global_array_of_B[3]/y2/y2[2][2]/x',
                        varmap, memdump, enumA.get_value('BBB'))

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
                    self.assert_value_at_path(
                        '/global/my_global_array_of_B/my_global_array_of_B[3]/y2/y2[2][2]/y/y[0][1]',
                        varmap, memdump, 0x2378)

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
                    self.assert_value_at_path(
                        '/static/main.cpp/main/my_static_array_of_B/my_static_array_of_B[2]/x2',
                        varmap, memdump, 0x6abcdef0)

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
                    self.assert_value_at_path(
                        '/static/main.cpp/main/my_static_array_of_B/my_static_array_of_B[2]/y2/y2[1][2]/x',
                        varmap, memdump, enumA.get_value('AAA'))

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
                    self.assert_value_at_path(
                        '/static/main.cpp/main/my_static_array_of_B/my_static_array_of_B[2]/y2/y2[1][2]/y/y[0][2]',
                        varmap, memdump, 0x1829)

    # endregion

    # region struct C

                    # === my_global_C ===
                    v = '/global/my_global_C/a'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_array_segments(v))
                    self.assertIsNone(varmap.get_enum(v))
                    self.assert_value_at_path('/global/my_global_C/a', varmap, memdump, 0xaabbccdd)

                    v = '/global/my_global_C/b'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_array_segments(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assert_value_at_path('/global/my_global_C/b', varmap, memdump, enumA.get_value('AAA'))

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
                    self.assert_value_at_path(
                        '/global/my_global_array_of_C/my_global_array_of_C[3]/a',
                        varmap, memdump, 0x99448855
                    )

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
                    self.assert_value_at_path(
                        '/global/my_global_array_of_C/my_global_array_of_C[3]/b',
                        varmap, memdump, enumA.get_value('AAA')
                    )

                    # === my_static_C ===
                    v = '/static/main.cpp/main/my_static_C/a'
                    self.assertTrue(varmap.has_var(v))
                    self.assertIsNone(varmap.get_enum(v))
                    self.assertFalse(varmap.has_array_segments(v))
                    self.assert_value_at_path('/static/main.cpp/main/my_static_C/a', varmap, memdump, 0xa1b2c3d4)

                    v = '/static/main.cpp/main/my_static_C/b'
                    self.assertTrue(varmap.has_var(v))
                    self.assertFalse(varmap.has_array_segments(v))
                    self.assertEqual(varmap.get_enum(v), enumA)
                    self.assert_value_at_path('/static/main.cpp/main/my_static_C/b', varmap, memdump, enumA.get_value('BBB'))

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
                    self.assert_value_at_path(
                        '/static/main.cpp/main/my_static_array_of_C/my_static_array_of_C[6]/a',
                        varmap, memdump, 0x66115522
                    )

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
                    self.assert_value_at_path(
                        '/static/main.cpp/main/my_static_array_of_C/my_static_array_of_C[6]/b',
                        varmap, memdump, enumA.get_value('BBB')
                    )
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
                    self.assert_value_at_path(
                        '/global/my_global_array_of_array345/my_global_array_of_array345[1][2][3]',
                        varmap, memdump, 31415926)

    # endregion

    @unittest.skipIf(
        not has_elf_toolchain(compiler='g++', cppfilt='c++filt')
        or not has_elf_toolchain(compiler='clang++', cppfilt='c++filt'),
        "No toolchain available")
    def test_extract_pointers(self):
        code = """
#include <cstdint>
%s
volatile uint32_t gu32;
volatile uint32_t *gu32_ptr = &gu32;

struct A
{
    volatile uint32_t* gu32_ptr;
    volatile int64_t i64;
};

struct B
{
    volatile A* gStructAPtr;
};

struct C
{
    volatile int32_t i32;
    volatile A a;
};

struct D
{
    int32_t i32;
    volatile D* d_ptr;
};

enum class EnumA
{
    AAA=100,
    BBB=200,
    CCC=300
};

struct E
{
    volatile EnumA enumA;
    volatile EnumA* enumA_ptr;
};

// Test circular pointer
struct G;
struct F
{
    int32_t i32;
    volatile struct G* g;
};
struct G
{
    uint32_t u32;
    volatile struct F* f;
};

volatile A gStructA;
volatile B gStructB;
volatile C gStructC;
volatile D gStructD1;
volatile D gStructD2;

volatile A* gStructAptr = &gStructA;
volatile C* gStructCptr = &gStructC;

volatile EnumA gEnumA;
volatile EnumA* gEnumA_ptr;

volatile E gStructE;
volatile E *gStructEptr;

volatile F gStructF;
volatile G gStructG;

int main(int argc, char* argv[])
{
    gu32 = 0xAABBCCDD;
    gStructA.gu32_ptr = &gu32;
    gStructA.i64 = 0x123456789abcdef;

    gStructB.gStructAPtr = &gStructA;

    gStructC.i32 = 0x1a2b3c4d;
    gStructC.a.gu32_ptr = &gu32;
    gStructC.a.i64 = 0x213243546576;

    gStructD1.i32 = 0x34651122;
    gStructD1.d_ptr = &gStructD2;
    gStructD2.i32 = 0x57954358;
    gStructD2.d_ptr = &gStructD1;

    gEnumA = EnumA::BBB;
    gEnumA_ptr = &gEnumA;

    gStructE.enumA = EnumA::CCC;
    gStructE.enumA_ptr = &gEnumA;
    gStructEptr = &gStructE;

    gStructF.i32 = 0x511425;
    gStructF.g = &gStructG;
    gStructG.u32 = 0xFA197345;
    gStructG.f = &gStructF;

%s
    return 0;
}
""" % (memdump_declare, memdump_invocation)

        for compiler in ['g++', 'clang++']:
            for dwarf_version in [2, 3, 4]:
                with self.subTest(f"{compiler}-dwarf{dwarf_version}"):
                    varmap, memdump = self._make_varmap_and_memdump(code, dwarf_version=dwarf_version, compiler=compiler, cppfilt='c++filt')

                    vpath = '/global/gu32'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.uint32)
                    self.assertFalse(v.has_pointed_address())
                    self.assertTrue(v.has_absolute_address())
                    self.assert_value_at_path(vpath, varmap, memdump, 0xAABBCCDD)

                    vpath = '/global/gu32_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())

                    self.assertTrue(v.has_absolute_address())
                    self.assertFalse(v.has_pointed_address())

                    vpath = '/global/*gu32_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.uint32)
                    self.assertTrue(v.has_pointed_address())
                    self.assertFalse(v.has_absolute_address())
                    self.assert_value_at_path(vpath, varmap, memdump, 0xAABBCCDD)

                    vpath = '/global/gStructA/gu32_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())

                    vpath = '/global/gStructA/*gu32_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.uint32)
                    self.assertTrue(v.has_pointed_address())
                    self.assertFalse(v.has_absolute_address())
                    self.assert_value_at_path(vpath, varmap, memdump, 0xAABBCCDD)

                    # Struct A
                    vpath = '/global/gStructAptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())

                    vpath = '/global/*gStructAptr/i64'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.sint64)
                    self.assertTrue(v.has_pointed_address())
                    self.assertFalse(v.has_absolute_address())
                    self.assert_value_at_path(vpath, varmap, memdump, 0x123456789abcdef)

                    # Struct B
                    vpath = '/global/gStructB/gStructAPtr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())

                    vpath = '/global/gStructB/*gStructAPtr/i64'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.sint64)
                    self.assertTrue(v.has_pointed_address())
                    self.assertFalse(v.has_absolute_address())
                    self.assert_value_at_path(vpath, varmap, memdump, 0x123456789abcdef)

                    # Struct C
                    vpath = '/global/gStructCptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())

                    vpath = '/global/*gStructCptr/i32'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.sint32)
                    self.assertTrue(v.has_pointed_address())
                    self.assertFalse(v.has_absolute_address())
                    self.assert_value_at_path(vpath, varmap, memdump, 0x1a2b3c4d)

                    vpath = '/global/*gStructCptr/a/i64'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.sint64)
                    self.assertTrue(v.has_pointed_address())
                    self.assertFalse(v.has_absolute_address())
                    self.assert_value_at_path(vpath, varmap, memdump, 0x213243546576)

                    vpath = '/global/*gStructCptr/a/gu32_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assertTrue(v.has_pointed_address())
                    self.assertFalse(v.has_absolute_address())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gu32').get_address())

                    # StructD
                    vpath = '/global/gStructD1/i32'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.sint32)
                    self.assert_value_at_path(vpath, varmap, memdump, 0x34651122)

                    vpath = '/global/gStructD1/d_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gStructD2/i32').get_address())

                    vpath = '/global/gStructD2/i32'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.sint32)
                    self.assert_value_at_path(vpath, varmap, memdump, 0x57954358)

                    vpath = '/global/gStructD2/d_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gStructD1/i32').get_address())

                    # Check for struct D dereferencing

                    vpath = '/global/gStructD1/*d_ptr/i32'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.sint32)
                    self.assert_value_at_path(vpath, varmap, memdump, 0x57954358)   # D2 value

                    vpath = '/global/gStructD1/*d_ptr/d_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gStructD1/i32').get_address())

                    vpath = '/global/gStructD2/*d_ptr/i32'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.sint32)
                    self.assert_value_at_path(vpath, varmap, memdump, 0x34651122)   # D1 value

                    vpath = '/global/gStructD2/*d_ptr/d_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gStructD2/i32').get_address())

                    # Check no nested dereferencing
                    self.assertFalse(varmap.has_var('/global/gStructD1/*d_ptr/*d_ptr/i32'))
                    self.assertFalse(varmap.has_var('/global/gStructD1/*d_ptr/*d_ptr/d_ptr'))
                    self.assertFalse(varmap.has_var('/global/gStructD2/*d_ptr/*d_ptr/i32'))
                    self.assertFalse(varmap.has_var('/global/gStructD2/*d_ptr/*d_ptr/d_ptr'))

                    # Enums
                    vpath = '/global/gEnumA'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.has_enum())
                    enumA = v.get_enum()
                    self.assertEqual(enumA.get_value('AAA'), 100)
                    self.assertEqual(enumA.get_value('BBB'), 200)
                    self.assertEqual(enumA.get_value('CCC'), 300)
                    self.assert_value_at_path(vpath, varmap, memdump, enumA.get_value('BBB'))

                    vpath = '/global/gEnumA_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gEnumA').get_address())

                    vpath = '/global/*gEnumA_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.has_enum())
                    enumA = v.get_enum()
                    self.assertEqual(enumA.get_value('AAA'), 100)
                    self.assertEqual(enumA.get_value('BBB'), 200)
                    self.assertEqual(enumA.get_value('CCC'), 300)
                    self.assert_value_at_path(vpath, varmap, memdump, enumA.get_value('BBB'))

                    # Struct E
                    vpath = '/global/gStructE/enumA'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.has_enum())
                    enumA = v.get_enum()
                    self.assertEqual(enumA.get_value('AAA'), 100)
                    self.assertEqual(enumA.get_value('BBB'), 200)
                    self.assertEqual(enumA.get_value('CCC'), 300)
                    self.assert_value_at_path(vpath, varmap, memdump, enumA.get_value('CCC'))

                    vpath = '/global/gStructE/enumA_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gEnumA').get_address())

                    vpath = '/global/gStructE/*enumA_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.has_enum())
                    enumA = v.get_enum()
                    self.assertEqual(enumA.get_value('AAA'), 100)
                    self.assertEqual(enumA.get_value('BBB'), 200)
                    self.assertEqual(enumA.get_value('CCC'), 300)
                    self.assert_value_at_path(vpath, varmap, memdump, self.get_value_at_path('/global/gEnumA', varmap, memdump))

                    vpath = '/global/gStructEptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gStructE/enumA').get_address())

                    vpath = '/global/*gStructEptr/enumA'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.has_enum())
                    enumA = v.get_enum()
                    self.assertEqual(enumA.get_value('AAA'), 100)
                    self.assertEqual(enumA.get_value('BBB'), 200)
                    self.assertEqual(enumA.get_value('CCC'), 300)
                    self.assert_value_at_path(vpath, varmap, memdump, self.get_value_at_path('/global/gStructE/enumA', varmap, memdump))

                    vpath = '/global/*gStructEptr/enumA_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gEnumA').get_address())

                    vpath = '/global/*gStructEptr/*enumA_ptr'   # Double dereferencing not supposed to happen
                    self.assertFalse(varmap.has_var(vpath))

                    # Test circular pointers  F&G
                    vpath = '/global/gStructF/i32'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.sint32)
                    self.assert_value_at_path(vpath, varmap, memdump, 0x511425)

                    vpath = '/global/gStructF/g'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gStructG/u32').get_address())

                    vpath = '/global/gStructG/u32'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.uint32)
                    self.assert_value_at_path(vpath, varmap, memdump, 0xFA197345)

                    vpath = '/global/gStructG/f'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gStructF/i32').get_address())

                    # F&G dereferencing
                    vpath = '/global/gStructF/*g/u32'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.uint32)
                    self.assert_value_at_path(vpath, varmap, memdump, 0xFA197345)

                    vpath = '/global/gStructF/*g/f'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gStructF/i32').get_address())

                    vpath = '/global/gStructF/*g/*f/i32'
                    self.assertFalse(varmap.has_var(vpath))  # Double dereferencing not allowed

                    vpath = '/global/gStructG/*f/i32'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.sint32)
                    self.assert_value_at_path(vpath, varmap, memdump, 0x511425)

                    vpath = '/global/gStructG/*f/g'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gStructG/u32').get_address())

                    vpath = '/global/gStructF/*f/*g/u32'
                    self.assertFalse(varmap.has_var(vpath))  # Double dereferencing not allowed

    @unittest.skipIf(
        not has_elf_toolchain(compiler='g++', cppfilt='c++filt')
        or not has_elf_toolchain(compiler='clang++', cppfilt='c++filt'),
        "No toolchain available")
    def test_extract_pointers_array_mix(self):
        code = """
#include <cstdint>
%s

enum EnumU32 : uint32_t
{
    XXX = 123,
    YYY = 456,
    ZZZ = 789
};

struct A
{
 int32_t i32;
};

struct B
{
 uint32_t u32;
 uint32_t *u32_ptr;
};

struct C
{
    int32_t i32;
    uint16_t u16_array[5][10];
    EnumU32 u32_enum;
};

struct D
{
    C* c_ptr;
    C* c_ptr_array[2][5];
    C c_array[5];
    uint32_t* u32_ptr_array[3][2];
    EnumU32* u32_enum_ptr_array[4][5];
};

uint32_t gu32;
EnumU32 gu32_enum;
uint32_t * array_of_ptr[10];
A* array_of_a_ptr[5];
B array_of_b[5];

C gStructC;
C gStructC2;
C* gStructCptr;

D gStructD;
D* gStructDptr;

int main(int argc, char* argv[])
{
    gu32 = 0x12345678;
    gu32_enum = EnumU32::YYY;
    static uint32_t some_u32 = 0x11223344;
    array_of_ptr[5] = &some_u32;

    array_of_b[3].u32 = 0xab128246;
    array_of_b[3].u32_ptr = &gu32;

    gStructC.i32 = 0x534751;
    gStructC.u16_array[2][3] = 0xb0a7;
    gStructC.u32_enum = EnumU32::ZZZ;
    gStructC2.i32 = 0x66474;
    gStructC2.u16_array[1][2] = 0x4821;
    gStructC2.u32_enum = EnumU32::XXX;

    gStructCptr = &gStructC;

    gStructD.c_ptr = &gStructC;
    gStructD.c_ptr_array[1][3] = &gStructC2;
    gStructD.c_array[2].i32 = 0x34672;
    gStructD.c_array[2].u16_array[1][0] = 0x8421;
    gStructD.u32_ptr_array[2][1] = &gu32;
    gStructD.u32_enum_ptr_array[2][3] = &gu32_enum;

    gStructDptr = &gStructD;
    %s
    return 0;
}
""" % (memdump_declare, memdump_invocation)

        def assert_is_enumU32(enum: EmbeddedEnum):
            self.assertTrue(enum.get_name(), 'EnumU32')
            self.assertTrue(enum.get_value('XXX'), 123)
            self.assertTrue(enum.get_value('YYY'), 456)
            self.assertTrue(enum.get_value('ZZZ'), 789)

        for compiler in ['g++', 'clang++']:
            for dwarf_version in [2, 3, 4]:
                with self.subTest(f"{compiler}-dwarf{dwarf_version}"):
                    varmap, memdump = self._make_varmap_and_memdump(code, dwarf_version=dwarf_version, compiler=compiler, cppfilt='c++filt')

                    vpath = '/global/array_of_ptr/array_of_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(f"{vpath}[0]")
                    self.assertTrue(v.get_type().is_pointer())
                    self.assertTrue(varmap.has_array_segments(vpath))
                    array_segments = varmap.get_array_segments(vpath)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/global/array_of_ptr/array_of_ptr"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (10, ))
                    self.assertEqual(array_segments[p1].element_byte_size, 8)

                    vpath = '/global/array_of_ptr/*array_of_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    v = varmap.get_var(f"{vpath}[0]")
                    self.assertTrue(v.get_type(), EmbeddedDataType.uint32)
                    self.assertFalse(varmap.has_array_segments(vpath))
                    self.assertTrue(varmap.has_pointer_array_segments(vpath))
                    # varmap storage first
                    array_segments = varmap.get_pointer_array_segments(vpath)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/global/array_of_ptr/array_of_ptr"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (10, ))
                    self.assertEqual(array_segments[p1].element_byte_size, 8)
                    # public api check
                    self.assertTrue(v.has_pointed_address())
                    pointer = v.get_pointer()
                    self.assertEqual(pointer.pointer_path, '/global/array_of_ptr/array_of_ptr[0]')
                    self.assertEqual(pointer.pointer_offset, 0)

                    self.assert_value_at_path("/global/array_of_ptr/*array_of_ptr[5]", varmap, memdump, 0x11223344)

                    vpath = '/global/array_of_b/array_of_b/u32'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertTrue(varmap.has_array_segments(vpath))
                    array_segments = varmap.get_array_segments(vpath)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/global/array_of_b/array_of_b"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (5, ))
                    self.assert_value_at_path("/global/array_of_b/array_of_b[3]/u32", varmap, memdump, 0xab128246)

                    vpath = '/global/array_of_b/array_of_b/u32_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertTrue(varmap.has_array_segments(vpath))
                    array_segments = varmap.get_array_segments(vpath)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/global/array_of_b/array_of_b"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (5, ))
                    self.assert_value_at_path(
                        "/global/array_of_b/array_of_b[3]/u32_ptr",
                        varmap, memdump, varmap.get_var('/global/gu32').get_address()
                    )

                    vpath = '/global/array_of_b/array_of_b/*u32_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertFalse(varmap.has_array_segments(vpath))
                    self.assertTrue(varmap.has_pointer_array_segments(vpath))

                    array_segments = varmap.get_pointer_array_segments(vpath)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/global/array_of_b/array_of_b"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (5, ))
                    v = varmap.get_var('/global/array_of_b/array_of_b[3]/*u32_ptr')
                    self.assertTrue(v.has_pointed_address())
                    self.assertFalse(v.has_absolute_address())
                    self.assertEqual(v.get_pointer().pointer_path, '/global/array_of_b/array_of_b[3]/u32_ptr')
                    self.assertEqual(v.get_pointer().pointer_offset, 0)
                    self.assert_value_at_path(
                        "/global/array_of_b/array_of_b[3]/*u32_ptr",
                        varmap, memdump, self.get_value_at_path('/global/gu32', varmap, memdump)
                    )

                    vpath = '/global/gStructC/i32'
                    self.assert_value_at_path(vpath, varmap, memdump, 0x534751)

                    vpath = '/global/gStructC/u16_array/u16_array'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertTrue(varmap.has_array_segments(vpath))
                    array_segments = varmap.get_array_segments(vpath)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/global/gStructC/u16_array/u16_array"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (5, 10))
                    self.assert_value_at_path('/global/gStructC/u16_array/u16_array[2][3]', varmap, memdump, 0xb0a7)

                    vpath = '/global/gStructCptr'
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gStructC/i32').get_address())

                    # dereference
                    vpath = '/global/*gStructCptr/i32'
                    self.assert_value_at_path(vpath, varmap, memdump, 0x534751)

                    vpath = '/global/*gStructCptr/u32_enum'
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.has_enum())
                    enum = v.get_enum()
                    assert_is_enumU32(enum)
                    self.assert_value_at_path(v.get_fullname(), varmap, memdump, enum.get_value('ZZZ'))

                    vpath = '/global/*gStructCptr/u16_array/u16_array'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertTrue(varmap.has_array_segments(vpath))
                    self.assertFalse(varmap.has_pointer_array_segments(vpath))
                    array_segments = varmap.get_array_segments(vpath)
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/global/*gStructCptr/u16_array/u16_array"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (5, 10))
                    self.assert_value_at_path('/global/*gStructCptr/u16_array/u16_array[2][3]', varmap, memdump, 0xb0a7)

                    # Struct D
                    vpath = '/global/gStructD/c_ptr'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertFalse(varmap.has_array_segments(vpath))
                    self.assertFalse(varmap.has_pointer_array_segments(vpath))
                    v = varmap.get_var(vpath)
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(vpath, varmap, memdump, varmap.get_var('/global/gStructC/i32').get_address())

                    vpath = '/global/gStructD/*c_ptr/i32'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertFalse(varmap.has_array_segments(vpath))
                    self.assertFalse(varmap.has_pointer_array_segments(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.sint32)
                    self.assert_value_at_path(vpath, varmap, memdump, 0x534751)

                    vpath = '/global/gStructD/*c_ptr/u32_enum'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertFalse(varmap.has_array_segments(vpath))
                    self.assertFalse(varmap.has_pointer_array_segments(vpath))
                    v = varmap.get_var(vpath)
                    self.assertEqual(v.get_type(), EmbeddedDataType.uint32)
                    self.assertTrue(v.has_enum())
                    enum = v.get_enum()
                    assert_is_enumU32(enum)
                    self.assert_value_at_path(vpath, varmap, memdump, enum.get_value('ZZZ'))

                    vpath = '/global/gStructD/*c_ptr/u16_array/u16_array'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertTrue(varmap.has_array_segments(vpath))
                    self.assertFalse(varmap.has_pointer_array_segments(vpath))
                    v = varmap.get_var(f"{vpath}[2][3]")
                    self.assertTrue(v.has_pointed_address())
                    array_segments = varmap.get_array_segments(vpath)
                    self.assertEqual(len(array_segments), 1)
                    p1 = '/global/gStructD/*c_ptr/u16_array/u16_array'
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (5, 10))
                    self.assertEqual(v.get_pointer().pointer_path, '/global/gStructD/c_ptr')
                    self.assertEqual(v.get_type(), EmbeddedDataType.uint16)
                    self.assert_value_at_path(v.get_fullname(), varmap, memdump, 0xb0a7)

                    vpath = '/global/gStructD/u32_ptr_array/u32_ptr_array'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertTrue(varmap.has_array_segments(vpath))
                    self.assertFalse(varmap.has_pointer_array_segments(vpath))
                    v = varmap.get_var(f"{vpath}[2][1]")
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(v.get_fullname(), varmap, memdump, varmap.get_var('/global/gu32').get_address())

                    vpath = '/global/gStructD/u32_ptr_array/*u32_ptr_array'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertFalse(varmap.has_array_segments(vpath))
                    self.assertTrue(varmap.has_pointer_array_segments(vpath))
                    pointer_array_segments = varmap.get_pointer_array_segments(vpath)
                    self.assertEqual(len(pointer_array_segments), 1)
                    p1 = "/global/gStructD/u32_ptr_array/u32_ptr_array"
                    self.assertIn(p1, pointer_array_segments)
                    self.assertEqual(pointer_array_segments[p1].dims, (3, 2))
                    v = varmap.get_var('/global/gStructD/u32_ptr_array/*u32_ptr_array[2][1]')
                    self.assertEqual(v.get_pointer().pointer_offset, 0)
                    self.assertEqual(v.get_pointer().pointer_path, '/global/gStructD/u32_ptr_array/u32_ptr_array[2][1]')
                    self.assert_value_at_path(
                        v.get_fullname(), varmap, memdump,
                        self.get_value_at_path('/global/gu32', varmap, memdump)
                    )

                    vpath = '/global/gStructD/u32_enum_ptr_array/*u32_enum_ptr_array'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertFalse(varmap.has_array_segments(vpath))
                    self.assertTrue(varmap.has_pointer_array_segments(vpath))
                    pointer_array_segments = varmap.get_pointer_array_segments(vpath)
                    self.assertEqual(len(pointer_array_segments), 1)
                    p1 = "/global/gStructD/u32_enum_ptr_array/u32_enum_ptr_array"
                    self.assertIn(p1, pointer_array_segments)
                    self.assertEqual(pointer_array_segments[p1].dims, (4, 5))
                    v = varmap.get_var('/global/gStructD/u32_enum_ptr_array/*u32_enum_ptr_array[2][3]')
                    self.assertEqual(v.get_pointer().pointer_offset, 0)
                    self.assertEqual(v.get_pointer().pointer_path, '/global/gStructD/u32_enum_ptr_array/u32_enum_ptr_array[2][3]')
                    self.assertTrue(v.has_enum())
                    enum = v.get_enum()
                    assert_is_enumU32(enum)
                    self.assert_value_at_path('/global/gu32_enum', varmap, memdump, enum.get_value('YYY'))

                    self.assert_value_at_path(
                        v.get_fullname(), varmap, memdump,
                        self.get_value_at_path('/global/gu32_enum', varmap, memdump)
                    )

                    vpath = '/global/gStructD/c_ptr_array/c_ptr_array'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertTrue(varmap.has_array_segments(vpath))
                    self.assertFalse(varmap.has_pointer_array_segments(vpath))
                    v = varmap.get_var(f"{vpath}[1][3]")
                    self.assertTrue(v.get_type().is_pointer())
                    self.assert_value_at_path(v.get_fullname(), varmap, memdump, varmap.get_var('/global/gStructC2/i32').get_address())

                    vpath = '/global/gStructD/c_ptr_array/*c_ptr_array/i32'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertFalse(varmap.has_array_segments(vpath))
                    self.assertTrue(varmap.has_pointer_array_segments(vpath))
                    pointer_array_segments = varmap.get_pointer_array_segments(vpath)
                    self.assertEqual(len(pointer_array_segments), 1)
                    p1 = "/global/gStructD/c_ptr_array/c_ptr_array"
                    self.assertIn(p1, pointer_array_segments)
                    self.assertEqual(pointer_array_segments[p1].dims, (2, 5))
                    v = varmap.get_var(f"/global/gStructD/c_ptr_array/*c_ptr_array[1][3]/i32")
                    self.assertEqual(v.get_type(), EmbeddedDataType.sint32)
                    self.assert_value_at_path(v.get_fullname(), varmap, memdump, 0x66474)

                    vpath = '/global/gStructD/c_ptr_array/*c_ptr_array/u32_enum'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertFalse(varmap.has_array_segments(vpath))
                    self.assertTrue(varmap.has_pointer_array_segments(vpath))
                    pointer_array_segments = varmap.get_pointer_array_segments(vpath)
                    self.assertEqual(len(pointer_array_segments), 1)
                    p1 = "/global/gStructD/c_ptr_array/c_ptr_array"
                    self.assertIn(p1, pointer_array_segments)
                    self.assertEqual(pointer_array_segments[p1].dims, (2, 5))
                    v = varmap.get_var(f"/global/gStructD/c_ptr_array/*c_ptr_array[1][3]/u32_enum")
                    self.assertEqual(v.get_type(), EmbeddedDataType.uint32)
                    self.assertTrue(v.has_enum())
                    enum = v.get_enum()
                    assert_is_enumU32(enum)
                    self.assert_value_at_path(v.get_fullname(), varmap, memdump, enum.get_value('XXX'))

                    vpath = '/global/gStructD/c_ptr_array/*c_ptr_array/u16_array/u16_array'
                    self.assertTrue(varmap.has_var(vpath))
                    self.assertTrue(varmap.has_array_segments(vpath))
                    self.assertTrue(varmap.has_pointer_array_segments(vpath))
                    array_segments = varmap.get_array_segments(vpath)
                    pointer_array_segments = varmap.get_pointer_array_segments(vpath)
                    self.assertEqual(len(array_segments), 1)
                    self.assertEqual(len(pointer_array_segments), 1)
                    p1 = "/global/gStructD/c_ptr_array/c_ptr_array"
                    self.assertIn(p1, pointer_array_segments)
                    self.assertEqual(pointer_array_segments[p1].dims, (2, 5))
                    self.assertEqual(len(array_segments), 1)
                    p1 = "/global/gStructD/c_ptr_array/*c_ptr_array/u16_array/u16_array"
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (5, 10))
                    v = varmap.get_var(f"/global/gStructD/c_ptr_array/*c_ptr_array[1][3]/u16_array/u16_array[1][2]")
                    self.assertEqual(v.get_type(), EmbeddedDataType.uint16)
                    self.assertFalse(v.has_enum())
                    self.assert_value_at_path(v.get_fullname(), varmap, memdump, 0x4821)

    @unittest.skipIf(
        not has_elf_toolchain(compiler='g++', cppfilt='c++filt')
        or not has_elf_toolchain(compiler='clang++', cppfilt='c++filt'),
        "No toolchain available")
    def test_extract_pointers_array_mix_complex(self):
        code = """
#include <cstdint>
%s

namespace NamespaceA{
    class A {
        public:
        int16_t x;

        union {
            struct {
                uint32_t a1: 5;
                uint32_t a2: 9;
                uint32_t a3: 7;
                uint32_t a4: 3;
            } bitfield;
        }  union1;
    };

    struct B {

        int64_t _pad;
        A a;
    };

    struct C {
        int32_t _pad;
        B b_array[5][8];
    };

    struct D {
        int32_t _pad;
        struct {
            int16_t pad;
            C c_array[4];
        } anon_member;

        int32_t _pad2;
    };

    struct E {
        char _pad[20];
        D* d_ptr;
    };

    class F {
        public:
        int64_t _pad;
        E e_array[3][2][4];
    };

    struct G {
        int8_t _pad;
        F f_array[2][3];
    };
}


namespace NamespaceB
{
    namespace NamespaceC {
        static NamespaceA::G static_g_instance;
    }
}

namespace NamespaceD
{
    NamespaceA::D global_d_instance;
}


int main(int argc, char* argv[])
{
    NamespaceD::global_d_instance.anon_member.c_array[2].b_array[3][5].a.union1.bitfield.a3 = 23;
    NamespaceB::NamespaceC::static_g_instance.f_array[1][0].e_array[2][1][3].d_ptr = &NamespaceD::global_d_instance;
    %s
    return 0;
}
""" % (memdump_declare, memdump_invocation)
        for compiler in ['g++', 'clang++']:
            for dwarf_version in [2, 3, 4]:
                with self.subTest(f"{compiler}-dwarf{dwarf_version}"):
                    varmap, memdump = self._make_varmap_and_memdump(code, dwarf_version=dwarf_version, compiler=compiler, cppfilt='c++filt')

                    unresolved_vpath = '/static/main.cpp/NamespaceB/NamespaceC/static_g_instance/f_array/f_array/e_array/e_array/*d_ptr/anon_member/c_array/c_array/b_array/b_array/a/union1/bitfield/a3'
                    resolved_vpath = '/static/main.cpp/NamespaceB/NamespaceC/static_g_instance/f_array/f_array[1][0]/e_array/e_array[2][1][3]/*d_ptr/anon_member/c_array/c_array[2]/b_array/b_array[3][5]/a/union1/bitfield/a3'
                    self.assertTrue(varmap.has_var(unresolved_vpath))

                    self.assertTrue(varmap.has_array_segments(unresolved_vpath))
                    self.assertTrue(varmap.has_pointer_array_segments(unresolved_vpath))
                    array_segments = varmap.get_array_segments(unresolved_vpath)
                    pointer_array_segments = varmap.get_pointer_array_segments(unresolved_vpath)

                    self.assertEqual(len(array_segments), 2)
                    p1 = '/static/main.cpp/NamespaceB/NamespaceC/static_g_instance/f_array/f_array/e_array/e_array/*d_ptr/anon_member/c_array/c_array'
                    self.assertIn(p1, array_segments)
                    self.assertEqual(array_segments[p1].dims, (4,))
                    p2 = '/static/main.cpp/NamespaceB/NamespaceC/static_g_instance/f_array/f_array/e_array/e_array/*d_ptr/anon_member/c_array/c_array/b_array/b_array'
                    self.assertEqual(array_segments[p2].dims, (5, 8))
                    self.assertIn(p2, array_segments)

                    self.assertEqual(len(pointer_array_segments), 2)
                    p1 = '/static/main.cpp/NamespaceB/NamespaceC/static_g_instance/f_array/f_array'
                    self.assertIn(p1, pointer_array_segments)
                    self.assertEqual(pointer_array_segments[p1].dims, (2, 3))
                    p2 = '/static/main.cpp/NamespaceB/NamespaceC/static_g_instance/f_array/f_array/e_array/e_array'
                    self.assertIn(p2, pointer_array_segments)
                    self.assertEqual(pointer_array_segments[p2].dims, (3, 2, 4))

                    v = varmap.get_var(resolved_vpath)
                    self.assertIsInstance(v.get_pointer(), ResolvedPathPointedLocation)
                    self.assertEqual(v.get_pointer().pointer_path,
                                     '/static/main.cpp/NamespaceB/NamespaceC/static_g_instance/f_array/f_array[1][0]/e_array/e_array[2][1][3]/d_ptr')
                    self.assert_value_at_path(v.get_fullname(), varmap, memdump, 23)

    @unittest.skipIf(not has_rust_toolchain(), "No Rust toolchain available")
    def test_rust_collapse_wrapper_types(self):
        # Wrapper types with a single descendant must be registered under the variable name, without the inner member names.
        code = """
#![allow(static_mut_refs, dead_code, non_upper_case_globals)]
use core::cell::{Cell, RefCell, UnsafeCell};
use core::cmp::Reverse;
use core::marker::PhantomData;
use core::mem::{ManuallyDrop, MaybeUninit};
use core::num::{NonZeroU32, Saturating, Wrapping};
use core::pin::Pin;
use core::ptr::NonNull;
use core::sync::atomic::{AtomicBool, AtomicI16, AtomicPtr, AtomicU32, AtomicU64, AtomicU8, AtomicUsize};

// Replicas of crate wrappers with the same layout. Collapse rules match the struct name only, not the namespace.
pub struct VolatileCell<T> { value: UnsafeCell<T> }     // vcell
pub struct RW<T> { register: VolatileCell<T> }           // volatile_register
pub struct Mutex<T> { inner: UnsafeCell<T> }             // critical_section, bare_metal
pub struct InMemoryRegister<T, R> { value: UnsafeCell<T>, associated_register: PhantomData<R> }    // tock_registers
pub struct AtomicF32(UnsafeCell<f32>);                   // atomic_float
#[repr(align(128))]
pub struct CachePadded<T> { value: T }                   // crossbeam_utils
pub struct OrderedFloat<T>(pub T);                       // ordered_float

// Not collapsible
pub struct Config { speed: u32 }
pub struct MyNewtype(pub u32);
pub struct Holder { counter: AtomicU32, flag: u8 }

#[used] pub static mut ptr_target: u32 = 0x31415926;
#[used] pub static mut pin_target: u32 = 0x27182818;

#[used] pub static mut atomic_u8: AtomicU8 = AtomicU8::new(0x12);
#[used] pub static mut atomic_i16: AtomicI16 = AtomicI16::new(-1234);
#[used] pub static mut atomic_u32: AtomicU32 = AtomicU32::new(0x12345678);
#[used] pub static mut atomic_u64: AtomicU64 = AtomicU64::new(0x1122334455667788);
#[used] pub static mut atomic_usize: AtomicUsize = AtomicUsize::new(0xABCDEF);
#[used] pub static mut atomic_bool: AtomicBool = AtomicBool::new(true);
#[used] pub static mut atomic_ptr: AtomicPtr<u32> = AtomicPtr::new(&raw mut ptr_target);
#[used] pub static mut cell: Cell<u32> = Cell::new(0x11223344);
#[used] pub static mut unsafecell: UnsafeCell<u32> = UnsafeCell::new(0x55667788);
#[used] pub static mut manuallydrop: ManuallyDrop<u32> = ManuallyDrop::new(0x99AABBCC);
#[used] pub static mut maybeuninit: MaybeUninit<u32> = MaybeUninit::new(0x0BADF00D);
#[used] pub static mut wrapping: Wrapping<u32> = Wrapping(1001);
#[used] pub static mut saturating: Saturating<u32> = Saturating(1002);
#[used] pub static mut reverse: Reverse<u32> = Reverse(1003);
#[used] pub static mut nonzero: NonZeroU32 = match NonZeroU32::new(7777) { Some(v) => v, None => panic!() };
#[used] pub static mut nonnull: NonNull<u32> = unsafe { NonNull::new_unchecked(&raw mut ptr_target) };
#[used] pub static mut pin: Pin<&'static u32> = Pin::static_ref(unsafe { &*(&raw const pin_target) });
#[used] pub static mut atomic_array: [AtomicU32; 3] = [AtomicU32::new(10), AtomicU32::new(20), AtomicU32::new(30)];

#[used] pub static mut vcell: VolatileCell<u32> = VolatileCell { value: UnsafeCell::new(0x01020304) };
#[used] pub static mut rw: RW<u32> = RW { register: VolatileCell { value: UnsafeCell::new(0x05060708) } };
#[used] pub static mut mutex_cell: Mutex<Cell<u32>> = Mutex { inner: UnsafeCell::new(Cell::new(0x0A0B0C0D)) };
#[used] pub static mut mutex_refcell: Mutex<RefCell<u32>> = Mutex { inner: UnsafeCell::new(RefCell::new(0x0E0F1011)) };
#[used] pub static mut inmemreg: InMemoryRegister<u32, ()> = InMemoryRegister { value: UnsafeCell::new(0x2468ACE0), associated_register: PhantomData };
#[used] pub static mut atomic_f32: AtomicF32 = AtomicF32(UnsafeCell::new(3.5));
#[used] pub static mut cachepadded: CachePadded<u32> = CachePadded { value: 0x13579BDF };
#[used] pub static mut ordered_float: OrderedFloat<f32> = OrderedFloat(2.25);

#[used] pub static mut refcell: RefCell<u32> = RefCell::new(4242);
#[used] pub static mut config: Config = Config { speed: 3000 };
#[used] pub static mut newtype: MyNewtype = MyNewtype(5000);
#[used] pub static mut holder: Holder = Holder { counter: AtomicU32::new(0xDEADBEEF), flag: 0x5A };

fn main() {}
"""
        for dwarf_version in [4, 5]:
            with self.subTest(f"rustc-dwarf{dwarf_version}"):
                varmap, memdump = self._make_rust_varmap_and_memdump(code, crate_name='collapse_test', dwarf_version=dwarf_version)
                prefix = '/static/collapse_test'

                # core
                self.assert_value_at_path(f'{prefix}/atomic_u8', varmap, memdump, 0x12)
                self.assert_value_at_path(f'{prefix}/atomic_i16', varmap, memdump, -1234)
                self.assert_value_at_path(f'{prefix}/atomic_u32', varmap, memdump, 0x12345678)
                self.assert_value_at_path(f'{prefix}/atomic_u64', varmap, memdump, 0x1122334455667788)
                self.assert_value_at_path(f'{prefix}/atomic_usize', varmap, memdump, 0xABCDEF)
                self.assert_value_at_path(f'{prefix}/cell', varmap, memdump, 0x11223344)
                self.assert_value_at_path(f'{prefix}/unsafecell', varmap, memdump, 0x55667788)
                self.assert_value_at_path(f'{prefix}/manuallydrop', varmap, memdump, 0x99AABBCC)
                self.assert_value_at_path(f'{prefix}/maybeuninit', varmap, memdump, 0x0BADF00D)
                self.assert_value_at_path(f'{prefix}/wrapping', varmap, memdump, 1001)
                self.assert_value_at_path(f'{prefix}/saturating', varmap, memdump, 1002)
                self.assert_value_at_path(f'{prefix}/reverse', varmap, memdump, 1003)
                self.assert_value_at_path(f'{prefix}/nonzero', varmap, memdump, 7777)
                self.assertFalse(varmap.has_var(f'{prefix}/atomic_u32/v/value/__0'))
                self.assertFalse(varmap.has_var(f'{prefix}/cell/value/value'))

                # Pointer leaves
                ptr_target_address = varmap.get_var(f'{prefix}/ptr_target').get_address()
                pin_target_address = varmap.get_var(f'{prefix}/pin_target').get_address()
                self.assert_value_at_path(f'{prefix}/atomic_ptr', varmap, memdump, ptr_target_address)
                self.assert_value_at_path(f'{prefix}/nonnull', varmap, memdump, ptr_target_address)
                self.assert_value_at_path(f'{prefix}/pin', varmap, memdump, pin_target_address)

                # Array of collapsible elements
                self.assert_value_at_path(f'{prefix}/atomic_array/atomic_array[0]', varmap, memdump, 10)
                self.assert_value_at_path(f'{prefix}/atomic_array/atomic_array[1]', varmap, memdump, 20)
                self.assert_value_at_path(f'{prefix}/atomic_array/atomic_array[2]', varmap, memdump, 30)

                # Crate replicas
                self.assert_value_at_path(f'{prefix}/vcell', varmap, memdump, 0x01020304)
                self.assert_value_at_path(f'{prefix}/rw', varmap, memdump, 0x05060708)
                self.assert_value_at_path(f'{prefix}/mutex_cell', varmap, memdump, 0x0A0B0C0D)
                self.assert_value_at_path(f'{prefix}/inmemreg', varmap, memdump, 0x2468ACE0)
                self.assert_value_at_path(f'{prefix}/atomic_f32', varmap, memdump, 3.5)
                self.assert_value_at_path(f'{prefix}/cachepadded', varmap, memdump, 0x13579BDF)
                self.assert_value_at_path(f'{prefix}/ordered_float', varmap, memdump, 2.25)

                # Collapsible member inside a regular struct
                self.assert_value_at_path(f'{prefix}/holder/counter', varmap, memdump, 0xDEADBEEF)
                self.assert_value_at_path(f'{prefix}/holder/flag', varmap, memdump, 0x5A)

                # Many descendants: the outer struct stays, the inner wrappers collapse
                self.assert_value_at_path(f'{prefix}/refcell/borrow', varmap, memdump, 0)
                self.assert_value_at_path(f'{prefix}/refcell/value', varmap, memdump, 4242)
                self.assert_value_at_path(f'{prefix}/mutex_refcell/inner/value/borrow', varmap, memdump, 0)
                self.assert_value_at_path(f'{prefix}/mutex_refcell/inner/value/value', varmap, memdump, 0x0E0F1011)

                # Atomic<bool> is excluded by the regex because its leaf is a u8. Only the inner wrappers collapse
                self.assert_value_at_path(f'{prefix}/atomic_bool/v', varmap, memdump, 1)

                # Name not matching a known wrapper
                self.assert_value_at_path(f'{prefix}/config/speed', varmap, memdump, 3000)
                self.assert_value_at_path(f'{prefix}/newtype/__0', varmap, memdump, 5000)

    @unittest.skipIf(
        not has_elf_toolchain(compiler='g++', cppfilt='c++filt')
        or not has_elf_toolchain(compiler='clang++', cppfilt='c++filt'),
        "No toolchain available")
    def test_no_collapse_for_non_rust_compiler(self):
        # Struct names matching the Rust wrappers must not be collapsed when the compiler is not rustc
        code = """
#include <cstdint>
%s
template <typename T>
struct Cell
{
    T value;
};

template <typename T>
struct Atomic
{
    T v;
};

Cell<uint32_t> my_cell;
Atomic<uint32_t> my_atomic;

int main(int argc, char* argv[])
{
    my_cell.value = 0x11223344;
    my_atomic.v = 0x55667788;
    %s
    return 0;
}
""" % (memdump_declare, memdump_invocation)
        for compiler in ['g++', 'clang++']:
            with self.subTest(compiler):
                varmap, memdump = self._make_varmap_and_memdump(code, dwarf_version=4, compiler=compiler, cppfilt='c++filt')
                self.assert_value_at_path('/global/my_cell/value', varmap, memdump, 0x11223344)
                self.assert_value_at_path('/global/my_atomic/v', varmap, memdump, 0x55667788)
                self.assertFalse(varmap.has_var('/global/my_cell'))
                self.assertFalse(varmap.has_var('/global/my_atomic'))


if __name__ == '__main__':
    import unittest
    unittest.main()
