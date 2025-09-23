#    test_math_expr.py
#        Test suite for the math parser
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

from test import ScrutinyUnitTest
from scrutiny.core.math_expr import parse_expr, ParsingError
import math


class TestMathExpr(ScrutinyUnitTest):
    def test_arithmetic(self):
        self.assertEqual(parse_expr("1+1"), 2)
        self.assertEqual(parse_expr("1+(1+1)"), 3)
        self.assertEqual(parse_expr("1+2*3"), 7)
        self.assertEqual(parse_expr("2+2"), 4)
        self.assertEqual(parse_expr("5-3"), 2)
        self.assertEqual(parse_expr("4*3"), 12)
        self.assertEqual(parse_expr("10/2"), 5)
        self.assertEqual(parse_expr("2+3*4"), 14)
        self.assertEqual(parse_expr("(2+3)*4"), 20)
        self.assertEqual(parse_expr("((1+2)*3)+(4-1)/2"), 10.5)
        self.assertEqual(parse_expr("3.5+2.1"), 5.6)
        self.assertEqual(parse_expr("-2"), -2)
        self.assertEqual(parse_expr("3.2221"), 3.2221)
        self.assertEqual(parse_expr("2      + 3"), 5)
        self.assertEqual(parse_expr("2^3"), 8)
        self.assertEqual(parse_expr("2^3^4"), 2**3**4)
        self.assertEqual(parse_expr("5+2^(3+4)*2.5"), 5 + 2**(3 + 4) * 2.5)
        self.assertEqual(parse_expr(".5"), 0.5)
        self.assertEqual(parse_expr("--2"), 2)
        self.assertEqual(parse_expr("---2"), -2)

    def test_math_func(self):
        self.assertEqual(parse_expr("sin(0)"), math.sin(0))
        self.assertEqual(parse_expr("sin ( 0 )"), math.sin(0))
        self.assertEqual(parse_expr("sIn ( 0 )"), math.sin(0))
        self.assertEqual(parse_expr("sin(pi)"), math.sin(math.pi))
        self.assertEqual(parse_expr("sin(pi/4*2)"), math.sin(math.pi / 4 * 2))
        self.assertEqual(parse_expr("abs(sin(3*pi/2))"), abs(math.sin(3 * math.pi / 2)))
        self.assertEqual(parse_expr("atan2(2,3)"), math.atan2(2,3))

        self.assertEqual(parse_expr("-(abs(sin(3*pi/2))+1)"), -(abs(math.sin(3 * math.pi / 2)) + 1))


    def test_malformed_expr(self):
        expressions=[
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
        ]

        for expr in expressions:
            with self.assertRaises(ParsingError, msg=f'expr:{expr}'):
                parse_expr(expr)
