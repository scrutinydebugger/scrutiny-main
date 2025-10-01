#    test_scrutiny_path.py
#        A test suite for the ScrutinyPath class
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from test import ScrutinyUnitTest
from scrutiny.core.scrutiny_path import ScrutinyPath
from scrutiny.core.variable import UntypedArray

class TestScrutinyPath(ScrutinyUnitTest):
    def test_segments_manipulation(self):
        self.assertEqual(ScrutinyPath.join_segments(['aaa', 'bbb', 'ccc']), '/aaa/bbb/ccc')
        self.assertEqual(ScrutinyPath.join_segments([]), '/')
        self.assertEqual(ScrutinyPath.make_segments('/aaa/bbb/ccc'), ['aaa', 'bbb', 'ccc'])
        self.assertEqual(ScrutinyPath.make_segments('/aaa/bbb///ccc//'), ['aaa', 'bbb', 'ccc'])

    def test_path_parsing(self):
        self.assertFalse(ScrutinyPath.from_string('/aaa/bbb/ccc').has_array_information())
        
        path = ScrutinyPath.from_string('/aaa/bbb[2][3]/ccc[5]/ddd[7][8][9]')
        self.assertTrue(path.has_array_information())

        self.assertEqual(path.get_name_segment(), 'ddd[7][8][9]') 
        self.assertEqual(path.get_raw_name_segment(), 'ddd') 

        self.assertEqual(path.get_segments(), ['aaa','bbb[2][3]','ccc[5]', 'ddd[7][8][9]']) 
        self.assertEqual(path.get_raw_segments(), ['aaa','bbb','ccc', 'ddd']) 

        self.assertEqual(path.to_str(), '/aaa/bbb[2][3]/ccc[5]/ddd[7][8][9]') 
        self.assertEqual(path.to_raw_str(), '/aaa/bbb/ccc/ddd' ) 


        d = path.get_path_to_array_pos_dict()
        self.assertEqual(len(d), 3)
        self.assertIn('/aaa/bbb', d)
        self.assertIn('/aaa/bbb/ccc', d)
        self.assertIn('/aaa/bbb/ccc/ddd', d)


    def test_array_position_extension(self):
        path = ScrutinyPath.from_string('/aaa[3][4]/bbb/ccc[2]')
        d = {
            '/aaa' : UntypedArray((10,20), '', 100),
            '/aaa/bbb/ccc' : UntypedArray((5,), '', 8)
        }

        offset = path.compute_address_offset(d)
        self.assertEqual(offset, (3*20+4)*100+2*8)

    def test_array_bad_format(self):

        path = ScrutinyPath.from_string('/aaa[3][4]/bbb/ccc[2]')

        d = {
            '/aaa' : UntypedArray((10,20), '', 100),
            '/aaa/bbb/cc' : UntypedArray((5,), '', 8)
        }
        with self.assertRaises(Exception):
            path.compute_address_offset(d)

        d = {
            '/aaa' : UntypedArray((2,20), '', 100),
            '/aaa/bbb/ccc' : UntypedArray((5,), '', 8)
        }
        with self.assertRaises(Exception):
            path.compute_address_offset(d)

        d = {
            '/aaa' : UntypedArray((2,20), '', 100),
            '/aaa/bbb' : UntypedArray((5,), '', 8)
        }
        with self.assertRaises(Exception):
            path.compute_address_offset(d)
