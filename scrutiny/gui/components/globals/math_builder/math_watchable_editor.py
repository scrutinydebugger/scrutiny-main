#    math_watchable_editor.py
#        A widget allowing to define and edit a GUIMathWatchable from the UI.
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import functools
from PySide6.QtWidgets import QWidget, QFormLayout, QVBoxLayout, QGroupBox, QLabel
from PySide6.QtCore import Qt, QObject, Signal
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny.gui.widgets.watchable_line_edit import WatchableLineEdit
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.tools.validators import NotEmptyValidator
from scrutiny.gui.widgets.validable_line_edit import ValidableLineEdit

from scrutiny.tools.typing import *


class MathWatchableEditor(QWidget):

    class _Signals(QObject):
        content_changed = Signal()

    _txt_name: ValidableLineEdit
    """The display name editor"""
    _txt_expr: ValidableLineEdit
    """The mat expression editor"""
    _lbl_expr_validity: FeedbackLabel
    """A label to show if the expression is valid or not"""
    _varlist_gb: QGroupBox
    """Group box where the variables to bind are displayed"""
    _variable_list_form_layout: QFormLayout
    """Layout for the variable binding"""
    _var_to_wlineedit_map: Dict[str, WatchableLineEdit]
    """A dict mapping variable name to their WatchableLineEdit entry that hold the Watchable dragged by the user"""
    _signals: _Signals
    """The signals"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._signals = self._Signals()
        self._var_to_wlineedit_map = {}

        self._txt_name = ValidableLineEdit(soft_validator=NotEmptyValidator())
        self._txt_name.setPlaceholderText("Name")
        self._txt_expr = ValidableLineEdit(soft_validator=NotEmptyValidator())
        self._txt_expr.setPlaceholderText("e.g. sqrt(a^2+b^2)")
        self._lbl_expr_validity = FeedbackLabel()

        name_expr_section = QWidget()
        name_expr_section_layout = QFormLayout(name_expr_section)
        name_expr_section_layout.addRow("Name", self._txt_name)
        name_expr_section_layout.addRow("Expression", self._txt_expr)
        name_expr_section_layout.addRow(QLabel(""), self._lbl_expr_validity)  # Empty row label causes sizing issues

        self._varlist_gb = QGroupBox("Variables")
        self._variable_list_form_layout = QFormLayout(self._varlist_gb)
        self._variable_list_form_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(name_expr_section)
        layout.addWidget(self._varlist_gb)

        self._txt_expr.textChanged.connect(self._expr_changed_slot)
        self._txt_expr.editingFinished.connect(self._expr_edit_slot)
        self._txt_expr.returnPressed.connect(self._expr_edit_slot)
        self._txt_name.textChanged.connect(self._name_edit_slot)

        self._txt_name.editingFinished.connect(self._signals.content_changed)
        self._txt_expr.editingFinished.connect(self._signals.content_changed)
        self._txt_expr.returnPressed.connect(self._signals.content_changed)

        self._update_visibility()

# region Public
    @property
    def signals(self) -> _Signals:
        return self._signals

    def clear(self) -> None:
        changed = False

        if len(self._txt_name.text()) > 0:
            changed = True
        self._txt_name.clear()

        if len(self._txt_expr.text()) > 0:
            changed = True
        self._txt_expr.clear()

        if len(self._var_to_wlineedit_map) > 0:
            changed = True

        for varname in list(self._var_to_wlineedit_map.keys()):
            self._remove_var_row(varname)

        assert self._variable_list_form_layout.rowCount() == 0
        assert len(self._var_to_wlineedit_map) == 0

        self._update_visibility()

        if changed:
            self._signals.content_changed.emit()

    def load(self, math_watchable: GUIMathWatchable, keep_unset_var: bool = False) -> None:
        self._txt_name.setText(math_watchable.get_name())
        self._txt_expr.setText(math_watchable.get_expr())

        actual_vars = set(self._var_to_wlineedit_map.keys())
        var_fqn_map = math_watchable.get_var_fqn_map()
        new_vars = set(var_fqn_map.keys())
        to_remove_var = actual_vars - new_vars
        to_add_var = new_vars - actual_vars
        to_update_var = actual_vars & new_vars

        for var_name in to_remove_var:
            self._remove_var_row(var_name)

        for var_name in to_add_var:
            wline_edit = self._add_var_row(var_name)
            fqn_name_pair = var_fqn_map[var_name]
            if fqn_name_pair is not None:
                parsed_fqn = FQN.parse(fqn_name_pair.fqn)
                wline_edit.set_watchable_mode(node_type=parsed_fqn.node_type, string_id=parsed_fqn.path, name=fqn_name_pair.name)

        for var_name in to_update_var:
            fqn_name_pair = var_fqn_map[var_name]
            wline_edit = self._var_to_wlineedit_map[var_name]
            if fqn_name_pair is not None:
                parsed_fqn = FQN.parse(fqn_name_pair.fqn)
                wline_edit.set_watchable_mode(node_type=parsed_fqn.node_type, string_id=parsed_fqn.path, name=fqn_name_pair.name)
            else:
                if not keep_unset_var:
                    wline_edit.clear()

        self._update_feedback(math_watchable)
        self._update_visibility()

        self._signals.content_changed.emit()

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

    def validate(self) -> bool:
        valid = True

        if not self._txt_name.validate_expect_valid():
            valid = False
        if not self._txt_expr.validate_expect_valid():
            valid = False

        for wline_edit in self._var_to_wlineedit_map.values():
            if not wline_edit.is_watchable_mode():
                wline_edit.set_error_state()
                valid = False

        return valid

    def get_var_names(self) -> Set[str]:
        return set(self._var_to_wlineedit_map.keys())

    def var_count(self) -> int:
        return len(self._var_to_wlineedit_map)

# end region

# region Private
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
        self._txt_expr.validate_expect_not_wrong()
        if self._txt_expr.hasFocus() and len(self._txt_expr.text()) > 0:
            self._lbl_expr_validity.set_info("Press Enter to validate")
        else:
            self._lbl_expr_validity.clear()

    def _expr_edit_slot(self) -> None:
        w = GUIMathWatchable(name=self._txt_name.text(), expr=self._txt_expr.text())
        self.load(w, keep_unset_var=True)

    def _name_edit_slot(self) -> None:
        self._txt_name.validate_expect_not_wrong()

    def _add_var_row(self, var_name: str) -> WatchableLineEdit:
        if var_name in self._var_to_wlineedit_map:
            raise ValueError(f"Variable with name {var_name} already has a row")

        wline_edit = WatchableLineEdit()
        wline_edit.set_text_mode_enabled(False)
        wline_edit.set_allowed_types([RegistryNodeType.Alias, RegistryNodeType.RuntimePublishedValue, RegistryNodeType.Variable])
        wline_edit.signals.watchable_cleared.connect(functools.partial(self._watchable_line_edit_changed_slot, wline_edit))
        wline_edit.signals.watchable_dropped.connect(functools.partial(self._watchable_line_edit_changed_slot, wline_edit))
        self._var_to_wlineedit_map[var_name] = wline_edit
        label = QLabel(var_name)
        label.setAlignment(Qt.AlignmentFlag.AlignRight)
        label.setMinimumWidth(30)
        self._variable_list_form_layout.addRow(label, wline_edit)

        return wline_edit

    def _remove_var_row(self, var_name: str) -> None:
        if var_name not in self._var_to_wlineedit_map:
            raise ValueError(f"Variable with name {var_name} not in layout")

        wline_edit = self._var_to_wlineedit_map[var_name]
        row_to_delete: Optional[int] = None
        for row_index in range(self._variable_list_form_layout.rowCount()):
            item = self._variable_list_form_layout.itemAt(row_index, QFormLayout.ItemRole.FieldRole)
            assert item is not None
            widget = item.widget()
            if widget is wline_edit:
                row_to_delete = row_index

        if row_to_delete is None:
            raise ValueError(f"Could not find variable {var_name} in the layout.")

        wline_edit.signals.watchable_cleared.disconnect()
        wline_edit.signals.watchable_dropped.disconnect()
        self._variable_list_form_layout.removeRow(row_to_delete)
        del self._var_to_wlineedit_map[var_name]

    def _watchable_line_edit_changed_slot(self, wline_edit: WatchableLineEdit, fqn: str) -> None:
        wline_edit.set_default_state()
        self._signals.content_changed.emit()
# end region
