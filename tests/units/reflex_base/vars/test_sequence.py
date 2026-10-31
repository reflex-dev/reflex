"""Tests for reflex_base.vars.sequence literal string var creation."""

from reflex_base.constants.base import REFLEX_VAR_CLOSING_TAG, REFLEX_VAR_OPENING_TAG
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


def test_unicode_numeric_marker_text_is_preserved_verbatim():
    """isdecimal, not isnumeric: int() rejects characters like the 1/2 glyph."""
    text = "x <reflex.Var>½</reflex.Var> y"
    var = LiteralStringVar.create(text)
    assert var._get_all_var_data() is None
    # json.dumps escapes the 1/2 glyph in the compiled expression.
    assert str(var) == '"x <reflex.Var>\\u00bd</reflex.Var> y"'


def test_oversized_numeric_marker_text_is_preserved_verbatim():
    """A decimal string past int()'s conversion limit is user text."""
    text = f"<reflex.Var>{'1' * 5000}</reflex.Var>"
    var = LiteralStringVar.create(text)
    assert str(var) == '"' + text + '"'


def test_real_var_inside_literal_tags_still_decodes():
    """A real marker inside the user's literal tags must decode, not stay
    preserved as text when the tags came from an f-string with a var inside.
    """
    real_var = LiteralVar.create("imagination", _var_data=VarData(state="fear"))
    f_string = f"{REFLEX_VAR_OPENING_TAG}{real_var}{REFLEX_VAR_CLOSING_TAG}"

    var = LiteralStringVar.create(f_string)

    var_data = var._get_all_var_data()
    assert var_data is not None
    assert var_data.state == "fear"
    assert str(hash(real_var)) not in str(var)
    assert "imagination" in str(var)
    assert REFLEX_VAR_OPENING_TAG in str(var)


def test_real_state_var_inside_literal_tags_stays_reactive():
    """A non-literal var nested in literal tag text interpolates reactively."""
    state_var = Var(_js_expr="state_value", _var_type=str)
    f_string = f"{REFLEX_VAR_OPENING_TAG}{state_var}{REFLEX_VAR_CLOSING_TAG}"

    var = LiteralStringVar.create(f_string)

    # A decoder that baked the var's current value into a literal would pass
    # the string asserts below, so pin the var being a live concatenation.
    assert not isinstance(var, LiteralStringVar)
    assert "state_value" in str(var)
    assert str(hash(state_var)) not in str(var)


def test_many_opening_tags_scan_in_one_pass():
    """Many opening tags before one closing tag must not rescan the suffix."""
    text = "<reflex.Var>" * 2000 + "text</reflex.Var>"
    var = LiteralStringVar.create(text)
    assert var._get_all_var_data() is None
    assert str(var) == '"' + text + '"'


def test_decode_many_opening_tags_in_one_pass():
    """The decode path also handles repeated opening tags in one pass."""
    text = "<reflex.Var>" * 2000 + "text</reflex.Var>"
    var = Var(_js_expr=text)
    assert var._js_expr == text
    assert var._var_data is None


def test_var_data_decode_finds_real_marker_inside_literal_tags():
    """The decode path also decodes real markers nested in literal tags."""
    real_var = LiteralVar.create("imagination", _var_data=VarData(state="fear"))
    f_string = f"{REFLEX_VAR_OPENING_TAG}{real_var}{REFLEX_VAR_CLOSING_TAG}"

    var = Var(_js_expr=f_string)

    assert var._var_data is not None
    assert var._var_data.state == "fear"
    assert str(hash(real_var)) not in str(var)
    assert REFLEX_VAR_OPENING_TAG in str(var)
