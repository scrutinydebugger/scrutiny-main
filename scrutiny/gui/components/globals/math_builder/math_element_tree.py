#    math_element_tree.py
#        Contains the TreeView dedicated to MathBuilder. Allow to insert Math element and
#        nested watchable to bound variables.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import functools

from PySide6.QtCore import QMimeData, QModelIndex, QObject, Signal, Qt
from PySide6.QtWidgets import QHeaderView, QAbstractItemView
from PySide6.QtGui import QContextMenuEvent, QStandardItem
from scrutiny.gui.tools.drag_and_drop import make_watchable_list_dragdata_if_possible
from scrutiny.gui.widgets.base_tree import BaseTreeModelWithStyle, BaseTreeView
from scrutiny.gui.widgets.watchable_tree import WatchableStandardItem
from scrutiny.gui.widgets.scrutiny_qmenu import ScrutinyQMenu
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.core.watchable_registry.watchable_registry import WatchableRegistry
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets

from scrutiny.tools.typing import *


class Cols:
    ItemOrVar = 0
    ExprOrWatchable = 1
    FQN = 2


class MathStandardItem(WatchableStandardItem):

    def __init__(self, text: str, fqn: str) -> None:
        super().__init__(RegistryNodeType.Math, text, fqn)
        self.setEditable(False)


class MathExprStandardItem(QStandardItem):
    def __init__(self, expr: str) -> None:
        super().__init__()
        self.setText(expr)
        self.setEditable(False)

# region Model


class MathTreeModel(BaseTreeModelWithStyle):

    HEADERS = ['Element', 'Content', 'Path']
    _watchable_registry: WatchableRegistry

    def __init__(self, watchable_registry: WatchableRegistry) -> None:
        super().__init__(nesting_col=Cols.ItemOrVar, parent=None)
        self._watchable_registry = watchable_registry
        self.setColumnCount(len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)

    def sync_with_registry(self) -> None:
        all_math = {signature: math_watchable for signature, math_watchable in self._watchable_registry.get_all_math_watchables()}
        to_remove: List[MathStandardItem] = []
        already_there: Set[str] = set()

        for i in range(self.rowCount()):
            item = cast(MathStandardItem, self.item(i, Cols.ItemOrVar))
            signature = FQN.parse(item.fqn).string_id
            already_there.add(signature)
            if signature not in all_math:
                to_remove.append(item)

        for item in to_remove:
            self.removeRow(item.index().row())
        del to_remove

        for signature, math_watchable in all_math.items():
            if signature not in already_there:
                row = self._make_row(math_watchable)
                self.appendRow(row)

    def get_fqn_from_row(self, row_index: int) -> Optional[str]:
        """Reads the FQN from a row"""
        if row_index < 0 or row_index > self.rowCount() - 1:
            return None

        math_item = cast(MathStandardItem, self.item(row_index, Cols.ItemOrVar))
        return math_item.fqn

    def math_watchable_count(self) -> int:
        return self.rowCount()

    def get_math_watchable_info(self, row_index: int) -> Optional[Tuple[str, str, str]]:
        """Returns (name, expression, fqn) for a given row, or None if out of range"""
        if row_index < 0 or row_index > self.rowCount() - 1:
            return None
        math_item = cast(MathStandardItem, self.item(row_index, Cols.ItemOrVar))
        expr_item = cast(MathExprStandardItem, self.item(row_index, Cols.ExprOrWatchable))
        return (math_item.text(), expr_item.text(), math_item.fqn)

    def update_availabilities(self) -> None:
        for i in range(self.rowCount()):
            math_item = self.item(i, Cols.ItemOrVar)
            assert isinstance(math_item, MathStandardItem)
            math_watchable = self._watchable_registry.get_math_watchable_node(FQN.parse(math_item.fqn).math_signature)
            assert math_watchable is not None

            is_available = True
            for varname, fqn_name_pair in math_watchable.get_var_fqn_map().items():
                if fqn_name_pair is None:
                    continue  # Should not happen

                if not self._watchable_registry.is_watchable_fqn(fqn_name_pair.fqn):
                    is_available = False

            if is_available:
                self.set_available(math_item)
                for j in range(math_item.rowCount()):
                    var_item = math_item.child(j, Cols.ItemOrVar)
                    self.set_available(var_item)

            else:
                self.set_unavailable(math_item)
                for j in range(math_item.rowCount()):
                    var_item = math_item.child(j, Cols.ItemOrVar)
                    self.set_unavailable(var_item)

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        all_items = [self.itemFromIndex(index) for index in indexes]
        watchable_items = [item for item in all_items if isinstance(item, WatchableStandardItem)]
        drag_data = make_watchable_list_dragdata_if_possible(watchable_items)
        if drag_data is not None:
            mimedata = drag_data.to_mime()
            if mimedata is not None:
                return mimedata

        return QMimeData()

    def _make_row(self, math_watchable: GUIMathWatchable) -> List[QStandardItem]:
        fqn = FQN.make(RegistryNodeType.Math, math_watchable.signature())
        math_item = MathStandardItem(math_watchable.get_name(), fqn)
        expr_item = MathExprStandardItem(math_watchable.get_expr())
        self._fill_with_variables(math_item, math_watchable)

        filler_item = QStandardItem()
        filler_item.setEditable(False)

        return [math_item, expr_item, filler_item]

    def _fill_with_variables(self, math_item: WatchableStandardItem, math_watchable: GUIMathWatchable) -> None:
        """Adds the watchable rows underneath a MathStandardItem"""
        math_item.removeRows(0, math_item.rowCount())

        name_fqn_map = math_watchable.get_var_fqn_map()
        for var_name in sorted(name_fqn_map.keys()):
            fqn_name = name_fqn_map[var_name]
            if fqn_name is None:
                raise ValueError(f"No watchable element assigned to variable {var_name}")

            var_item = QStandardItem(var_name)
            var_item.setEditable(False)
            parsed_fqn = FQN.parse(fqn_name.fqn)
            watchable_item = WatchableStandardItem(node_type=parsed_fqn.node_type, text=fqn_name.name, fqn=fqn_name.fqn)
            watchable_item.setEditable(False)
            fqn_item = QStandardItem(fqn_name.fqn)
            fqn_item.setEditable(False)
            math_item.appendRow([var_item, watchable_item, fqn_item])

# end region


# region TreeView
class MathTreeView(BaseTreeView):
    class _Signals(QObject):
        edit_requested = Signal(str)        # str
        remove_requested = Signal(object)   # Set[str]

    _model: MathTreeModel
    _signals: _Signals

    def __init__(self, watchable_registry: WatchableRegistry) -> None:
        super().__init__()
        self._signals = self._Signals()
        self._model = MathTreeModel(watchable_registry)
        self.setModel(self._model)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setRootIsDecorated(True)
        self.header().setStretchLastSection(True)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        self.setDragEnabled(True)
        self.setDragDropMode(self.DragDropMode.DragOnly)

    def model(self) -> MathTreeModel:
        return self._model

    @property
    def signals(self) -> _Signals:
        return self._signals

    def get_fqn_from_row(self, row_index: int) -> Optional[str]:
        return self._model.get_fqn_from_row(row_index)

    def sync_with_registry(self) -> None:
        return self._model.sync_with_registry()

    def math_watchable_count(self) -> int:
        return self._model.math_watchable_count()

    def get_math_watchable_info(self, row_index: int) -> Optional[Tuple[str, str, str]]:
        return self._model.get_math_watchable_info(row_index)

    def selected_math_items(self) -> List[MathStandardItem]:
        def iterate() -> Generator[MathStandardItem, None, None]:
            for index in self.selectedIndexes():
                if index.column() == Cols.ItemOrVar:
                    item = self._model.itemFromIndex(index)
                    if isinstance(item, MathStandardItem):
                        yield item
        return list(iterate())

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        context_menu = ScrutinyQMenu()

        selected_math_items = self.selected_math_items()
        edit_action = context_menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.TextEdit), "Edit")
        remove_action = context_menu.addAction(scrutiny_get_theme().load_tiny_icon(assets.Icons.RedX), "Remove")

        if len(selected_math_items) == 1:
            edit_action.setEnabled(True)
            edit_action.triggered.connect(functools.partial(self._context_menu_edit_slot, selected_math_items[0]))
        else:
            edit_action.setEnabled(False)

        if len(selected_math_items) > 0:
            remove_action.setEnabled(True)
            remove_action.triggered.connect(functools.partial(self._context_menu_remove_slot, selected_math_items))
        else:
            remove_action.setEnabled(False)

        context_menu.exec_at_first_and_disconnect(self.mapToGlobal(event.pos()))

    def update_availabilities(self) -> None:
        self._model.update_availabilities()


# region Private


    def _context_menu_edit_slot(self, math_item: MathStandardItem) -> None:
        fqn = self.get_fqn_from_row(math_item.row())
        if fqn is None:
            return  # Should not really happen

        self._signals.edit_requested.emit(fqn)

    def _context_menu_remove_slot(self, math_items: List[MathStandardItem]) -> None:
        fqn_to_remove = set()
        for item in math_items:
            fqn_to_remove.add(item.fqn)

        self._signals.remove_requested.emit(fqn_to_remove)

# end region
# end region
