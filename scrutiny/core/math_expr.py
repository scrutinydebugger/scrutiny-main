#    math_expr.py
#        A math expression parser based of https://github.com/louisfisch/mathematical-expression-parser
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['ParsingError', 'parse_expr']

import math
from scrutiny.tools.typing import *

_CONSTANTS: Dict[str, float] = {
    'pi': math.pi,
    'e': math.e
}

_FUNCTIONS: Dict[str, Callable[..., float]] = {
    'abs': lambda x: abs(float(x)),
    'acos': math.acos,
    'asin': math.asin,
    'atan': math.atan,
    'atan2': math.atan2,
    'ceil': math.ceil,
    'cos': math.cos,
    'cosh': math.cosh,
    'degrees': math.degrees,
    'exp': math.exp,
    'fabs': math.fabs,
    'floor': math.floor,
    'fmod': math.fmod,
    'hypot': math.hypot,
    'log': math.log,
    'log10': math.log10,
    'pow': math.pow,
    'radians': math.radians,
    'sin': math.sin,
    'sinh': math.sinh,
    'sqrt': math.sqrt,
    'tan': math.tan,
    'tanh': math.tanh
}


def parse_expr(expr: str) -> float:
    return _Parser(expr).get_val()


class ParsingError(Exception):
    pass


class _Parser:

    _expr: str
    _index: int
    _vars: Dict[str, Any]

    def __init__(self, expr: str, vars: Optional[Dict[str, Any]] = None) -> None:
        self._expr = expr
        self._index = 0
        self._vars = {} if vars == None else vars.copy()
        for constant in _CONSTANTS.keys():
            if self._vars.get(constant) != None:
                raise ParsingError(f"Cannot redefine the value of {constant}")

    def get_val(self) -> float:
        value = self._parse_expr()
        self._skip_whitespace()

        if self._has_next():
            raise ParsingError(f"Unexpected character found: '{self._peek()}' at index {self._index}")
        return value

    def _peek(self) -> str:
        return self._expr[self._index:self._index + 1]

    def _has_next(self) -> bool:
        return self._index < len(self._expr)

    def _is_next(self, value: str) -> bool:
        return self._expr[self._index:self._index + len(value)] == value

    def _pop_if_next(self, value: str) -> bool:
        if self._is_next(value):
            self._index += len(value)
            return True
        return False

    def _pop_expected(self, value: str) -> None:
        if not self._pop_if_next(value):
            raise ParsingError(f"Expected {value} at index {self._index}")

    def _skip_whitespace(self) -> None:
        while self._has_next():
            if self._peek() in ' \t\n\r':
                self._index += 1
            else:
                return

    def _parse_expr(self) -> float:
        return self._parse_add()

    def _parse_add(self) -> float:
        values = [self._parse_mul()]

        while True:
            self._skip_whitespace()
            char = self._peek()

            if char == '+':
                self._index += 1
                values.append(self._parse_mul())
            elif char == '-':
                self._index += 1
                values.append(-1 * self._parse_mul())
            else:
                break

        return sum(values)

    def _parse_mul(self) -> float:
        values = [self._parse_power()]

        while True:
            self._skip_whitespace()
            char = self._peek()

            if char == '*':
                self._index += 1
                values.append(self._parse_power())
            elif char == '/':
                div_index = self._index
                self._index += 1
                denominator = self._parse_power()

                if denominator == 0:
                    raise ParsingError(f"Division by 0 (occurred at index {div_index})")
                values.append(1.0 / denominator)
            else:
                break

        value = 1.0

        for factor in values:
            value *= factor
        return value

    def _parse_power(self) -> float:
        values = [self._parse_parenthesis()]

        while True:
            self._skip_whitespace()
            char = self._peek()

            if char == '^':
                self._index += 1
                values.append(self._parse_power())
            else:
                break

        values.append(1)
        assert len(values) >= 2
        pos = len(values) - 1
        v = math.pow(values[pos - 1], values[pos])
        pos -= 1
        while pos > 0:
            v = math.pow(values[pos - 1], v)
            pos -= 1

        return v

    def _parse_parenthesis(self) -> float:
        self._skip_whitespace()
        char = self._peek()

        if char == '(':
            self._index += 1
            value = self._parse_expr()
            self._skip_whitespace()

            if self._peek() != ')':
                raise ParsingError(f"No closing parenthesis found at character {self._index}")
            self._index += 1
            return value
        else:
            return self._parse_neg()

    def _parse_arg(self) -> List[float]:
        args: List[float] = []
        self._skip_whitespace()
        self._pop_expected('(')
        while not self._pop_if_next(')'):
            self._skip_whitespace()
            if len(args) > 0:
                self._pop_expected(',')
                self._skip_whitespace()
            args.append(self._parse_expr())
            self._skip_whitespace()
        return args

    def _parse_neg(self) -> float:
        self._skip_whitespace()
        char = self._peek()

        if char == '-':
            self._index += 1
            return -1 * self._parse_parenthesis()
        else:
            return self._parse_val()

    def _parse_val(self) -> float:
        self._skip_whitespace()
        char = self._peek()

        if char in '0123456789.':
            return self._parse_constant()
        else:
            return self._parse_var()

    def _parse_var(self) -> float:
        self._skip_whitespace()
        var: List[str] = []
        while self._has_next():
            char = self._peek()

            if char.lower() in '_abcdefghijklmnopqrstuvwxyz0123456789':
                var.append(char)
                self._index += 1
            else:
                break
        var_str = ''.join(var)

        function = _FUNCTIONS.get(var_str.lower())
        if function != None:
            args = self._parse_arg()
            return float(function(*args))

        constant = _CONSTANTS.get(var_str.lower())
        if constant != None:
            return constant

        value = self._vars.get(var_str, None)
        if value != None:
            return float(value)

        raise ParsingError(f"Unrecognized variable: '{var_str}'")

    def _parse_constant(self) -> float:
        self._skip_whitespace()
        strValue = ''
        decimal_found = False
        char = ''

        while self._has_next():
            char = self._peek()

            if char == '.':
                if decimal_found:
                    raise ParsingError(f"Unexpected decimal separator at {self._index}")
                decimal_found = True
                strValue += '.'
            elif char in '0123456789':
                strValue += char
            else:
                break
            self._index += 1

        if len(strValue) == 0:
            if char == '':
                raise ParsingError("Unexpected end found")
            else:
                raise ParsingError(f"Unexpected token at index {self._index}")

        return float(strValue)
