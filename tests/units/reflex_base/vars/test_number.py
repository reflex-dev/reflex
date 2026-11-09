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
