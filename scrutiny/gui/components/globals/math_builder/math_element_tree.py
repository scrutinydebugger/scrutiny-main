from scrutiny.gui.widgets.base_tree import BaseTreeModel, BaseTreeView, QWidget
from scrutiny.gui.widgets.watchable_tree import get_watchable_icon, WatchableStandardItem
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.tools.typing import *
from scrutiny import tools
from scrutiny.gui.core.gui_math_watchable import MathWatchable

from PySide6.QtWidgets import QHeaderView, QAbstractItemView
from PySide6.QtGui import QStandardItem


class Cols:
    ItemName = 0
    MathExpr = 1
    FQN = 1


class MathStandardItem(QStandardItem):
    def __init__(self, name: str) -> None:
        super().__init__()
        self.setText(name)
        self.setEditable(False)
        self.setIcon(get_watchable_icon(RegistryNodeType.Math))


class MathExprStandardItem(QStandardItem):
    def __init__(self, expr: str) -> None:
        super().__init__()
        self.setText(expr)
        self.setEditable(False)


class MathTreeModel(BaseTreeModel):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(nesting_col=0, parent=parent)

    def insert_math_element(self, math_element: MathWatchable) -> None:
        math_item = MathStandardItem(math_element.get_name())
        expr_item = MathExprStandardItem(math_element.get_expr())

        math_row = [math_item, expr_item]

        if not math_element.is_valid():
            raise ValueError("Math element is not valid")

        name_fqn_map = math_element.get_var_fqn_map()
        for name in sorted(name_fqn_map.keys()):
            fqn = name_fqn_map[name]
            if fqn is None:
                raise ValueError(f"No watchable element assigned to variable {name}")

            var_item = WatchableStandardItem(FQN.parse(fqn).node_type, name, fqn)
            var_item.setEditable(False)
            fqn_item = QStandardItem(fqn)
            fqn_item.setEditable(False)
            math_item.appendRow([var_item, fqn_item])

        self.appendRow(math_row)


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
