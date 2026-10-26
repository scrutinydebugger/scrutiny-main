#    gui_math_watchable.py
#        Represent a Math Watchable that can be carried across GUI components. Analogous to
#        Variables/Alaises/RPVs, but defined fully from the GUI side
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from scrutiny.tools.typing import *
from dataclasses import dataclass
from scrutiny.sdk import datalogging
from scrutiny.core.math_parser import MathParser, MathParsingError
from scrutiny.core.basic_types import MathWatchable as core_MathWatchable
from scrutiny.gui.core.fqn_name_pair import FqnNamePair, FqnNamePairDict
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.tools import validation
from scrutiny.core import path_tools
import re
import json
import hashlib
import re

ValueType: TypeAlias = Optional[Union[float, int, bool]]


class GUIMathWatchableDictDef(TypedDict):
    name: str
    expr: str
    variables: Dict[str, Optional[FqnNamePairDict]]


@dataclass(slots=True)
class GUIMathWatchable:

    @dataclass(slots=True)
    class VarData:
        fqn_name: Optional[FqnNamePair]
        val: ValueType

    _name: str
    _expr: str
    _var_defs: Dict[str, VarData]
    _committed_vals: Dict[str, float]
    _val: ValueType
    _eval_error: Optional[str]
    _parsing_error: Optional[str]
    _parser: Optional[MathParser]

    def __init__(self, name: str, expr: str) -> None:
        self._name = name
        self._expr = expr
        self._var_defs = {}
        self._committed_vals = {}
        self._val = None
        self._eval_error = None
        self._parsing_error = None

        try:
            self._parser = MathParser(self._expr)
            vars = self._parser.get_vars()
            for var in vars:
                self._var_defs[var] = self.VarData(fqn_name=None, val=None)

            self._commit_vals()
        except MathParsingError as e:
            self._parsing_error = f"Parsing error : {e}"
        except Exception as e:
            self._parsing_error = str(e)

    def _assert_valid(self) -> None:
        if self._parsing_error is not None:
            raise ValueError(f"Invalid expression : {self._parsing_error}")

    def _commit_vals(self) -> None:
        self._committed_vals = {name: float(data.val) for name, data in self._var_defs.items() if data.val is not None}

    def get_expr(self) -> str:
        return self._expr

    def get_name(self) -> str:
        return self._name

    def is_valid(self) -> bool:
        return self._parsing_error is None

    def is_fully_configured(self) -> bool:
        return self.is_valid() and all([data.fqn_name is not None for data in self._var_defs.values()])

    def is_evaluable(self) -> bool:
        return self.is_fully_configured() and (len(self._committed_vals) == len(self._var_defs))

    def bind_watchable(self, name: str, fqn_name: FqnNamePair) -> None:
        self._assert_valid()
        validation.assert_type(name, 'name', str)
        if name not in self._var_defs:
            raise ValueError(f"No variable with name {name} in expression {self._expr}")

        if FQN.parse(fqn_name.fqn).node_type == RegistryNodeType.Math:
            raise ValueError("Math watchables cannot be bound to other math watchables")

        self._var_defs[name].fqn_name = fqn_name
        self._commit_vals()

    def assign_var_value(self, name: str, val: ValueType, commit: bool = True) -> None:
        self._assert_valid()
        try:
            self._var_defs[name].val = val
            if commit:
                self._commit_vals()
        except KeyError:
            raise ValueError(f"Math watchable {self._name} has no variable named {name}")

    def assign_var_value_by_fqn(self, fqn: str, val: ValueType) -> None:
        self._assert_valid()
        found = False
        for name, data in self._var_defs.items():
            if data.fqn_name is not None and data.fqn_name.fqn == fqn:
                self.assign_var_value(name, val, commit=False)
                found = True
        if not found:
            raise ValueError(f"No variable is bound to watchable with FQN : {fqn}")
        self._commit_vals()

    def clear_vals(self) -> None:
        for var_name in self._var_defs:
            self._var_defs[var_name].val = None
        self._commit_vals()
        self._val = None

    def eval(self) -> Optional[float]:
        if self._parsing_error is not None:
            self._eval_error = self._parsing_error
            return None
        assert self._parser is not None
        try:
            self._val = self._parser.eval(self._committed_vals)
            self._eval_error = None
        except Exception as e:
            self._val = None
            self._eval_error = str(e)

        return self._val

    def get_var_fqn_map(self) -> Dict[str, Optional[FqnNamePair]]:
        return {name: data.fqn_name for name, data in self._var_defs.items()}

    def get_vars(self) -> Set[str]:
        return set(self._var_defs.keys())

    def get_val(self) -> ValueType:
        return self._val

    def get_error(self) -> Optional[str]:
        if self._parsing_error:
            return self._parsing_error

        return self._eval_error

    def copy(self) -> Self:
        el = self.__class__(self._name, self._expr)
        for name, data in self._var_defs.items():
            if data.fqn_name is not None:
                el.bind_watchable(name, data.fqn_name)
        return el

    def serialize(self) -> str:
        return json.dumps(self.to_dict())

    def to_dict(self) -> GUIMathWatchableDictDef:
        return {
            'name': self.get_name(),
            'expr': self.get_expr(),
            'variables': {k: v.to_dict() if v is not None else None for k, v in self.get_var_fqn_map().items()}
        }

    def to_datalogging_config(self) -> Optional[datalogging.MathSignalConfig]:
        if not self.is_fully_configured():
            return None

        var_dict: Dict[str, str] = {}
        for varname, fqn_name_pair in self.get_var_fqn_map().items():
            assert fqn_name_pair is not None
            var_dict[varname] = FQN.parse(fqn_name_pair.fqn).path

        return datalogging.MathSignalConfig(
            expr=self.get_expr(),
            variables=var_dict
        )

    def is_equivalent(self, other: "GUIMathWatchable") -> bool:
        if self.normalize_expr(self._expr) != self.normalize_expr(other.get_expr()):
            return False

        # We drop the visual name given to the associated watchable. Hence the "equivalence"
        fqn_map1 = {k: v.fqn if v is not None else None for k, v in self.get_var_fqn_map().items()}
        fqn_map2 = {k: v.fqn if v is not None else None for k, v in other.get_var_fqn_map().items()}

        if fqn_map1 != fqn_map2:
            return False
        return True

    @classmethod
    def from_core_def(cls, name: str, coredef: core_MathWatchable) -> Self:
        instance = cls(
            name=name,
            expr=coredef.expr
        )

        for varname, watchable in coredef.watchables.items():
            fqn = FQN.make(RegistryNodeType.from_sdk(watchable.type), watchable.path)
            watchable_display_name = path_tools.make_segments(watchable.path)[-1]
            instance.bind_watchable(varname, FqnNamePair(watchable_display_name, fqn))

        return instance

    @classmethod
    def deserialize(cls, data: str) -> Self:
        return cls.from_dict(json.loads(data))

    @classmethod
    def from_dict(cls, d: GUIMathWatchableDictDef) -> Self:
        validation.assert_dict_key(d, 'name', str)
        validation.assert_dict_key(d, 'expr', str)
        validation.assert_dict_key(d, 'variables', dict)
        o = cls(d['name'], d['expr'])
        for name, fqn_name in d['variables'].items():
            validation.assert_type(name, 'name', str)
            validation.assert_type_or_none(fqn_name, 'fqn_name', dict)
            if fqn_name is not None:
                o.bind_watchable(name, FqnNamePair.from_dict(fqn_name))
        return o

    @staticmethod
    def normalize_expr(expr: str) -> str:
        return re.sub(r"\s", "", expr)

    def signature(self) -> str:
        d = self.to_dict()
        d['expr'] = self.normalize_expr(d['expr'])
        canonical = json.dumps(d, sort_keys=True)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()

    def make_fqn(self) -> str:
        return FQN.make(RegistryNodeType.Math, self.signature())
