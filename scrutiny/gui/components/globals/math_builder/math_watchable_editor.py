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
    _txt_expr: ValidableLineEdit
    _lbl_expr_validity: FeedbackLabel
    _varlist_gb: QGroupBox
    _variable_list_form_layout: QFormLayout
    _var_to_wlineedit_map: Dict[str, WatchableLineEdit]
    _signals: _Signals
    _inhibit_change_signal: bool

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._signals = self._Signals()
        self._var_to_wlineedit_map = {}
        self._inhibit_change_signal = False

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
        self._txt_name.textChanged.connect(self._name_edit_slot)

        self._txt_name.editingFinished.connect(self._maybe_emit_content_changed)
        self._txt_expr.editingFinished.connect(self._maybe_emit_content_changed)

        self._update_visibility()

    @property
    def signals(self) -> _Signals:
        return self._signals

    def _maybe_emit_content_changed(self) -> None:
        if not self._inhibit_change_signal:
            self._signals.content_changed.emit()

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
        self._lbl_expr_validity.clear()

    def _expr_edit_slot(self) -> None:
        w = GUIMathWatchable(name=self._txt_name.text(), expr=self._txt_expr.text())
        self.load(w)

    def _name_edit_slot(self) -> None:
        self._txt_name.validate_expect_not_wrong()

    def _add_var_row(self, var_name: str) -> Optional[WatchableLineEdit]:
        if var_name in self._var_to_wlineedit_map:
            return None

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

        if not self._inhibit_change_signal:
            self._signals.content_changed.emit()

        return wline_edit

    def clear(self, no_change_event: bool = False) -> None:
        changed = False
        self._inhibit_change_signal = True

        if len(self._txt_name.text()) > 0:
            changed = True
        self._txt_name.clear()

        if len(self._txt_expr.text()) > 0:
            changed = True
        self._txt_expr.clear()

        if len(self._var_to_wlineedit_map) > 0:
            changed = True

        self._inhibit_change_signal = False

        for wline_edit in self._var_to_wlineedit_map.values():
            wline_edit.signals.watchable_cleared.disconnect()
            wline_edit.signals.watchable_dropped.disconnect()
        while self._variable_list_form_layout.rowCount() > 0:
            self._variable_list_form_layout.removeRow(0)
        self._var_to_wlineedit_map.clear()

        self._update_visibility()

        if changed and not no_change_event:
            self._signals.content_changed.emit()

    def load(self, math_watchable: GUIMathWatchable) -> None:
        self.clear(no_change_event=True)
        self._inhibit_change_signal = True

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

        self._inhibit_change_signal = False
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
            wline_edit.set_error_state()

        return valid

    def _watchable_line_edit_changed_slot(self, wline_edit: WatchableLineEdit, fqn: str) -> None:
        wline_edit.set_default_state()
        self._signals.content_changed.emit()
