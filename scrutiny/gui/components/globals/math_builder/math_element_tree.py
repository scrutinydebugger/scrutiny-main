#    math_element_tree.py
#        Contains the TreeView dedicated to MathBuilder. Allow to insert Math element and
#        nested watchable to bound variables. Supports folder organization.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import functools

from PySide6.QtCore import QMimeData, QModelIndex, QObject, Signal, Qt, QPoint, QPersistentModelIndex
from PySide6.QtWidgets import QHeaderView, QAbstractItemView
from PySide6.QtGui import (QContextMenuEvent, QKeyEvent, QMouseEvent, QPaintEvent, QPainter,
                           QStandardItem, QDragEnterEvent, QDragMoveEvent, QDropEvent)
from scrutiny.gui.tools.drag_and_drop import make_watchable_list_dragdata_if_possible
from scrutiny.gui.widgets.base_tree import BaseTreeModelWithStyle, BaseTreeView, SerializableItemIndexDescriptor
from scrutiny.gui.widgets.watchable_tree import WatchableStandardItem, FolderStandardItem, BaseWatchableRegistryTreeStandardItem, SerializableTreeDescriptor
from scrutiny.gui.widgets.scrutiny_qmenu import ScrutinyQMenu
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.core.watchable_registry.watchable_registry import WatchableRegistry
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.core.scrutiny_drag_data import ScrutinyDragData
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
        self.setDropEnabled(False)


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

    def iter_math_items(self, parent: Optional[QStandardItem] = None) -> Generator[MathStandardItem, None, None]:
        """Recursively yield all MathStandardItems in the tree, traversing folders"""
        nesting_col = self.nesting_col()
        get_child: Callable[[int], Optional[QStandardItem]]
        if parent is None:
            count = self.rowCount()
            get_child = lambda i: self.item(i, nesting_col)
        else:
            count = parent.rowCount()
            get_child = lambda i: parent.child(i, nesting_col)

        for i in range(count):
            child = get_child(i)
            if isinstance(child, MathStandardItem):
                yield child
            elif isinstance(child, FolderStandardItem):
                yield from self.iter_math_items(child)

    def find_item_by_fqn(self, fqn: str) -> Optional[MathStandardItem]:
        for item in self.iter_math_items():
            if item.fqn == fqn:
                return item
        return None

    def sync_with_registry(self) -> None:
        """Synchronize the content of the model with the WatchableRegistry.
        - Items no longer in registry are removed.
        - New items are appended at root.
        - Folders are left untouched.
        """
        all_math = {signature: math_watchable for signature, math_watchable in self._watchable_registry.get_all_math_watchables()}
        to_remove: List[MathStandardItem] = []
        already_there: Set[str] = set()

        for item in self.iter_math_items():
            signature = FQN.parse(item.fqn).string_id
            if signature in all_math:
                already_there.add(signature)
            else:
                to_remove.append(item)

        for item in to_remove:
            parent = item.parent()
            if parent is not None:
                parent.removeRow(item.row())
            else:
                self.removeRow(item.row())
        del to_remove

        for signature, math_watchable in all_math.items():
            if signature not in already_there:
                row = self._make_row(math_watchable)
                self.appendRow(row)

    def replace_math_item_by_fqn(self, old_fqn: str, new_math_watchable: GUIMathWatchable) -> None:
        """Replace the item identified by old_fqn with a new one at the same position.
        The new item does not need to exist in the registry yet, next sync will relink."""
        old_item = self.find_item_by_fqn(old_fqn)
        if old_item is None:
            return
        parent = old_item.parent()
        row_index = old_item.row()
        if parent is not None:
            parent.removeRow(row_index)
        else:
            self.removeRow(row_index)
        new_row = self._make_row(new_math_watchable)
        self.add_row_to_parent(parent, row_index, new_row)

    def math_watchable_count(self) -> int:
        return sum(1 for _ in self.iter_math_items())

    def update_availabilities(self) -> None:
        """Gray out Math elements that depend on another watchable not available in the registry"""
        for math_item in self.iter_math_items():
            math_watchable = self._watchable_registry.get_math_watchable_node(FQN.parse(math_item.fqn).math_signature)
            assert math_watchable is not None  # Should not happen

            is_available = True
            for varname, fqn_name_pair in math_watchable.get_var_fqn_map().items():
                if fqn_name_pair is None:
                    continue
                if not self._watchable_registry.is_watchable_fully_available_fqn(fqn_name_pair.fqn):
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

    def make_folder_row(self, name: str, expanded: bool = False) -> List[QStandardItem]:
        """Build a new folder row"""
        item = FolderStandardItem(name, expanded=expanded, fqn=None)
        item.setEditable(True)
        item.setDragEnabled(True)
        row: List[QStandardItem] = [item]
        for _ in range(1, len(self.HEADERS)):
            filler = QStandardItem()
            filler.setEditable(False)
            row.append(filler)
        return row

    def _make_serializable_tree_descriptor(self, item: BaseWatchableRegistryTreeStandardItem, sortkey: int = 0) -> SerializableTreeDescriptor:
        """Serialize an item as a tree descriptor for watch components.
        MathStandardItems are treated as leaf watchables (variable bindings are not included)."""
        descriptor: SerializableTreeDescriptor = {
            'node': item.to_serialized_data(),
            'sortkey': sortkey,
            'children': [],
        }

        if isinstance(item, FolderStandardItem):
            nesting_col = self.nesting_col()
            for row_index in range(item.rowCount()):
                child = item.child(row_index, nesting_col)
                if isinstance(child, (MathStandardItem, FolderStandardItem)):
                    descriptor['children'].append(self._make_serializable_tree_descriptor(child, sortkey=row_index))

        return descriptor

    def mimeData(self, indexes: Sequence[QModelIndex]) -> QMimeData:
        """Generate drag data. Folders produce a FullTree, individual math items produce a WatchableList."""
        nesting_col = self.nesting_col()

        navigable_items: List[QStandardItem] = []
        child_watchable_items: List[WatchableStandardItem] = []

        for index in indexes:
            item = self.itemFromIndex(index)
            if index.column() == nesting_col:
                if isinstance(item, (MathStandardItem, FolderStandardItem)):
                    navigable_items.append(item)
            if isinstance(item, WatchableStandardItem) and not isinstance(item, MathStandardItem):
                child_watchable_items.append(item)

        if len(navigable_items) > 0:
            top_level_indexes = self.remove_nested_indexes_unordered([item.index() for item in navigable_items])
            items = [cast(BaseWatchableRegistryTreeStandardItem, self.itemFromIndex(idx)) for idx in top_level_indexes]
            self.sort_items_by_path(items, top_to_bottom=True)
            move_data = [self.make_serializable_item_index_descriptor(item) for item in items]

            drag_data = make_watchable_list_dragdata_if_possible(items, data_move=move_data)
            if drag_data is None:
                copy_data = [self._make_serializable_tree_descriptor(item, sortkey=i) for i, item in enumerate(items)]
                drag_data = ScrutinyDragData(
                    type=ScrutinyDragData.DataType.WatchableFullTree,
                    data_copy=copy_data,
                    data_move=move_data
                )

            mime = drag_data.to_mime()
            if mime is not None:
                return mime

        elif len(child_watchable_items) > 0:
            drag_data = make_watchable_list_dragdata_if_possible(child_watchable_items)
            if drag_data is not None:
                mime = drag_data.to_mime()
                if mime is not None:
                    return mime

        return QMimeData()

    def canDropMimeData(self,
                        mime_data: QMimeData,
                        action: Qt.DropAction,
                        row_index: int,
                        column_index: int,
                        parent: Union[QModelIndex, QPersistentModelIndex]
                        ) -> bool:
        """Only accept internal moves onto root or folders"""
        if action != Qt.DropAction.MoveAction:
            return False
        drag_data = ScrutinyDragData.from_mime(mime_data)
        if drag_data is None:
            return False
        if drag_data.type not in (ScrutinyDragData.DataType.WatchableFullTree, ScrutinyDragData.DataType.WatchableList):
            return False
        if drag_data.data_move is None:
            return False
        if parent.isValid():
            if not isinstance(self.itemFromIndex(parent), FolderStandardItem):
                return False
        return True

    def dropMimeData(self,
                     mime_data: QMimeData,
                     action: Qt.DropAction,
                     row_index: int,
                     column_index: int,
                     parent: Union[QModelIndex, QPersistentModelIndex]
                     ) -> bool:
        """Handle internal move drops"""
        if action != Qt.DropAction.MoveAction:
            return False
        drag_data = ScrutinyDragData.from_mime(mime_data)
        if drag_data is None or drag_data.data_move is None:
            return False
        if drag_data.type not in (ScrutinyDragData.DataType.WatchableFullTree, ScrutinyDragData.DataType.WatchableList):
            return False
        return self.handle_internal_move(parent, row_index, cast(List[SerializableItemIndexDescriptor], drag_data.data_move))

    def append_math_watchable(self, math_watchable: GUIMathWatchable, parent: Optional[QStandardItem] = None) -> None:
        """Build a math row and append it to the given parent (or root)"""
        row = self._make_row(math_watchable)
        self.add_row_to_parent(parent, -1, row)

    def _make_row(self, math_watchable: GUIMathWatchable) -> List[QStandardItem]:
        """Build a new empty Math row"""
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
        for var_name in name_fqn_map.keys():    # Ordered by formula appearance
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
    NEW_FOLDER_DEFAULT_NAME = "New Folder"

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
        self.setDropIndicatorShown(True)
        self.setDragDropMode(self.DragDropMode.DragDrop)

        self.expanded.connect(self._set_expanded_slot)
        self.collapsed.connect(self._set_collapsed_slot)

    def model(self) -> MathTreeModel:
        return self._model

    @property
    def signals(self) -> _Signals:
        return self._signals

    def find_item_by_fqn(self, fqn: str) -> Optional[MathStandardItem]:
        return self._model.find_item_by_fqn(fqn)

    def sync_with_registry(self) -> None:
        return self._model.sync_with_registry()

    def math_watchable_count(self) -> int:
        return self._model.math_watchable_count()

    def selected_math_items(self) -> List[MathStandardItem]:
        def iterate() -> Generator[MathStandardItem, None, None]:
            for index in self.selectedIndexes():
                if index.column() == Cols.ItemOrVar:
                    item = self._model.itemFromIndex(index)
                    if isinstance(item, MathStandardItem):
                        yield item
        return list(iterate())

    def selected_removable_items(self) -> List[QStandardItem]:
        """Returns selected MathStandardItems and FolderStandardItems, removing nested duplicates"""
        nesting_col = self._model.nesting_col()
        indexes = self._model.remove_nested_indexes_unordered(self.selectedIndexes(), columns_to_keep=[nesting_col])
        items: List[QStandardItem] = []
        for index in indexes:
            item = self._model.itemFromIndex(index)
            if isinstance(item, (MathStandardItem, FolderStandardItem)):
                items.append(item)
        return items

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:
        context_menu = ScrutinyQMenu()
        theme = scrutiny_get_theme()

        selected_math_items = self.selected_math_items()
        removable_items = self.selected_removable_items()

        parent, insert_row = self._find_new_folder_position_from_position(event.pos())

        def new_folder_slot() -> None:
            self._new_folder(self.NEW_FOLDER_DEFAULT_NAME, parent, insert_row)

        new_folder_action = context_menu.addAction(theme.load_tiny_icon(assets.Icons.Folder), "New Folder")
        new_folder_action.triggered.connect(new_folder_slot)

        edit_action = context_menu.addAction(theme.load_tiny_icon(assets.Icons.TextEdit), "Edit")
        remove_action = context_menu.addAction(theme.load_tiny_icon(assets.Icons.RedX), "Remove")

        if len(selected_math_items) == 1:
            edit_action.setEnabled(True)
            edit_action.triggered.connect(functools.partial(self._context_menu_edit_slot, selected_math_items[0]))
        else:
            edit_action.setEnabled(False)

        if len(removable_items) > 0:
            remove_action.setEnabled(True)
            remove_action.triggered.connect(functools.partial(self._context_menu_remove_slot, removable_items))
        else:
            remove_action.setEnabled(False)

        context_menu.exec_at_first_and_disconnect(self.mapToGlobal(event.pos()))

    def update_availabilities(self) -> None:
        self._model.update_availabilities()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Delete:
            removable = self.selected_removable_items()
            if len(removable) > 0:
                self._handle_remove(removable)
                return
        elif event.key() == Qt.Key.Key_F2:
            nesting_col = self._model.nesting_col()
            index = self.currentIndex().siblingAtColumn(nesting_col)
            if index.isValid():
                item = self._model.itemFromIndex(index)
                if isinstance(item, FolderStandardItem):
                    self.edit(index)
                    return
        elif event.key() == Qt.Key.Key_N and event.modifiers() == (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier):
            parent, insert_row = self._find_new_folder_position_from_selection()
            self._new_folder(self.NEW_FOLDER_DEFAULT_NAME, parent, insert_row)
            return
        super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        index = self.indexAt(event.pos())
        if index.isValid():
            item = self._model.itemFromIndex(index.siblingAtColumn(Cols.ItemOrVar))
            if isinstance(item, MathStandardItem):
                self._signals.edit_requested.emit(item.fqn)
                return
        super().mouseDoubleClickEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        super().paintEvent(event)
        if self._model.rowCount() == 0:
            painter = QPainter(self.viewport())
            painter.setPen(self.palette().placeholderText().color())
            painter.drawText(self.viewport().rect(), Qt.AlignmentFlag.AlignCenter, "No math elements defined")
            painter.end()


# region Private


    def _set_expanded_slot(self, index: QModelIndex) -> None:
        item = self._model.itemFromIndex(index)
        if isinstance(item, FolderStandardItem):
            item.set_expanded(True)

    def _set_collapsed_slot(self, index: QModelIndex) -> None:
        item = self._model.itemFromIndex(index)
        if isinstance(item, FolderStandardItem):
            item.set_expanded(False)

    def _set_drag_and_drop_action(self, event: Union[QDragEnterEvent, QDragMoveEvent, QDropEvent]) -> None:
        if event.source() is self:
            event.setDropAction(Qt.DropAction.MoveAction)
        else:
            event.setDropAction(Qt.DropAction.CopyAction)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self._set_drag_and_drop_action(event)
        super().dragEnterEvent(event)
        event.accept()

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        self._set_drag_and_drop_action(event)
        return super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        self._set_drag_and_drop_action(event)
        return super().dropEvent(event)

    def _new_folder(self, name: str, parent: Optional[QStandardItem], insert_row: int) -> None:
        """Create a new folder at the given position"""
        new_row = self._model.make_folder_row(name)
        self._model.add_row_to_parent(parent, insert_row, new_row)
        if parent is not None:
            self.expand(parent.index())
        self.edit(new_row[0].index())

    def _find_new_folder_position_from_selection(self) -> Tuple[Optional[QStandardItem], int]:
        """Find where to insert a new folder based on the current selection"""
        nesting_col = self._model.nesting_col()
        selected_list = [index for index in self.selectedIndexes() if index.column() == nesting_col]
        parent: Optional[QStandardItem] = None
        insert_row = -1

        if len(selected_list) > 0:
            selected_item = self._model.itemFromIndex(selected_list[0])
            if isinstance(selected_item, MathStandardItem):
                insert_row = selected_item.row()
                parent = selected_item.parent()
            elif isinstance(selected_item, FolderStandardItem):
                insert_row = -1
                parent = selected_item

        return parent, insert_row

    def _find_new_folder_position_from_position(self, position: QPoint) -> Tuple[Optional[QStandardItem], int]:
        """Find where to insert a new folder based on a click position"""
        index = self.indexAt(position)
        if not index.isValid():
            return None, -1
        item = self._model.itemFromIndex(index.siblingAtColumn(Cols.ItemOrVar))

        if isinstance(item, FolderStandardItem):
            return item, -1
        if isinstance(item, MathStandardItem):
            return item.parent(), item.row()
        # Variable binding row - position relative to the parent MathStandardItem
        parent = item.parent() if item is not None else None
        if parent is not None and isinstance(parent, MathStandardItem):
            return parent.parent(), parent.row()
        return None, -1

    def _handle_remove(self, items: List[QStandardItem]) -> None:
        """Remove items from tree and emit FQNs for registry removal"""
        fqns: Set[str] = set()
        for item in items:
            if isinstance(item, MathStandardItem):
                fqns.add(item.fqn)
            elif isinstance(item, FolderStandardItem):
                for math_item in self._model.iter_math_items(item):
                    fqns.add(math_item.fqn)

        for item in items:
            if item is not None:
                self._model.removeRow(item.row(), item.index().parent())

        if len(fqns) > 0:
            self._signals.remove_requested.emit(fqns)

    def _context_menu_edit_slot(self, math_item: MathStandardItem) -> None:
        self._signals.edit_requested.emit(math_item.fqn)

    def _context_menu_remove_slot(self, items: List[QStandardItem]) -> None:
        self._handle_remove(items)

# end region
# end region
