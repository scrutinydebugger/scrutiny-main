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
from test.artifacts import get_artifact
from scrutiny.core.bintools.elf_dwarf_var_extractor import ElfDwarfVarExtractor

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
    print(sys.platform )
    if sys.platform == 'win32':
        return False
    
    if subprocess.call(["which", compiler]) != 0:
        return False
    
    if subprocess.call(["which", cppfilt]) != 0:
        return False
    
    return True

class TestElf2VarMapFromBuilds(ScrutinyUnitTest):

    def _make_varmap(self, code:str, dwarf_version=4, compiler = "g++", cppfilt='c++filt'):
        with tempfile.TemporaryDirectory() as d:
            main_cpp = os.path.join(d, 'main.cpp')
            outbin = os.path.join(d, 'out.bin')
            with open(main_cpp, 'wb') as f:
                f.write(code.encode('utf8'))
            
            p = subprocess.Popen([compiler, '-no-pie', f'-gdwarf-{dwarf_version}', main_cpp, '-o', outbin], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, stderr  = p.communicate()

            logger.debug(stdout.decode('utf8'))
            logger.debug(stderr.decode('utf8'))


            if p.returncode != 0:
                raise RuntimeError("Failed to compile code")
            
            with open(outbin, 'rb') as f:
                if f.read(4) != b'\x7fELF':
                    raise RuntimeError("Toolchain does not produce an elf.")
            
            extractor = ElfDwarfVarExtractor(outbin, cppfilt=cppfilt)
            return extractor.get_varmap()


    @unittest.skipIf(not has_elf_toolchain(compiler='g++', cppfilt='c++filt'), "No toolchain available")
    def test_extract_arrays(self):
        code = """
#include <cstdint>
#pragma pack(push, 1)
struct A
{
    int32_t x;
    int16_t y[2][3];
};

struct B
{
    int32_t x2;
    A y2[4][5];
};

struct C {
    uint32_t a;
    uint32_t b;
};
#pragma pack(pop)

A my_global_A;
B my_global_B;
C my_global_C;
A my_global_array_of_A[3];
B my_global_array_of_B[4];
C my_global_array_of_C[5];
int32_t my_global_int32_array[10][20];

int main(int argc, char* argv[])
{
    static volatile A my_static_A;
    static volatile B my_static_B;
    static volatile C my_static_C;
    static volatile A my_static_array_of_A[5];
    static volatile B my_static_array_of_B[6];
    static volatile C my_static_array_of_C[7];
    static volatile int32_t my_global_int32_array[10][20];

    return 0;
}
"""

        varmap = self._make_varmap(code, dwarf_version=4, compiler='g++', cppfilt='c++filt')
        v = '/global/my_global_A/x'
        self.assertTrue(varmap.has_var(v))
        self.assertFalse(varmap.has_array_segments(v))

        v = '/global/my_global_A/y'
        self.assertTrue(varmap.has_var(v))
        self.assertTrue(varmap.has_array_segments(v))
        array_segments = varmap.get_array_segments(v)
        self.assertIn(v, array_segments)
        self.assertEqual(array_segments[v].dims, (2, 3))
        self.assertEqual(array_segments[v].element_byte_size, 2)

        v = '/global/my_global_int32_array'
        self.assertTrue(varmap.has_var(v))
        self.assertTrue(varmap.has_array_segments(v))
        array_segments = varmap.get_array_segments(v)
        self.assertIn(v, array_segments)
        self.assertEqual(array_segments[v].dims, (10, 20))
        self.assertEqual(array_segments[v].element_byte_size, 4)

        v = '/static/main.cpp/main/my_static_A/x'
        self.assertTrue(varmap.has_var(v))


if __name__ == '__main__':
    import unittest
    unittest.main()
