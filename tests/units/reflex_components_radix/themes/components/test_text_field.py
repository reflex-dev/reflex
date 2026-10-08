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
