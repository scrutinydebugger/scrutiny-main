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
    _fqn: str

    def __init__(self, name: str, fqn: str) -> None:
        super().__init__()
        self.setText(name)
        self.setEditable(False)
        self.setIcon(get_watchable_icon(RegistryNodeType.Math))
        self._fqn = fqn

    @property
    def fqn(self) -> str:
        return self._fqn


class MathExprStandardItem(QStandardItem):
    def __init__(self, expr: str) -> None:
        super().__init__()
        self.setText(expr)
        self.setEditable(False)


class MathTreeModel(BaseTreeModelWithStyle):

    HEADERS = ['Element', 'Content', 'Path']
    _watchable_registry: WatchableRegistry

    def __init__(self, watchable_registry: WatchableRegistry) -> None:
        super().__init__(nesting_col=Cols.ItemOrVar, parent=None)
        self._watchable_registry = watchable_registry
        self.setColumnCount(len(self.HEADERS))
        self.setHorizontalHeaderLabels(self.HEADERS)

    def _make_row(self, math_watchable: GUIMathWatchable) -> List[QStandardItem]:
        fqn = FQN.make(RegistryNodeType.Math, math_watchable.signature())
        math_item = MathStandardItem(math_watchable.get_name(), fqn)
        expr_item = MathExprStandardItem(math_watchable.get_expr())
        self._fill_with_variables(math_item, math_watchable)

        return [math_item, expr_item]

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

    def sync_with_registry(self) -> None:
        all_math = {signature: math_watcahble for signature, math_watcahble in self._watchable_registry.get_all_math_watchables()}
        to_remove: List[MathStandardItem] = []
        to_update: Dict[str, MathStandardItem] = {}

        for i in range(self.rowCount()):
            item = cast(MathStandardItem, self.item(i, Cols.ItemOrVar))
            signature = FQN.parse(item.fqn).string_id
            if signature not in all_math:
                to_remove.append(item)
            else:
                to_update[signature] = item

        for item in to_remove:
            self.removeRow(item.index().row())
        del to_remove

        for signature, item in to_update.items():
            math_watchable = all_math[signature]
            if signature != math_watchable.signature():
                self._fill_with_variables(item, math_watchable)
                expr_item = cast(MathExprStandardItem, self.item(item.row(), Cols.ExprOrWatchable))
                expr_item.setText(math_watchable.get_expr())
            del all_math[signature]

        for signature, math_watchable in all_math.items():
            row = self._make_row(math_watchable)
            self.appendRow(row)

    def get_fqn_from_row(self, row_index: int) -> Optional[str]:
        """Reads the FQN from a row"""
        if row_index < 0 or row_index > self.rowCount() - 1:
            return None

        math_item = cast(MathStandardItem, self.item(row_index, Cols.ItemOrVar))
        return math_item.fqn


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

    @property
    def signals(self) -> _Signals:
        return self._signals

    def get_fqn_from_row(self, row_index: int) -> Optional[str]:
        return self._model.get_fqn_from_row(row_index)

    def sync_with_registry(self) -> None:
        return self._model.sync_with_registry()

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
        fqn = self.get_fqn_from_row(math_item.row())
        if fqn is None:
            return  # Should not really happen

        self._signals.edit_requested.emit(fqn)

    def _context_menu_remove_slot(self, math_items: List[MathStandardItem]) -> None:
        fqn_to_remove = set()
        for item in math_items:
            fqn_to_remove.add(item.fqn)

        self._signals.remove_requested.emit(fqn_to_remove)
