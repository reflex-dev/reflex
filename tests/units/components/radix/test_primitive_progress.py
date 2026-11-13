"""Tests for the Radix primitive progress wrapper."""

import pytest
from reflex_base.vars.base import Var
from reflex_components_radix.primitives.progress import (
    ProgressIndicator,
    ProgressRoot,
    progress,
)


@pytest.mark.parametrize(
    ("value", "max_value", "expected_value", "expected_max"),
    [
        (25, 200, "25", "200"),
        (
            Var(_js_expr="progress_state.amount", _var_type=int),
            Var(_js_expr="progress_state.total", _var_type=int),
            "progress_state.amount",
            "progress_state.total",
        ),
    ],
)
def test_progress_forwards_numeric_props_to_root_and_indicator(
    value: int | Var[int],
    max_value: int | Var[int],
    expected_value: str,
    expected_max: str,
) -> None:
    """The Root exposes numeric progress while the Indicator uses it for width."""
    component = progress(value=value, max=max_value)

    assert isinstance(component, ProgressRoot)
    indicator = component.children[0]
    assert isinstance(indicator, ProgressIndicator)

    for part in (component, indicator):
        props = part._render().props
        assert props["value"]._js_expr == expected_value
        assert props["max"]._js_expr == expected_max


def test_progress_forwards_defaults_to_root_and_indicator() -> None:
    """The default progress state is shared by both primitive parts."""
    component = progress()
    assert isinstance(component, ProgressRoot)
    indicator = component.children[0]
    assert isinstance(indicator, ProgressIndicator)

    for part in (component, indicator):
        props = part._render().props
        assert props["value"]._js_expr == "0"
        assert props["max"]._js_expr == "100"
