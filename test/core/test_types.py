#    test_types.py
#        Make some checks on Scrutiny basic types used project wide
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2022 Scrutiny Debugger

from scrutiny.core.basic_types import *
from scrutiny.core.codecs import *
from test import ScrutinyUnitTest
import math
import struct


class TestTypes(ScrutinyUnitTest):

    def test_type_size(self):
        self.assertEqual(EmbeddedDataType.sint8.get_size_8bits(), 1)
        self.assertEqual(EmbeddedDataType.sint16.get_size_8bits(), 2)
        self.assertEqual(EmbeddedDataType.sint32.get_size_8bits(), 4)
        self.assertEqual(EmbeddedDataType.sint64.get_size_8bits(), 8)
        self.assertEqual(EmbeddedDataType.sint128.get_size_8bits(), 16)
        self.assertEqual(EmbeddedDataType.sint256.get_size_8bits(), 32)

        self.assertEqual(EmbeddedDataType.uint8.get_size_8bits(), 1)
        self.assertEqual(EmbeddedDataType.uint16.get_size_8bits(), 2)
        self.assertEqual(EmbeddedDataType.uint32.get_size_8bits(), 4)
        self.assertEqual(EmbeddedDataType.uint64.get_size_8bits(), 8)
        self.assertEqual(EmbeddedDataType.uint128.get_size_8bits(), 16)
        self.assertEqual(EmbeddedDataType.uint256.get_size_8bits(), 32)

        self.assertEqual(EmbeddedDataType.float8.get_size_8bits(), 1)
        self.assertEqual(EmbeddedDataType.float16.get_size_8bits(), 2)
        self.assertEqual(EmbeddedDataType.float32.get_size_8bits(), 4)
        self.assertEqual(EmbeddedDataType.float64.get_size_8bits(), 8)
        self.assertEqual(EmbeddedDataType.float128.get_size_8bits(), 16)
        self.assertEqual(EmbeddedDataType.float256.get_size_8bits(), 32)

        self.assertEqual(EmbeddedDataType.cfloat8.get_size_8bits(), 1)
        self.assertEqual(EmbeddedDataType.cfloat16.get_size_8bits(), 2)
        self.assertEqual(EmbeddedDataType.cfloat32.get_size_8bits(), 4)
        self.assertEqual(EmbeddedDataType.cfloat64.get_size_8bits(), 8)
        self.assertEqual(EmbeddedDataType.cfloat128.get_size_8bits(), 16)
        self.assertEqual(EmbeddedDataType.cfloat256.get_size_8bits(), 32)

        self.assertEqual(EmbeddedDataType.bool8.get_size_8bits(), 1)

    def test_is_signed(self):
        self.assertTrue(EmbeddedDataType.sint8.is_signed())
        self.assertTrue(EmbeddedDataType.sint16.is_signed())
        self.assertTrue(EmbeddedDataType.sint32.is_signed())
        self.assertTrue(EmbeddedDataType.sint64.is_signed())
        self.assertTrue(EmbeddedDataType.sint128.is_signed())
        self.assertTrue(EmbeddedDataType.sint256.is_signed())

        self.assertFalse(EmbeddedDataType.uint8.is_signed())
        self.assertFalse(EmbeddedDataType.uint16.is_signed())
        self.assertFalse(EmbeddedDataType.uint32.is_signed())
        self.assertFalse(EmbeddedDataType.uint64.is_signed())
        self.assertFalse(EmbeddedDataType.uint128.is_signed())
        self.assertFalse(EmbeddedDataType.uint256.is_signed())

        self.assertTrue(EmbeddedDataType.float8.is_signed())
        self.assertTrue(EmbeddedDataType.float16.is_signed())
        self.assertTrue(EmbeddedDataType.float32.is_signed())
        self.assertTrue(EmbeddedDataType.float64.is_signed())
        self.assertTrue(EmbeddedDataType.float128.is_signed())
        self.assertTrue(EmbeddedDataType.float256.is_signed())

        self.assertTrue(EmbeddedDataType.cfloat8.is_signed())
        self.assertTrue(EmbeddedDataType.cfloat16.is_signed())
        self.assertTrue(EmbeddedDataType.cfloat32.is_signed())
        self.assertTrue(EmbeddedDataType.cfloat64.is_signed())
        self.assertTrue(EmbeddedDataType.cfloat128.is_signed())
        self.assertTrue(EmbeddedDataType.cfloat256.is_signed())

        self.assertFalse(EmbeddedDataType.bool8.is_signed())

    def test_is_integer(self):
        self.assertTrue(EmbeddedDataType.sint8.is_integer())
        self.assertTrue(EmbeddedDataType.sint16.is_integer())
        self.assertTrue(EmbeddedDataType.sint32.is_integer())
        self.assertTrue(EmbeddedDataType.sint64.is_integer())
        self.assertTrue(EmbeddedDataType.sint128.is_integer())
        self.assertTrue(EmbeddedDataType.sint256.is_integer())

        self.assertTrue(EmbeddedDataType.uint8.is_integer())
        self.assertTrue(EmbeddedDataType.uint16.is_integer())
        self.assertTrue(EmbeddedDataType.uint32.is_integer())
        self.assertTrue(EmbeddedDataType.uint64.is_integer())
        self.assertTrue(EmbeddedDataType.uint128.is_integer())
        self.assertTrue(EmbeddedDataType.uint256.is_integer())

        self.assertFalse(EmbeddedDataType.float8.is_integer())
        self.assertFalse(EmbeddedDataType.float16.is_integer())
        self.assertFalse(EmbeddedDataType.float32.is_integer())
        self.assertFalse(EmbeddedDataType.float64.is_integer())
        self.assertFalse(EmbeddedDataType.float128.is_integer())
        self.assertFalse(EmbeddedDataType.float256.is_integer())

        self.assertFalse(EmbeddedDataType.cfloat8.is_integer())
        self.assertFalse(EmbeddedDataType.cfloat16.is_integer())
        self.assertFalse(EmbeddedDataType.cfloat32.is_integer())
        self.assertFalse(EmbeddedDataType.cfloat64.is_integer())
        self.assertFalse(EmbeddedDataType.cfloat128.is_integer())
        self.assertFalse(EmbeddedDataType.cfloat256.is_integer())

        self.assertFalse(EmbeddedDataType.bool8.is_integer())

    def test_is_float(self):
        self.assertFalse(EmbeddedDataType.sint8.is_float())
        self.assertFalse(EmbeddedDataType.sint16.is_float())
        self.assertFalse(EmbeddedDataType.sint32.is_float())
        self.assertFalse(EmbeddedDataType.sint64.is_float())
        self.assertFalse(EmbeddedDataType.sint128.is_float())
        self.assertFalse(EmbeddedDataType.sint256.is_float())

        self.assertFalse(EmbeddedDataType.uint8.is_float())
        self.assertFalse(EmbeddedDataType.uint16.is_float())
        self.assertFalse(EmbeddedDataType.uint32.is_float())
        self.assertFalse(EmbeddedDataType.uint64.is_float())
        self.assertFalse(EmbeddedDataType.uint128.is_float())
        self.assertFalse(EmbeddedDataType.uint256.is_float())

        self.assertTrue(EmbeddedDataType.float8.is_float())
        self.assertTrue(EmbeddedDataType.float16.is_float())
        self.assertTrue(EmbeddedDataType.float32.is_float())
        self.assertTrue(EmbeddedDataType.float64.is_float())
        self.assertTrue(EmbeddedDataType.float128.is_float())
        self.assertTrue(EmbeddedDataType.float256.is_float())

        self.assertTrue(EmbeddedDataType.cfloat8.is_float())
        self.assertTrue(EmbeddedDataType.cfloat16.is_float())
        self.assertTrue(EmbeddedDataType.cfloat32.is_float())
        self.assertTrue(EmbeddedDataType.cfloat64.is_float())
        self.assertTrue(EmbeddedDataType.cfloat128.is_float())
        self.assertTrue(EmbeddedDataType.cfloat256.is_float())

        self.assertFalse(EmbeddedDataType.bool8.is_float())


class TestCodecs(ScrutinyUnitTest):
    def test_make_valid_sint(self):
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint8, 128), 127)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint8, -129), -128)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint8, -50), -50)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint8, 50), 50)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint8, -50, bitsize=5), -16)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint8, 50, bitsize=5), 15)

        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint16, 0x8000), 0x7FFF)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint16, -0x8001), -0x8000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint16, -1000), -1000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint16, 2000), 2000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint16, -1000, bitsize=5), -16)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint16, 2000, bitsize=5), 15)

        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint32, 0x80000000), 0x7fffffff)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint32, -0x80000001), -0x80000000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint32, -1000000), -1000000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint32, 2000000), 2000000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint32, -1000000, bitsize=5), -16)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint32, 2000000, bitsize=5), 15)

        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint64, 0x8000000000000000), 0x7fffffffffffffff)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint64, -0x8000000000000001), -0x8000000000000000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint64, -0x123456789), -0x123456789)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.sint64, 0x234567892), 0x234567892)

        for dtype in [EmbeddedDataType.sint8, EmbeddedDataType.sint16, EmbeddedDataType.sint32, EmbeddedDataType.sint64]:
            with self.assertRaises(ValueError):
                Codecs.make_value_valid(dtype, math.nan)
            with self.assertRaises(ValueError):
                Codecs.make_value_valid(dtype, math.inf)
            with self.assertRaises(ValueError):
                Codecs.make_value_valid(dtype, -math.inf)

    def test_make_valid_uint(self):
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint8, 0x100), 0xFF)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint8, -1), 0)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint8, 50), 50)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint8, 50, bitsize=5), 31)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint8, -5, bitsize=5), 0)

        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint16, 0x10000), 0xFFFF)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint16, -1), 0)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint16, 2000), 2000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint16, 2000, bitsize=5), 31)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint16, -500, bitsize=5), 0)

        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint32, 0x100000000), 0xffffffff)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint32, -1), 0)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint32, 2000000), 2000000)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint32, 2000000, bitsize=5), 31)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint32, -500000, bitsize=5), 0)

        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint64, 0x10000000000000000), 0xffffffffffffffff)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint64, -0x10000000000000000), 0)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint64, -1), 0)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint64, 0x234567892), 0x234567892)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint64, 2000000, bitsize=5), 31)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.uint64, -500000, bitsize=5), 0)

        for dtype in [EmbeddedDataType.uint8, EmbeddedDataType.uint16, EmbeddedDataType.uint32, EmbeddedDataType.uint64]:
            with self.assertRaises(ValueError):
                Codecs.make_value_valid(dtype, math.nan)
            with self.assertRaises(ValueError):
                Codecs.make_value_valid(dtype, math.inf)
            with self.assertRaises(ValueError):
                Codecs.make_value_valid(dtype, -math.inf)

    def test_int_codecs_encode_decode(self):
        # Covers both the struct based codecs and the 128 bits codecs, in both endianness
        all_types = [
            EmbeddedDataType.sint8, EmbeddedDataType.sint16, EmbeddedDataType.sint32, EmbeddedDataType.sint64, EmbeddedDataType.sint128,
            EmbeddedDataType.uint8, EmbeddedDataType.uint16, EmbeddedDataType.uint32, EmbeddedDataType.uint64, EmbeddedDataType.uint128,
        ]
        for dtype in all_types:
            size = dtype.get_size_8bits()
            signed = dtype.is_signed()
            if signed:
                values = [0, 1, -1, (1 << (size * 8 - 1)) - 1, -(1 << (size * 8 - 1))]
            else:
                values = [0, 1, (1 << (size * 8)) - 1, 0x0102030405060708090A0B0C0D0E0F10 & ((1 << (size * 8)) - 1)]
            for endianness in (Endianness.Little, Endianness.Big):
                byteorder = 'little' if endianness == Endianness.Little else 'big'
                codec = Codecs.get(dtype, endianness)
                for value in values:
                    with self.subTest(dtype=dtype.name, endianness=endianness.name, value=value):
                        expected = value.to_bytes(size, byteorder, signed=signed)
                        self.assertEqual(codec.encode(value), expected)
                        self.assertEqual(codec.decode(expected), value)
                        self.assertEqual(codec.decode(bytearray(expected)), value)

    def test_int128_codecs_types(self):
        self.assertIsInstance(Codecs.get(EmbeddedDataType.uint128, Endianness.Little), UInt128Codec)
        self.assertIsInstance(Codecs.get(EmbeddedDataType.uint128, Endianness.Little), UIntCodec)
        self.assertIsInstance(Codecs.get(EmbeddedDataType.sint128, Endianness.Big), SInt128Codec)
        self.assertIsInstance(Codecs.get(EmbeddedDataType.sint128, Endianness.Big), SIntCodec)

        with self.assertRaises(NotImplementedError):
            UInt128Codec(8, Endianness.Little)
        with self.assertRaises(NotImplementedError):
            SInt128Codec(8, Endianness.Little)
        with self.assertRaises(NotImplementedError):
            UIntCodec(16, Endianness.Little)

    def test_codecs_get_cached(self):
        # Every supported type returns the same instance on each call, and a distinct one per endianness
        for dtype in EmbeddedDataType:
            try:
                Codecs._create(dtype, Endianness.Little)
            except NotImplementedError:
                with self.assertRaises(NotImplementedError):
                    Codecs.get(dtype, Endianness.Little)
                with self.assertRaises(NotImplementedError):
                    Codecs.get(dtype, Endianness.Big)
                continue

            with self.subTest(dtype=dtype.name):
                little = Codecs.get(dtype, Endianness.Little)
                big = Codecs.get(dtype, Endianness.Big)
                self.assertIs(little, Codecs.get(dtype, Endianness.Little))
                self.assertIs(big, Codecs.get(dtype, Endianness.Big))
                self.assertIsNot(little, big)
                self.assertIs(type(little), type(Codecs._create(dtype, Endianness.Little)))

        self.assertEqual(Codecs.get(EmbeddedDataType.uint32, Endianness.Little).encode(0x12345678), b'\x78\x56\x34\x12')
        self.assertEqual(Codecs.get(EmbeddedDataType.uint32, Endianness.Big).encode(0x12345678), b'\x12\x34\x56\x78')

    def test_int_codecs_out_of_range(self):
        with self.assertRaises(struct.error):
            Codecs.get(EmbeddedDataType.uint8, Endianness.Little).encode(256)
        with self.assertRaises(OverflowError):
            Codecs.get(EmbeddedDataType.uint128, Endianness.Little).encode(1 << 128)
        with self.assertRaises(OverflowError):
            Codecs.get(EmbeddedDataType.uint128, Endianness.Little).encode(-1)
        with self.assertRaises(OverflowError):
            Codecs.get(EmbeddedDataType.sint128, Endianness.Little).encode(1 << 127)

    def test_make_valid_bool(self):
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.bool8, 1), True)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.bool8, 0), False)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.bool8, 0.0), False)
        self.assertEqual(Codecs.make_value_valid(EmbeddedDataType.bool8, 10000000000), True)

        with self.assertRaises(ValueError):
            Codecs.make_value_valid(EmbeddedDataType.bool8, math.nan)
        with self.assertRaises(ValueError):
            Codecs.make_value_valid(EmbeddedDataType.bool8, math.inf)
        with self.assertRaises(ValueError):
            Codecs.make_value_valid(EmbeddedDataType.bool8, -math.inf)


if __name__ == '__main__':
    import unittest
    unittest.main()
