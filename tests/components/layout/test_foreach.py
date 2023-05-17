from typing import Dict, List, Set, Tuple

import pytest

from pynecone.components import box, foreach, text
from pynecone.components.layout import Foreach
from pynecone.state import State


class ForEachState(State):
    """The test  state."""

    color_a: List[str] = ["red", "yellow"]
    color_b: List[Dict[str, str]] = [
        {
            "name": "red",
        },
        {"name": "yellow"},
    ]
    color_c: List[Dict[str, List[str]]] = [{"shades": ["light-red"]}]
    color_d: Dict[str, str] = {"category": "primary", "name": "red"}
    color_e: Dict[str, List[str]] = {
        "red": ["orange", "yellow"],
        "yellow": ["orange", "green"],
    }
    color_f: Dict[str, Dict[str, List[Dict[str, str]]]] = {
        "primary": {"red": [{"shade": "dark"}]}
    }
    color_g: Tuple[str, str] = (
        "red",
        "yellow",
    )
    color_h: Set[str] = {"red", "green"}


def display_a(color):
    return box(text(color))


def display_b(color):
    return box(text(color["name"]))


def display_c(color):
    return box(text(color["shades"][0]))


def display_d(color):
    return box(text(color[0]), text(color[1]))


def display_e(color):
    # color is a key-value pair list similar to `dict.items()`
    return box(text(color[0]), text(color[1][0]))


def display_f(color):
    return box(text(color[0]), text(color[1]["red"][0]["shade"]))


def show_item(item):
    return text(item[1][0]["shade"])


def display_f1(color):
    return box(text(foreach(color[1], show_item)))


def display_g(color):
    return box(text(color))


def display_h(color):
    return box(text(color))


@pytest.mark.parametrize(
    "state_var, render_fn, render_dict",
    [
        (
            ForEachState.color_a,
            display_a,
            {
                "iterable_state": "for_each_state.color_a",
                "arg_index": "i",
                "iterable_type": "list",
            },
        ),
        (
            ForEachState.color_b,
            display_b,
            {
                "iterable_state": "for_each_state.color_b",
                "arg_index": "i",
                "iterable_type": "list",
            },
        ),
        (
            ForEachState.color_c,
            display_c,
            {
                "iterable_state": "for_each_state.color_c",
                "arg_index": "i",
                "iterable_type": "list",
            },
        ),
        (
            ForEachState.color_d,
            display_d,
            {
                "iterable_state": "for_each_state.color_d",
                "arg_index": "i",
                "iterable_type": "dict",
            },
        ),
        (
            ForEachState.color_e,
            display_e,
            {
                "iterable_state": "for_each_state.color_e",
                "arg_index": "i",
                "iterable_type": "dict",
            },
        ),
        (
            ForEachState.color_f,
            display_f,
            {
                "iterable_state": "for_each_state.color_f",
                "arg_index": "i",
                "iterable_type": "dict",
            },
        ),
        (
            ForEachState.color_f,
            display_f1,
            {
                "iterable_state": "for_each_state.color_f",
                "arg_index": "i",
                "iterable_type": "dict",
            },
        ),
        (
            ForEachState.color_g,
            display_g,
            {
                "iterable_state": "for_each_state.color_g",
                "arg_index": "i",
                "iterable_type": "tuple",
            },
        ),
        (
            ForEachState.color_h,
            display_h,
            {
                "iterable_state": "for_each_state.color_h",
                "arg_index": "i",
                "iterable_type": "set",
            },
        ),
    ],
)
def test_foreach_render(state_var, render_fn, render_dict):
    """Test that the foreach component renders without error.

    Args:
        state_var: the state var.
        render_fn: The render callable
        render_dict: return dict on calling `component.render`
    """
    component = Foreach.create(state_var, render_fn)

    rend = component.render()

    assert rend["iterable_state"] == render_dict["iterable_state"]
    assert rend["arg_index"] == render_dict["arg_index"]
    assert rend["iterable_type"] == render_dict["iterable_type"]
