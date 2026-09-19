#    test_math_watchable.py
#        A test suite to test the scrutiny.core.GUIMathWatchable
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import math
from test import ScrutinyUnitTest
from scrutiny.gui.core.gui_math_watchable import GUIMathWatchable
from scrutiny.gui.core.watchable_registry.fqn import FQN
from scrutiny.gui.core.watchable_registry.common import RegistryNodeType


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
        watchable.bind_watchable("a", 'var:/a/b/c')
        watchable.assign_var_value("a", 3)
        self.assertEqual(watchable.eval(), 6, watchable.get_error())
        self.assertEqual(watchable.get_val(), 6, watchable.get_error())

    def test_with_many_vars(self):
        watchable = GUIMathWatchable('test', '1+2+a*b+abs(-x)')
        self.assertTrue(watchable.is_valid())
        watchable.bind_watchable("a", 'var:/a/a/a')
        watchable.bind_watchable("b", 'var:/a/a/b')
        watchable.bind_watchable("x", 'var:/a/a/x')

        watchable.assign_var_value("a", 10)
        watchable.assign_var_value_by_fqn("var:/a/a/b", 20)
        watchable.assign_var_value("x", 0.5)
        val = 1 + 2 + 10 * 20 + abs(-0.5)
        self.assertEqual(watchable.eval(), val, watchable.get_error())
        self.assertEqual(watchable.get_val(), val, watchable.get_error())

    def test_duplicate_fqn_is_fine(self):
        watchable = GUIMathWatchable('test', '1+2+a1*a2+abs(-x)')
        self.assertTrue(watchable.is_valid())
        watchable.bind_watchable("a1", 'var:/a/a/a')
        watchable.bind_watchable("a2", 'var:/a/a/a')
        watchable.bind_watchable("x", 'var:/a/a/x')

        watchable.assign_var_value_by_fqn("var:/a/a/a", 10)
        watchable.assign_var_value("x", 0.5)
        val = 1 + 2 + 10 * 10 + abs(-0.5)
        self.assertEqual(watchable.eval(), val, watchable.get_error())
        self.assertEqual(watchable.get_val(), val, watchable.get_error())

    def test_cannot_bind_inexistant_fqn(self):
        watchable = GUIMathWatchable('test', 'a+b')
        self.assertTrue(watchable.is_valid())
        with self.assertRaises(Exception):
            watchable.bind_watchable("c", 'var:/a/a/a')

    def test_cannot_assign_val_inexistent_var(self):
        watchable = GUIMathWatchable('test', 'a+b')
        self.assertTrue(watchable.is_valid())
        watchable.bind_watchable("a", 'var:/a/a/a')
        watchable.bind_watchable("b", 'var:/a/a/b')

        with self.assertRaises(Exception):
            watchable.assign_var_value("c", 1)

    def test_cannot_assign_val_inexistent_fqn(self):
        watchable = GUIMathWatchable('test', 'a+b')
        self.assertTrue(watchable.is_valid())
        watchable.bind_watchable("a", 'var:/a/a/a')
        watchable.bind_watchable("b", 'var:/a/a/b')

        with self.assertRaises(Exception):
            watchable.assign_var_value_by_fqn('var:/a/a/c', 0)

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
        watchable.bind_watchable("a", 'var:/a/a/a')
        watchable.bind_watchable("a", 'var:/a/a/b')
        watchable.bind_watchable("a", 'var:/a/a/c')

    def test_variable_case_sensitive(self):
        watchable = GUIMathWatchable('test', '1+hElLo_World+aaa+AAA')
        self.assertTrue(watchable.is_valid())
        vars = watchable.get_vars()
        self.assertEqual(len(vars), 3)
        self.assertIn("hElLo_World", vars)
        self.assertIn("aaa", vars)
        self.assertIn("AAA", vars)

        watchable.bind_watchable("hElLo_World", 'var:/a/a/a')
        watchable.bind_watchable("aaa", 'var:/a/a/b')
        watchable.bind_watchable("AAA", 'var:/a/a/c')

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
            watchable.bind_watchable("a", "var:/a/b/c")
        with self.assertRaises(ValueError):
            watchable.assign_var_value("a", 1)
        with self.assertRaises(ValueError):
            watchable.assign_var_value_by_fqn("var:/a/b/c", 1)

    def test_copy(self):
        watchable = GUIMathWatchable("test", "1+sin(x)-cos(y)")
        watchable.bind_watchable("x", "var:/aaa/bbb/ccc")
        watchable.bind_watchable("y", "alias:/aaa/bbb/ccc")

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
        watchable.bind_watchable("x", FQN.make(RegistryNodeType.Variable, "/aaa/bbb/ccc"))
        with self.assertRaises(ValueError):
            watchable.bind_watchable("y", FQN.make(RegistryNodeType.Math, "/aaa/bbb/ccc"))

    def test_serialization(self):
        watchable = GUIMathWatchable('test', 'a+b')
        watchable.bind_watchable("a", 'var:/a/a/a')
        watchable.bind_watchable("b", 'var:/a/a/b')

        data = watchable.serialize()
        self.assertIsInstance(data, str)
        watchable2 = GUIMathWatchable.deserialize(data)
        self.assertEqual(watchable.get_name(), watchable2.get_name())
        self.assertEqual(watchable.get_expr(), watchable2.get_expr())
        self.assertEqual(watchable.get_var_fqn_map(), watchable2.get_var_fqn_map())
