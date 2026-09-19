from scrutiny.tools.typing import *
from dataclasses import dataclass
from scrutiny.core.math_parser import MathParser, MathParsingError
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.tools import validation
import json

ValueType: TypeAlias = Optional[Union[float, int, bool]]


class GUIMathWatchableDictDef(TypedDict):
    name: str
    expr: str
    variables: Dict[str, Optional[str]]


@dataclass(slots=True)
class GUIMathWatchable:

    @dataclass(slots=True)
    class VarData:
        fqn: Optional[str]
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
                self._var_defs[var] = self.VarData(fqn=None, val=None)

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
        return self.is_valid() and all([data.fqn is not None for data in self._var_defs.values()])

    def is_evaluable(self) -> bool:
        return self.is_fully_configured() and (len(self._committed_vals) == len(self._var_defs))

    def bind_watchable(self, name: str, fqn: str) -> None:
        self._assert_valid()
        validation.assert_type(name, 'name', str)
        if name not in self._var_defs:
            raise ValueError(f"No variable with name {name} in expression {self._expr}")

        if FQN.parse(fqn).node_type == RegistryNodeType.Math:
            raise ValueError("Math watchables cannot be bound to other math watchables")

        self._var_defs[name].fqn = fqn
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
            if data.fqn == fqn:
                self.assign_var_value(name, val, commit=False)
                found = True
        if not found:
            raise ValueError(f"No variable is bound to watchable with FQN : {fqn}")
        self._commit_vals()

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

    def get_var_fqn_map(self) -> Dict[str, Optional[str]]:
        return {name: data.fqn for name, data in self._var_defs.items()}

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
            if data.fqn is not None:
                el.bind_watchable(name, data.fqn)
        return el

    def serialize(self) -> str:
        return json.dumps(self.to_dict())

    def to_dict(self) -> GUIMathWatchableDictDef:
        return {
            'name': self.get_name(),
            'expr': self.get_expr(),
            'variables': self.get_var_fqn_map()
        }

    @classmethod
    def deserialize(cls, data: str) -> Self:
        return cls.from_dict(json.loads(data))

    @classmethod
    def from_dict(cls, d: GUIMathWatchableDictDef) -> Self:
        validation.assert_dict_key(d, 'name', str)
        validation.assert_dict_key(d, 'expr', str)
        validation.assert_dict_key(d, 'variables', dict)
        o = cls(d['name'], d['expr'])
        for name, fqn in d['variables'].items():
            validation.assert_type(name, 'name', str)
            validation.assert_type_or_none(name, 'fqn', str)
            if fqn is not None:
                o.bind_watchable(name, fqn)
        return o
