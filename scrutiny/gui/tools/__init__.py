
__all__ = ['nodetype_2_icon']

from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui import assets


def nodetype_2_icon(node_type: RegistryNodeType) -> assets.Icons:
    """Return the proper icon for a given watchable type (var, alias, rpv)"""
    if node_type == RegistryNodeType.Variable:
        return assets.Icons.Var
    if node_type == RegistryNodeType.Alias:
        return assets.Icons.Alias
    if node_type == RegistryNodeType.RuntimePublishedValue:
        return assets.Icons.Rpv
    if node_type == RegistryNodeType.Math:
        return assets.Icons.Math
    raise NotImplementedError(f"Unsupported icon for {node_type}")
