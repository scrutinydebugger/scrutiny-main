from test import ScrutinyUnitTest
from scrutiny.gui.core.math_element import MathElement


class TestMathElement(ScrutinyUnitTest):
    def test_no_vars(self):
        element = MathElement('test', '1+2+3')
        self.assertIsNone(element.get_val())
        self.assertEqual(element.eval(), 6)
        self.assertEqual(element.get_val(), 6)

    def test_with_single_var(self):
        element = MathElement('test', '1+2+$a')
        element.bind_watchable("$a", 'var:/a/b/c')
        element.assign_var_value("$a", 3)
        self.assertEqual(element.eval(), 6, element.get_error())
        self.assertEqual(element.get_val(), 6, element.get_error())

    def test_with_many_vars(self):
        element = MathElement('test', '1+2+$a*$b+abs(-$x)')
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
        element.bind_watchable("$a1", 'var:/a/a/a')
        element.bind_watchable("$a2", 'var:/a/a/a')
        element.bind_watchable("$x", 'var:/a/a/x')

        element.assign_var_value_by_fqn("var:/a/a/a", 10)
        element.assign_var_value("$x", 0.5)
        val = 1 + 2 + 10 * 10 + abs(-0.5)
        self.assertEqual(element.eval(), val, element.get_error())
        self.assertEqual(element.get_val(), val, element.get_error())

    def test_cannot_bind_inexistant_var(self):
        element = MathElement('test', '$a+$b')
        with self.assertRaises(Exception):
            element.bind_watchable("$c", 'var:/a/a/a')

    def test_get_var_from_expr(self):
        element = MathElement('test', '1+2+$a1*$a2+abs(-$x)')
        vars = element.get_vars()
        self.assertEqual(len(vars), 3)
        self.assertIn("$a1", vars)
        self.assertIn("$a2", vars)
        self.assertIn("$x", vars)
