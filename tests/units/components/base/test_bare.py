import pytest
from reflex_base.vars.base import Var
from reflex_components_core.base.bare import Bare

from reflex.minify import StateEntry, get_state_full_path
from reflex.state import State
from tests.units.minify_helpers import install_config, set_minify_modes

STATE_VAR = Var(_js_expr="default_state.name")


@pytest.mark.parametrize(
    ("contents", "expected"),
    [
        ("hello", '"hello"'),
        ("{}", '"{}"'),
        (None, '""'),
        (STATE_VAR, "default_state.name"),
    ],
)
def test_fstrings(contents, expected):
    """Test that fstrings are rendered correctly.

    Args:
        contents: The contents of the component.
        expected: The expected output.
    """
    comp = Bare.create(contents).render()
    assert comp["contents"] == expected


@pytest.mark.parametrize(
    ("minify_states", "minify_vars"),
    [(True, False), (True, True), (False, True)],
    ids=["states", "states-and-vars", "vars"],
)
def test_stringified_var_flagged_when_minified(
    temp_minify_json, monkeypatch, mocker, minify_states, minify_vars
):
    """The perf-mode check flags state Vars whatever minification renames."""
    from reflex_base.environment import PerformanceMode

    import reflex as rx

    set_minify_modes(monkeypatch, states=minify_states, vars=minify_vars)

    class StrVarProbe(State):
        field: int = 1

    path = get_state_full_path(StrVarProbe)
    install_config(
        states={path: StateEntry(id="b", parent="reflex.state.State")},
        vars={path: {"field": "c"}},
        include_state_root=True,
    )
    stringified = str(StrVarProbe.field)
    assert (State.get_name() == "a") is minify_states
    assert stringified.endswith(".c") is minify_vars

    mocker.patch(
        "reflex_components_core.base.bare.get_performance_mode",
        return_value=PerformanceMode.RAISE,
    )

    with pytest.raises(ValueError, match="displayed as a string"):
        rx.vstack(stringified)
    # The issued state local followed by a key it never handed out.
    rx.vstack(f"{stringified.split('.')[0]}.not_a_key")
