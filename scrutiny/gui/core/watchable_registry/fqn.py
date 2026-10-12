#    fqn.py
#        Tools to parse/make a Fully Qualified Name, e.g. a string that can point to an item
#        in the registry.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

__all__ = [
    'ParsedFullyQualifiedName',
    'FQN'
]

from scrutiny.tools.typing import *
from dataclasses import dataclass
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui.core.watchable_registry.errors import WatchableRegistryError
from scrutiny.core import path_tools


TYPESTR_MAP_S2WT = {
    'var': RegistryNodeType.Variable,
    'alias': RegistryNodeType.Alias,
    'rpv': RegistryNodeType.RuntimePublishedValue,
    'math': RegistryNodeType.Math
}

TYPESTR_MAP_WT2S: Dict[RegistryNodeType, str] = {v: k for k, v in TYPESTR_MAP_S2WT.items()}


@dataclass(slots=True)
class ParsedFullyQualifiedName:
    node_type: RegistryNodeType
    string_id: str

    @property
    def path(self) -> str:
        if not self.node_type.is_server_node():
            raise ValueError("Non server node have no path")
        return self.string_id

    @property
    def math_signature(self) -> str:
        if self.node_type != RegistryNodeType.Math:
            raise ValueError("Math signature exist only on Math nodes")
        return self.string_id


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
            node_type=TYPESTR_MAP_S2WT[typestr],
            string_id=fqn[colon_position + 1:]
        )

    @staticmethod
    def make(node_type: RegistryNodeType, string_id: str) -> str:
        """Create a string representation that conveys enough information to find a specific element in the registry.
        Contains the type and the tree string_id (server path or math signature).

        :param node_type: The registry node type
        :param string_id: The tree string_id

        :return: A fully qualified name containing the type and the tree path
        """
        return f"{TYPESTR_MAP_WT2S[node_type]}:{string_id}"

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
        if not parsed.node_type.is_server_node():
            raise ValueError("Cannot extend a FQN that does not have a server path")
        path_parts = path_tools.make_segments(parsed.string_id)
        return FQN.make(parsed.node_type, path_tools.join_segments(path_parts + pieces))

    @staticmethod
    def is_equal(fqn1: str, fqn2: str) -> bool:
        """Compares 2 Fully Qualified Names and return ``True`` if they point to the same node

        :param fqn1: First operand
        :param fqn2: Second operand

        :return: ``True`` if equals
        """
        parsed1 = FQN.parse(fqn1)
        parsed2 = FQN.parse(fqn2)

        if parsed1.node_type != parsed2.node_type:
            return False

        if parsed1.node_type.is_server_node():
            path1 = path_tools.make_segments(parsed1.string_id)
            path2 = path_tools.make_segments(parsed2.string_id)

            if len(path1) != len(path2):
                return False
            for i in range(len(path1)):
                if path1[i] != path2[i]:
                    return False

            return True
        else:
            return parsed1.string_id == parsed2.string_id
