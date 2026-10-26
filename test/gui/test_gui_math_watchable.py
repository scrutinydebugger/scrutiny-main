#    test_gui_math_watchable.py
#        A test suite for the GUIMathWatchable
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import math
from test import ScrutinyUnitTest
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.core.fqn_name_pair import FqnNamePair
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType
from scrutiny.core.basic_types import Watchable as core_Watchable, MathWatchable as core_MathWatchable, WatchableType
from scrutiny.sdk.datalogging import MathSignalConfig


class TestGUIMathWatchable(ScrutinyUnitTest):
    def test_no_vars(self):
        watchable = GUIMathWatchable('test', '1+2+3')
        self.assertTrue(watchable.is_valid())
        self.assertIsNone(watchable.get_val())
        self.assertEqual(watchable.eval(), 6)
        self.assertEqual(watchable.get_val(), 6)

    def test_with_single_var(self):
        watchable = GUIMathWatchable('test', '1+2+a')
        self.assertTrue(watchable.is_valid())
        watchable.bind_watchable("a", FqnNamePair('AAA', 'var:/a/b/c'))
        watchable.assign_var_value("a", 3)
        self.assertEqual(watchable.eval(), 6, watchable.get_error())
        self.assertEqual(watchable.get_val(), 6, watchable.get_error())

    def test_with_many_vars(self):
        watchable = GUIMathWatchable('test', '1+2+a*b+abs(-x)')
        self.assertTrue(watchable.is_valid())
        watchable.bind_watchable("a", FqnNamePair('AAA', 'var:/a/a/a'))
        watchable.bind_watchable("b", FqnNamePair('BBB', 'var:/a/a/b'))
        watchable.bind_watchable("x", FqnNamePair('XXX', 'var:/a/a/x'))

        watchable.assign_var_value("a", 10)
        watchable.assign_var_value_by_fqn("var:/a/a/b", 20)
        watchable.assign_var_value("x", 0.5)
        val = 1 + 2 + 10 * 20 + abs(-0.5)
        self.assertEqual(watchable.eval(), val, watchable.get_error())
        self.assertEqual(watchable.get_val(), val, watchable.get_error())

    def test_duplicate_fqn_is_fine(self):
        watchable = GUIMathWatchable('test', '1+2+a1*a2+abs(-x)')
        self.assertTrue(watchable.is_valid())
        watchable.bind_watchable("a1", FqnNamePair('AAA', 'var:/a/a/a'))
        watchable.bind_watchable("a2", FqnNamePair('BBB', 'var:/a/a/a'))
        watchable.bind_watchable("x", FqnNamePair('CCC', 'var:/a/a/x'))

        watchable.assign_var_value_by_fqn("var:/a/a/a", 10)
        watchable.assign_var_value("x", 0.5)
        val = 1 + 2 + 10 * 10 + abs(-0.5)
        self.assertEqual(watchable.eval(), val, watchable.get_error())
        self.assertEqual(watchable.get_val(), val, watchable.get_error())

    def test_cannot_bind_inexistant_fqn(self):
        watchable = GUIMathWatchable('test', 'a+b')
        self.assertTrue(watchable.is_valid())
        with self.assertRaises(Exception):
            watchable.bind_watchable("c", FqnNamePair('AAA', 'var:/a/a/a'))

    def test_cannot_assign_val_inexistent_var(self):
        watchable = GUIMathWatchable('test', 'a+b')
        self.assertTrue(watchable.is_valid())
        watchable.bind_watchable("a", FqnNamePair('AAA', 'var:/a/a/a'))
        watchable.bind_watchable("b", FqnNamePair('BBB', 'var:/a/a/b'))

        with self.assertRaises(Exception):
            watchable.assign_var_value("c", 1)

    def test_cannot_assign_val_inexistent_fqn(self):
        watchable = GUIMathWatchable('test', 'a+b')
        self.assertTrue(watchable.is_valid())
        watchable.bind_watchable("a", FqnNamePair('AAA', 'var:/a/a/a'))
        watchable.bind_watchable("b", FqnNamePair('BBB', 'var:/a/a/b'))

        with self.assertRaises(Exception):
            watchable.assign_var_value_by_fqn("var:/a/a/c", 0)

    def test_get_var_from_expr(self):
        watchable = GUIMathWatchable('test', '1+2+a1*a2+abs(-x)')
        self.assertTrue(watchable.is_valid())
        vars = watchable.get_vars()
        self.assertEqual(len(vars), 3)
        self.assertIn("a1", vars)
        self.assertIn("a2", vars)
        self.assertIn("x", vars)

    def test_rebind_is_allowed(self):
        watchable = GUIMathWatchable('test', '1+a')
        self.assertTrue(watchable.is_valid())
        watchable.bind_watchable("a", FqnNamePair('AAA', 'var:/a/a/a'))
        watchable.bind_watchable("a", FqnNamePair('BBB', 'var:/a/a/b'))
        watchable.bind_watchable("a", FqnNamePair("CCC", 'var:/a/a/c'))

    def test_variable_case_sensitive(self):
        watchable = GUIMathWatchable('test', '1+hElLo_World+aaa+AAA')
        self.assertTrue(watchable.is_valid())
        vars = watchable.get_vars()
        self.assertEqual(len(vars), 3)
        self.assertIn("hElLo_World", vars)
        self.assertIn("aaa", vars)
        self.assertIn("AAA", vars)

        watchable.bind_watchable("hElLo_World", FqnNamePair('AAA', 'var:/a/a/a'))
        watchable.bind_watchable("aaa", FqnNamePair('BBB', 'var:/a/a/b'))
        watchable.bind_watchable("AAA", FqnNamePair("CCC", 'var:/a/a/c'))

        watchable.assign_var_value("hElLo_World", 10)
        watchable.assign_var_value("aaa", 20)
        watchable.assign_var_value("AAA", 30)

        self.assertEqual(watchable.eval(), 1 + 10 + 20 + 30)

    def test_invalid_func(self):
        watchable = GUIMathWatchable("test", "1+potato(2)")
        self.assertFalse(watchable.is_valid())
        self.assertIsNone(watchable.eval())

    def test_constants_are_not_vars(self):
        watchable = GUIMathWatchable("test", "1+pi+x+y")
        self.assertTrue(watchable.is_valid())
        vars = watchable.get_vars()
        self.assertEqual(len(vars), 2)
        self.assertIn('x', vars)
        self.assertIn('y', vars)

    def test_func_are_case_insensitive(self):
        watchable = GUIMathWatchable("test", "1+sIn(0.5) - COS(2)")
        val = watchable.eval()
        self.assertIsNotNone(val)
        self.assertAlmostEqual(val, 1 + math.sin(0.5) - math.cos(2), 5)

    def test_eval_invalid_expr_returns_none_and_sets_error(self):
        watchable = GUIMathWatchable("test", "1+potato(2)")
        self.assertFalse(watchable.is_valid())
        self.assertIsNone(watchable.eval())
        self.assertIsNotNone(watchable.get_error())

    def test_operations_raise_on_invalid_expr(self):
        watchable = GUIMathWatchable("test", "1+potato(2)")
        self.assertFalse(watchable.is_valid())
        with self.assertRaises(ValueError):
            watchable.bind_watchable("a", FqnNamePair("CCC", "var:/a/b/c"))
        with self.assertRaises(ValueError):
            watchable.assign_var_value("a", 1)
        with self.assertRaises(ValueError):
            watchable.assign_var_value_by_fqn("var:/a/b/c", 1)

    def test_copy(self):
        watchable = GUIMathWatchable("test", "1+sin(x)-cos(y)")
        watchable.bind_watchable("x", FqnNamePair("XXX", "var:/aaa/bbb/ccc"))
        watchable.bind_watchable("y", FqnNamePair("YYY", "alias:/aaa/bbb/ccc"))

        watchable2 = watchable.copy()
        self.assertEqual(watchable2.get_name(), watchable.get_name())
        self.assertEqual(watchable2.get_expr(), watchable.get_expr())
        self.assertEqual(watchable2.get_var_fqn_map(), watchable.get_var_fqn_map())
        self.assertIsNot(watchable2, watchable)
        self.assertIsNot(watchable2.get_var_fqn_map(), watchable.get_var_fqn_map())

        watchable.assign_var_value('x', 1)
        watchable.assign_var_value('y', 2)
        watchable2.assign_var_value('x', 1)
        watchable2.assign_var_value('y', 2)

        self.assertEqual(watchable.eval(), watchable2.eval())

    def test_no_bind_math(self):
        watchable = GUIMathWatchable("test", "1+sin(x)-cos(y)")
        watchable.bind_watchable("x", FqnNamePair("xxx", FQN.make(RegistryNodeType.Variable, "/aaa/bbb/ccc")))
        with self.assertRaises(ValueError):
            watchable.bind_watchable("y", FqnNamePair("yyy", FQN.make(RegistryNodeType.Math, "/aaa/bbb/ccc")))

    def test_serialization(self):
        watchable = GUIMathWatchable('test', 'a+b')
        watchable.bind_watchable("a", FqnNamePair('AAA', 'var:/a/a/a'))
        watchable.bind_watchable("b", FqnNamePair('BBB', 'var:/a/a/b'))

        data = watchable.serialize()
        self.assertIsInstance(data, str)
        watchable2 = GUIMathWatchable.deserialize(data)
        self.assertEqual(watchable.get_name(), watchable2.get_name())
        self.assertEqual(watchable.get_expr(), watchable2.get_expr())
        self.assertEqual(watchable.get_var_fqn_map(), watchable2.get_var_fqn_map())

    def test_state_check(self):
        test1 = GUIMathWatchable('test1', 'x+++2')   # parsing error
        self.assertFalse(test1.is_valid())
        self.assertFalse(test1.is_fully_configured())
        self.assertFalse(test1.is_evaluable())

        test2 = GUIMathWatchable('test2', 'x+y')
        test2.bind_watchable("x", FqnNamePair("xxx", FQN.make(RegistryNodeType.Alias, "/aa/bb/cc")))

        self.assertTrue(test2.is_valid())
        self.assertFalse(test2.is_fully_configured())
        self.assertFalse(test2.is_evaluable())

        test3 = GUIMathWatchable('test3', 'x+y')
        test3.bind_watchable("x", FqnNamePair("xxx", FQN.make(RegistryNodeType.Alias, "/aa/bb/cc")))
        test3.bind_watchable("y", FqnNamePair("yyy", FQN.make(RegistryNodeType.Alias, "/aa/bb/dd")))

        self.assertTrue(test3.is_valid())
        self.assertTrue(test3.is_fully_configured())
        self.assertFalse(test3.is_evaluable())

        test3.assign_var_value("x", 1)
        self.assertFalse(test3.is_evaluable())
        self.assertIsNone(test3.eval())
        test3.assign_var_value("y", 2)
        self.assertTrue(test3.is_evaluable())
        self.assertIsNotNone(test3.eval())
        self.assertEqual(test3.get_val(), 3)

    def test_signature_ignores_whitespace(self):
        expressions = [
            "a + b * sin(x)",
            "a+b*sin(x)",
            "a +b* sin( x )",
            "  a  +  b  *  sin  (  x  )  ",
            "a+b*sin(x)  ",
            "  a+b*sin(x)",
            "a\t+\tb\t*\tsin(\tx\t)",
        ]

        fqn_a = FqnNamePair('AAA', 'var:/a/a/a')
        fqn_b = FqnNamePair('BBB', 'var:/a/a/b')
        fqn_x = FqnNamePair('XXX', 'var:/a/a/x')

        signatures = set()
        for expr in expressions:
            w = GUIMathWatchable('test', expr)
            self.assertTrue(w.is_valid(), f"Expression should be valid: '{expr}'")
            w.bind_watchable("a", fqn_a)
            w.bind_watchable("b", fqn_b)
            w.bind_watchable("x", fqn_x)
            signatures.add(w.signature())

        self.assertEqual(len(signatures), 1, f"All expressions should yield the same signature, got {len(signatures)}")

    def test_export_to_datalogging_config(self):
        w = GUIMathWatchable("test", "v1+v2")
        w.bind_watchable("v1", FqnNamePair("AAA", FQN.make(RegistryNodeType.Variable, "/a/b/c")))
        w.bind_watchable("v2", FqnNamePair("BBB", FQN.make(RegistryNodeType.Alias, "/x/y/z")))

        cfg = w.to_datalogging_config()
        self.assertIsNotNone(cfg)
        self.assertIsInstance(cfg, MathSignalConfig)
        self.assertEqual(cfg.expr, "v1+v2")
        self.assertEqual(cfg.variables["v1"], "/a/b/c")
        self.assertEqual(cfg.variables["v2"], "/x/y/z")

    def test_export_to_datalogging_config_incomplete(self):
        w = GUIMathWatchable("test", "v1+v2")
        w.bind_watchable("v1", FqnNamePair("AAA", FQN.make(RegistryNodeType.Variable, "/a/b/c")))
        # v2 not bound
        self.assertIsNone(w.to_datalogging_config())

    def test_load_from_core_def(self):
        core_def = core_MathWatchable(
            expr="v1+v2",
            watchables={
                "v1": core_Watchable(path="/a/b/ccc", type=WatchableType.Variable),
                "v2": core_Watchable(path="/x/y/zzz", type=WatchableType.Alias),
            }
        )
        gui_w = GUIMathWatchable.from_core_def("my_math", core_def)
        self.assertEqual(gui_w.get_name(), "my_math")
        self.assertEqual(gui_w.get_expr(), "v1+v2")
        self.assertTrue(gui_w.is_fully_configured())

        var_map = gui_w.get_var_fqn_map()
        self.assertEqual(var_map["v1"].fqn, FQN.make(RegistryNodeType.Variable, "/a/b/ccc"))
        self.assertEqual(var_map["v1"].name, "ccc")
        self.assertEqual(var_map["v2"].fqn, FQN.make(RegistryNodeType.Alias, "/x/y/zzz"))
        self.assertEqual(var_map["v2"].name, "zzz")

    def test_load_from_core_def_roundtrip_to_datalogging(self):
        core_def = core_MathWatchable(
            expr="v1*2+v2",
            watchables={
                "v1": core_Watchable(path="/a/b/c", type=WatchableType.Variable),
                "v2": core_Watchable(path="/d/e/f", type=WatchableType.Variable),
            }
        )
        gui_w = GUIMathWatchable.from_core_def("roundtrip", core_def)
        cfg = gui_w.to_datalogging_config()
        self.assertIsNotNone(cfg)
        self.assertEqual(cfg.expr, core_def.expr)
        for varname, watchable in core_def.watchables.items():
            self.assertEqual(cfg.variables[varname], watchable.path)

    def test_equivalence_same_expr_same_bindings(self):
        w1 = GUIMathWatchable("name_A", "v1 + v2")
        w1.bind_watchable("v1", FqnNamePair("display1", FQN.make(RegistryNodeType.Variable, "/a/b/c")))
        w1.bind_watchable("v2", FqnNamePair("display2", FQN.make(RegistryNodeType.Variable, "/a/b/d")))

        w2 = GUIMathWatchable("name_B", "v1+v2")
        w2.bind_watchable("v1", FqnNamePair("other_display", FQN.make(RegistryNodeType.Variable, "/a/b/c")))
        w2.bind_watchable("v2", FqnNamePair("other_display2", FQN.make(RegistryNodeType.Variable, "/a/b/d")))

        self.assertTrue(w1.is_equivalent(w2))
        self.assertTrue(w2.is_equivalent(w1))

    def test_equivalence_different_expr(self):
        w1 = GUIMathWatchable("test", "v1+v2")
        w1.bind_watchable("v1", FqnNamePair("A", FQN.make(RegistryNodeType.Variable, "/a/b/c")))
        w1.bind_watchable("v2", FqnNamePair("B", FQN.make(RegistryNodeType.Variable, "/a/b/d")))

        w2 = GUIMathWatchable("test", "v1*v2")
        w2.bind_watchable("v1", FqnNamePair("A", FQN.make(RegistryNodeType.Variable, "/a/b/c")))
        w2.bind_watchable("v2", FqnNamePair("B", FQN.make(RegistryNodeType.Variable, "/a/b/d")))

        self.assertFalse(w1.is_equivalent(w2))

    def test_equivalence_different_bindings(self):
        w1 = GUIMathWatchable("test", "v1+v2")
        w1.bind_watchable("v1", FqnNamePair("A", FQN.make(RegistryNodeType.Variable, "/a/b/c")))
        w1.bind_watchable("v2", FqnNamePair("B", FQN.make(RegistryNodeType.Variable, "/a/b/d")))

        w2 = GUIMathWatchable("test", "v1+v2")
        w2.bind_watchable("v1", FqnNamePair("A", FQN.make(RegistryNodeType.Variable, "/a/b/c")))
        w2.bind_watchable("v2", FqnNamePair("B", FQN.make(RegistryNodeType.Variable, "/a/b/DIFFERENT")))

        self.assertFalse(w1.is_equivalent(w2))

    def test_equivalence_ignores_display_names(self):
        w1 = GUIMathWatchable("test", "v1+v2")
        w1.bind_watchable("v1", FqnNamePair("DisplayA", FQN.make(RegistryNodeType.Variable, "/a/b/c")))
        w1.bind_watchable("v2", FqnNamePair("DisplayB", FQN.make(RegistryNodeType.Variable, "/a/b/d")))

        w2 = GUIMathWatchable("test", "v1+v2")
        w2.bind_watchable("v1", FqnNamePair("XXXXX", FQN.make(RegistryNodeType.Variable, "/a/b/c")))
        w2.bind_watchable("v2", FqnNamePair("YYYYY", FQN.make(RegistryNodeType.Variable, "/a/b/d")))

        self.assertTrue(w1.is_equivalent(w2))
