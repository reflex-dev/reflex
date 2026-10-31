"""Tests for reflex_base.vars.sequence literal string var creation."""

from reflex_base.vars import VarData
from reflex_base.vars.base import LiteralVar, Var
from reflex_base.vars.sequence import LiteralStringVar


def test_marker_like_text_is_preserved_verbatim():
    """Tag-pair text that is not an encoded var stays in the string."""
    text = "use <reflex.Var>state</reflex.Var> to interpolate"
    var = LiteralStringVar.create(text)
    assert str(var) == '"use <reflex.Var>state</reflex.Var> to interpolate"'
    assert var._get_all_var_data() is None


def test_unknown_marker_hash_is_preserved_verbatim():
    """A hash that is not in the global registry is user text, not a var."""
    text = "ref <reflex.Var>12345678901234567890</reflex.Var>"
    var = LiteralStringVar.create(text)
    assert str(var) == '"ref <reflex.Var>12345678901234567890</reflex.Var>"'
    assert var._get_all_var_data() is None


def test_empty_marker_text_is_preserved_verbatim():
    """Empty tags hold no hash and must not be treated as an encoded var."""
    text = "a<reflex.Var></reflex.Var>b"
    var = LiteralStringVar.create(text)
    assert str(var) == '"a<reflex.Var></reflex.Var>b"'


def test_real_var_and_marker_like_text_interpolate_together():
    """Real encoded vars still decode when literal tag text follows."""
    real_var = LiteralVar.create("imagination", _var_data=VarData(state="fear"))
    f_string = f"{real_var} wrote <reflex.Var>fear</reflex.Var> down"

    var = LiteralStringVar.create(f_string)

    var_data = var._get_all_var_data()
    assert var_data is not None
    assert var_data.state == "fear"


def test_var_data_decode_tolerates_marker_like_text():
    """Var construction tolerates tag-pair text in the expression."""
    assert Var(_js_expr="<reflex.Var></reflex.Var>")._var_data is None
    assert Var(_js_expr="<reflex.Var>999</reflex.Var>")._var_data is None
    text = '"<reflex.Var>state</reflex.Var>"'
    assert Var(_js_expr=text)._js_expr == text
