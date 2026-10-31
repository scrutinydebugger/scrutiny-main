#    test_math_builder_component.py
#        A test suite for the MathBuilder component
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import json
from dataclasses import dataclass

from PySide6.QtWidgets import QWidget
from test.gui.fake_server_manager import FakeServerManager
from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.components.globals.math_builder.math_element_tree import MathStandardItem, Cols
from scrutiny.gui.widgets.watchable_tree import FolderStandardItem
from scrutiny.gui.components.globals.math_builder.math_builder_component import MathBuilderComponent
from scrutiny.gui.core.watchable_registry.watchable_registry import WatchableRegistry
from scrutiny.gui.component_app_interface import AbstractComponentAppInterface
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.core.fqn_name_pair import FqnNamePair
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.sdk import WatchableType, BriefWatchableConfiguration, EmbeddedDataType


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


class TestMathBuilderComponent(ScrutinyBaseGuiTest):
    def setUp(self):
        super().setUp()

        self.main_window = MainWindowStub()
        app_interface = DummyAppInterface()
        app_interface.server_manager = self.main_window.get_server_manager()
        app_interface.watchable_registry = self.main_window.get_watchable_registry()
        self.builder = MathBuilderComponent(
            self.main_window,
            'mathbuilder',
            app_interface
        )
        self.builder.setup()

    def tearDown(self):
        self.builder.teardown()
        return super().tearDown()

    def _registry(self) -> WatchableRegistry:
        return self.main_window.registry

    def _make_math_watchable(self, name: str, expr: str, bindings: Dict[str, VarBinding]) -> GUIMathWatchable:
        """Creates a fully configured GUIMathWatchable. Bindings maps var_name to a VarBinding"""
        w = GUIMathWatchable(name=name, expr=expr)
        for var_name, binding in bindings.items():
            w.bind_watchable(var_name, FqnNamePair(binding.display_name, FQN.make(binding.node_type, binding.path)))
        return w

    def _add_to_registry(self, math_watchable: GUIMathWatchable) -> str:
        """Adds a math watchable to the registry and returns its FQN"""
        self._registry().add_math_watchable(math_watchable)
        self.process_events()
        return math_watchable.make_fqn()

    def _count_registry_math(self) -> int:
        return sum(1 for _ in self._registry().get_all_math_watchables())

    def test_add_math_watchable(self):
        w = self._make_math_watchable("magnitude", "sqrt(x^2+y^2)", {
            "x": VarBinding("var_x", RegistryNodeType.Variable, "/a/b/x"),
            "y": VarBinding("var_y", RegistryNodeType.Variable, "/a/b/y"),
        })

        self.builder.get_editor().load(w)
        self.builder.commit()

        self.assertEqual(self._count_registry_math(), 1)
        tree = self.builder.get_math_tree()
        self.assertEqual(tree.math_watchable_count(), 1)
        items = list(tree.model().iter_math_items())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].text(), "magnitude")

    def test_add_multiple_math_watchables(self):
        w1 = self._make_math_watchable("sum", "a+b", {
            "a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a"),
            "b": VarBinding("var_b", RegistryNodeType.Variable, "/a/b/b"),
        })
        w2 = self._make_math_watchable("diff", "a-b", {
            "a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a"),
            "b": VarBinding("var_b", RegistryNodeType.Variable, "/a/b/b"),
        })

        self.builder.get_editor().load(w1)
        self.builder.commit()
        self.builder.get_editor().load(w2)
        self.builder.commit()

        self.assertEqual(self._count_registry_math(), 2)
        self.assertEqual(self.builder.get_math_tree().math_watchable_count(), 2)

    def test_edit_math_watchable(self):
        w = self._make_math_watchable("sum", "a+b", {
            "a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a"),
            "b": VarBinding("var_b", RegistryNodeType.Variable, "/a/b/b"),
        })
        fqn = self._add_to_registry(w)

        self.builder.start_edit_by_fqn(fqn)
        self.assertIsNotNone(self.builder.get_watchable_being_edited_fqn())

        w2 = self._make_math_watchable("product", "a*b", {
            "a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a"),
            "b": VarBinding("var_b", RegistryNodeType.Variable, "/a/b/b"),
        })
        self.builder.get_editor().load(w2)
        self.builder.commit()

        self.assertEqual(self._count_registry_math(), 1)
        tree = self.builder.get_math_tree()
        self.assertEqual(tree.math_watchable_count(), 1)
        items = list(tree.model().iter_math_items())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].text(), "product")

    def test_remove_math_watchable(self):
        w1 = self._make_math_watchable("sum", "a+b", {
            "a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a"),
            "b": VarBinding("var_b", RegistryNodeType.Variable, "/a/b/b"),
        })
        w2 = self._make_math_watchable("diff", "a-b", {
            "a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a"),
            "b": VarBinding("var_b", RegistryNodeType.Variable, "/a/b/b"),
        })
        fqn1 = self._add_to_registry(w1)
        self._add_to_registry(w2)

        self.builder.remove_by_fqn({fqn1})
        self.process_events()

        self.assertEqual(self._count_registry_math(), 1)
        tree = self.builder.get_math_tree()
        self.assertEqual(tree.math_watchable_count(), 1)
        items = list(tree.model().iter_math_items())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].text(), "diff")

    def test_remove_while_editing_clears_editor(self):
        w = self._make_math_watchable("sum", "a+b", {
            "a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a"),
            "b": VarBinding("var_b", RegistryNodeType.Variable, "/a/b/b"),
        })
        fqn = self._add_to_registry(w)

        self.builder.start_edit_by_fqn(fqn)
        self.assertIsNotNone(self.builder.get_watchable_being_edited_fqn())

        self.builder.remove_by_fqn({fqn})
        self.process_events()

        self.assertIsNone(self.builder.get_watchable_being_edited_fqn())
        self.assertIsNone(self.builder.get_editor().get_if_fully_configured())
        self.assertEqual(self.builder.get_editor().var_count(), 0)

    def test_editor_load_updates_shared_variables(self):
        w1 = self._make_math_watchable("expr1", "a+b", {
            "a": VarBinding("var_x", RegistryNodeType.Variable, "/a/b/x"),
            "b": VarBinding("var_y", RegistryNodeType.Variable, "/a/b/y"),
        })
        w2 = self._make_math_watchable("expr2", "a+c", {
            "a": VarBinding("var_z", RegistryNodeType.Alias, "/a/b/z"),
            "c": VarBinding("var_w", RegistryNodeType.Variable, "/a/b/w"),
        })

        editor = self.builder.get_editor()
        editor.load(w1)
        self.assertEqual(editor.get_var_names(), {"a", "b"})

        editor.load(w2)
        self.assertEqual(editor.get_var_names(), {"a", "c"})

        result = editor.get_if_fully_configured()
        self.assertIsNotNone(result)
        var_map = result.get_var_fqn_map()
        self.assertEqual(var_map["a"].fqn, FQN.make(RegistryNodeType.Alias, "/a/b/z"))
        self.assertEqual(var_map["c"].fqn, FQN.make(RegistryNodeType.Variable, "/a/b/w"))

    def test_commit_without_full_config_does_nothing(self):
        w = GUIMathWatchable(name="incomplete", expr="a+b")
        self.builder.get_editor().load(w)
        self.builder.commit()

        self.assertEqual(self._count_registry_math(), 0)

    def test_update_availabilities_checks_all_rows(self):
        self._registry().write_server_content({
            WatchableType.Variable: {
                '/a/b/x': BriefWatchableConfiguration(WatchableType.Variable, EmbeddedDataType.float32, enum=None),

                '/a/b/y': BriefWatchableConfiguration(WatchableType.Variable, EmbeddedDataType.float32, enum=None),
            }
        })

        w1 = self._make_math_watchable("available_expr", "x+y", {
            "x": VarBinding("var_x", RegistryNodeType.Variable, "/a/b/x"),
            "y": VarBinding("var_y", RegistryNodeType.Variable, "/a/b/y"),
        })

        w2 = self._make_math_watchable("unavailable_expr", "p+q", {
            "p": VarBinding("var_p", RegistryNodeType.Variable, "/missing/p"),
            "q": VarBinding("var_q", RegistryNodeType.Variable, "/missing/q"),
        })

        self._add_to_registry(w1)
        self._add_to_registry(w2)

        tree = self.builder.get_math_tree()
        self.assertEqual(tree.math_watchable_count(), 2)

        tree.update_availabilities()

        model = tree.model()
        availabilities: Dict[str, bool] = {}
        for row in range(model.rowCount()):
            item = model.item(row, Cols.ItemOrVar)
            assert isinstance(item, MathStandardItem)
            availabilities[item.text()] = model.is_available(item)

        self.assertTrue(availabilities["available_expr"])
        self.assertFalse(availabilities["unavailable_expr"])

    def test_state_reload(self):
        w1 = self._make_math_watchable("magnitude", "sqrt(x^2+y^2)", {
            "x": VarBinding("var_x", RegistryNodeType.Variable, "/a/b/x"),
            "y": VarBinding("var_y", RegistryNodeType.Variable, "/a/b/y"),
        })
        w2 = self._make_math_watchable("sum", "a+b", {
            "a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a"),
            "b": VarBinding("var_b", RegistryNodeType.Alias, "/c/d/b"),
        })
        w3 = self._make_math_watchable("ratio", "p/q", {
            "p": VarBinding("var_p", RegistryNodeType.RuntimePublishedValue, "/rpv/p"),
            "q": VarBinding("var_q", RegistryNodeType.Variable, "/e/f/q"),
        })

        self._add_to_registry(w1)
        self._add_to_registry(w2)
        self._add_to_registry(w3)
        self.assertEqual(self._count_registry_math(), 3)

        # Get state and serialize to JSON
        state = self.builder.get_state()
        serialized = json.dumps(state)

        # Clear the registry
        self._registry().clear()
        self.process_events()
        self.assertEqual(self._count_registry_math(), 0)

        # Deserialize and reload
        deserialized = json.loads(serialized)
        result = self.builder.load_state(deserialized)
        self.process_events()

        self.assertTrue(result)
        self.assertEqual(self._count_registry_math(), 3)

        # Verify each math watchable is present with the correct content
        restored: Dict[str, GUIMathWatchable] = {}
        for _, mw in self._registry().get_all_math_watchables():
            restored[mw.get_name()] = mw

        self.assertEqual(set(restored.keys()), {"magnitude", "sum", "ratio"})

        self.assertEqual(restored["magnitude"].get_expr(), "sqrt(x^2+y^2)")
        mag_vars = restored["magnitude"].get_var_fqn_map()
        self.assertEqual(mag_vars["x"].fqn, FQN.make(RegistryNodeType.Variable, "/a/b/x"))
        self.assertEqual(mag_vars["y"].fqn, FQN.make(RegistryNodeType.Variable, "/a/b/y"))

        self.assertEqual(restored["sum"].get_expr(), "a+b")
        sum_vars = restored["sum"].get_var_fqn_map()
        self.assertEqual(sum_vars["a"].fqn, FQN.make(RegistryNodeType.Variable, "/a/b/a"))
        self.assertEqual(sum_vars["b"].fqn, FQN.make(RegistryNodeType.Alias, "/c/d/b"))

        self.assertEqual(restored["ratio"].get_expr(), "p/q")
        ratio_vars = restored["ratio"].get_var_fqn_map()
        self.assertEqual(ratio_vars["p"].fqn, FQN.make(RegistryNodeType.RuntimePublishedValue, "/rpv/p"))
        self.assertEqual(ratio_vars["q"].fqn, FQN.make(RegistryNodeType.Variable, "/e/f/q"))

    def test_edit_preserves_position_in_folder(self):
        # Build 3 math watchables: w1, w2 (target), w3
        bindings = {
            "a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a"),
            "b": VarBinding("var_b", RegistryNodeType.Variable, "/a/b/b"),
        }
        w1 = self._make_math_watchable("first", "a+b", bindings)
        w2 = self._make_math_watchable("middle", "a-b", bindings)
        w3 = self._make_math_watchable("last", "a*b", bindings)

        fqn1 = self._add_to_registry(w1)
        fqn2 = self._add_to_registry(w2)
        fqn3 = self._add_to_registry(w3)

        # Build tree: root > folder_outer > folder_inner > [w1, w2, w3]
        model = self.builder.get_math_tree().model()
        model.removeRows(0, model.rowCount())

        outer_row = model.make_folder_row("outer")
        model.add_row_to_parent(None, -1, outer_row)
        outer = outer_row[0]

        inner_row = model.make_folder_row("inner")
        model.add_row_to_parent(outer, -1, inner_row)
        inner = inner_row[0]

        model.append_math_watchable(w1, inner)
        model.append_math_watchable(w2, inner)
        model.append_math_watchable(w3, inner)

        self.assertEqual(model.math_watchable_count(), 3)

        # Edit w2 (the middle one) into a replacement
        self.builder.start_edit_by_fqn(fqn2)
        w2_replaced = self._make_math_watchable("replaced", "a/b", bindings)
        self.builder.get_editor().load(w2_replaced)
        self.builder.commit()
        self.process_events()

        # Tree count should match registry count
        self.assertEqual(self._count_registry_math(), 3)
        self.assertEqual(model.math_watchable_count(), 3)

        # The replaced item should be at row 1 inside inner, between first and last
        items_in_inner = [inner.child(i, Cols.ItemOrVar) for i in range(inner.rowCount())]
        math_items = [item for item in items_in_inner if isinstance(item, MathStandardItem)]
        self.assertEqual(len(math_items), 3)
        self.assertEqual(math_items[0].text(), "first")
        self.assertEqual(math_items[1].text(), "replaced")
        self.assertEqual(math_items[2].text(), "last")

    def test_state_reload_with_folders(self):
        # Create tree: root > [w1, folder_A > [w2, folder_B > [w3]]]
        bindings = {
            "a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a"),
            "b": VarBinding("var_b", RegistryNodeType.Variable, "/a/b/b"),
        }
        w1 = self._make_math_watchable("at_root", "a+b", bindings)
        w2 = self._make_math_watchable("in_A", "a-b", bindings)
        w3 = self._make_math_watchable("in_B", "a*b", bindings)

        self._add_to_registry(w1)
        self._add_to_registry(w2)
        self._add_to_registry(w3)

        model = self.builder.get_math_tree().model()
        model.removeRows(0, model.rowCount())

        model.append_math_watchable(w1)

        folder_a_row = model.make_folder_row("folder_A", expanded=True)
        model.add_row_to_parent(None, -1, folder_a_row)
        folder_a = folder_a_row[0]

        model.append_math_watchable(w2, folder_a)

        folder_b_row = model.make_folder_row("folder_B", expanded=False)
        model.add_row_to_parent(folder_a, -1, folder_b_row)
        folder_b = folder_b_row[0]

        model.append_math_watchable(w3, folder_b)

        # Expand folder_A so the expanded state is saved
        tree = self.builder.get_math_tree()
        tree.expand(folder_a.index())

        state = self.builder.get_state()
        serialized = json.dumps(state)

        # Clear and reload
        self._registry().clear()
        self.process_events()
        self.assertEqual(self._count_registry_math(), 0)

        deserialized = json.loads(serialized)
        result = self.builder.load_state(deserialized)
        self.process_events()

        self.assertTrue(result)
        self.assertEqual(self._count_registry_math(), 3)
        self.assertEqual(model.math_watchable_count(), 3)

        # Verify tree structure: root has 2 children (w1 + folder_A)
        nesting_col = model.nesting_col()
        self.assertEqual(model.rowCount(), 2)
        root_item0 = model.item(0, nesting_col)
        root_item1 = model.item(1, nesting_col)
        self.assertIsInstance(root_item0, MathStandardItem)
        self.assertEqual(root_item0.text(), "at_root")
        self.assertIsInstance(root_item1, FolderStandardItem)
        self.assertEqual(root_item1.text(), "folder_A")

        # folder_A has 2 children (w2 + folder_B)
        restored_a = root_item1
        math_children_a = []
        folder_children_a = []
        for i in range(restored_a.rowCount()):
            child = restored_a.child(i, nesting_col)
            if isinstance(child, MathStandardItem):
                math_children_a.append(child)
            elif isinstance(child, FolderStandardItem):
                folder_children_a.append(child)
        self.assertEqual(len(math_children_a), 1)
        self.assertEqual(math_children_a[0].text(), "in_A")
        self.assertEqual(len(folder_children_a), 1)
        self.assertEqual(folder_children_a[0].text(), "folder_B")

        # folder_B has 1 child (w3)
        restored_b = folder_children_a[0]
        self.assertEqual(restored_b.rowCount(), 1)
        child_in_b = restored_b.child(0, nesting_col)
        self.assertIsInstance(child_in_b, MathStandardItem)
        self.assertEqual(child_in_b.text(), "in_B")

    def _collect_tree_structure(self, parent: Optional[FolderStandardItem] = None) -> List[Dict[str, Any]]:
        """Walk the tree and return a list of dicts describing each node.
        Each dict has 'type' ('math' or 'folder'), 'name', and for folders 'children'."""
        model = self.builder.get_math_tree().model()
        nesting_col = model.nesting_col()
        if parent is None:
            count = model.rowCount()
            get_child = lambda i: model.item(i, nesting_col)
        else:
            count = parent.rowCount()
            get_child = lambda i: parent.child(i, nesting_col)

        result: List[Dict[str, Any]] = []
        for i in range(count):
            child = get_child(i)
            if isinstance(child, MathStandardItem):
                result.append({'type': 'math', 'name': child.text(), 'fqn': child.fqn})
            elif isinstance(child, FolderStandardItem):
                result.append({'type': 'folder', 'name': child.text(), 'children': self._collect_tree_structure(child)})
        return result

    def _collect_math_names_in_folder(self, tree_nodes: List[Dict[str, Any]], folder_path: List[str]) -> Set[str]:
        """Given a tree structure from _collect_tree_structure, navigate to folder_path and return math names found there."""
        nodes = tree_nodes
        for folder_name in folder_path:
            found = None
            for node in nodes:
                if node['type'] == 'folder' and node['name'] == folder_name:
                    found = node
                    break
            if found is None:
                return set()
            nodes = found['children']
        return {n['name'] for n in nodes if n['type'] == 'math'}

    def _collect_subfolder_names(self, tree_nodes: List[Dict[str, Any]], folder_path: List[str]) -> Set[str]:
        """Navigate to folder_path in the tree structure and return the names of child folders."""
        nodes = tree_nodes
        for folder_name in folder_path:
            found = None
            for node in nodes:
                if node['type'] == 'folder' and node['name'] == folder_name:
                    found = node
                    break
            if found is None:
                return set()
            nodes = found['children']
        return {n['name'] for n in nodes if n['type'] == 'folder'}

    def _setup_math_in_folders(self, watchables_by_folder: Dict[Optional[str], List[GUIMathWatchable]]) -> None:
        """Add math watchables to registry and arrange them in folders in the tree.
        Keys are folder names (None for root). All folders are at root level."""
        model = self.builder.get_math_tree().model()
        for folder_name, watchables in watchables_by_folder.items():
            for w in watchables:
                self._add_to_registry(w)

        # Clear tree and rebuild with folder structure
        model.removeRows(0, model.rowCount())
        for folder_name, watchables in watchables_by_folder.items():
            if folder_name is None:
                parent = None
            else:
                folder_row = model.make_folder_row(folder_name)
                model.add_row_to_parent(None, -1, folder_row)
                parent = folder_row[0]
            for w in watchables:
                model.append_math_watchable(w, parent)

    def test_export_reimport_identity(self):
        # Create math watchables organized in a folder structure:
        # root > [w1, folder_A > [w2, folder_B > [w3]]]
        bindings_xy = {
            "x": VarBinding("var_x", RegistryNodeType.Variable, "/a/b/x"),
            "y": VarBinding("var_y", RegistryNodeType.Variable, "/a/b/y"),
        }
        bindings_pq = {
            "p": VarBinding("var_p", RegistryNodeType.RuntimePublishedValue, "/rpv/p"),
            "q": VarBinding("var_q", RegistryNodeType.Variable, "/e/f/q"),
        }
        bindings_ab = {
            "a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a"),
            "b": VarBinding("var_b", RegistryNodeType.Alias, "/c/d/b"),
        }

        w1 = self._make_math_watchable("magnitude", "sqrt(x^2+y^2)", bindings_xy)
        w2 = self._make_math_watchable("ratio", "p/q", bindings_pq)
        w3 = self._make_math_watchable("sum", "a+b", bindings_ab)

        self._add_to_registry(w1)
        self._add_to_registry(w2)
        self._add_to_registry(w3)

        model = self.builder.get_math_tree().model()
        model.removeRows(0, model.rowCount())

        model.append_math_watchable(w1)

        folder_a_row = model.make_folder_row("folder_A", expanded=True)
        model.add_row_to_parent(None, -1, folder_a_row)
        folder_a = folder_a_row[0]
        model.append_math_watchable(w2, folder_a)

        folder_b_row = model.make_folder_row("folder_B", expanded=False)
        model.add_row_to_parent(folder_a, -1, folder_b_row)
        folder_b = folder_b_row[0]
        model.append_math_watchable(w3, folder_b)

        tree.expand(folder_a.index()) if (tree := self.builder.get_math_tree()) else None

        # Capture original state
        original_tree = self._collect_tree_structure()
        original_registry: Dict[str, GUIMathWatchable] = {}
        for _, mw in self._registry().get_all_math_watchables():
            original_registry[mw.get_name()] = mw

        # Export
        export_data = self.builder._get_math_export_def()
        serialized = json.dumps(export_data)

        # Clear and reimport (replace = clear + additive)
        deserialized = json.loads(serialized)
        self.builder._load_math_expressions_replace(deserialized)
        self.process_events()

        # Verify registry content is identical
        self.assertEqual(self._count_registry_math(), 3)
        restored_registry: Dict[str, GUIMathWatchable] = {}
        for _, mw in self._registry().get_all_math_watchables():
            restored_registry[mw.get_name()] = mw
        self.assertEqual(set(restored_registry.keys()), set(original_registry.keys()))

        for name in original_registry:
            orig = original_registry[name]
            rest = restored_registry[name]
            self.assertEqual(rest.get_name(), orig.get_name())
            self.assertEqual(rest.get_expr(), orig.get_expr())
            orig_vars = orig.get_var_fqn_map()
            rest_vars = rest.get_var_fqn_map()
            self.assertEqual(set(rest_vars.keys()), set(orig_vars.keys()))
            for var_name in orig_vars:
                self.assertEqual(rest_vars[var_name].fqn, orig_vars[var_name].fqn)
                self.assertEqual(rest_vars[var_name].name, orig_vars[var_name].name)

        # Verify tree structure is identical
        restored_tree = self._collect_tree_structure()
        self.assertEqual(len(restored_tree), len(original_tree))

        # Root level: w1 at root, folder_A
        root_math_names = {n['name'] for n in restored_tree if n['type'] == 'math'}
        root_folder_names = {n['name'] for n in restored_tree if n['type'] == 'folder'}
        self.assertEqual(root_math_names, {"magnitude"})
        self.assertEqual(root_folder_names, {"folder_A"})

        # folder_A contains w2 and folder_B
        math_in_a = self._collect_math_names_in_folder(restored_tree, ["folder_A"])
        folders_in_a = self._collect_subfolder_names(restored_tree, ["folder_A"])
        self.assertEqual(math_in_a, {"ratio"})
        self.assertEqual(folders_in_a, {"folder_B"})

        # folder_B contains w3
        math_in_b = self._collect_math_names_in_folder(restored_tree, ["folder_A", "folder_B"])
        self.assertEqual(math_in_b, {"sum"})

    def test_additive_import_three_sets_with_folder_merge(self):
        # Set 1: folder_A > [w1, w2], folder_B > [w3]
        # Set 2: folder_A > [w4], folder_C > [w5]        (folder_A overlaps)
        # Set 3: folder_A > folder_D > [w6], folder_B > [w7]  (folder_A and folder_B overlap)
        # Also include w1 again in set 3 to verify duplicates are skipped.
        bindings = {
            "a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a"),
            "b": VarBinding("var_b", RegistryNodeType.Variable, "/a/b/b"),
        }

        w1 = self._make_math_watchable("expr1", "a+b", bindings)
        w2 = self._make_math_watchable("expr2", "a-b", bindings)
        w3 = self._make_math_watchable("expr3", "a*b", bindings)
        w4 = self._make_math_watchable("expr4", "a/b", bindings)
        w5 = self._make_math_watchable("expr5", "a^b", bindings)
        w6 = self._make_math_watchable("expr6", "b-a", bindings)
        w7 = self._make_math_watchable("expr7", "b/a", bindings)

        model = self.builder.get_math_tree().model()

        # --- Build and export set 1 ---
        for w in [w1, w2, w3]:
            self._add_to_registry(w)
        model.removeRows(0, model.rowCount())

        fa1_row = model.make_folder_row("folder_A")
        model.add_row_to_parent(None, -1, fa1_row)
        model.append_math_watchable(w1, fa1_row[0])
        model.append_math_watchable(w2, fa1_row[0])

        fb1_row = model.make_folder_row("folder_B")
        model.add_row_to_parent(None, -1, fb1_row)
        model.append_math_watchable(w3, fb1_row[0])

        export1 = json.loads(json.dumps(self.builder._get_math_export_def()))

        # --- Clear and build set 2 ---
        self._registry().clear_all_math_content()
        model.removeRows(0, model.rowCount())
        self.process_events()

        for w in [w4, w5]:
            self._add_to_registry(w)
        model.removeRows(0, model.rowCount())

        fa2_row = model.make_folder_row("folder_A")
        model.add_row_to_parent(None, -1, fa2_row)
        model.append_math_watchable(w4, fa2_row[0])

        fc_row = model.make_folder_row("folder_C")
        model.add_row_to_parent(None, -1, fc_row)
        model.append_math_watchable(w5, fc_row[0])

        export2 = json.loads(json.dumps(self.builder._get_math_export_def()))

        # --- Clear and build set 3 (includes w1 duplicate) ---
        self._registry().clear_all_math_content()
        model.removeRows(0, model.rowCount())
        self.process_events()

        for w in [w1, w6, w7]:
            self._add_to_registry(w)
        model.removeRows(0, model.rowCount())

        fa3_row = model.make_folder_row("folder_A")
        model.add_row_to_parent(None, -1, fa3_row)

        fd_row = model.make_folder_row("folder_D")
        model.add_row_to_parent(fa3_row[0], -1, fd_row)
        model.append_math_watchable(w6, fd_row[0])
        # w1 is a duplicate from set 1
        model.append_math_watchable(w1, fa3_row[0])

        fb3_row = model.make_folder_row("folder_B")
        model.add_row_to_parent(None, -1, fb3_row)
        model.append_math_watchable(w7, fb3_row[0])

        export3 = json.loads(json.dumps(self.builder._get_math_export_def()))

        # --- Now clear everything and reimport one by one (additive) ---
        self._registry().clear_all_math_content()
        model.removeRows(0, model.rowCount())
        self.process_events()
        self.assertEqual(self._count_registry_math(), 0)

        stats1 = self.builder._load_math_expressions_additive(export1)
        self.process_events()
        self.assertFalse(stats1.has_error)
        self.assertEqual(self._count_registry_math(), 3)

        stats2 = self.builder._load_math_expressions_additive(export2)
        self.process_events()
        self.assertFalse(stats2.has_error)
        self.assertEqual(self._count_registry_math(), 5)

        stats3 = self.builder._load_math_expressions_additive(export3)
        self.process_events()
        self.assertFalse(stats3.has_error)
        # w1 is duplicated in set 3, so only w6 and w7 are new => 7 total
        self.assertEqual(self._count_registry_math(), 7)

        # Verify all 7 unique math watchables are present in the registry
        all_names: Set[str] = set()
        for _, mw in self._registry().get_all_math_watchables():
            all_names.add(mw.get_name())
        self.assertEqual(all_names, {"expr1", "expr2", "expr3", "expr4", "expr5", "expr6", "expr7"})

        # Verify tree structure: folders were merged, not duplicated
        tree_struct = self._collect_tree_structure()
        root_folder_names = {n['name'] for n in tree_struct if n['type'] == 'folder'}
        self.assertEqual(root_folder_names, {"folder_A", "folder_B", "folder_C"})

        # No root-level math items (everything is in folders)
        root_math_names = {n['name'] for n in tree_struct if n['type'] == 'math'}
        self.assertEqual(root_math_names, set())

        # folder_A should contain w1, w2 (set1), w4 (set2), folder_D > w6 (set3), and w1 duplicate skipped
        math_in_a = self._collect_math_names_in_folder(tree_struct, ["folder_A"])
        self.assertIn("expr1", math_in_a)
        self.assertIn("expr2", math_in_a)
        self.assertIn("expr4", math_in_a)
        # w1 duplicate should not appear twice in folder_A
        math_items_in_a_list = []
        for n in tree_struct:
            if n['type'] == 'folder' and n['name'] == 'folder_A':
                math_items_in_a_list = [c['name'] for c in n['children'] if c['type'] == 'math']
        self.assertEqual(len([n for n in math_items_in_a_list if n == "expr1"]), 1, "Duplicate expr1 should not appear twice")

        # folder_A > folder_D should contain w6
        math_in_d = self._collect_math_names_in_folder(tree_struct, ["folder_A", "folder_D"])
        self.assertEqual(math_in_d, {"expr6"})

        # folder_A should have exactly one folder_D subfolder (not duplicated)
        subfolders_in_a = self._collect_subfolder_names(tree_struct, ["folder_A"])
        self.assertEqual(subfolders_in_a, {"folder_D"})

        # folder_B should contain w3 (set1) and w7 (set3), merged
        math_in_b = self._collect_math_names_in_folder(tree_struct, ["folder_B"])
        self.assertEqual(math_in_b, {"expr3", "expr7"})

        # folder_C should contain w5
        math_in_c = self._collect_math_names_in_folder(tree_struct, ["folder_C"])
        self.assertEqual(math_in_c, {"expr5"})

        # Final check: total math items in tree matches registry
        self.assertEqual(self.builder.get_math_tree().math_watchable_count(), 7)

    def test_remove_folder_removes_contained_math(self):
        # Create tree: root > [w1, folder > [w2, w3]]
        bindings = {
            "a": VarBinding("var_a", RegistryNodeType.Variable, "/a/b/a"),
            "b": VarBinding("var_b", RegistryNodeType.Variable, "/a/b/b"),
        }
        w1 = self._make_math_watchable("outside", "a+b", bindings)
        w2 = self._make_math_watchable("inside1", "a-b", bindings)
        w3 = self._make_math_watchable("inside2", "a*b", bindings)

        self._add_to_registry(w1)
        self._add_to_registry(w2)
        self._add_to_registry(w3)

        model = self.builder.get_math_tree().model()
        model.removeRows(0, model.rowCount())

        model.append_math_watchable(w1)

        folder_row = model.make_folder_row("my_folder")
        model.add_row_to_parent(None, -1, folder_row)
        folder = folder_row[0]

        model.append_math_watchable(w2, folder)
        model.append_math_watchable(w3, folder)

        self.assertEqual(self._count_registry_math(), 3)
        self.assertEqual(model.math_watchable_count(), 3)

        # Remove the folder through the tree view
        tree = self.builder.get_math_tree()
        tree._handle_remove([folder])
        self.process_events()

        # w2 and w3 should be removed from registry, w1 should remain
        self.assertEqual(self._count_registry_math(), 1)
        self.assertEqual(model.math_watchable_count(), 1)
        remaining = list(model.iter_math_items())
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].text(), "outside")
