"""Tests for reflex_base.vars.number."""

import json
import math
import re
import shutil
import subprocess
from pathlib import Path

import pytest
import reflex_base
from reflex_base.constants.base import Dirs
from reflex_base.vars.base import Var
from reflex_base.vars.number import LiteralNumberVar, NumberVar

STATE_JS = (
    Path(reflex_base.__file__).parent / ".templates" / "web" / "utils" / "state.js"
)


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
    assert str(x % -2.5) == "pyMod(x, -2.5, true)"
    assert str(Var(_js_expr="y").to(float) % x) == "pyMod(y, x, true)"
    modulo = 5 % x
    assert str(modulo) == "pyMod(5, x)"
    var_data = modulo._get_all_var_data()
    assert var_data is not None
    assert [
        import_var.tag for import_var in dict(var_data.imports)[f"$/{Dirs.STATE_PATH}"]
    ] == ["pyMod"]


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js is unavailable")
@pytest.mark.parametrize("var_type", [int, float])
def test_modulo_matches_python_in_js(var_type: type):
    """Compiled `%` evaluates in JS to Python's result, including the sign of a zero.

    Python's int `%` never returns -0; its float `%` gives a zero the divisor's sign.

    Args:
        var_type: The type of both operand Vars.
    """
    py_mod = re.search(
        r"^export const pyMod = .*?^};$", STATE_JS.read_text(), re.MULTILINE | re.DOTALL
    )
    assert py_mod is not None
    a = Var(_js_expr="a").to(NumberVar, var_type)
    b = Var(_js_expr="b").to(NumberVar, var_type)
    pairs = [
        (var_type(x), var_type(y))
        for x, y in [(-7, 3), (7, -3), (-7, -3), (5, 2), (36, -3), (-48, -16), (0, -5)]
    ]
    script = "\n".join([
        py_mod.group().removeprefix("export "),
        *(
            f"{{ const a = {x}, b = {y}, r = {a % b!s}; "
            "console.log(JSON.stringify(Object.is(r, -0) ? '-0' : r)); }"
            for x, y in pairs
        ),
    ])
    result = subprocess.run(
        ["node", "-e", script], capture_output=True, text=True, check=True, timeout=30
    )
    assert [json.loads(line) for line in result.stdout.splitlines()] == [
        "-0" if r == 0 and math.copysign(1, r) < 0 else r
        for r in (x % y for x, y in pairs)
    ]
