#    math_expr.py
#        A math expression parser based of https://github.com/louisfisch/mathematical-expression-parser
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['ParsingError', 'parse_math_expr']

import math
import string
from scrutiny.tools.typing import *

_CONSTANTS: Dict[str, float] = {
    'pi': math.pi
}


def _round(val: float, digit: Optional[float] = None) -> float:
    if digit is None:
        return round(val)

    digit_int = int(digit)
    decimal_part = abs(float(digit_int) - digit)
    if decimal_part > 1e-10:
        raise ValueError("digit must be an integer")
    return round(val, digit_int)


_FUNCTIONS: Dict[str, Callable[..., float]] = {
    'abs': math.fabs,
    'exp': math.exp,
    'pow': math.pow,
    'sqrt': math.sqrt,
    'mod': math.fmod,
    'ceil': math.ceil,
    'floor': math.floor,
    'round': _round,
    'log': math.log,
    'ln': lambda x: math.log(x, math.e),
    'log10': math.log10,
    'hypot': math.hypot,
    'degrees': math.degrees,
    'radians': math.radians,
    'cos': math.cos,
    'cosh': math.cosh,
    'acos': math.acos,
    'sin': math.sin,
    'sinh': math.sinh,
    'asin': math.asin,
    'tan': math.tan,
    'tanh': math.tanh,
    'atan': math.atan,
    'atan2': math.atan2,
}


def parse_math_expr(expr: str) -> float:
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
            if self._peek() not in string.whitespace:
                return
            self._index += 1

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
        last = len(values) - 1
        v = math.pow(values[last - 1], values[last])
        last -= 1
        while last > 0:
            v = math.pow(values[last - 1], v)
            last -= 1

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
            return -1 * self._parse_power()
        else:
            return self._parse_val()

    def _parse_val(self) -> float:
        self._skip_whitespace()
        char = self._peek()

        if char in '0123456789.':   # hex and bin val must start with 0, so this is fine
            return self._parse_literal()
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

    def _parse_literal(self) -> float:
        self._skip_whitespace()
        str_val = ''
        decimal_found = False
        exponent_str = ""
        exponent_found = False
        exponent_sign_found = False
        char = ''
        exponent = float(0)

        if self._pop_if_next("0b"):
            allowed_charset = "01"
            base = 2
        elif self._pop_if_next("0x"):
            allowed_charset = "0123456789abcdef"
            base = 16
        else:
            allowed_charset = "0123456789"
            base = 10

        while self._has_next():
            char = self._peek().lower()

            if char == '.':
                if decimal_found or base != 10 or exponent_found:
                    raise ParsingError(f"Unexpected '{char}' at {self._index}")
                decimal_found = True
                str_val += char
            elif char == 'e' and base == 10:
                if exponent_found:
                    raise ParsingError(f"Unexpected '{char}' at {self._index}")
                exponent_found = True

            elif char in allowed_charset or (char in "+-" and exponent_found and not exponent_sign_found):
                if exponent_found:
                    exponent_sign_found = True
                    exponent_str += char
                else:
                    str_val += char
            else:
                break
            self._index += 1

        if len(str_val) == 0:
            if char == '':
                raise ParsingError("Unexpected end found")
            else:
                raise ParsingError(f"Unexpected '{char}' at {self._index}")

        if exponent_found:
            if exponent_str == '':
                if char == '':
                    raise ParsingError("Unexpected end found")
            try:
                exponent = float(exponent_str)
            except ValueError:
                raise ParsingError(f"Unexpected '{char}' at {self._index}")

        try:
            if base == 10:
                return float(str_val) * (10**exponent)
            else:
                return float(int(str_val, base=base))
        except Exception as e:
            raise ParsingError(f"Error while parsing literal before {self._index}. Underlying error: {e}")
