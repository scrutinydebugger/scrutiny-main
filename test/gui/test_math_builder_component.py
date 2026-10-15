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
from PySide6.QtCore import Qt, QModelIndex
from test.gui.fake_server_manager import FakeServerManager
from test.gui.base_gui_test import ScrutinyBaseGuiTest
from scrutiny.gui.components.globals.math_builder.math_element_tree import MathTreeModel, MathStandardItem, Cols
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
    def reveal_varlist_fqn(self, fqn: str) -> None:
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
        info = tree.get_math_watchable_info(0)
        self.assertIsNotNone(info)
        self.assertEqual(info[0], "magnitude")
        self.assertEqual(info[1], "sqrt(x^2+y^2)")

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
        info = tree.get_math_watchable_info(0)
        self.assertIsNotNone(info)
        self.assertEqual(info[0], "product")
        self.assertEqual(info[1], "a*b")

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
        info = tree.get_math_watchable_info(0)
        self.assertIsNotNone(info)
        self.assertEqual(info[0], "diff")

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
