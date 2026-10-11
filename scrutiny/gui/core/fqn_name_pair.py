#    fqn_name_pair.py
#        Simple container used across the GUI to carry a display name an a Fully Qualified
#        Name pointing to an item int he registry
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from dataclasses import dataclass
from scrutiny.tools.typing import *
from scrutiny.tools import validation


class FqnNamePairDict(TypedDict):
    fqn: str
    name: str


@dataclass(slots=True)
class FqnNamePair:
    name: str
    fqn: str

    def to_dict(self) -> FqnNamePairDict:
        return {
            'fqn': self.fqn,
            'name': self.name,
        }

    @classmethod
    def from_dict(cls, d: FqnNamePairDict) -> Self:
        validation.assert_dict_key(d, 'name', str)
        validation.assert_dict_key(d, 'fqn', str)
        return cls(name=d['name'], fqn=d['fqn'])
