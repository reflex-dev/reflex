"""Tests for reflex_base.vars.number."""

from reflex_base.vars.base import Var
from reflex_base.vars.number import LiteralNumberVar


def test_exponent_parenthesizes_a_unary_base():
    """JavaScript rejects a unary expression as the base of `**` (`-2 ** 2` is a SyntaxError)."""
    x = Var(_js_expr="x").to(int)
    assert str(LiteralNumberVar.create(-2) ** 3) == "((-2) ** 3)"
    assert str(LiteralNumberVar.create(-2.5) ** x) == "((-2.5) ** x)"
    assert str((-x) ** 2) == "((-(x)) ** 2)"
    assert str(-(x**2)) == "-((x ** 2))"
    assert str(x**-1) == "(x ** -1)"
    assert str(2**-x) == "(2 ** -(x))"


def test_modulo_takes_the_sign_of_the_divisor():
    """Python's `%` takes the sign of the divisor (`-7 % 3` is 2), JavaScript's the dividend's."""
    x = Var(_js_expr="x").to(int)
    py_mod = "((a, b) => { const r = a % b; return r === 0 ? (b < 0 ? -0 : 0) : (r < 0) !== (b < 0) ? r + b : r; })"
    assert str(LiteralNumberVar.create(-7) % 3) == f"{py_mod}(-7, 3)"
    assert str(x % -2.5) == f"{py_mod}(x, -2.5)"
    assert str(5 % x) == f"{py_mod}(5, x)"
