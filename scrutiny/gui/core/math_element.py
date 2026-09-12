#    math_element.py
#        A stateful math element that can have variables and be reevaluated at will
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from scrutiny.tools.typing import *
from dataclasses import dataclass
from scrutiny.core.math_expr import MathParser, MathParsingError
from scrutiny.tools import validation
import re

VAR_NAME_REGEX = re.compile(r'^\$[\w\d]+$')
ValueType: TypeAlias = Optional[Union[float, int, bool]]


@dataclass(slots=True)
class MathElement:

    @dataclass(slots=True)
    class VarData:
        fqn: Optional[str]
        val: ValueType

    _name: str
    _expr: str
    _var_defs: Dict[str, VarData]
    _committed_vals: Dict[str, ValueType]
    _val: ValueType
    _error: Optional[str]
    _invalid_expr: bool

    def __init__(self, name: str, expr: str) -> None:
        self._name = name
        self._expr = expr
        self._var_defs = {}
        self._committed_vals = {}
        self._val = None
        self._error = None
        self._invalid_expr = False

        try:
            parser = MathParser(self._expr, mode=MathParser.Mode.Parse)
            vars = parser.get_vars()
            for var in vars:
                if not VAR_NAME_REGEX.match(var):
                    raise ValueError(f"Variable name is invalid \"{name}\"")
                self._var_defs[var] = self.VarData(fqn=None, val=0)

        except MathParsingError as e:
            self._invalid_expr = True
            self._error = f"Parsing error : {e}"
        except Exception as e:
            self._invalid_expr = True
            self._error = str(e)

    def _commit_vals(self) -> None:
        self._committed_vals = {name: data.val for name, data in self._var_defs.items()}

    def is_valid(self) -> bool:
        return not self._invalid_expr

    def bind_watchable(self, name: str, fqn: str) -> None:
        validation.assert_type(name, 'name', str)
        if name not in self._var_defs:
            raise ValueError(f"No variable with name {name} in expression {self._expr}")

        self._var_defs[name].fqn = fqn
        self._commit_vals()

    def assign_var_value(self, name: str, val: ValueType, commit: bool = True) -> None:
        try:
            self._var_defs[name].val = val
            if commit:
                self._commit_vals()
        except KeyError:
            raise ValueError(f"Math element {self._name} has no variable named {name}")

    def assign_var_value_by_fqn(self, fqn: str, val: ValueType) -> None:
        found = False
        for name, data in self._var_defs.items():
            if data.fqn == fqn:
                self.assign_var_value(name, val, commit=False)
                found = True
        if not found:
            raise ValueError(f"No variable is bound to watchable with FQN : {fqn}")
        self._commit_vals()

    def eval(self) -> Optional[float]:
        try:
            self._val = MathParser(self._expr, MathParser.Mode.Eval, self._committed_vals).get_val()
            self._error = None
        except Exception as e:
            self._val = None
            self._error = str(e)

        return self._val

    def get_vars(self) -> Set[str]:
        return set(self._var_defs.keys())

    def get_val(self) -> ValueType:
        return self._val

    def get_error(self) -> Optional[str]:
        return self._error
