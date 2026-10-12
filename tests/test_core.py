"""Tests for the lexer, parser, evaluator and formatter."""

from __future__ import annotations

import math
import unittest
from decimal import Decimal

from calcengine.core import (
    AngleMode,
    ArityError,
    DomainError,
    Engine,
    LexError,
    NotationMode,
    ParseError,
    UnknownSymbolError,
)
from calcengine.core.errors import CalcError
from calcengine.core.lexer import tokenize
from calcengine.core.nodes import unparse
from calcengine.core.parser import parse
from calcengine.core.tokens import TokenType


def ast_of(source: str):
    return parse(tokenize(source), source)


class LexerTests(unittest.TestCase):
    def test_token_types(self):
        types = [token.type for token in tokenize("1+x*(2)")]
        self.assertEqual(
            types,
            [
                TokenType.NUMBER, TokenType.PLUS, TokenType.IDENT, TokenType.STAR,
                TokenType.LPAREN, TokenType.NUMBER, TokenType.RPAREN, TokenType.EOF,
            ],
        )

    def test_unicode_operator_aliases(self):
        self.assertEqual(tokenize("1\u00d72")[1].type, TokenType.STAR)
        self.assertEqual(tokenize("1\u00f72")[1].type, TokenType.SLASH)
        self.assertEqual(tokenize("1\u22122")[1].type, TokenType.MINUS)

    def test_superscripts_are_operators_not_digits(self):
        # "\u00b2".isdigit() is True in Python, so this guards a real trap.
        tokens = tokenize("4\u00b2")
        self.assertEqual(tokens[0].text, "4")
        self.assertEqual(tokens[1].type, TokenType.SQUARE)

    def test_greek_aliases_expand_to_names(self):
        self.assertEqual(tokenize("\u03c0")[0].text, "pi")
        self.assertEqual(tokenize("\u03c4")[0].text, "tau")

    def test_digit_grouping_is_stripped(self):
        self.assertEqual(tokenize("1_000_000")[0].text, "1000000")

    def test_exponent_vs_eulers_number(self):
        self.assertEqual(tokenize("2e5")[0].text, "2e5")
        self.assertEqual(len(tokenize("2e")), 3)  # NUMBER, IDENT, EOF

    def test_power_alias(self):
        self.assertEqual(tokenize("2**3")[1].type, TokenType.CARET)

    def test_rejects_unknown_character(self):
        with self.assertRaises(LexError):
            tokenize("2 $ 3")

    def test_malformed_number(self):
        with self.assertRaises(LexError):
            tokenize("1.")

    def test_error_carries_position(self):
        with self.assertRaises(LexError) as caught:
            tokenize("12 @ 4")
        self.assertEqual(caught.exception.position, 3)


class ParserTests(unittest.TestCase):
    def assert_shape(self, source: str, expected: str):
        self.assertEqual(unparse(ast_of(source)), expected)

    def test_multiplicative_binds_tighter(self):
        self.assert_shape("2+3*4", "2 + 3 * 4")
        self.assert_shape("(2+3)*4", "(2 + 3) * 4")

    def test_power_is_right_associative(self):
        self.assert_shape("2^3^2", "2 ^ 3 ^ 2")
        self.assert_shape("(2^3)^2", "(2 ^ 3) ^ 2")

    def test_unary_minus_binds_looser_than_power(self):
        self.assert_shape("-2^2", "-2 ^ 2")
        self.assert_shape("(-2)^2", "(-2) ^ 2")

    def test_left_associativity_preserved(self):
        self.assert_shape("1-2-3", "1 - 2 - 3")
        self.assert_shape("1-(2-3)", "1 - (2 - 3)")

    def test_implicit_multiplication(self):
        self.assert_shape("2pi", "2pi")
        self.assert_shape("3(4+5)", "3(4 + 5)")

    def test_radical_becomes_a_call(self):
        self.assert_shape("\u221a9", "sqrt(9)")

    def test_assignment_is_right_associative(self):
        self.assert_shape("a = b = 3", "a = b = 3")

    def test_unparse_round_trips(self):
        engine = Engine()
        for source in [
            "2+3*4", "(2+3)*4", "2^3^2", "(2^3)^2", "-2^2", "(-2)^2",
            "1-(2-3)", "-(2*3)", "5%+1", "3!!", "2pi", "3(4+5)", "-5\u00b2",
            "7 mod 3", "root(16,4)", "2*(1+3)^2",
        ]:
            first = engine.evaluate(source)
            second = engine.evaluate(first.normalized)
            self.assertEqual(first.value, second.value, source)

    def test_unbalanced_parenthesis(self):
        with self.assertRaises(ParseError):
            ast_of("(1+2")

    def test_trailing_operator(self):
        with self.assertRaises(ParseError):
            ast_of("2^")

    def test_leading_operator(self):
        with self.assertRaises(ParseError):
            ast_of("*5")

    def test_empty_source(self):
        with self.assertRaises(ParseError):
            ast_of("")


class ArithmeticTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def value(self, source: str) -> Decimal:
        return self.engine.evaluate(source).value

    def test_basic_operators(self):
        self.assertEqual(self.value("2+3"), 5)
        self.assertEqual(self.value("10-4"), 6)
        self.assertEqual(self.value("6*7"), 42)
        self.assertEqual(self.value("10/4"), Decimal("2.5"))

    def test_decimal_arithmetic_is_exact(self):
        # The headline reason for Decimal over float.
        self.assertEqual(self.value("0.1+0.2"), Decimal("0.3"))
        self.assertEqual(self.value("1.1*3"), Decimal("3.3"))

    def test_floored_modulo(self):
        self.assertEqual(self.value("7 mod 3"), 1)
        self.assertEqual(self.value("-7 mod 3"), 2)

    def test_postfix_operators(self):
        self.assertEqual(self.value("5!"), 120)
        self.assertEqual(self.value("50%"), Decimal("0.5"))
        self.assertEqual(self.value("4\u00b2"), 16)
        self.assertEqual(self.value("2\u00b3"), 8)

    def test_precedence_results(self):
        self.assertEqual(self.value("2+3*4"), 14)
        self.assertEqual(self.value("2^3^2"), 512)
        self.assertEqual(self.value("-2^2"), -4)
        self.assertEqual(self.value("(-2)^2"), 4)

    def test_negative_base_rejects_fractional_exponent(self):
        with self.assertRaises(DomainError):
            self.value("(-8)^0.5")

    def test_negative_base_integer_exponent(self):
        self.assertEqual(self.value("(-2)^3"), -8)

    def test_ans_variable(self):
        self.engine.evaluate("6*7")
        self.assertEqual(self.value("ans+1"), 43)

    def test_user_variables(self):
        self.engine.evaluate("r = 4")
        self.assertEqual(self.value("r*2"), 8)

    def test_cannot_rebind_constants_or_functions(self):
        for source in ("pi = 3", "sin = 2"):
            with self.assertRaises(CalcError):
                self.value(source)

    def test_division_by_zero(self):
        with self.assertRaises(DomainError):
            self.value("1/0")

    def test_unknown_name_suggests_alternative(self):
        with self.assertRaises(UnknownSymbolError) as caught:
            self.value("sine(1)")
        self.assertEqual(caught.exception.suggestion, "sin")

    def test_arity_is_enforced(self):
        with self.assertRaises(ArityError):
            self.value("sin(1,2)")

    def test_variadic_functions(self):
        self.assertEqual(self.value("sum(1,2,3,4)"), 10)
        self.assertEqual(self.value("max(1,9,4)"), 9)
        self.assertEqual(self.value("avg(2,4)"), 3)

    def test_optional_arguments(self):
        self.assertEqual(self.value("log(1000)"), 3)
        self.assertEqual(self.value("log(8,2)"), 3)

    def test_error_positions_point_at_the_problem(self):
        with self.assertRaises(CalcError) as caught:
            self.value("12 + sqrt(-1)")
        self.assertEqual(caught.exception.position, 5)


class HighPrecisionTests(unittest.TestCase):
    """The series implementations must agree with libm to double precision."""

    def setUp(self):
        self.engine = Engine(precision=40)

    def assert_close(self, source: str, expected: float):
        got = float(self.engine.evaluate(source).value)
        self.assertAlmostEqual(got, expected, places=12, msg=source)

    def test_circular_functions(self):
        self.assert_close("sin(1)", math.sin(1))
        self.assert_close("cos(1)", math.cos(1))
        self.assert_close("tan(1)", math.tan(1))
        self.assert_close("sin(100)", math.sin(100))
        self.assert_close("cos(-50)", math.cos(-50))

    def test_inverse_circular_functions(self):
        self.assert_close("asin(0.5)", math.asin(0.5))
        self.assert_close("acos(-0.25)", math.acos(-0.25))
        self.assert_close("atan(7)", math.atan(7))
        self.assert_close("atan2(-3,-4)", math.atan2(-3, -4))

    def test_hyperbolic_functions(self):
        self.assert_close("sinh(1.5)", math.sinh(1.5))
        self.assert_close("cosh(1.5)", math.cosh(1.5))
        self.assert_close("tanh(0.7)", math.tanh(0.7))

    def test_logarithms_and_roots(self):
        self.assert_close("ln(7)", math.log(7))
        self.assert_close("log2(100)", math.log2(100))
        self.assert_close("sqrt(2)", math.sqrt(2))
        self.assert_close("cbrt(10)", 10 ** (1 / 3))

    def test_pythagorean_identity(self):
        self.assertEqual(
            self.engine.evaluate("sin(1.234)^2 + cos(1.234)^2").value, 1
        )

    def test_pi_digits(self):
        engine = Engine(precision=60)
        engine.formatter.decimals = 50
        reference = "3.14159265358979323846264338327950288419716939937510"
        # Compare a prefix: the final displayed digit is rounded, not truncated.
        self.assertEqual(engine.evaluate("pi").formatted[:40], reference[:40])

    def test_large_factorial_is_exact(self):
        engine = Engine(precision=100)
        self.assertEqual(engine.evaluate("25!").value, Decimal(math.factorial(25)))

    def test_domain_errors(self):
        for source in ("sqrt(-1)", "ln(0)", "asin(2)", "log(5,1)", "0^-1"):
            with self.assertRaises(DomainError, msg=source):
                self.engine.evaluate(source)


class AngleModeTests(unittest.TestCase):
    def test_degrees(self):
        engine = Engine(angle_mode=AngleMode.DEGREES)
        self.assertEqual(engine.evaluate("sin(30)").formatted, "0.5")
        self.assertEqual(engine.evaluate("cos(60)").formatted, "0.5")
        self.assertEqual(engine.evaluate("asin(0.5)").formatted, "30")

    def test_gradians(self):
        engine = Engine(angle_mode=AngleMode.GRADIANS)
        self.assertEqual(engine.evaluate("sin(100)").formatted, "1")

    def test_mode_cycles(self):
        self.assertEqual(AngleMode.RADIANS.next(), AngleMode.DEGREES)
        self.assertEqual(AngleMode.GRADIANS.next(), AngleMode.RADIANS)


class FormatterTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def formatted(self, source: str) -> str:
        return self.engine.evaluate(source).formatted

    def test_trailing_zeros_removed(self):
        self.assertEqual(self.formatted("1.5000"), "1.5")
        self.assertEqual(self.formatted("4/2"), "2")

    def test_thousands_grouping(self):
        self.assertEqual(self.formatted("1234567"), "1,234,567")

    def test_grouping_can_be_disabled(self):
        self.engine.formatter.group_thousands = False
        self.assertEqual(self.formatted("1234567"), "1234567")

    def test_auto_switches_to_scientific(self):
        self.assertIn("\u00d710", self.formatted("2^100"))

    def test_notation_modes(self):
        self.engine.notation = NotationMode.SCIENTIFIC
        self.assertEqual(self.formatted("1234.5"), "1.2345\u00d710\u00b3")
        self.engine.notation = NotationMode.ENGINEERING
        self.assertEqual(self.formatted("12345"), "12.345\u00d710\u00b3")

    def test_notation_cycles(self):
        self.assertEqual(NotationMode.AUTO.next(), NotationMode.FIXED)

    def test_negative_values(self):
        self.assertEqual(self.formatted("0-45.5"), "-45.5")

    def test_formatter_honours_engine_precision(self):
        # Regression: quantize used to run in the default 28-digit context and
        # silently truncate high-precision results.
        engine = Engine(precision=60)
        engine.formatter.decimals = 40
        self.assertGreater(len(engine.evaluate("pi").formatted), 35)


class EngineIntrospectionTests(unittest.TestCase):
    def setUp(self):
        self.engine = Engine()

    def test_result_metadata(self):
        result = self.engine.evaluate("2+3*4")
        self.assertEqual(result.node_count, 5)
        self.assertEqual(result.tree.depth, 3)
        self.assertGreater(result.elapsed_ms, 0)

    def test_tree_lines_render(self):
        lines = self.engine.evaluate("1+2*3").tree_lines()
        self.assertTrue(any("Binary +" in line for line in lines))
        self.assertTrue(any("\u2514\u2500" in line for line in lines))

    def test_trace_collection(self):
        self.engine.collect_trace = True
        result = self.engine.evaluate("1+2*3")
        self.assertEqual([str(step.value) for step in result.trace], ["6", "7"])

    def test_completions(self):
        self.assertIn("sin", self.engine.completions("si"))
        self.assertEqual(self.engine.completions(""), [])

    def test_describe(self):
        self.assertIn("Sine", self.engine.describe("sin"))
        self.assertIsNone(self.engine.describe("nope"))

    def test_try_evaluate_swallows_errors(self):
        self.assertIsNone(self.engine.try_evaluate("1/0"))
        self.assertIsNotNone(self.engine.try_evaluate("1+1"))

    def test_precision_is_clamped(self):
        self.engine.precision = 5000
        self.assertEqual(self.engine.precision, 200)
        self.engine.precision = 1
        self.assertEqual(self.engine.precision, 6)

    def test_deeply_nested_parentheses_are_refused(self):
        with self.assertRaises(ParseError):
            self.engine.evaluate("(" * 400 + "1" + ")" * 400)

    def test_deeply_chained_operators_are_refused(self):
        with self.assertRaises(CalcError):
            self.engine.evaluate("1+" * 300 + "1")

    def test_moderate_nesting_still_works(self):
        self.assertEqual(self.engine.evaluate("(" * 20 + "7" + ")" * 20).value, 7)


if __name__ == "__main__":
    unittest.main()
