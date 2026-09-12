#    math_expr.py
#        A math expression parser based of https://github.com/louisfisch/mathematical-expression-parser
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2025 Scrutiny Debugger

__all__ = ['MathParsingError', 'parse_math_expr', 'MathParser']

import functools
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

Fn: TypeAlias = Callable[[], float]


def parse_math_expr(expr: str) -> float:
    return MathParser(expr).eval()


class MathExprError(Exception):
    pass


class MathParsingError(MathExprError):
    pass


class MathEvalError(MathExprError):
    pass


class MathParser:

    _expr: str
    _index: int
    _vars: Dict[str, Any]
    _required_funcs: Set[str]
    _required_vars: Set[str]
    _eval_func: Optional[Callable[[], float]]

    def __init__(self, expr: str, vars: Optional[Dict[str, Any]] = None) -> None:
        self._expr = expr
        self._index = 0
        self._vars = {} if vars is None else vars.copy()
        self._required_funcs = set()
        self._required_vars = set()
        self._eval_func = self._parse_expr()
        self._skip_whitespace()

        if self._has_next():
            raise MathParsingError(f"Unexpected character found: '{self._peek()}' at index {self._index}")

    def get_vars(self) -> Set[str]:
        return self._required_vars

    def change_vars(self, vars: Optional[Dict[str, float]] = None) -> None:
        for constant in _CONSTANTS.keys():
            if self._vars.get(constant) != None:
                raise MathParsingError(f"Cannot redefine the value of {constant}")

    def eval(self, vars: Optional[Dict[str, float]] = None) -> float:
        if self._eval_func is None:
            raise MathEvalError("Parsing error")
        self._vars = vars.copy() if vars is not None else {}
        return self._eval_func()

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
            raise MathParsingError(f"Expected {value} at index {self._index}")

    def _skip_whitespace(self) -> None:
        while self._has_next():
            if self._peek() not in string.whitespace:
                return
            self._index += 1

    def _parse_expr(self) -> Fn:
        return self._parse_add()

    def _parse_add(self) -> Fn:
        ops = [self._parse_mul()]

        while True:
            self._skip_whitespace()
            char = self._peek()

            if char == '+':
                self._index += 1
                ops.append(self._parse_mul())
            elif char == '-':
                self._index += 1
                op = self._parse_mul()
                ops.append(functools.partial(self._eval_neg, op))
            else:
                break

        return lambda: sum([v() for v in ops])

    def _parse_mul(self) -> Fn:
        ops = [self._parse_power()]

        while True:
            self._skip_whitespace()
            char = self._peek()

            if char == '*':
                self._index += 1
                ops.append(self._parse_power())
            elif char == '/':
                self._index += 1
                den = self._parse_power()
                ops.append(functools.partial(self._eval_div, lambda: 1.0, den))
            else:
                break

        return lambda: self._eval_mul_list(ops)

    @staticmethod
    def _eval_neg(op: Fn) -> float:
        return -op()

    @staticmethod
    def _eval_mul_list(ops: Iterable[Fn]) -> float:
        acc = 1.0
        for op in ops:
            acc *= op()
        return acc

    @staticmethod
    def _eval_div(op1: Fn, op2: Fn) -> float:
        v2 = op2()
        if v2 == 0:
            raise MathEvalError("Division by 0")
        return op1() / v2

    def _parse_power(self) -> Fn:
        f1 = self._parse_parenthesis()
        self._skip_whitespace()
        char = self._peek()

        if char == '^':
            self._index += 1
            f2 = self._parse_power()
            return lambda: f1()**f2()

        return f1

    def _parse_parenthesis(self) -> Fn:
        self._skip_whitespace()
        char = self._peek()

        if char == '(':
            self._index += 1
            expr = self._parse_expr()
            self._skip_whitespace()

            if self._peek() != ')':
                raise MathParsingError(f"No closing parenthesis found at character {self._index}")
            self._index += 1
            return lambda: expr()
        else:
            return self._parse_neg()

    def _parse_arg(self) -> List[Fn]:
        args: List[Fn] = []
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

    def _parse_neg(self) -> Fn:
        self._skip_whitespace()
        char = self._peek()

        if char == '-':
            self._index += 1
            op = self._parse_power()
            return lambda: -1 * op()
        else:
            return self._parse_val()

    def _parse_val(self) -> Fn:
        self._skip_whitespace()
        char = self._peek()

        if char in '0123456789.':   # hex and bin val must start with 0, so this is fine
            return self._parse_literal()
        else:
            return self._parse_var()

    def _parse_var(self) -> Fn:
        self._skip_whitespace()
        var: List[str] = []
        while self._has_next():
            char = self._peek()

            if char in '_abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789$':
                var.append(char)
                self._index += 1
            else:
                break
        var_str = ''.join(var)
        var_str_lower = var_str.lower()
        function = _FUNCTIONS.get(var_str_lower)
        if function is not None:
            self._required_funcs.add(var_str_lower)
            args = self._parse_arg()
            return lambda: self._eval_math_func(function, args)

        constant = _CONSTANTS.get(var_str_lower)
        if constant is not None:
            return lambda: constant

        self._required_vars.add(var_str)
        return functools.partial(self._lookup_var, var_str)

    @staticmethod
    def _eval_math_func(f: Fn, args: Iterable[Fn]) -> float:
        return f(*[arg() for arg in args])

    def _lookup_var(self, name: str) -> float:
        v = self._vars.get(name, None)
        if v is None:
            raise MathParsingError(f"Unrecognized variable: '{name}'")
        return float(v)

    def _parse_literal(self) -> Fn:
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
                    raise MathParsingError(f"Unexpected '{char}' at {self._index}")
                decimal_found = True
                str_val += char
            elif char == 'e' and base == 10:
                if exponent_found:
                    raise MathParsingError(f"Unexpected '{char}' at {self._index}")
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
                raise MathParsingError("Unexpected end found")
            else:
                raise MathParsingError(f"Unexpected '{char}' at {self._index}")

        if exponent_found:
            if exponent_str == '':
                if char == '':
                    raise MathParsingError("Unexpected end found")
            try:
                exponent = float(exponent_str)
            except ValueError:
                raise MathParsingError(f"Unexpected '{char}' at {self._index}")

        try:
            if base == 10:
                v = float(str_val) * (10**exponent)
            else:
                v = float(int(str_val, base=base))
        except Exception as e:
            raise MathParsingError(f"Error while parsing literal before {self._index}. Underlying error: {e}")

        return lambda: v
