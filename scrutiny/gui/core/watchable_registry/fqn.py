__all__ = [
    'ParsedFullyQualifiedName',
    'FQN'
]

from scrutiny.tools.typing import *
from scrutiny import sdk
from dataclasses import dataclass
from scrutiny.gui.core.watchable_registry.errors import WatchableRegistryError
from scrutiny.core import path_tools


TYPESTR_MAP_S2WT = {
    'var': sdk.WatchableType.Variable,
    'alias': sdk.WatchableType.Alias,
    'rpv': sdk.WatchableType.RuntimePublishedValue,
}

TYPESTR_MAP_WT2S: Dict[sdk.WatchableType, str] = {v: k for k, v in TYPESTR_MAP_S2WT.items()}


@dataclass(slots=True)
class ParsedFullyQualifiedName:
    watchable_type: sdk.WatchableType
    path: str


class FQN:
    @staticmethod
    def parse(fqn: str) -> ParsedFullyQualifiedName:
        """Parses a fully qualified name and return the information needed to query the registry.

        :param fqn: The fully qualified name

        :return: An object containing the type and the tree path separated
        """
        colon_position = fqn.find(':')
        if colon_position == -1:
            raise WatchableRegistryError(f"Bad fully qualified name {fqn}")
        typestr = fqn[0:colon_position]
        if typestr not in TYPESTR_MAP_S2WT:
            raise WatchableRegistryError(f"Unknown watchable type {typestr}")

        return ParsedFullyQualifiedName(
            watchable_type=TYPESTR_MAP_S2WT[typestr],
            path=fqn[colon_position + 1:]
        )

    @staticmethod
    def make(watchable_type: sdk.WatchableType, path: str) -> str:
        """Create a string representation that conveys enough information to find a specific element in the registry.
        Contains the type and the tree path.

        :param watchable_type: The SDK watchable type
        :param path: The tree path

        :return: A fully qualified name containing the type and the tree path
        """
        return f"{TYPESTR_MAP_WT2S[watchable_type]}:{path}"

    @staticmethod
    def extend(fqn: str, pieces: Union[str, List[str]]) -> str:
        """Add one or many path parts to an existing Fully Qualified Name
        Ex. var:/a/b/c + ['x', 'y'] = var:/a/b/c/x/y

        :param fqn: The Fully Qualified Name to extend
        :param pieces: The parts to add
        """
        if isinstance(pieces, str):
            pieces = [pieces]
        parsed = FQN.parse(fqn)
        path_parts = path_tools.make_segments(parsed.path)
        return FQN.make(parsed.watchable_type, path_tools.join_segments(path_parts + pieces))

    @staticmethod
    def is_equal(fqn1: str, fqn2: str) -> bool:
        """Compares 2 Fully Qualified Names and return ``True`` if they point to the same node

        :param fqn1: First operand
        :param fqn2: Second operand

        :return: ``True`` if equals
        """
        parsed1 = FQN.parse(fqn1)
        parsed2 = FQN.parse(fqn2)

        if parsed1.watchable_type != parsed2.watchable_type:
            return False

        path1 = path_tools.make_segments(parsed1.path)
        path2 = path_tools.make_segments(parsed2.path)

        if len(path1) != len(path2):
            return False
        for i in range(len(path1)):
            if path1[i] != path2[i]:
                return False

        return True
