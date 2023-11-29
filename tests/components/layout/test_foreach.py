from typing import Dict, List, Set, Tuple

import pytest

from reflex.components import box, foreach, text
from reflex.components.layout import Foreach
from reflex.state import BaseState


class ForEachState(BaseState):
    """A state for testing the ForEach component."""

    colors_list: List[str] = ["red", "yellow"]
    nested_colors_list: List[List[str]] = [["red", "yellow"], ["blue", "green"]]
    colors_dict_list: List[Dict[str, str]] = [
        {
            "name": "red",
        },
        {"name": "yellow"},
    ]
    colors_nested_dict_list: List[Dict[str, List[str]]] = [{"shades": ["light-red"]}]
    primary_color: Dict[str, str] = {"category": "primary", "name": "red"}
    color_with_shades: Dict[str, List[str]] = {
        "red": ["orange", "yellow"],
        "yellow": ["orange", "green"],
    }
    nested_colors_with_shades: Dict[str, Dict[str, List[Dict[str, str]]]] = {
        "primary": {"red": [{"shade": "dark"}]}
    }
    color_tuple: Tuple[str, str] = (
        "red",
        "yellow",
    )
    colors_set: Set[str] = {"red", "green"}


def display_color(color):
    return box(text(color))


def display_color_name(color):
    return box(text(color["name"]))


def display_shade(color):
    return box(text(color["shades"][0]))


def display_primary_colors(color):
    return box(text(color[0]), text(color[1]))


def display_color_with_shades(color):
    return box(text(color[0]), text(color[1][0]))


def display_nested_color_with_shades(color):
    return box(text(color[0]), text(color[1]["red"][0]["shade"]))


def show_shade(item):
    return text(item[1][0]["shade"])


def display_nested_color_with_shades_v2(color):
    return box(text(foreach(color[1], show_shade)))


def display_color_tuple(color):
    return box(text(color, "tuple"))


def display_colors_set(color):
    return box(text(color, "set"))


def display_nested_list_element(element: str, index: int):
    return box(text(element[index]))


seen_index_vars = set()


@pytest.mark.parametrize(
    "state_var, render_fn, render_dict",
    [
        (
            ForEachState.colors_list,
            display_color,
            {
                "iterable_state": "for_each_state.colors_list",
                "iterable_type": "list",
            },
        ),
        (
            ForEachState.colors_dict_list,
            display_color_name,
            {
                "iterable_state": "for_each_state.colors_dict_list",
                "iterable_type": "list",
            },
        ),
        (
            ForEachState.colors_nested_dict_list,
            display_shade,
            {
                "iterable_state": "for_each_state.colors_nested_dict_list",
                "iterable_type": "list",
            },
        ),
        (
            ForEachState.primary_color,
            display_primary_colors,
            {
                "iterable_state": "for_each_state.primary_color",
                "iterable_type": "dict",
            },
        ),
        (
            ForEachState.color_with_shades,
            display_color_with_shades,
            {
                "iterable_state": "for_each_state.color_with_shades",
                "iterable_type": "dict",
            },
        ),
        (
            ForEachState.nested_colors_with_shades,
            display_nested_color_with_shades,
            {
                "iterable_state": "for_each_state.nested_colors_with_shades",
                "iterable_type": "dict",
            },
        ),
        (
            ForEachState.nested_colors_with_shades,
            display_nested_color_with_shades_v2,
            {
                "iterable_state": "for_each_state.nested_colors_with_shades",
                "iterable_type": "dict",
            },
        ),
        (
            ForEachState.color_tuple,
            display_color_tuple,
            {
                "iterable_state": "for_each_state.color_tuple",
                "iterable_type": "tuple",
            },
        ),
        (
            ForEachState.colors_set,
            display_colors_set,
            {
                "iterable_state": "for_each_state.colors_set",
                "iterable_type": "set",
            },
        ),
        (
            ForEachState.nested_colors_list,
            lambda el, i: display_nested_list_element(el, i),
            {
                "iterable_state": "for_each_state.nested_colors_list",
                "iterable_type": "list",
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
    assert rend["iterable_type"] == render_dict["iterable_type"]

    # Make sure the index vars are unique.
    arg_index = rend["arg_index"]
    assert arg_index._var_name not in seen_index_vars
    assert arg_index._var_type == int
    seen_index_vars.add(arg_index._var_name)
