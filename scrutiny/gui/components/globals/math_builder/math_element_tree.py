from dataclasses import dataclass
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import QItemSelection
from scrutiny.gui.widgets.base_tree import BaseTreeModel, BaseTreeView
from scrutiny.gui.widgets.watchable_tree import get_watchable_icon, WatchableStandardItem
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.core.fqn_name_pair import FqnNamePair
from scrutiny.tools.typing import *
from scrutiny import tools
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable

from PySide6.QtWidgets import QHeaderView, QAbstractItemView
from PySide6.QtGui import QStandardItem
from scrutiny.tools.global_counters import global_i64_counter


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
class MathItemUidPair:
    math_watchable: GUIMathWatchable
    uid: int


class MathTreeModel(BaseTreeModel):

    HEADERS = ['Element', 'Content', 'Path']

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(nesting_col=Cols.ItemOrVar, parent=parent)

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

    def replace_math_watchable(self, uid: int, math_watchable: GUIMathWatchable,) -> None:
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
        if not math_watchable.is_fully_configured():
            raise ValueError("Math element is not complete")

        math_item = MathStandardItem(math_watchable.get_name())
        expr_item = MathExprStandardItem(math_watchable.get_expr())
        placeholder = QStandardItem()
        placeholder.setEditable(False)
        math_row = [math_item, expr_item, placeholder]

        self._fill_with_variables(math_item, math_watchable)
        self.appendRow(math_row)

    def extract_math_watchable(self, row_index: int) -> Optional[MathItemUidPair]:
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

        return MathItemUidPair(
            math_watchable=math_watchable,
            uid=math_item.get_uid()
        )


class MathTreeView(BaseTreeView):

    _model: MathTreeModel

    @tools.copy_type(BaseTreeView.__init__)
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._model = MathTreeModel()
        self.setModel(self._model)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setRootIsDecorated(True)
        self.header().setStretchLastSection(True)
        self.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)

    def insert_math_watchable(self, math_watchable: GUIMathWatchable) -> None:
        self._model.insert_math_watchable(math_watchable)

    def replace_math_watchable(self, uid: int, math_watchable: GUIMathWatchable) -> None:
        self._model.replace_math_watchable(uid, math_watchable)

    def extract_math_watchable(self, row_index: int) -> Optional[MathItemUidPair]:
        return self._model.extract_math_watchable(row_index)
