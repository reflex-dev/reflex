from typing import Any

import pytest
from reflex_base.vars.base import Var
from reflex_components_radix.themes.components.text_field import TextFieldRoot


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
        {"hidden": True, "value": "foo"},
    ],
)
def test_static_hidden_input_hides_the_wrapper(props: dict[str, Any]):
    """The TextField.Root wrapper of a hidden input must not show as a bar.

    https://github.com/reflex-dev/reflex/issues/6874

    Args:
        props: The props of a statically hidden input.
    """
    text_field = TextFieldRoot.create(**props)

    assert isinstance(text_field, TextFieldRoot)
    assert text_field.style["display"].equals(Var.create("none"))


@pytest.mark.parametrize(
    "props",
    [
        {"placeholder": "Name"},
        {"type": Var(_js_expr="input_type", _var_type=str)},
        {"hidden": Var(_js_expr="is_hidden", _var_type=bool)},
    ],
)
def test_visible_input_keeps_the_wrapper(props: dict[str, Any]):
    """An input that is not hidden at compile time keeps its wrapper visible.

    Args:
        props: The props of an input that may be visible.
    """
    assert "display" not in TextFieldRoot.create(**props).style
