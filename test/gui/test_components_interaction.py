#    test_components_interaction.py
#        Tests for cross-component interactions (drag & drop between components)
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

from dataclasses import dataclass

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QModelIndex
from test.gui.fake_server_manager import FakeServerManager
from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.components.globals.math_builder.math_builder_component import MathBuilderComponent
from scrutiny.gui.components.globals.math_builder.math_element_tree import MathStandardItem, Cols
from scrutiny.gui.components.locals.watch.watch_component import WatchComponent
from scrutiny.gui.core.watchable_registry.watchable_registry import WatchableRegistry
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.core.fqn_name_pair import FqnNamePair
from scrutiny.gui.widgets.watchable_tree import WatchableStandardItem, FolderStandardItem

from scrutiny.tools.typing import *


@dataclass(frozen=True, slots=True)
class VarBinding:
    display_name: str
    node_type: RegistryNodeType
    path: str


class MainWindowStub(QWidget):
    def __init__(self):
        super().__init__()
        self.registry = WatchableRegistry()
        self.server_manager = FakeServerManager(self.registry)

    def get_server_manager(self):
        return self.server_manager

    def get_watchable_registry(self):
        return self.registry


class DummyAppInterface(AbstractComponentAppInterface):
    def reveal_source_from_fqn(self, fqn: str) -> None:
        pass


class TestMathBuilderToWatch(ScrutinyBaseGuiTest):

    def setUp(self):
        super().setUp()
        self.main_window = MainWindowStub()
        app_interface = DummyAppInterface()
        app_interface.server_manager = self.main_window.get_server_manager()
        app_interface.watchable_registry = self.main_window.get_watchable_registry()

        self.builder = MathBuilderComponent(self.main_window, 'mathbuilder', app_interface)
        self.builder.setup()

        self.watch = WatchComponent(self.main_window, 'watch1', app_interface)
        self.watch.setup()

    def tearDown(self):
        self.builder.teardown()
        self.watch.teardown()
        return super().tearDown()

    def _registry(self) -> WatchableRegistry:
        return self.main_window.registry

    def _make_math_watchable(self, name: str, expr: str, bindings: Dict[str, VarBinding]) -> GUIMathWatchable:
        w = GUIMathWatchable(name=name, expr=expr)
        for var_name, binding in bindings.items():
            w.bind_watchable(var_name, FqnNamePair(binding.display_name, FQN.make(binding.node_type, binding.path)))
        return w

    def _add_to_registry(self, math_watchable: GUIMathWatchable) -> str:
        self._registry().add_math_watchable(math_watchable)
        self.process_events()
        return math_watchable.make_fqn()

    def test_drag_math_item_to_watch(self):
        # Single math item drag produces a WatchableList that the watch can consume
        bindings = {"a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a")}
        w1 = self._make_math_watchable("expr1", "2*a", bindings)
        fqn1 = self._add_to_registry(w1)

        math_model = self.builder.get_math_tree().model()
        math_item = math_model.find_item_by_fqn(fqn1)
        self.assertIsNotNone(math_item)

        mime_data = math_model.mimeData([math_item.index()])

        watch_model = self.watch.internal_model_for_unit_test()
        result = watch_model.dropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, QModelIndex())
        self.assertTrue(result)
        self.assertEqual(watch_model.rowCount(), 1)

        dropped_item = watch_model.item(0, watch_model.nesting_col())
        self.assertIsInstance(dropped_item, WatchableStandardItem)
        self.assertEqual(dropped_item.fqn, fqn1)

    def test_drag_folder_with_math_items_to_watch(self):
        # Folder drag produces a FullTree that the watch can consume with structure preserved
        bindings = {"a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a")}
        w1 = self._make_math_watchable("expr1", "2*a", bindings)
        w2 = self._make_math_watchable("expr2", "3*a", bindings)

        self._add_to_registry(w1)
        self._add_to_registry(w2)

        math_model = self.builder.get_math_tree().model()
        math_model.removeRows(0, math_model.rowCount())

        folder_row = math_model.make_folder_row("my_folder")
        math_model.add_row_to_parent(None, -1, folder_row)
        folder = folder_row[0]

        math_model.append_math_watchable(w1, folder)
        math_model.append_math_watchable(w2, folder)

        mime_data = math_model.mimeData([folder.index()])

        watch_model = self.watch.internal_model_for_unit_test()
        result = watch_model.dropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, QModelIndex())
        self.assertTrue(result)

        # Watch should have 1 folder at root containing 2 watchables
        self.assertEqual(watch_model.rowCount(), 1)
        nesting_col = watch_model.nesting_col()
        dropped_folder = watch_model.item(0, nesting_col)
        self.assertIsInstance(dropped_folder, FolderStandardItem)
        self.assertEqual(dropped_folder.text(), "my_folder")
        self.assertEqual(dropped_folder.rowCount(), 2)

        child0 = dropped_folder.child(0, nesting_col)
        child1 = dropped_folder.child(1, nesting_col)
        self.assertIsInstance(child0, WatchableStandardItem)
        self.assertIsInstance(child1, WatchableStandardItem)
        self.assertEqual(child0.fqn, w1.make_fqn())
        self.assertEqual(child1.fqn, w2.make_fqn())

    def test_drag_nested_folders_to_watch(self):
        # Nested folder structure is preserved when dropped into watch
        bindings = {"a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a")}
        w1 = self._make_math_watchable("deep_expr", "2*a", bindings)
        self._add_to_registry(w1)

        math_model = self.builder.get_math_tree().model()
        math_model.removeRows(0, math_model.rowCount())

        outer_row = math_model.make_folder_row("outer")
        math_model.add_row_to_parent(None, -1, outer_row)
        outer = outer_row[0]

        inner_row = math_model.make_folder_row("inner")
        math_model.add_row_to_parent(outer, -1, inner_row)
        inner = inner_row[0]

        math_model.append_math_watchable(w1, inner)

        mime_data = math_model.mimeData([outer.index()])

        watch_model = self.watch.internal_model_for_unit_test()
        result = watch_model.dropMimeData(mime_data, Qt.DropAction.CopyAction, -1, 0, QModelIndex())
        self.assertTrue(result)

        # outer > inner > deep_expr
        nesting_col = watch_model.nesting_col()
        self.assertEqual(watch_model.rowCount(), 1)
        dropped_outer = watch_model.item(0, nesting_col)
        self.assertIsInstance(dropped_outer, FolderStandardItem)
        self.assertEqual(dropped_outer.text(), "outer")

        dropped_inner = dropped_outer.child(0, nesting_col)
        self.assertIsInstance(dropped_inner, FolderStandardItem)
        self.assertEqual(dropped_inner.text(), "inner")

        dropped_item = dropped_inner.child(0, nesting_col)
        self.assertIsInstance(dropped_item, WatchableStandardItem)
        self.assertEqual(dropped_item.fqn, w1.make_fqn())
