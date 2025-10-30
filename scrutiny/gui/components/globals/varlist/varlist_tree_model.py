#    varlist_tree_model.py
#        TreeWidget model used for the Variable List component
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2025 Scrutiny Debugger

__all__ = ['VarListComponentTreeModel']

from PySide6.QtGui import QStandardItem
from PySide6.QtCore import QModelIndex, QMimeData

from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData
from scrutiny.gui.widgets.watchable_tree import (
    BaseWatchableRegistryTreeStandardItem,
    WatchableTreeModel,
    NodeSerializableData
)

from scrutiny.sdk import WatchableConfiguration
from scrutiny.tools.typing import *


class VarListComponentTreeModel(WatchableTreeModel):
    """An extension of the data model used by Watchable Trees dedicated for the Variable List Component
    Mainly handles drag&drop logic
    """

    def get_watchable_extra_columns(self, fqn: str, watchable_config: Optional[WatchableConfiguration] = None) -> List[QStandardItem]:
        """Define the columns to add for a watchable (leaf) row. Called by the parent class"""
        if watchable_config is None:
            return []
        typecol = QStandardItem(watchable_config.datatype.name)
        typecol.setEditable(False)
        if watchable_config.enum is not None:
            enumcol = QStandardItem(watchable_config.enum.name)
            enumcol.setEditable(False)
            return [typecol, enumcol]
        else:
            return [typecol]

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        """Generate the mimeData when a drag&drop starts"""

        indexes_without_nested_values = self.remove_nested_indexes_unordered(indexes)
        # Statement below keeps the original order but does extra lookups in the unordered set
        items = [cast(Optional[BaseWatchableRegistryTreeStandardItem], self.itemFromIndex(x)) for x in indexes if x in indexes_without_nested_values]

        # We first start use to most supported format of watchable list.
        drag_data = self.make_watchable_list_dragdata_if_possible(items)

        # If the item selection had folders in it, we can't make a WatchableList mime data.
        # Let's make a WatchableTreeNodesTiedToRegistry instead, can only be dropped in a watch window
        if drag_data is None:
            # Make a serialized version of the data that will be passed a text
            serializable_items: List[NodeSerializableData] = []

            for index in indexes_without_nested_values:
                item = self.itemFromIndex(index)
                if isinstance(item, BaseWatchableRegistryTreeStandardItem):  # Only keep column 0
                    serializable_items.append(item.to_serialized_data())

            drag_data = ScrutinyDragData(type=ScrutinyDragData.DataType.WatchableTreeNodesTiedToRegistry, data_copy=serializable_items)
        mime_data = drag_data.to_mime()

        assert mime_data is not None
        return mime_data

    def _load_node_if_needed(self, node: BaseWatchableRegistryTreeStandardItem) -> None:
        if not node.is_loaded():
            fqn = node.fqn
            assert fqn is not None  # All data is coming from the index, so it has an Fully Qualified Name
            parsed_fqn = WatchableRegistry.FQN.parse(fqn)
            self.lazy_load(node, parsed_fqn.watchable_type, parsed_fqn.path)

    def find_item_by_fqn(self, fqn: str) -> Optional[BaseWatchableRegistryTreeStandardItem]:
        """Find an item in the model using the Watchable registry.
        In this model, each node has a Fully Qualified Name defined and data is organized 
        following the registry structure.

        :param fqn: The Fully Qualified Name to search for

        :return:
        """

        # This method is mainly used by unit tests.
        # We do not expect the application to query this data model
        # with a WatchableRegistry path, it will query the registry directly.

        parsed = WatchableRegistry.FQN.parse(fqn)
        path_parts = WatchableRegistry.split_path(parsed.path)

        if len(path_parts) == 0:
            return None

        empty_fqn = WatchableRegistry.FQN.make(parsed.watchable_type, '')
        first_fqn = WatchableRegistry.FQN.extend(empty_fqn, [path_parts.pop(0)])

        def find_item_recursive(
                item: BaseWatchableRegistryTreeStandardItem,
                wanted_fqn: str,
                remaining_parts: List[str]) -> Optional[BaseWatchableRegistryTreeStandardItem]:

            for row_index in range(item.rowCount()):
                child = cast(Optional[BaseWatchableRegistryTreeStandardItem], item.child(row_index, 0))

                if child is None:
                    continue
                if child.fqn is None:
                    continue
                self._load_node_if_needed(child)

                if WatchableRegistry.FQN.is_equal(child.fqn, wanted_fqn):
                    if len(remaining_parts) == 0:
                        return child
                    new_fqn = WatchableRegistry.FQN.extend(wanted_fqn, [remaining_parts.pop(0)])
                    return find_item_recursive(child, new_fqn, remaining_parts.copy())

            return None

        # For each row at the root, we launch the recursive function if the watchable type matches
        for i in range(self.rowCount()):
            start_node = cast(Optional[BaseWatchableRegistryTreeStandardItem], self.item(i, 0))
            if start_node is not None:
                if start_node.fqn is not None:
                    if WatchableRegistry.FQN.parse(start_node.fqn).watchable_type == parsed.watchable_type:
                        result = find_item_recursive(start_node, first_fqn, path_parts.copy())
                        if result is not None:
                            return result
        return None
