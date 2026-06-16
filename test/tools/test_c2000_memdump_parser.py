#    test_c2000_memdump_parser.py
#        A test suite to check the C2000 Memory Dump parser
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import tempfile
import os
import unittest
from contextlib import contextmanager
from typing import Generator

from scrutiny.tools.c2000_memdump_parser import C2000MemdumpParser, OutOfRange
from test import ScrutinyUnitTest


@contextmanager
def make_memdump(content: str) -> Generator[str, None, None]:
    """Context manager that writes content to a temporary file and yields its path."""
    fd, path = tempfile.mkstemp(suffix='.memdump')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content)
        yield path
    finally:
        os.unlink(path)


class TestC2000MemdumpParserRead(ScrutinyUnitTest):

    def test_read_single_word(self):
        # word 0xABCD at address 0x0010
        with make_memdump("@0010\nABCD\n") as path:
            parser = C2000MemdumpParser(path)
            result = parser.read_little_endian(0x0010, 1)

        self.assertEqual(len(result), 2)
        # little endian: low byte first → 0xCD, then high byte → 0xAB
        self.assertEqual(result, bytes([0xCD, 0xAB]))

    def test_little_endian_encoding(self):
        # Explicit verification of the user's example:
        # python [0xAB, 0xCD] should come from memdump word CDAB
        with make_memdump("@0000\nCDAB\n") as path:
            parser = C2000MemdumpParser(path)
            result = parser.read_little_endian(0x0000, 1)

        self.assertEqual(result, bytes([0xAB, 0xCD]))

    def test_read_multiple_words(self):
        # Three consecutive words at 0x0020
        with make_memdump("@0020\n1234 5678 9ABC\n") as path:
            parser = C2000MemdumpParser(path)
            result = parser.read_little_endian(0x0020, 3)

        # word 0x1234 → [0x34, 0x12]
        # word 0x5678 → [0x78, 0x56]
        # word 0x9ABC → [0xBC, 0x9A]
        self.assertEqual(result, bytes([0x34, 0x12, 0x78, 0x56, 0xBC, 0x9A]))

    def test_read_words_across_lines(self):
        # 16 words on the first line, then 2 more on the second
        line1 = ' '.join(['0001'] * 16)
        with make_memdump(f"@0000\n{line1}\nABCD 1234\n") as path:
            parser = C2000MemdumpParser(path)
            result = parser.read_little_endian(0x0010, 2)  # words at 0x10 and 0x11

        self.assertEqual(result, bytes([0xCD, 0xAB, 0x34, 0x12]))

    def test_multiple_regions(self):
        with make_memdump("@0010\nAAAA\n@0020\nBBBB\n") as path:
            parser = C2000MemdumpParser(path)
            r1 = parser.read_little_endian(0x0010, 1)
            r2 = parser.read_little_endian(0x0020, 1)

        self.assertEqual(r1, bytes([0xAA, 0xAA]))
        self.assertEqual(r2, bytes([0xBB, 0xBB]))

    def test_out_of_range_before_region(self):
        with make_memdump("@0010\nABCD\n") as path:
            parser = C2000MemdumpParser(path)
            with self.assertRaises(OutOfRange):
                parser.read_little_endian(0x000F, 1)

    def test_out_of_range_after_region(self):
        with make_memdump("@0010\nABCD\n") as path:
            parser = C2000MemdumpParser(path)
            with self.assertRaises(OutOfRange):
                parser.read_little_endian(0x0011, 1)

    def test_out_of_range_overrun(self):
        # Region has 2 words; reading 3 should raise on the third
        with make_memdump("@0010\n1111 2222\n") as path:
            parser = C2000MemdumpParser(path)
            with self.assertRaises(OutOfRange):
                parser.read_little_endian(0x0010, 3)

    def test_out_of_range_in_gap_between_regions(self):
        # Region 1: 0x0010. Region 2: 0x0012. Address 0x0011 is a gap.
        with make_memdump("@0010\nAAAA\n@0012\nBBBB\n") as path:
            parser = C2000MemdumpParser(path)
            with self.assertRaises(OutOfRange):
                parser.read_little_endian(0x0010, 2)  # spans 0x0010 and 0x0011 (gap)


if __name__ == '__main__':
    unittest.main()
