"""Tests for reflex_base.vars.number."""

from reflex_base.constants.base import Dirs
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
    assert str(LiteralNumberVar.create(-7) % 3) == "pyMod(-7, 3)"
    assert str(x % -2.5) == "pyMod(x, -2.5)"
    modulo = 5 % x
    assert str(modulo) == "pyMod(5, x)"
    var_data = modulo._get_all_var_data()
    assert var_data is not None
    assert [
        import_var.tag for import_var in dict(var_data.imports)[f"$/{Dirs.STATE_PATH}"]
    ] == ["pyMod"]
