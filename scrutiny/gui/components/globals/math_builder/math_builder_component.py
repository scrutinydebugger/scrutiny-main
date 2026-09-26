
from PySide6.QtWidgets import QVBoxLayout, QPushButton, QWidget, QHBoxLayout, QSplitter, QGroupBox
from PySide6.QtCore import Qt, QModelIndex, QItemSelection, SignalInstance
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent
from scrutiny.gui.components.globals.math_builder.math_element_tree import MathTreeView
from scrutiny.gui.components.globals.math_builder.math_watchable_editor import MathWatchableEditor

from scrutiny.tools.typing import *


class MathBuilderComponent(ScrutinyGUIBaseGlobalComponent):

    _math_tree: MathTreeView
    _editor: MathWatchableEditor
    _btn_new: QPushButton
    _btn_edit: QPushButton
    _btn_commit: QPushButton
    _btn_close: QPushButton
    _splitter: QSplitter
    _uid_being_edited: Optional[int]

    _signals_connected: List[Tuple[SignalInstance, object]]

    def setup(self) -> None:
        self._signals_connected = []
        self._math_tree = MathTreeView()
        self._editor = MathWatchableEditor()
        self._btn_new = QPushButton("New")
        self._btn_new.setEnabled(True)
        self._btn_edit = QPushButton("Edit")
        self._btn_edit.setEnabled(False)
        self._btn_commit = QPushButton("Commit")
        self._btn_commit.setEnabled(False)
        self._btn_close = QPushButton("Close")
        self._btn_close.setEnabled(True)
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setContentsMargins(0, 0, 0, 0)

        upper_button_container = QWidget()
        upper_button_container_layout = QHBoxLayout(upper_button_container)
        upper_button_container_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        upper_button_container_layout.addWidget(self._btn_new)
        upper_button_container_layout.addWidget(self._btn_edit)

        lower_button_container = QWidget()
        lower_button_container_layout = QHBoxLayout(lower_button_container)
        lower_button_container_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
        lower_button_container_layout.addWidget(self._btn_commit)
        lower_button_container_layout.addWidget(self._btn_close)

        upper_part = QWidget()
        upper_part_layout = QVBoxLayout(upper_part)
        upper_part_layout.setContentsMargins(0, 0, 0, 0)
        upper_part_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        upper_part_layout.addWidget(self._math_tree)
        upper_part_layout.addWidget(upper_button_container)

        lower_part = QGroupBox("Editor")
        lower_part_layout = QVBoxLayout(lower_part)
        lower_part_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        lower_part_layout.addWidget(self._editor)
        lower_part_layout.addWidget(lower_button_container)

        self._splitter.addWidget(upper_part)
        self._splitter.addWidget(lower_part)

        self._splitter.setCollapsible(0, False)
        self._splitter.setCollapsible(1, True)

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self._splitter)

        self._connect_signal(self._btn_new.clicked, self._btn_new_clicked_slot)
        self._connect_signal(self._btn_edit.clicked, self._btn_edit_clicked_slot)
        self._connect_signal(self._btn_commit.clicked, self._btn_commit_clicked_slot)
        self._connect_signal(self._btn_close.clicked, self._btn_close_clicked_slot)
        self._connect_signal(self._math_tree.selectionModel().selectionChanged, self._selection_changed_slot)
        self._connect_signal(self._math_tree.signals.edit_requested, self._tree_edit_slot)
        self._connect_signal(self._math_tree.signals.removed, self._tree_remove_slot)
        self._connect_signal(self._editor.signals.content_changed, self._edit_content_changed_slot)
        self._connect_signal(self.app.server_manager.signals.registry_changed, self._registry_changed_slot)

    def _connect_signal(self, sig: SignalInstance, slot: object) -> None:
        sig.connect(slot)
        self._signals_connected.append((sig, slot))

    def ready(self) -> None:
        self._show_editor(True)

    def teardown(self) -> None:
        for sig, slot in self._signals_connected:
            sig.disconnect(slot)

    def visibilityChanged(self, visible: bool) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {}

    def load_state(self, state: Dict[Any, Any]) -> bool:
        return True

    def _show_editor(self, val: bool) -> None:
        """Show or hide the left part of the splitter"""
        if val:
            self._splitter.handle(1).setEnabled(True)
            self._splitter.setHandleWidth(5)
            if self._splitter.sizes()[1] == 0:
                editor_height = self._editor.sizeHint().height()
                self._splitter.setSizes([self.height() - editor_height, editor_height])
            self._splitter.setCollapsible(1, False)
        else:
            self._splitter.setCollapsible(1, True)
            self._splitter.setHandleWidth(0)
            self._splitter.setSizes([1, 0])
            self._splitter.handle(1).setEnabled(False)

    def _btn_new_clicked_slot(self) -> None:
        self._editor.clear()
        self._uid_being_edited = None
        self._show_editor(True)

    def _btn_commit_clicked_slot(self) -> None:
        # TODO:
        # Presently insert in the math tree.
        # Need to insert in the registry and leave the tree get updated by it
        self._editor.validate()
        math_watchable = self._editor.get_if_fully_configured()
        if math_watchable is None:
            return

        if self._uid_being_edited is not None:
            self._math_tree.replace_math_watchable(self._uid_being_edited, math_watchable)
        else:
            self._math_tree.insert_math_watchable(math_watchable)

        self._stop_edit()

    def _btn_close_clicked_slot(self) -> None:
        self._stop_edit_and_hide()

    def _selection_changed_slot(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        selected_math_watchables = self._get_selected_math_watchable_items()
        self._btn_edit.setEnabled(len(selected_math_watchables) == 1)

    def _edit_content_changed_slot(self) -> None:
        m = self._editor.get_if_fully_configured()
        self._btn_commit.setEnabled(m is not None)

    def _get_selected_math_watchable_items(self) -> List[QModelIndex]:
        selected_indexes = self._math_tree.selectedIndexes()
        return [index for index in selected_indexes if index.column() == 0 and not index.parent().isValid()]

    def _btn_edit_clicked_slot(self) -> None:
        selected = self._get_selected_math_watchable_items()
        if len(selected) != 1:
            return

        index = selected[0]
        data = self._math_tree.extract_math_watchable(index.row())
        if data is None:
            return

        self._start_edit(data.math_watchable, data.uid)

    def _tree_edit_slot(self, math_watchable: GUIMathWatchable, uid: int) -> None:
        self._start_edit(math_watchable, uid)

    def _tree_remove_slot(self, uid_removed: Set[int]) -> None:
        if self._uid_being_edited is not None:
            if self._uid_being_edited in uid_removed:
                self._stop_edit_and_hide()

    def _start_edit(self, math_watchable: GUIMathWatchable, uid: int) -> None:
        self._editor.load(math_watchable)
        self._uid_being_edited = uid
        self._show_editor(True)

    def _stop_edit(self) -> None:
        self._editor.clear()
        self._uid_being_edited = None

    def _stop_edit_and_hide(self) -> None:
        self._stop_edit()
        self._show_editor(False)

    def _registry_changed_slot(self) -> None:
        self._update_availability()

    def _update_availability(self) -> None:
        pass
