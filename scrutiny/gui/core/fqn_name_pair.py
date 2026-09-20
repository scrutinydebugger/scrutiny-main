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
