#    test_elf_dwarf_var_extractor.py
#        Test the extraction of dwarf symbols from a .elf file
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2022 Scrutiny Debugger

import re
from test import ScrutinyUnitTest
from test.artifacts import get_artifact
from scrutiny.core.bintools.elf_dwarf_var_extractor import ElfDwarfVarExtractor

from scrutiny.tools.typing import *


class TestElf2VarMap(ScrutinyUnitTest):

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

    def test_extract_arrays(self):
        testbin = get_artifact('testarray_dwarf4.elf')
        extractor = ElfDwarfVarExtractor(testbin)
        varmap = extractor.get_varmap()

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
