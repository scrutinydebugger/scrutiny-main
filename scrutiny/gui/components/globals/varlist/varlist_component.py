#    varlist_component.py
#        A component that shows the content of the watchable registry, a copy og what's available
#        on the server
#
#   - License : MIT - See LICENSE file.
#   - Project :  Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#   Copyright (c) 2024 Scrutiny Debugger

__all__ = [
    'VarlistComponentTreeWidget',
    'VarListComponent',
]

from PySide6.QtWidgets import QVBoxLayout, QWidget, QStackedLayout
from PySide6.QtGui import QStandardItemModel, QIcon
from PySide6.QtCore import QModelIndex, Qt

from scrutiny.gui import assets
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.core.watchable_registry import WatchableRegistry
from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent
from scrutiny.gui.components.globals.varlist.varlist_tree_model import VarListComponentTreeModel
from scrutiny.gui.components.globals.varlist.varlist_search import SearchResultWidget, SearchControlWidget
from scrutiny.gui.widgets.watchable_tree import (
    BaseWatchableRegistryTreeStandardItem,
    WatchableTreeWidget
)

from scrutiny.sdk import WatchableType
from scrutiny.tools.typing import *


class VarlistComponentTreeWidget(WatchableTreeWidget):
    def __init__(self, parent: QWidget, model: VarListComponentTreeModel) -> None:
        super().__init__(parent, model)
        self.set_header_labels(['', 'Type', 'Enum'])
        self.setDragDropMode(self.DragDropMode.DragOnly)
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def model(self) -> VarListComponentTreeModel:
        return cast(VarListComponentTreeModel, super().model())


class VarListComponent(ScrutinyGUIBaseGlobalComponent):
    instance_name: str

    _NAME = "Variable List"
    _TYPE_ID = "varlist"

    _tree: VarlistComponentTreeWidget
    _tree_model: VarListComponentTreeModel
    _search_result_widget: SearchResultWidget
    _search_controls: SearchControlWidget

    _var_folder: BaseWatchableRegistryTreeStandardItem
    _alias_folder: BaseWatchableRegistryTreeStandardItem
    _rpv_folder: BaseWatchableRegistryTreeStandardItem
    _index_change_counters: Dict[WatchableType, int]
    _tree_stack_layout: QStackedLayout

    @classmethod
    def get_icon(cls) -> QIcon:
        return scrutiny_get_theme().load_medium_icon(assets.Icons.VarList)

    def setup(self) -> None:
        layout = QVBoxLayout(self)

        self._tree_model = VarListComponentTreeModel(self, watchable_registry=self.watchable_registry)
        self._tree = VarlistComponentTreeWidget(self, self._tree_model)
        self._search_controls = SearchControlWidget(self)
        self._search_result_widget = SearchResultWidget(self, self.watchable_registry, search_batch_size=100)

        self._search_controls.signals.search_string_updated.connect(self._search_string_updated_slot)
        self._search_controls.signals.search_string_cleared.connect(self._search_string_cleared_slot)

        var_row = self._tree_model.make_folder_row("Var", WatchableRegistry.FQN.make(WatchableType.Variable, '/'), editable=False)
        alias_row = self._tree_model.make_folder_row("Alias", WatchableRegistry.FQN.make(WatchableType.Alias, '/'), editable=False)
        rpv_row = self._tree_model.make_folder_row("RPV", WatchableRegistry.FQN.make(WatchableType.RuntimePublishedValue, '/'), editable=False)

        self._tree.model().appendRow(var_row)
        self._tree.model().appendRow(alias_row)
        self._tree.model().appendRow(rpv_row)

        self._var_folder = cast(BaseWatchableRegistryTreeStandardItem, var_row[0])
        self._alias_folder = cast(BaseWatchableRegistryTreeStandardItem, alias_row[0])
        self._rpv_folder = cast(BaseWatchableRegistryTreeStandardItem, rpv_row[0])

        layout.addWidget(self._search_controls)

        stacked_container = QWidget()
        self._tree_stack_layout = QStackedLayout(stacked_container)
        self._tree_stack_layout.setStackingMode(QStackedLayout.StackingMode.StackOne)
        self._tree_stack_layout.addWidget(self._tree)
        self._tree_stack_layout.addWidget(self._search_result_widget)
        layout.addWidget(stacked_container)
        self._tree_stack_layout.setCurrentWidget(self._tree)

        self.reload_model([WatchableType.RuntimePublishedValue, WatchableType.Alias, WatchableType.Variable])
        self._index_change_counters = self.watchable_registry.get_change_counters()

        self.server_manager.signals.registry_changed.connect(self.registry_changed_slot)
        self._tree.expanded.connect(self.node_expanded_slot)

    def _search_string_updated_slot(self, txt: str) -> None:
        self._search_result_widget.start_search(txt)
        self._tree_stack_layout.setCurrentWidget(self._search_result_widget)

    def _search_string_cleared_slot(self) -> None:
        self._search_result_widget.stop_search()
        self._tree_stack_layout.setCurrentWidget(self._tree)

    def node_expanded_slot(self, index: QModelIndex) -> None:
        # Lazy loading implementation
        item = cast(BaseWatchableRegistryTreeStandardItem, cast(QStandardItemModel, index.model()).itemFromIndex(index))
        for row in range(item.rowCount()):
            child = cast(BaseWatchableRegistryTreeStandardItem, item.child(row, 0))
            if not child.is_loaded():
                fqn = child.fqn
                assert fqn is not None  # All data is coming from the index, so it has an Fully Qualified Name
                parsed_fqn = WatchableRegistry.FQN.parse(fqn)
                self._tree_model.lazy_load(child, parsed_fqn.watchable_type, parsed_fqn.path)

        self._tree.expand_first_column_to_content()

    def registry_changed_slot(self) -> None:
        """Called when the server manager finishes downloading the server watchable list and update the registry"""
        index_change_counters = self.watchable_registry.get_change_counters()
        # Identify all the types that changed since the last model update
        types_to_reload = []
        for wt, count in index_change_counters.items():
            if count != self._index_change_counters[wt]:
                types_to_reload.append(wt)
        self.reload_model(types_to_reload)
        self._index_change_counters = index_change_counters

    def reload_model(self, watchable_types: List[WatchableType]) -> None:
        """Fully reload to model

        :param watchable_types: The list of watchable types to reload
        """

        # reload first level with max_level=0 as we do lazy loading
        # Collapse root node to avoid lazy loading glitch that require to collapse/reexpand to load new data
        if WatchableType.RuntimePublishedValue in watchable_types:
            self._rpv_folder.removeRows(0, self._rpv_folder.rowCount())
            self._tree.collapse(self._rpv_folder.index())
            self._tree_model.lazy_load(self._rpv_folder, WatchableType.RuntimePublishedValue, '/')

        if WatchableType.Alias in watchable_types:
            self._alias_folder.removeRows(0, self._alias_folder.rowCount())
            self._tree.collapse(self._alias_folder.index())
            self._tree_model.lazy_load(self._alias_folder, WatchableType.Alias, '/')

        if WatchableType.Variable in watchable_types:
            self._var_folder.removeRows(0, self._var_folder.rowCount())
            self._tree.collapse(self._var_folder.index())
            self._tree_model.lazy_load(self._var_folder, WatchableType.Variable, '/')

    def teardown(self) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state: Dict[Any, Any]) -> bool:
        return True
