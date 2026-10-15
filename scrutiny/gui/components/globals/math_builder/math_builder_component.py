#    math_builder_component.py
#        A component where the user can view, edit and add GUIMathWatchables in the registry
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import logging
from PySide6.QtWidgets import QVBoxLayout, QPushButton, QWidget, QHBoxLayout, QSplitter, QGroupBox
from PySide6.QtCore import Qt, QModelIndex, QItemSelection, SignalInstance
from PySide6.QtGui import QIcon
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent
from scrutiny.gui.components.globals.math_builder.math_element_tree import MathTreeView
from scrutiny.gui.components.globals.math_builder.math_watchable_editor import MathWatchableEditor
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui import assets
from scrutiny import tools
from scrutiny.tools.typing import *


class State:
    MATH_WATCHABLE_KEY = 'math_watchables'


class MathBuilderComponent(ScrutinyGUIBaseGlobalComponent):
    """A component that let the user edit the Math Watchables available in the registry"""
    _NAME = "Math Expressions"
    _TYPE_ID = "math"

    _math_tree: MathTreeView
    """The tree view showing what's in the registry"""
    _editor: MathWatchableEditor
    """An editor at the bottom of the component that can let the user modify or create a new math watchable"""
    _btn_new: QPushButton
    """Button to set the editor ready for a new insert"""
    _btn_edit: QPushButton
    """Button bring the content of a math watchable to the editor for modification"""
    _btn_commit: QPushButton
    """Button that save a new or overwrite an existing math watchable."""
    _btn_close: QPushButton
    """Button to hide the editor and clear it"""
    _splitter: QSplitter
    """The splitter that separate the tree view from the editor"""
    _watchable_being_edited_fqn: Optional[str]
    """A state variable keeping track of what registry entry was put in the editor for modification."""
    _signals_connected: List[Tuple[SignalInstance, object]]
    """A list of signals to disconnect in teardown"""

# region Overrides
    @classmethod
    def get_icon(cls) -> QIcon:
        return scrutiny_get_theme().load_medium_icon(assets.Icons.F_x)

    def setup(self) -> None:
        self._watchable_being_edited_fqn = None
        self._signals_connected = []
        self._math_tree = MathTreeView(self.app.watchable_registry)
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
        self._connect_signal(self._math_tree.signals.remove_requested, self._tree_remove_requested_slot)
        self._connect_signal(self._editor.signals.content_changed, self._edit_content_changed_slot)
        self._connect_signal(self.app.watchable_registry.signals.content_changed, self._registry_changed_slot)

    def ready(self) -> None:
        self._show_editor(True)

    def teardown(self) -> None:
        for sig, slot in self._signals_connected:
            sig.disconnect(slot)

    def visibilityChanged(self, visible: bool) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        all_math = [o[1] for o in self.app.watchable_registry.get_all_math_watchables()]
        return {
            State.MATH_WATCHABLE_KEY: [m.serialize() for m in all_math]
        }

    def load_state(self, state: Dict[Any, Any]) -> bool:
        all_good = True
        math_watchables: List[GUIMathWatchable] = []
        try:
            if State.MATH_WATCHABLE_KEY not in state:
                raise Exception(f"Missing key {State.MATH_WATCHABLE_KEY}")

            if not isinstance(state[State.MATH_WATCHABLE_KEY], list):
                raise Exception("Wrong data type")

            for element in state[State.MATH_WATCHABLE_KEY]:
                try:
                    math_watchables.append(GUIMathWatchable.deserialize(element))
                except Exception as e:
                    tools.log_exception(self.logger, e, "Failed to deserialize math watchable", str_level=logging.WARNING)
                    all_good = False

        except Exception as e:
            tools.log_exception(self.logger, e, "Failed to load math elements", str_level=logging.WARNING)
            all_good = False

        for math_watchable in math_watchables:
            existing_node = self.app.watchable_registry.get_math_watchable_node(math_watchable.signature())
            if existing_node is None:
                self.app.watchable_registry.add_math_watchable(math_watchable)

        return all_good

# end region

# region Getter for tests mainly

    def get_watchable_being_edited_fqn(self) -> Optional[str]:
        """Returns the FQN of the math watchable currently being edited, or None"""
        return self._watchable_being_edited_fqn

    def get_editor(self) -> MathWatchableEditor:
        """Returns the math watchable editor widget"""
        return self._editor

    def get_math_tree(self) -> MathTreeView:
        """Returns the tree view listing all math watchables"""
        return self._math_tree

    def commit(self) -> None:
        """Validates and commits the editor content to the registry"""
        self._btn_commit_clicked_slot()

    def start_edit_by_fqn(self, fqn: str) -> None:
        """Loads the math watchable identified by fqn into the editor for modification"""
        self._tree_edit_slot(fqn)

    def remove_by_fqn(self, fqns: Set[str]) -> None:
        """Removes math watchables identified by the given FQNs from the registry"""
        self._tree_remove_requested_slot(fqns)

# end region

# region Private

    def _connect_signal(self, sig: SignalInstance, slot: object) -> None:
        """Connects a signal to a slot and registers it for teardown disconnection"""
        sig.connect(slot)
        self._signals_connected.append((sig, slot))

    def _show_editor(self, val: bool) -> None:
        """Show or hide the lower part of the splitter"""
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
        """Clears the editor and prepares it for a new math watchable"""
        self._editor.clear()
        self._watchable_being_edited_fqn = None
        self._show_editor(True)

    def _btn_commit_clicked_slot(self) -> None:
        """Validates the editor and adds or updates the math watchable in the registry"""
        self._editor.validate()
        math_watchable = self._editor.get_if_fully_configured()
        if math_watchable is None:
            return

        if self._watchable_being_edited_fqn is None:
            self.app.watchable_registry.add_math_watchable(math_watchable)
        else:
            self.app.watchable_registry.update_math_watchable_fqn(self._watchable_being_edited_fqn, math_watchable)

        self._stop_edit()

    def _btn_close_clicked_slot(self) -> None:
        """Clears the editor and hides it"""
        self._stop_edit_and_hide()

    def _selection_changed_slot(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        """Enables/disables the Edit button based on the tree selection"""
        selected_math_watchables = self._get_selected_math_watchable_items()
        self._btn_edit.setEnabled(len(selected_math_watchables) == 1)

    def _edit_content_changed_slot(self) -> None:
        """Enables/disables the Commit button based on editor completeness"""
        m = self._editor.get_if_fully_configured()
        self._btn_commit.setEnabled(m is not None)

    def _get_selected_math_watchable_items(self) -> List[QModelIndex]:
        """Returns top-level selected indexes from the tree (column 0 only)"""
        selected_indexes = self._math_tree.selectedIndexes()
        return [index for index in selected_indexes if index.column() == 0 and not index.parent().isValid()]

    def _btn_edit_clicked_slot(self) -> None:
        """Loads the selected math watchable into the editor"""
        selected = self._get_selected_math_watchable_items()
        if len(selected) != 1:
            return

        index = selected[0]
        fqn = self._math_tree.get_fqn_from_row(index.row())
        if fqn is None:
            return
        math_watchable = self.app.watchable_registry.get_watchable_node_fqn(fqn)
        if math_watchable is None:
            self.logger.error("Math watchable is not in the registry.")
            return
        assert isinstance(math_watchable, GUIMathWatchable)

        self._start_edit(math_watchable)

    def _tree_edit_slot(self, fqn: str) -> None:
        """Slot for the tree's edit_requested signal; fetches and loads the watchable"""
        math_watchable = self.app.watchable_registry.get_watchable_node_fqn(fqn)
        if math_watchable is None:
            self.logger.error("Math watchable is not in the registry.")
            return
        assert isinstance(math_watchable, GUIMathWatchable)
        self._start_edit(math_watchable)

    def _tree_remove_requested_slot(self, fqn_to_remove: Set[str]) -> None:
        """Removes entries from registry and clears editor if the edited entry was removed"""
        self.app.watchable_registry.remove_math_watchable_list_fqn(fqn_to_remove)
        if self._watchable_being_edited_fqn is not None:
            if self._watchable_being_edited_fqn in fqn_to_remove:
                self._stop_edit()

    def _start_edit(self, math_watchable: GUIMathWatchable) -> None:
        """Loads a math watchable into the editor and tracks it for update on commit"""
        self._editor.load(math_watchable)
        self._watchable_being_edited_fqn = FQN.make(RegistryNodeType.Math, math_watchable.signature())
        self._show_editor(True)

    def _stop_edit(self) -> None:
        """Clears the editor and resets the edit tracking state"""
        self._editor.clear()
        self._watchable_being_edited_fqn = None

    def _stop_edit_and_hide(self) -> None:
        """Stops editing and collapses the editor panel"""
        self._stop_edit()
        self._show_editor(False)

    def _registry_changed_slot(self, node_types: List[RegistryNodeType]) -> None:
        """Syncs the tree when math watchables change in the registry"""
        if RegistryNodeType.Math in node_types:
            self._math_tree.sync_with_registry()
        self._update_availability()

    def _update_availability(self) -> None:
        self._math_tree.update_availabilities()

# end region
