from typing import Any

import pytest
from reflex_base.vars.base import Var
from reflex_components_radix.themes.components.text_field import TextFieldRoot

# Hides the wrapper while the rendered input is hidden.
HIDDEN_INPUT_WRAPPER = "&:where(:has(> input:is([hidden], [type=hidden i])))"


@pytest.mark.parametrize(
    ("auto_complete", "expected"),
    [
        ("off", '"off"'),
        ("email", '"email"'),
        (False, '"off"'),
        (True, '"on"'),
        (Var(_js_expr="enabled", _var_type=bool), '(enabled ? "on" : "off")'),
        (Var(_js_expr="flag", _var_type=bool | None), '(flag ? "on" : "off")'),
        (Var(_js_expr="hint", _var_type=str), "hint"),
        (Var(_js_expr="maybe_hint", _var_type=str | None), "maybe_hint"),
    ],
)
def test_auto_complete_renders_a_string(auto_complete: Any, expected: str):
    """React drops a bool autoComplete, so a bool becomes "on" or "off".

    Args:
        auto_complete: The auto_complete prop, typed str but still accepting a bool.
        expected: The rendered autoComplete value.
    """
    text_field = TextFieldRoot.create(auto_complete=auto_complete)

    assert f"autoComplete:{expected}" in str(text_field)


@pytest.mark.parametrize(
    "props",
    [
        {"type": "hidden", "value": "foo"},
        {"type": "hidden", "value": "foo", "size": "2"},
        {"type": "HIDDEN", "value": "foo"},
        {"hidden": True, "value": "foo"},
        {"hidden": Var(_js_expr="is_hidden", _var_type=bool)},
        {"type": Var(_js_expr="input_type", _var_type=str)},
    ],
)
def test_hidden_input_hides_the_wrapper(props: dict[str, Any]):
    """The TextField.Root wrapper of a hidden input must not show as a bar.

    The rule matches the rendered input, so the wrapper also follows state and
    scripts that change ``hidden`` or ``type`` in the browser.

    https://github.com/reflex-dev/reflex/issues/6874

    Args:
        props: The props of an input that can be hidden.
    """
    text_field = TextFieldRoot.create(**props)

    assert isinstance(text_field, TextFieldRoot)
    assert "display" not in text_field.style
    assert text_field.style[HIDDEN_INPUT_WRAPPER]["display"].equals(Var.create("none"))


@pytest.mark.parametrize(
    "props",
    [
        {"placeholder": "Name"},
        {"hidden": False},
        {"type": "text"},
    ],
)
def test_visible_input_keeps_the_wrapper(props: dict[str, Any]):
    """An input that can not be hidden gets no extra style.

    Args:
        props: The props of a visible input.
    """
    assert not TextFieldRoot.create(**props).style


@pytest.mark.parametrize(
    ("props", "expected"),
    [
        ({"style": {"display": "block"}}, '"block"'),
        ({"style": {"display": Var(_js_expr="shown", _var_type=str)}}, "shown"),
        ({"display": Var(_js_expr="shown", _var_type=str)}, "shown"),
        ({"style": [{"color": "red"}, {"display": "grid"}]}, '"grid"'),
    ],
)
def test_hidden_input_keeps_a_user_display(props: dict[str, Any], expected: str):
    """A display set by the user, also from state, wins over the rule.

    Args:
        props: The display set on a hidden input.
        expected: The rendered display value.
    """
    text_field = TextFieldRoot.create(type="hidden", **props)

    assert str(text_field.style["display"]) == expected
    assert HIDDEN_INPUT_WRAPPER not in text_field.style


def test_hidden_input_keeps_a_display_from_a_style_var():
    """A style Var comes after the rule, so a display in it wins."""
    style = Var(_js_expr="input_style", _var_type=dict[str, str])
    text_field = TextFieldRoot.create(type="hidden", style=style)

    assert list(text_field.style) == [HIDDEN_INPUT_WRAPPER, "&"]
    assert text_field.style["&"].equals(style)
