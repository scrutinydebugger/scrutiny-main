from PySide6.QtWidgets import QWidget, QLineEdit, QFormLayout, QVBoxLayout, QGroupBox, QLabel
from PySide6.QtCore import Qt
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny.gui.widgets.watchable_line_edit import WatchableLineEdit
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.tools.typing import *


class MathWatchableEditor(QWidget):
    _txt_name: QLineEdit
    _txt_expr: QLineEdit
    _lbl_expr_validity: FeedbackLabel
    _varlist_gb: QGroupBox
    _variable_list_form_layout: QFormLayout
    _var_to_wlineedit_map: Dict[str, WatchableLineEdit]

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._var_to_wlineedit_map = {}

        self._txt_name = QLineEdit()
        self._txt_name.setPlaceholderText("Name")
        self._txt_expr = QLineEdit()
        self._txt_expr.setPlaceholderText("e.g. sqrt(a^2+b^2)")
        self._lbl_expr_validity = FeedbackLabel()

        name_expr_section = QWidget()
        name_expr_section_layout = QFormLayout(name_expr_section)
        name_expr_section_layout.addRow("Name", self._txt_name)
        name_expr_section_layout.addRow("Expression", self._txt_expr)
        name_expr_section_layout.addRow(QLabel(""), self._lbl_expr_validity)  # Empty row label causes sizing issues

        self._varlist_gb = QGroupBox("Variables")
        self._variable_list_form_layout = QFormLayout(self._varlist_gb)
        self._variable_list_form_layout.setLabelAlignment(Qt.AlignRight)

        layout = QVBoxLayout(self)
        layout.addWidget(name_expr_section)
        layout.addWidget(self._varlist_gb)
        layout.addStretch(1)

        self._txt_expr.textChanged.connect(self._expr_changed_slot)
        self._txt_expr.editingFinished.connect(self._expr_edit_slot)

        self._update_visibility()

    def _update_visibility(self) -> None:
        self._varlist_gb.setVisible(len(self._var_to_wlineedit_map) > 0)

    def _update_feedback(self, watchable: GUIMathWatchable) -> None:
        if len(watchable.get_expr()) == 0:
            self._lbl_expr_validity.clear()
        elif watchable.is_valid():
            self._lbl_expr_validity.set_success("Expression is valid!")
        else:
            error = "Invalid expression"
            details = watchable.get_error()
            if details is not None:
                error += " - " + details

            self._lbl_expr_validity.set_error(error)

    def _expr_changed_slot(self) -> None:
        self._lbl_expr_validity.clear()

    def _expr_edit_slot(self) -> None:
        w = GUIMathWatchable(name=self._txt_name.text(), expr=self._txt_expr.text())
        self.load(w)

    def _add_var_row(self, var_name: str) -> Optional[WatchableLineEdit]:
        if var_name in self._var_to_wlineedit_map:
            return None

        wline_edit = WatchableLineEdit()
        wline_edit.set_text_mode_enabled(False)
        wline_edit.set_allowed_types([RegistryNodeType.Alias, RegistryNodeType.RuntimePublishedValue, RegistryNodeType.Variable])
        self._var_to_wlineedit_map[var_name] = wline_edit
        label = QLabel(var_name)
        label.setAlignment(Qt.AlignmentFlag.AlignRight)
        label.setMinimumWidth(30)
        self._variable_list_form_layout.addRow(label, wline_edit)

        return wline_edit

    def _remove_var_row(self, var_name: str) -> None:
        if var_name not in self._var_to_wlineedit_map:
            return

        wline_edit = self._var_to_wlineedit_map[var_name]
        for i in range(self._variable_list_form_layout.rowCount()):
            item = self._variable_list_form_layout.itemAt(i, QFormLayout.ItemRole.FieldRole)
            if item is not None and item.widget() is wline_edit:
                self._variable_list_form_layout.removeRow(i)
                break
        del self._var_to_wlineedit_map[var_name]

    def clear(self, keep_vars: Optional[Set[str]] = None) -> None:
        self._txt_name.clear()
        self._txt_expr.clear()

        if keep_vars is None:
            keep_vars = set()

        vars = set(self._var_to_wlineedit_map.keys())
        for varname in vars:
            if varname in keep_vars:
                continue
            self._remove_var_row(varname)

        self._update_visibility()

    def load(self, math_watchable: GUIMathWatchable) -> None:
        self.clear(keep_vars=set(math_watchable.get_vars()))

        self._txt_name.setText(math_watchable.get_name())
        self._txt_expr.setText(math_watchable.get_expr())

        for var_name, fqn_name in math_watchable.get_var_fqn_map().items():
            wline_edit = self._add_var_row(var_name)
            if wline_edit is None:  # Already there
                continue

            if fqn_name is not None:    # Something to be bound to
                parsed_fqn = FQN.parse(fqn_name.fqn)
                wline_edit.set_watchable_mode(node_type=parsed_fqn.node_type, path=parsed_fqn.path, name=fqn_name.name)

        self._update_feedback(math_watchable)
        self._update_visibility()

    def get_if_fully_configured(self) -> Optional[GUIMathWatchable]:
        name = self._txt_name.text()
        expr = self._txt_expr.text()

        if len(name) == 0 or len(expr) == 0:
            return None

        gui_math_watchable = GUIMathWatchable(name=name, expr=expr)

        if not gui_math_watchable.is_valid():
            return None

        for var_name, wline_edit in self._var_to_wlineedit_map.items():
            try:
                fqn_name = wline_edit.get_watchable()
                if fqn_name is None:
                    return None
                gui_math_watchable.bind_watchable(var_name, fqn_name)
            except Exception as e:
                return None

        if not gui_math_watchable.is_fully_configured():
            return None

        return gui_math_watchable
