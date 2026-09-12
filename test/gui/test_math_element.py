#    test_math_element.py
#        A test suite to test the scrutiny.core.MathElement
#
#   - License : MIT - See LICENSE file
#   - Project : Scrutiny Debugger (github.com/scrutinydebugger/scrutiny-main)
#
#    Copyright (c) 2026 Scrutiny Debugger

import math
from test import ScrutinyUnitTest
from scrutiny.gui.core.math_element import MathElement


class TestMathElement(ScrutinyUnitTest):
    def test_no_vars(self):
        element = MathElement('test', '1+2+3')
        self.assertTrue(element.is_valid())
        self.assertIsNone(element.get_val())
        self.assertEqual(element.eval(), 6)
        self.assertEqual(element.get_val(), 6)

    def test_with_single_var(self):
        element = MathElement('test', '1+2+$a')
        self.assertTrue(element.is_valid())
        element.bind_watchable("$a", 'var:/a/b/c')
        element.assign_var_value("$a", 3)
        self.assertEqual(element.eval(), 6, element.get_error())
        self.assertEqual(element.get_val(), 6, element.get_error())

    def test_with_many_vars(self):
        element = MathElement('test', '1+2+$a*$b+abs(-$x)')
        self.assertTrue(element.is_valid())
        element.bind_watchable("$a", 'var:/a/a/a')
        element.bind_watchable("$b", 'var:/a/a/b')
        element.bind_watchable("$x", 'var:/a/a/x')

        element.assign_var_value("$a", 10)
        element.assign_var_value_by_fqn("var:/a/a/b", 20)
        element.assign_var_value("$x", 0.5)
        val = 1 + 2 + 10 * 20 + abs(-0.5)
        self.assertEqual(element.eval(), val, element.get_error())
        self.assertEqual(element.get_val(), val, element.get_error())

    def test_duplicate_fqn_is_fine(self):
        element = MathElement('test', '1+2+$a1*$a2+abs(-$x)')
        self.assertTrue(element.is_valid())
        element.bind_watchable("$a1", 'var:/a/a/a')
        element.bind_watchable("$a2", 'var:/a/a/a')
        element.bind_watchable("$x", 'var:/a/a/x')

        element.assign_var_value_by_fqn("var:/a/a/a", 10)
        element.assign_var_value("$x", 0.5)
        val = 1 + 2 + 10 * 10 + abs(-0.5)
        self.assertEqual(element.eval(), val, element.get_error())
        self.assertEqual(element.get_val(), val, element.get_error())

    def test_cannot_bind_inexistant_fqn(self):
        element = MathElement('test', '$a+$b')
        self.assertTrue(element.is_valid())
        with self.assertRaises(Exception):
            element.bind_watchable("$c", 'var:/a/a/a')

    def test_cannot_assign_val_inexistent_var(self):
        element = MathElement('test', '$a+$b')
        self.assertTrue(element.is_valid())
        element.bind_watchable("$a", 'var:/a/a/a')
        element.bind_watchable("$b", 'var:/a/a/b')

        with self.assertRaises(Exception):
            element.assign_var_value("$c", 1)

    def test_cannot_assign_val_inexistent_fqn(self):
        element = MathElement('test', '$a+$b')
        self.assertTrue(element.is_valid())
        element.bind_watchable("$a", 'var:/a/a/a')
        element.bind_watchable("$b", 'var:/a/a/b')

        with self.assertRaises(Exception):
            element.assign_var_value_by_fqn('var:/a/a/c', 0)

    def test_get_var_from_expr(self):
        element = MathElement('test', '1+2+$a1*$a2+abs(-$x)')
        self.assertTrue(element.is_valid())
        vars = element.get_vars()
        self.assertEqual(len(vars), 3)
        self.assertIn("$a1", vars)
        self.assertIn("$a2", vars)
        self.assertIn("$x", vars)

    def test_rebind_is_allowed(self):
        element = MathElement('test', '1+$a')
        self.assertTrue(element.is_valid())
        element.bind_watchable("$a", 'var:/a/a/a')
        element.bind_watchable("$a", 'var:/a/a/b')
        element.bind_watchable("$a", 'var:/a/a/c')

    def test_variable_case_sensitive(self):
        element = MathElement('test', '1+$hElLo_World+$aaa+$AAA')
        self.assertTrue(element.is_valid())
        vars = element.get_vars()
        self.assertEqual(len(vars), 3)
        self.assertIn("$hElLo_World", vars)
        self.assertIn("$aaa", vars)
        self.assertIn("$AAA", vars)

        element.bind_watchable("$hElLo_World", 'var:/a/a/a')
        element.bind_watchable("$aaa", 'var:/a/a/b')
        element.bind_watchable("$AAA", 'var:/a/a/c')

        element.assign_var_value("$hElLo_World", 10)
        element.assign_var_value("$aaa", 20)
        element.assign_var_value("$AAA", 30)

        self.assertEqual(element.eval(), 1 + 10 + 20 + 30)

    def test_invalid_func(self):
        element = MathElement("test", "1+potato(2)")
        self.assertFalse(element.is_valid())
        self.assertIsNone(element.eval())

    def test_constants_are_not_vars(self):
        element = MathElement("test", "1+pi+$x+$y")
        self.assertTrue(element.is_valid())
        vars = element.get_vars()
        self.assertEqual(len(vars), 2)
        self.assertIn('$x', vars)
        self.assertIn('$y', vars)

    def test_var_require_cash_sign(self):
        element = MathElement("test", "1+pi+x+$y")
        self.assertFalse(element.is_valid())
        self.assertIsNone(element.eval())

    def test_func_are_case_insensitive(self):
        element = MathElement("test", "1+sIn(0.5) - COS(2)")
        val = element.eval()
        self.assertIsNotNone(val)
        self.assertAlmostEqual(val, 1 + math.sin(0.5) - math.cos(2), 5)

    def test_eval_with_default_var_values(self):
        """Vars default to 0, eval should work without prior assign or bind"""
        element = MathElement('test', '10+$a+$b')
        self.assertTrue(element.is_valid())
        self.assertEqual(element.eval(), 10, element.get_error())

    def test_invalid_var_name_error_mentions_var(self):
        """Error message should reference the bad variable name, not the element name"""
        element = MathElement("my_element", "1+pi+x+$y")
        self.assertFalse(element.is_valid())
        error = element.get_error()
        self.assertIsNotNone(error)
        assert error is not None
        self.assertIn("x", error)
        self.assertNotIn("my_element", error)

    def test_eval_invalid_expr_returns_none_and_sets_error(self):
        element = MathElement("test", "1+potato(2)")
        self.assertFalse(element.is_valid())
        self.assertIsNone(element.eval())
        self.assertIsNotNone(element.get_error())

    def test_operations_raise_on_invalid_expr(self):
        element = MathElement("test", "1+potato(2)")
        self.assertFalse(element.is_valid())
        with self.assertRaises(ValueError):
            element.bind_watchable("$a", "var:/a/b/c")
        with self.assertRaises(ValueError):
            element.assign_var_value("$a", 1)
        with self.assertRaises(ValueError):
            element.assign_var_value_by_fqn("var:/a/b/c", 1)
