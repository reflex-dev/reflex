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


def test_stringified_var_still_flagged_when_root_is_minified(
    temp_minify_json, monkeypatch, mocker
):
    """The perf-mode check keys on the field marker, not the root state name."""
    from reflex_base.environment import PerformanceMode

    import reflex as rx

    set_minify_modes(monkeypatch, states=True)

    class StrVarProbe(State):
        field: int = 1

    install_config(
        states={
            "reflex.state.State": StateEntry(id="a", parent=None),
            get_state_full_path(StrVarProbe): StateEntry(
                id="b", parent="reflex.state.State"
            ),
        }
    )
    assert State.get_name() == "a"

    mocker.patch(
        "reflex_components_core.base.bare.get_performance_mode",
        return_value=PerformanceMode.RAISE,
    )

    with pytest.raises(ValueError, match="displayed as a string"):
        rx.vstack(str(StrVarProbe.field))
