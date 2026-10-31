#    math_builder_component.py
#        A component where the user can view, edit and add GUIMathWatchables in the registry
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import logging
import json

from dataclasses import dataclass
from PySide6.QtWidgets import QVBoxLayout, QPushButton, QWidget, QHBoxLayout, QSplitter, QGroupBox
from PySide6.QtCore import Qt, QModelIndex, QItemSelection, SignalInstance, QItemSelectionModel
from PySide6.QtGui import QIcon, QStandardItem
from scrutiny.gui.widgets.feedback_label import FeedbackLabel
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable, GUIMathWatchableDictDef
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.core.watchable_registry.errors import WatchableRegistryError
from scrutiny.gui.components.globals.base_global_component import ScrutinyGUIBaseGlobalComponent
from scrutiny.gui.components.globals.math_builder.math_element_tree import MathTreeView, MathStandardItem
from scrutiny.gui.components.globals.math_builder.math_watchable_editor import MathWatchableEditor
from scrutiny.gui.widgets.watchable_tree import FolderStandardItem
from scrutiny.gui.themes import scrutiny_get_theme
from scrutiny.gui.tools import prompt
from scrutiny.gui import assets
from scrutiny import tools
from scrutiny.tools import validation
from scrutiny.tools.typing import *

MATH_EXPORT_FILE_EXT = '.scmat'


class State:
    MATH_WATCHABLE_KEY: Literal['math_watchables'] = 'math_watchables'
    TREE_KEY: Literal['math_tree'] = 'math_tree'
    MATH_DEFINITION_KEY: Literal['math_def'] = 'math_def'

    TYPE_FOLDER = 'f'
    TYPE_MATH_ELEMENT = 'm'

    KEY_TYPE: Literal['type'] = 'type'
    KEY_TEXT: Literal['txt'] = 'txt'
    KEY_FQN: Literal['fqn'] = 'fqn'
    KEY_ID: Literal['id'] = 'id'
    KEY_EXPANDED: Literal['expand'] = 'expand'
    KEY_CHILDREN: Literal['children'] = 'children'

    class MathElement(TypedDict):
        type: str
        id: str

    class Folder(TypedDict):
        type: str
        txt: str
        expand: bool
        children: List[Union["State.Folder", "State.MathElement"]]

    class MathDefinition(TypedDict):
        math_watchables: Dict[str, GUIMathWatchableDictDef]
        math_tree: List[Union["State.Folder", "State.MathElement"]]


@dataclass
class MathReloadStats:
    total: int = 0
    fail_count: int = 0
    has_error: bool = False


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
    _lbl_commit_error: FeedbackLabel

# region Public

    def reveal_fqn(self, fqn: str) -> None:
        item = self._math_tree.find_item_by_fqn(fqn)
        if item is None:
            return
        self._math_tree.collapseAll()
        # Expand path to item
        parents: List[FolderStandardItem] = []
        parent = item.parent()
        while parent is not None:
            if isinstance(parent, FolderStandardItem):
                parents.append(parent)
            parent = parent.parent()
        for p in reversed(parents):
            self._math_tree.expand(p.index())
        self._math_tree.selectionModel().setCurrentIndex(item.index(), QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)

# end region

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
        self._btn_close = QPushButton("Discard")
        self._btn_close.setEnabled(True)
        self._splitter = QSplitter(Qt.Orientation.Vertical)
        self._splitter.setContentsMargins(0, 0, 0, 0)
        self._lbl_commit_error = FeedbackLabel()

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
        lower_part_layout.addWidget(self._lbl_commit_error)

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
        self._show_editor(False)

    def teardown(self) -> None:
        for sig, slot in self._signals_connected:
            sig.disconnect(slot)
        self._signals_connected.clear()

    def visibilityChanged(self, visible: bool) -> None:
        pass

    def get_state(self) -> Dict[Any, Any]:
        return {
            State.MATH_DEFINITION_KEY: self._get_math_export_def()
        }

    def load_state(self, state: Dict[Any, Any]) -> bool:
        validation.assert_dict_key(state, State.MATH_DEFINITION_KEY, dict)
        math_def = cast(State.MathDefinition, state[State.MATH_DEFINITION_KEY])
        reload_stats = self._reload_math_export(math_def)
        return not reload_stats.has_error

    def export_math_to_file(self) -> None:
        filepath = prompt.get_save_filepath_from_last_save_dir(MATH_EXPORT_FILE_EXT, "Export math expression")
        if filepath is None:
            return

        try:
            math_export_data = self._get_math_export_def()
            with open(filepath, 'wb') as f:
                f.write(json.dumps(math_export_data).encode('utf8'))
        except Exception as e:
            prompt.exception_msgbox(e, "Failed", "Failed to export the math expressions")


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
        self._editor.validate()
        math_watchable = self._editor.get_if_fully_configured()
        if math_watchable is None:
            return

        try:
            if self._watchable_being_edited_fqn is None:
                self.app.watchable_registry.add_math_watchable(math_watchable)
            else:
                # Pre-place the new item at the old position so it keeps its spot in the tree
                self._math_tree.model().replace_math_item_by_fqn(self._watchable_being_edited_fqn, math_watchable)
                self.app.watchable_registry.update_math_watchable_fqn(self._watchable_being_edited_fqn, math_watchable)
            self._lbl_commit_error.clear()
            self._stop_edit_and_hide()
        except WatchableRegistryError as e:
            self._math_tree.sync_with_registry()
            self._lbl_commit_error.set_error(str(e))

    def start_edit_by_fqn(self, fqn: str) -> None:
        """Loads the math watchable identified by fqn into the editor for modification"""
        self._tree_edit_slot(fqn)

    def remove_by_fqn(self, fqns: Set[str]) -> None:
        """Removes math watchables identified by the given FQNs from the registry"""
        self._tree_remove_requested_slot(fqns)

# end region

# region Private

    def _get_math_export_def(self) -> State.MathDefinition:
        all_math = list(self.app.watchable_registry.get_all_math_watchables())
        fqn_to_key: Dict[str, str] = {}
        definitions: Dict[str, GUIMathWatchableDictDef] = {}
        for i, (signature, mw) in enumerate(all_math):
            key = str(i)
            fqn = FQN.make(RegistryNodeType.Math, signature)
            fqn_to_key[fqn] = key
            definitions[key] = mw.to_dict()

        return {
            State.MATH_WATCHABLE_KEY: definitions,
            State.TREE_KEY: list(self._get_tree_state_recursive(fqn_to_key=fqn_to_key))
        }

    def _reload_math_export(self, math_export: State.MathDefinition) -> MathReloadStats:
        stats = MathReloadStats()
        math_watchables: List[GUIMathWatchable] = []
        key_to_signature: Dict[str, str] = {}
        try:
            validation.assert_dict_key(math_export, State.MATH_WATCHABLE_KEY, dict)
            raw_definitions = math_export[State.MATH_WATCHABLE_KEY]
            for key, element in raw_definitions.items():
                stats.total += 1
                try:
                    mw = GUIMathWatchable.from_dict(element)
                    math_watchables.append(mw)
                    key_to_signature[key] = mw.signature()
                except Exception as e:
                    tools.log_exception(self.logger, e, "Failed to deserialize math watchable", str_level=logging.WARNING)
                    stats.has_error = True
                    stats.fail_count += 1

        except Exception as e:
            tools.log_exception(self.logger, e, "Failed to load math elements", str_level=logging.WARNING)
            stats.has_error = True

        to_add = [mw for mw in math_watchables if self.app.watchable_registry.get_math_watchable_node(mw.signature()) is None]
        self.app.watchable_registry.add_math_watchables(to_add)

        tree_data = math_export.get(State.TREE_KEY, None)
        if tree_data is not None and isinstance(tree_data, list):
            model = self._math_tree.model()
            model.removeRows(0, model.rowCount())
            referenced_fqns: Set[str] = set()
            try:
                self._load_tree_state_recursive(tree_data, None, referenced_fqns, key_to_signature)
            except Exception as e:
                tools.log_exception(self.logger, e, "Failed to load tree structure", str_level=logging.WARNING)
                stats.has_error = True

            # Add math watchables not referenced in the tree at root
            for _, mw in self.app.watchable_registry.get_all_math_watchables():
                fqn = mw.make_fqn()
                if fqn not in referenced_fqns:
                    model.append_math_watchable(mw)

            self._expand_saved_folders()
        else:
            self._math_tree.sync_with_registry()

        return stats

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
        self.commit()

    def _btn_close_clicked_slot(self) -> None:
        """Clears the editor and hides it"""
        self._stop_edit_and_hide()

    def _selection_changed_slot(self, selected: QItemSelection, deselected: QItemSelection) -> None:
        """Enables/disables the Edit button based on the tree selection"""
        selected_math = self._math_tree.selected_math_items()
        self._btn_edit.setEnabled(len(selected_math) == 1)

    def _edit_content_changed_slot(self) -> None:
        """Enables/disables the Commit button based on editor completeness"""
        m = self._editor.get_if_fully_configured()
        self._btn_commit.setEnabled(m is not None)

    def _btn_edit_clicked_slot(self) -> None:
        """Loads the selected math watchable into the editor"""
        selected = self._math_tree.selected_math_items()
        if len(selected) != 1:
            return

        math_item = selected[0]
        math_watchable = self.app.watchable_registry.get_watchable_node_fqn(math_item.fqn)
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
                self._stop_edit_and_hide()

    def _start_edit(self, math_watchable: GUIMathWatchable) -> None:
        """Loads a math watchable into the editor and tracks it for update on commit"""
        self._editor.load(math_watchable)
        self._watchable_being_edited_fqn = FQN.make(RegistryNodeType.Math, math_watchable.signature())
        self._lbl_commit_error.clear()
        self._show_editor(True)

    def _stop_edit(self) -> None:
        """Clears the editor and resets the edit tracking state"""
        self._editor.clear()
        self._lbl_commit_error.clear()
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

    def _get_tree_state_recursive(self,
                                  fqn_to_key: Dict[str, str],
                                  parent: Optional[FolderStandardItem] = None
                                  ) -> Generator[Union[State.Folder, State.MathElement], None, None]:
        """Walk the tree and produce a serializable state representation"""
        model = self._math_tree.model()
        nesting_col = model.nesting_col()
        if parent is None:
            row_count = model.rowCount()
            get_child: Callable[[int], Optional[QStandardItem]] = lambda i: model.item(i, nesting_col)
        else:
            row_count = parent.rowCount()
            get_child = lambda i: parent.child(i, nesting_col)

        for i in range(row_count):
            child = get_child(i)
            if isinstance(child, MathStandardItem):
                key = fqn_to_key.get(child.fqn)
                if key is not None:
                    yield State.MathElement(type=State.TYPE_MATH_ELEMENT, id=key)
            elif isinstance(child, FolderStandardItem):
                yield State.Folder(
                    type=State.TYPE_FOLDER,
                    txt=child.text(),
                    expand=self._math_tree.isExpanded(child.index()),
                    children=list(self._get_tree_state_recursive(fqn_to_key, child))
                )

    def _load_tree_state_recursive(self,
                                   tree_data: List[Union[State.Folder, State.MathElement]],
                                   parent: Optional[QStandardItem],
                                   referenced_fqns: Set[str],
                                   key_to_signature: Dict[str, str]) -> None:
        """Rebuild the tree from a saved state"""
        model = self._math_tree.model()
        for node in tree_data:
            node_type = node.get(State.KEY_TYPE)
            if node_type == State.TYPE_MATH_ELEMENT:
                math_node = cast(State.MathElement, node)
                signature: Optional[str] = None
                key = math_node.get(State.KEY_ID)
                if key is not None:
                    signature = key_to_signature.get(key)
                if signature is None:
                    continue
                mw = self.app.watchable_registry.get_math_watchable_node(signature)
                if mw is None:
                    continue
                referenced_fqns.add(mw.make_fqn())
                model.append_math_watchable(mw, parent)
            elif node_type == State.TYPE_FOLDER:
                folder_node = cast(State.Folder, node)
                text = folder_node.get(State.KEY_TEXT, "Folder")
                expanded = folder_node.get(State.KEY_EXPANDED, False)
                if not isinstance(expanded, bool):
                    expanded = False
                folder_row = model.make_folder_row(text, expanded=expanded)
                model.add_row_to_parent(parent, -1, folder_row)
                folder_item = folder_row[0]
                children = folder_node.get(State.KEY_CHILDREN, [])
                if isinstance(children, list):
                    self._load_tree_state_recursive(children, folder_item, referenced_fqns, key_to_signature)

    def _expand_saved_folders(self, parent: Optional[QStandardItem] = None) -> None:
        """Expand all folders that were saved as expanded"""
        model = self._math_tree.model()
        nesting_col = model.nesting_col()
        if parent is None:
            count = model.rowCount()
            get_child: Callable[[int], Optional[QStandardItem]] = lambda i: model.item(i, nesting_col)
        else:
            count = parent.rowCount()
            get_child = lambda i: parent.child(i, nesting_col)

        for i in range(count):
            child = get_child(i)
            if isinstance(child, FolderStandardItem):
                if child.is_expanded():
                    self._math_tree.expand(child.index())
                self._expand_saved_folders(child)

# end region
