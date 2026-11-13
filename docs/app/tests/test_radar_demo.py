"""Exercise the Radar example's actual state and component construction."""

import re
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
import reflex as rx
from reflex_base.registry import RegistrationContext

PAGE = Path(__file__).resolve().parents[2] / "library/graphing/charts/radarchart.md"


@pytest.fixture
def radar_example():
    """Evaluate the page's imports and dynamic demo in an isolated registry."""
    with RegistrationContext(_config=rx.Config(app_name="radar_example_test")):
        namespace = {"__name__": f"radar_example_test_{uuid4().hex}", "Any": Any}
        for kind, code in re.findall(
            r"^```python ([^\n]+)\n(.*?)^```",
            PAGE.read_text(),
            re.MULTILINE | re.DOTALL,
        ):
            if kind in {"exec", "demo exec"}:
                exec(code, namespace)
        yield namespace


def walk(component):
    """Yield each component in the example tree, including foreach templates."""
    yield component
    for child in component.children:
        yield from walk(child)


def test_radar_sliders_are_controlled(radar_example):
    """Accepted allocation drives the thumb instead of a stale initial value."""
    sliders = [
        node for node in walk(radar_example["radar_dynamic"]()) if node.tag == "Slider"
    ]
    assert len(sliders) == 1
    slider = sliders[0]
    assert slider.value is not None
    row = next(
        node
        for node in walk(radar_example["radar_dynamic"]())
        if slider.__class__ in [type(child) for child in node.children]
    )
    displayed = row.children[-1].children[0].contents.to(int)
    assert str(slider.value) == str(rx.Var.create([displayed]))


def test_radar_allocation_budget_and_recovery(radar_example):
    """Exhausting, releasing and reallocating points preserves the budget."""
    state_type = radar_example["RadarChartState"]
    state = state_type(_reflex_internal_init=True)
    for trait, requested, accepted, remaining in [
        ("Strength", 100, 25, 0),
        ("Strength", 100, 25, 0),
        ("Dexterity", 100, 15, 0),
        ("Strength", 0, 0, 25),
        ("Dexterity", 100, 40, 0),
    ]:
        state_type.set_trait.fn(state, trait, requested)
        state._mark_dirty_computed_vars()
        assert next(t["value"] for t in state.traits if t["trait"] == trait) == accepted
        assert state.remaining_points == remaining
