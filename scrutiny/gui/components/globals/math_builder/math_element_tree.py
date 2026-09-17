from dataclasses import dataclass
import functools

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QHeaderView, QAbstractItemView
from PySide6.QtGui import QContextMenuEvent, QStandardItem

from scrutiny.gui.widgets.base_tree import BaseTreeModelWithStyle, BaseTreeView
from scrutiny.gui.widgets.watchable_tree import get_watchable_icon, WatchableStandardItem
from scrutiny.gui.widgets.scrutiny_qmenu import ScrutinyQMenu
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.core.watchable_registry.watchable_registry import WatchableRegistry
from scrutiny.gui.core.fqn_name_pair import FqnNamePair
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets

from scrutiny.tools.global_counters import global_i64_counter
from scrutiny.tools.typing import *
from scrutiny import tools


class Cols:
    ItemOrVar = 0
    ExprOrWatchable = 1
    FQN = 2


class MathStandardItem(QStandardItem):
    _uid: int

    def __init__(self, name: str, uid: Optional[int] = None) -> None:
        super().__init__()
        self.setText(name)
        self.setEditable(False)
        self.setIcon(get_watchable_icon(RegistryNodeType.Math))

        if uid is None:
            self._uid = global_i64_counter()
        else:
            self._uid = uid

    def get_uid(self) -> int:
        return self._uid


class MathExprStandardItem(QStandardItem):
    def __init__(self, expr: str) -> None:
        super().__init__()
        self.setText(expr)
        self.setEditable(False)


@dataclass(slots=True)
class MathWatchableUidPair:
    math_watchable: GUIMathWatchable
    uid: int


class MathTreeModel(BaseTreeModelWithStyle):

    HEADERS = ['Element', 'Content', 'Path']
    _watchable_registry: WatchableRegistry

    def __init__(self, watchable_registry: WatchableRegistry) -> None:
        super().__init__(nesting_col=Cols.ItemOrVar, parent=None)
        self._watchable_registry = watchable_registry
        self.setColumnCount(len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)

    def _find_row_of_uid(self, uid: int) -> Optional[int]:
        for i in range(self.rowCount()):
            item = self.item(i, Cols.ItemOrVar)
            assert isinstance(item, MathStandardItem)
            if item.get_uid() == uid:
                return i
        return None

    def _fill_with_variables(self, math_item: MathStandardItem, math_watchable: GUIMathWatchable) -> None:
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

    def replace_math_watchable(self, uid: int, math_watchable: GUIMathWatchable) -> None:
        """Replace a Math item in the tree identified by its uid by a new MathWatchable"""
        if not math_watchable.is_fully_configured():
            raise ValueError("Math element is not complete")

        row_index = self._find_row_of_uid(uid)
        if row_index is None:
            raise KeyError(f"Could not find Math item with UID={uid}")
        math_item = self.item(row_index, Cols.ItemOrVar)
        expr_item = self.item(row_index, Cols.ExprOrWatchable)
        assert isinstance(math_item, MathStandardItem)
        assert isinstance(expr_item, MathExprStandardItem)

        math_item.setText(math_watchable.get_name())
        expr_item.setText(math_watchable.get_expr())

        self._fill_with_variables(math_item, math_watchable)

    def insert_math_watchable(self, math_watchable: GUIMathWatchable) -> None:
        """Add a row in the tree made from the given MathWatchable"""
        if not math_watchable.is_fully_configured():
            raise ValueError("Math element is not complete")

        math_item = MathStandardItem(math_watchable.get_name())
        expr_item = MathExprStandardItem(math_watchable.get_expr())
        placeholder = QStandardItem()
        placeholder.setEditable(False)
        math_row = [math_item, expr_item, placeholder]

        self._fill_with_variables(math_item, math_watchable)
        self.appendRow(math_row)

    def extract_math_watchable(self, row_index: int) -> Optional[MathWatchableUidPair]:
        """Reads the MathWatchable from a row"""
        if row_index < 0 or row_index > self.rowCount() - 1:
            return None

        math_item = cast(MathStandardItem, self.item(row_index, Cols.ItemOrVar))
        expr_item = cast(MathExprStandardItem, self.item(row_index, Cols.ExprOrWatchable))

        math_watchable = GUIMathWatchable(name=math_item.text(), expr=expr_item.text())
        for i in range(math_item.rowCount()):
            var_name = math_item.child(i, Cols.ItemOrVar).text()
            w = math_item.child(i, Cols.ExprOrWatchable)
            assert isinstance(w, WatchableStandardItem)
            math_watchable.bind_watchable(var_name, FqnNamePair(name=w.text(), fqn=w.fqn))

        return MathWatchableUidPair(
            math_watchable=math_watchable,
            uid=math_item.get_uid()
        )


class MathTreeView(BaseTreeView):
    class _Signals(QObject):
        edit_requested = Signal(object, int)    # MathWatchable, UID
        removed = Signal(object)                # Set[int]

    _model: MathTreeModel
    _signals: _Signals

    @tools.copy_type(BaseTreeView.__init__)
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

    @property
    def signals(self) -> _Signals:
        return self._signals

    def insert_math_watchable(self, math_watchable: GUIMathWatchable) -> None:
        self._model.insert_math_watchable(math_watchable)

    def replace_math_watchable(self, uid: int, math_watchable: GUIMathWatchable) -> None:
        self._model.replace_math_watchable(uid, math_watchable)

    def extract_math_watchable(self, row_index: int) -> Optional[MathWatchableUidPair]:
        return self._model.extract_math_watchable(row_index)

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

    def _context_menu_edit_slot(self, math_item: MathStandardItem) -> None:
        pair = self.extract_math_watchable(math_item.row())
        if pair is None:
            return  # Should not really happen

        self._signals.edit_requested.emit(pair.math_watchable, pair.uid)

    def _context_menu_remove_slot(self, math_items: List[MathStandardItem]) -> None:
        uid_removed = set()
        for item in math_items:
            uid_removed.add(item.get_uid())
            self._model.removeRow(item.row())

        self._signals.removed.emit(uid_removed)
