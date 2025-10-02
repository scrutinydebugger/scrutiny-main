#    test_varmap.py
#        A test suite for the VarMap class
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from binascii import unhexlify
import tempfile
import os
import json

from test import ScrutinyUnitTest
from scrutiny.core.varmap import VarMap
from scrutiny.core.basic_types import Endianness, EmbeddedDataType
from scrutiny.core.variable import VariableLocation
from scrutiny.core.array import UntypedArray
from scrutiny.core.embedded_enum import EmbeddedEnum


class TestVarmap(ScrutinyUnitTest):

    def test_basic_usage(self):
        varmap = VarMap()
        varmap.set_endianness(Endianness.Big)
        self.assertEqual(varmap.get_endianness(), Endianness.Big)
        varmap.register_base_type('float', EmbeddedDataType.float32)
        varmap.register_base_type('uint32_t', EmbeddedDataType.uint32)
        varmap.register_base_type('uint32_t', EmbeddedDataType.uint32)  # Adding twice is allowed
        with self.assertRaises(Exception):
            varmap.register_base_type('uint32_t', EmbeddedDataType.uint64)  # name collision and different type. not allowed
        varmap.register_base_type('int32_t', EmbeddedDataType.sint32)

        varmap.add_variable(['aaa', 'bbb', 'ccc'], VariableLocation(0x1234), original_type_name='float')
        varmap.add_variable(['aaa', 'bbb', 'ddd', 'eee'], VariableLocation(0x5555), original_type_name='uint32_t', bitsize=4, bitoffset=6)
        varmap.add_variable(['aaa', 'bbb', 'ddd', 'fff'], VariableLocation(0x8000), original_type_name='int32_t',
                            bitsize=4, bitoffset=6, enum=EmbeddedEnum("my_enum", {'aaa': 100, 'bbb': 200}))

        with self.assertRaises(Exception):
            varmap.add_variable(['a'], VariableLocation(0), original_type_name='uint32_t')
        with self.assertRaises(Exception):
            varmap.add_variable(['b'], VariableLocation(1110), original_type_name='asdasd')

        self.assertTrue(varmap.has_var('/aaa/bbb/ccc'))
        self.assertTrue(varmap.has_var('/aaa/bbb/ddd/eee'))

        with self.assertRaises(Exception):
            varmap.get_var('asdasdasd')

        self.assertFalse(varmap.is_known_type("aaa"))
        self.assertTrue(varmap.is_known_type('float'))

        varmap2 = VarMap.from_json(varmap.get_json())
        with tempfile.TemporaryDirectory() as tempdir:
            filename = os.path.join(tempdir, 'temp.varmap')
            varmap.write(filename)
            varmap3 = VarMap.from_file(filename)

        for candidate in [varmap, varmap2, varmap3]:
            ccc = candidate.get_var('/aaa/bbb/ccc')
            eee = candidate.get_var('/aaa/bbb/ddd/eee')
            fff = candidate.get_var('/aaa/bbb/ddd/fff')

            self.assertEqual(ccc.endianness, Endianness.Big)
            self.assertEqual(ccc.get_address(), 0x1234)
            self.assertEqual(ccc.get_fullname(), '/aaa/bbb/ccc')
            self.assertEqual(ccc.get_type(), EmbeddedDataType.float32)
            self.assertFalse(ccc.is_bitfield())
            self.assertIsNone(ccc.get_bitsize())
            self.assertIsNone(ccc.get_bitoffset())
            self.assertEqual(ccc.get_bitfield_mask(), unhexlify('FFFFFFFF'))
            self.assertFalse(ccc.has_enum())

            self.assertEqual(eee.endianness, Endianness.Big)
            self.assertEqual(eee.get_address(), 0x5555)
            self.assertEqual(eee.get_fullname(), '/aaa/bbb/ddd/eee')
            self.assertEqual(eee.get_type(), EmbeddedDataType.uint32)
            self.assertTrue(eee.is_bitfield())
            self.assertEqual(eee.get_bitsize(), 4)
            self.assertEqual(eee.get_bitoffset(), 6)
            self.assertEqual(eee.get_bitfield_mask(), unhexlify('000003c0'))
            self.assertFalse(eee.has_enum())

            self.assertTrue(fff.has_enum())
            theenum = fff.get_enum()
            self.assertIsNotNone(theenum)
            self.assertTrue(theenum.get_value('aaa'), 100)
            self.assertTrue(theenum.get_value('bbb'), 200)

            enums = list(candidate.get_enum_by_name('my_enum'))
            self.assertEqual(len(enums), 1)

            with self.assertRaises(Exception):
                list(candidate.get_enum_by_name('asd'))

            all_vars = list(candidate.iterate_simple_vars())
            self.assertEqual(len(all_vars), 3)

    def test_add_stuff_after_reload(self):
        varmap = VarMap()
        varmap.set_endianness(Endianness.Big)
        varmap.register_base_type('float', EmbeddedDataType.float32)
        varmap.register_base_type('uint32_t', EmbeddedDataType.uint32)

        varmap.add_variable(['aaa', 'bbb', 'ccc'], VariableLocation(0x1234), original_type_name='float')
        varmap.add_variable(['aaa', 'bbb', 'ddd', 'eee'], VariableLocation(0x5555), original_type_name='uint32_t', bitsize=4, bitoffset=6)
        varmap.add_variable(['aaa', 'bbb', 'ddd', 'fff'], VariableLocation(0x8000), original_type_name='uint32_t',
                            bitsize=4, bitoffset=6, enum=EmbeddedEnum("my_enum", {'aaa': 100, 'bbb': 200}))

        varmap2 = VarMap.from_json(varmap.get_json())

        varmap2.register_base_type('int32_t', EmbeddedDataType.sint32)
        varmap2.add_variable(['aaa', 'bbb', 'ddd', 'xxx'], VariableLocation(0x8004), original_type_name='int32_t',
                             bitsize=4, bitoffset=6, enum=EmbeddedEnum("my_enum2", {'aaa2': 100, 'bbb2': 200}))

        xxx = varmap2.get_var('/aaa/bbb/ddd/xxx')
        e = xxx.get_enum()
        self.assertIsNotNone(e)
        self.assertEqual(e.get_value('aaa2'), 100)
        self.assertEqual(e.get_value('bbb2'), 200)

        varmap3 = VarMap.from_json(varmap2.get_json())
        xxx = varmap3.get_var('/aaa/bbb/ddd/xxx')
        fff = varmap3.get_var('/aaa/bbb/ddd/fff')
        ex = xxx.get_enum()
        ef = fff.get_enum()

        self.assertTrue(ex.has_value('aaa2'))
        self.assertTrue(ex.has_value('bbb2'))
        self.assertTrue(ef.has_value('aaa'))
        self.assertTrue(ef.has_value('bbb'))

    def test_load_unversioned_dict(self):
        # Make sure backward compatibility works when loading unversioned files.
        d = {
            "endianness": "little",
            "type_map": {
                "0": {
                    "name": "int",
                    "type": "sint32"
                },
                "1": {
                    "name": "unsigned int",
                    "type": "uint32"
                }
            },
            "variables": {  # No version key in this dict.
                "/path1/path2/some_int32": {
                    "type_id": "0",
                    "addr": 1000
                },
                "/path1/path2/some_uint32": {
                    "type_id": "1",
                    "addr": 1004,
                    "enum": "0"
                }
            },
            "enums": {
                "0": {
                    "name": "EnumA",
                    "values": {
                        "eVal1": 0,
                        "eVal2": 1,
                        "eVal3": 100,
                        "eVal4": 101
                    }
                }
            }
        }

        varmap = VarMap.from_json(json.dumps(d))

        self.assertTrue(varmap.has_var('/path1/path2/some_int32'))
        self.assertTrue(varmap.has_var('/path1/path2/some_uint32'))

        v1 = varmap.get_var('/path1/path2/some_int32')
        v2 = varmap.get_var('/path1/path2/some_uint32')

        self.assertEqual(v1.get_type(), EmbeddedDataType.sint32)
        self.assertEqual(v2.get_type(), EmbeddedDataType.uint32)
        self.assertEqual(v2.get_enum().name, 'EnumA')

    def test_get_var_with_array_info(self):

        varmap = VarMap()
        varmap.set_endianness(Endianness.Big)
        self.assertEqual(varmap.get_endianness(), Endianness.Big)
        varmap.register_base_type('float', EmbeddedDataType.float32)
        varmap.add_variable(['aaa', 'bbb', 'ccc', 'ddd'], VariableLocation(0x1234), original_type_name='float', array_segments={
            '/aaa/bbb': UntypedArray((3, 3),  4),
            '/aaa/bbb/ccc/ddd': UntypedArray((5, 6, 7), 4)
        })

        varmap.get_var('/aaa/bbb[1][2]/ccc/ddd[2][3][4]')
