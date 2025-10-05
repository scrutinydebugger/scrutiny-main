#    test_math_expr.py
#        Test suite for the math parser
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from test import ScrutinyUnitTest
from scrutiny.core.math_expr import parse_math_expr, ParsingError
import math


class TestMathExpr(ScrutinyUnitTest):
    def test_arithmetic(self):
        self.assertEqual(parse_math_expr("1+1"), 2)
        self.assertEqual(parse_math_expr("1+(1+1)"), 3)
        self.assertEqual(parse_math_expr("1+2*3"), 7)
        self.assertEqual(parse_math_expr("2+2"), 4)
        self.assertEqual(parse_math_expr("5-3"), 2)
        self.assertEqual(parse_math_expr("4*3"), 12)
        self.assertEqual(parse_math_expr("10/2"), 5)
        self.assertEqual(parse_math_expr("2+3*4"), 14)
        self.assertEqual(parse_math_expr("(2+3)*4"), 20)
        self.assertEqual(parse_math_expr("((1+2)*3)+(4-1)/2"), 10.5)
        self.assertEqual(parse_math_expr("3.5+2.1"), 5.6)
        self.assertEqual(parse_math_expr("-2"), -2)
        self.assertEqual(parse_math_expr("3.2221"), 3.2221)
        self.assertEqual(parse_math_expr("2      + 3"), 5)
        self.assertEqual(parse_math_expr("2^3"), 8)
        self.assertEqual(parse_math_expr("-2^3"), -8)
        self.assertEqual(parse_math_expr("(-2)^2"), 4)
        self.assertEqual(parse_math_expr("(-2)^3"), -8)
        self.assertEqual(parse_math_expr("(-2)^4"), 16)
        self.assertEqual(parse_math_expr("-2^2"), -4)
        self.assertEqual(parse_math_expr("-2^3"), -8)
        self.assertEqual(parse_math_expr("-2^4"), -16)
        self.assertEqual(parse_math_expr("2^3^4"), 2**3**4)
        self.assertEqual(parse_math_expr("5+2^(3+4)*2.5"), 5 + 2**(3 + 4) * 2.5)
        self.assertEqual(parse_math_expr(".5"), 0.5)

        self.assertEqual(parse_math_expr("--2"), 2)
        self.assertEqual(parse_math_expr("---2"), -2)

        self.assertEqual(parse_math_expr("2 + 3"), 5)
        self.assertEqual(parse_math_expr("10 + 20"), 30)
        self.assertEqual(parse_math_expr("0 + 0"), 0)
        self.assertEqual(parse_math_expr("-5 + 3"), -2)
        self.assertEqual(parse_math_expr("10 - 3"), 7)
        self.assertEqual(parse_math_expr("5 - 8"), -3)
        self.assertEqual(parse_math_expr("0 - 5"), -5)
        self.assertEqual(parse_math_expr("-3 - 2"), -5)
        self.assertEqual(parse_math_expr("4 * 3"), 12)
        self.assertEqual(parse_math_expr("7 * 0"), 0)
        self.assertEqual(parse_math_expr("-2 * 5"), -10)
        self.assertEqual(parse_math_expr("-3 * -4"), 12)
        self.assertEqual(parse_math_expr("15 / 3"), 5.0)
        self.assertEqual(parse_math_expr("10 / 4"), 2.5)
        self.assertEqual(parse_math_expr("-8 / 2"), -4.0)
        self.assertEqual(parse_math_expr("7 / -2"), -3.5)

        self.assertEqual(parse_math_expr("2 + 3 * 4 - 5 / 2.5"), 12.0)
        self.assertEqual(parse_math_expr("(2 + 3) * (4 - 1) + 10"), 25)
        self.assertEqual(parse_math_expr("((2 + 3) * 4 - 5) / (3 + 2)"), 3.0)
        self.assertEqual(parse_math_expr("-2 * (3 + 4) - (5 - 8)"), -11)
        self.assertEqual(parse_math_expr("1 + 2 * 3 + 4 * 5 + 6"), 33)
        self.assertEqual(parse_math_expr("(1 + 2) * (3 + 4) * (5 - 3)"), 42)

        self.assertEqual(parse_math_expr("-12.5e-1*2.1e2/(1.1E1^2+0x123)"), -12.5e-1 * 2.1e2 / (1.1E1**2 + 0x123))

    def test_parentheses(self):
        self.assertEqual(parse_math_expr("(2 + 3)"), 5)
        self.assertEqual(parse_math_expr("(10 - 4)"), 6)
        self.assertEqual(parse_math_expr("(3 * 4)"), 12)
        self.assertEqual(parse_math_expr("(8 / 2)"), 4.0)
        self.assertEqual(parse_math_expr("(2 + 3) * 4"), 20)
        self.assertEqual(parse_math_expr("2 * (3 + 4)"), 14)
        self.assertEqual(parse_math_expr("(10 - 2) / 2"), 4.0)
        self.assertEqual(parse_math_expr("((2 + 3) * 4)"), 20)
        self.assertEqual(parse_math_expr("(2 * (3 + 4))"), 14)
        self.assertEqual(parse_math_expr("((5 - 2) * (4 + 1))"), 15)
        self.assertEqual(parse_math_expr("(((2 + 1) * 3) - 2)"), 7)
        self.assertEqual(parse_math_expr("(2 + 3) + (4 * 5)"), 25)
        self.assertEqual(parse_math_expr("(10 / 2) - (3 + 1)"), 1.0)
        self.assertEqual(parse_math_expr("(2 * 3) * (4 + 1)"), 30)

    def test_order_of_operations(self):
        self.assertEqual(parse_math_expr("2 + 3 * 4"), 14)
        self.assertEqual(parse_math_expr("3 * 4 + 2"), 14)
        self.assertEqual(parse_math_expr("10 - 6 / 2"), 7.0)
        self.assertEqual(parse_math_expr("6 / 2 - 1"), 2.0)
        self.assertEqual(parse_math_expr("2 + 3 * 4 - 1"), 13)
        self.assertEqual(parse_math_expr("20 / 4 + 2 * 3"), 11.0)
        self.assertEqual(parse_math_expr("2 * 3 + 4 * 5"), 26)
        self.assertEqual(parse_math_expr("10 / 2 * 3"), 15.0)
        self.assertEqual(parse_math_expr("8 - 3 + 2"), 7)

    def test_math_func(self):
        self.assertEqual(parse_math_expr("sin(0)"), math.sin(0))
        self.assertEqual(parse_math_expr("sin ( 0 )"), math.sin(0))
        self.assertEqual(parse_math_expr("sIn ( 0 )"), math.sin(0))
        self.assertEqual(parse_math_expr("sin(pi)"), math.sin(math.pi))
        self.assertEqual(parse_math_expr("sin(pi/4*2)"), math.sin(math.pi / 4 * 2))
        self.assertEqual(parse_math_expr("abs(sin(3*pi/2))"), abs(math.sin(3 * math.pi / 2)))
        self.assertEqual(parse_math_expr("atan2(2,3)"), math.atan2(2, 3))
        self.assertEqual(parse_math_expr("mod(10,3)"), 1)
        self.assertEqual(parse_math_expr("2*mod(10,3)"), 2)

        self.assertEqual(parse_math_expr("-(abs(sin(3*pi/2))+1)"), -(abs(math.sin(3 * math.pi / 2)) + 1))

        self.assertEqual(parse_math_expr('abs(-2)'), 2)
        self.assertEqual(parse_math_expr('exp(2)'), math.exp(2))
        self.assertEqual(parse_math_expr('pow(2,5)'), 32)
        self.assertEqual(parse_math_expr('sqrt(100)'), 10)
        self.assertEqual(parse_math_expr('mod(10,3)'), 1)
        self.assertEqual(parse_math_expr('ceil(1.2)'), 2)
        self.assertEqual(parse_math_expr('floor(2.8)'), 2)
        self.assertEqual(parse_math_expr('round(1.4)'), 1)
        self.assertEqual(parse_math_expr('round(1.6)'), 2)
        self.assertEqual(parse_math_expr('round(1.234, 2)'), 1.23)
        self.assertEqual(parse_math_expr("ln(10)"), math.log(10, math.e))
        self.assertEqual(parse_math_expr("log(128, 2)"), 7)
        self.assertEqual(parse_math_expr('log10(1000)'), 3)
        self.assertEqual(parse_math_expr('hypot(3,4)'), 5)
        self.assertEqual(parse_math_expr('degrees(pi/2)'), 90)
        self.assertEqual(parse_math_expr('radians(-90)'), -math.pi / 2)
        self.assertEqual(parse_math_expr('cos(0.2)'), math.cos(0.2))
        self.assertEqual(parse_math_expr('cosh(0.2)'), math.cosh(0.2))
        self.assertEqual(parse_math_expr('acos(0.2)'), math.acos(0.2))
        self.assertEqual(parse_math_expr('sin(0.2)'), math.sin(0.2))
        self.assertEqual(parse_math_expr('sinh(0.2)'), math.sinh(0.2))
        self.assertEqual(parse_math_expr('asin(0.2)'), math.asin(0.2))
        self.assertEqual(parse_math_expr('tan(0.2)'), math.tan(0.2))
        self.assertEqual(parse_math_expr('tanh(0.2)'), math.tanh(0.2))
        self.assertEqual(parse_math_expr('atan(0.2)'), math.atan(0.2))
        self.assertEqual(parse_math_expr('atan2(10,5)'), math.atan2(10, 5))

    def test_negative_numbers(self):
        self.assertEqual(parse_math_expr("-5"), -5)
        self.assertEqual(parse_math_expr("-2.5"), -2.5)
        self.assertEqual(parse_math_expr("-5 + 3"), -2)
        self.assertEqual(parse_math_expr("2 + -3"), -1)
        self.assertEqual(parse_math_expr("-4 * -2"), 8)
        self.assertEqual(parse_math_expr("-10 / 2"), -5.0)
        self.assertEqual(parse_math_expr("(-5)"), -5)
        self.assertEqual(parse_math_expr("(-2 + 3)"), 1)
        self.assertEqual(parse_math_expr("-(2 + 3)"), -5)
        self.assertEqual(parse_math_expr("2 * (-3 + 1)"), -4)

    def test_whitespace_handling(self):
        self.assertEqual(parse_math_expr("2+3"), 5)
        self.assertEqual(parse_math_expr("10-5"), 5)
        self.assertEqual(parse_math_expr("4*3"), 12)
        self.assertEqual(parse_math_expr("8/2"), 4.0)
        self.assertEqual(parse_math_expr("  2 + 3  "), 5)
        self.assertEqual(parse_math_expr("2   +   3"), 5)
        self.assertEqual(parse_math_expr("( 2 + 3 ) * 4"), 20)
        self.assertEqual(parse_math_expr("2\t+\t3"), 5)
        self.assertEqual(parse_math_expr("2 \t+\n \t3"), 5)

    def test_single_numbers(self):
        self.assertEqual(parse_math_expr("0"), 0)
        self.assertEqual(parse_math_expr("42"), 42)
        self.assertEqual(parse_math_expr("-17"), -17)
        self.assertEqual(parse_math_expr("3.14159"), 3.14159)
        self.assertEqual(parse_math_expr("-2.5"), -2.5)
        self.assertEqual(parse_math_expr("(5)"), 5)
        self.assertEqual(parse_math_expr("(-8)"), -8)
        self.assertEqual(parse_math_expr("1e5"), 100000)
        self.assertEqual(parse_math_expr("1e+5"), 100000)
        self.assertEqual(parse_math_expr("1e-2"), 0.01)
        self.assertEqual(parse_math_expr("-1e-2"), -0.01)
        self.assertEqual(parse_math_expr("(-1e-2)"), -0.01)
        self.assertEqual(parse_math_expr("-(-1E-2)"), 0.01)
        self.assertEqual(parse_math_expr("-(-1.2E+2)"), 120)

    def test_hex_numbers(self):
        self.assertEqual(parse_math_expr("0x123"), 0x123)
        self.assertEqual(parse_math_expr("-0xAAA"), -0xAAA)
        self.assertEqual(parse_math_expr("0xaBcDeF"), 0xabcdef)
        self.assertEqual(parse_math_expr("(0x12 + 5)"), 0x17)
        self.assertEqual(parse_math_expr("0x123e+5"), 0x123e + 5)

    def test_bin_numbers(self):
        self.assertEqual(parse_math_expr("0b101"), 5)
        self.assertEqual(parse_math_expr("-0b101"), -5)
        self.assertEqual(parse_math_expr("-0b101 * 0b111"), -35)
        self.assertEqual(parse_math_expr("0b100000001010100001101000010010001001"), 0b100000001010100001101000010010001001)

    def test_malformed_expr(self):
        expressions = [
            '1.2.3',
            '2**3',
            '1++1',
            '1+',
            '1+(2',
            '1+(2-',
            '',
            '..5',
            '2*asd(2)',
            'x+2'
            "1 / 0",
            "5 / (2 - 2)",
            "2 +",
            "+ 3",
            "2 + + 3",
            "2 3",
            "2 * * 3",
            "(2 + 3",
            "2 + 3)",
            "((2 + 3)",
            "(2 + 3))",
            "2 + a",
            "2 & 3",
            "2 + 3!",
            "()",
            "2 + ()",
            "2 ++ 3",
            "2 */ 3",
            "0x123.2",
            "0b12",
            "0b100101.1",
            "1e1e",
            "1e-1.0",
            "0b101010100e1010",
            "12e++2",
            "12e+-2",
            "12e--2",
            "12e",
        ]

        for expr in expressions:
            with self.subTest(msg=f'expr:{expr}'):
                with self.assertRaises(ParsingError, ):
                    parse_math_expr(expr)
