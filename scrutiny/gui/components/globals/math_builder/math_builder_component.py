
from PySide6.QtWidgets import QVBoxLayout, QPushButton, QWidget, QHBoxLayout, QSplitter, QGroupBox
from PySide6.QtCore import Qt
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
    _btn_clear: QPushButton
    _splitter: QSplitter
    _uid_being_edited: Optional[int]

    def setup(self) -> None:
        self._math_tree = MathTreeView()
        self._editor = MathWatchableEditor()
        self._btn_new = QPushButton("New")
        self._btn_edit = QPushButton("Edit")
        self._btn_commit = QPushButton("Commit")
        self._btn_clear = QPushButton("Clear")
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
        lower_button_container_layout.addWidget(self._btn_clear)

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

        self._btn_new.clicked.connect(self._btn_new_clicked_slot)
        self._btn_edit.clicked.connect(self._btn_edit_clicked_slot)
        self._btn_commit.clicked.connect(self._btn_commit_clicked_slot)
        self._btn_clear.clicked.connect(self._btn_clear_clicked_slot)

    def ready(self) -> None:
        self._show_editor(False)

    def teardown(self) -> None:
        pass

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
        math_watchable = self._editor.get_if_fully_configured()
        if math_watchable is None:
            return

        if self._uid_being_edited is not None:
            self._math_tree.replace_math_watchable(self._uid_being_edited, math_watchable)
        else:
            self._math_tree.insert_math_watchable(math_watchable)

        self._show_editor(False)

    def _btn_clear_clicked_slot(self) -> None:
        self._editor.clear()
        self._uid_being_edited = None
        self._show_editor(False)

    def _btn_edit_clicked_slot(self) -> None:
        selected_indexes = self._math_tree.selectedIndexes()
        selected_roots_one_per_row = [index for index in selected_indexes if index.column() == 0 and not index.parent().isValid()]

        if len(selected_roots_one_per_row) != 1:
            return

        index = selected_roots_one_per_row[0]
        data = self._math_tree.extract_math_watchable(index.row())
        if data is None:
            return

        self._editor.load(data.math_watchable)
        self._uid_being_edited = data.uid
        self._show_editor(True)
