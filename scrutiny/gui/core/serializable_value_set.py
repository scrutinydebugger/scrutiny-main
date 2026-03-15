#    serializable_value_set.py
#        A class that represent the content of a .scval file. It's a set of values tied to
#        a server path.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = ['InvalidFileFormatError', 'SerializableValueSet']

from scrutiny.tools.typing import *
import json
from pathlib import Path
from scrutiny.tools import validation
from scrutiny.gui.core.watchable_registry import WatchableRegistry

ValType: TypeAlias = Union[int, float, bool]


class InvalidFileFormatError(Exception):
    pass


class SerializableValueSet:
    DEFAULT_EXTENSION = '.scval'
    _storage: Dict[str, ValType]

    def __init__(self) -> None:
        self._storage = {}

    def add(self, fqn: str, value: ValType) -> None:
        validation.assert_type(fqn, 'fqn', str)
        validation.assert_type(value, 'value', (int, float, bool))

        WatchableRegistry.FQN.parse(fqn)    # Validate

        self._storage[fqn] = value

    def to_file(self, file: Path) -> None:
        with open(file, 'wb') as f:
            content = json.dumps(self.to_dict(), ensure_ascii=True, indent='\t')
            f.write(content.encode('utf-8'))

    def to_dict(self) -> Dict[str, ValType]:
        return self._storage.copy()

    @classmethod
    def from_file(cls, file: Path) -> Self:
        with open(file, 'rb') as f:
            try:
                data = json.loads(f.read().decode('utf-8'))
            except json.JSONDecodeError as e:
                raise InvalidFileFormatError(f"Failed to parse file {file}") from e

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: Dict[Any, Any]) -> Self:

        if not isinstance(data, dict):
            raise InvalidFileFormatError(f"Data is not a dictionary")

        outset = cls()
        for key, val in data.items():
            if not isinstance(key, str):
                raise InvalidFileFormatError(f"Unexpected entry key of type {key.__class__.__name__}")
            if not isinstance(val, (bool, int, float)):
                raise InvalidFileFormatError(f"Unexpected value entry for key {key}. Type : {val.__class__.__name__}")

            try:
                outset.add(key, val)
            except Exception as e:
                raise InvalidFileFormatError(f"Failed to add {key} in the value set. {e}") from e

        return outset

    def __len__(self) -> int:
        return len(self._storage)
