from typing import Dict, List, Set, Tuple, Union

import pytest

from reflex.components import box, foreach, text
from reflex.components.core import Foreach
from reflex.state import BaseState
from reflex.vars import Var

try:
    # When pydantic v2 is installed
    from pydantic.v1 import ValidationError  # type: ignore
except ImportError:
    from pydantic import ValidationError


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
    bad_annotation_list: list = [["red", "orange"], ["yellow", "blue"]]
    color_index_tuple: Tuple[int, str] = (0, "red")


def display_color(color):
    assert color._var_type == str
    return box(text(color))


def display_color_name(color):
    assert color._var_type == Dict[str, str]
    return box(text(color["name"]))


def display_shade(color):
    assert color._var_type == Dict[str, List[str]]
    return box(text(color["shades"][0]))


def display_primary_colors(color):
    assert color._var_type == Tuple[str, str]
    return box(text(color[0]), text(color[1]))


def display_color_with_shades(color):
    assert color._var_type == Tuple[str, List[str]]
    return box(text(color[0]), text(color[1][0]))


def display_nested_color_with_shades(color):
    assert color._var_type == Tuple[str, Dict[str, List[Dict[str, str]]]]
    return box(text(color[0]), text(color[1]["red"][0]["shade"]))


def show_shade(item):
    return text(item[1][0]["shade"])


def display_nested_color_with_shades_v2(color):
    assert color._var_type == Tuple[str, Dict[str, List[Dict[str, str]]]]
    return box(text(foreach(color[1], show_shade)))


def display_color_tuple(color):
    assert color._var_type == str
    return box(text(color, "tuple"))


def display_colors_set(color):
    assert color._var_type == str
    return box(text(color, "set"))


def display_nested_list_element(element: Var[str], index: Var[int]):
    assert element._var_type == List[str]
    assert index._var_type == int
    return box(text(element[index]))


def display_color_index_tuple(color):
    assert color._var_type == Union[int, str]
    return box(text(color, "index_tuple"))


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
        (
            ForEachState.color_index_tuple,
            display_color_index_tuple,
            {
                "iterable_state": "for_each_state.color_index_tuple",
                "iterable_type": "tuple",
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


def test_foreach_bad_annotations():
    """Test that the foreach component raises a TypeError if the iterable is of type Any."""
    with pytest.raises(TypeError):
        Foreach.create(
            ForEachState.bad_annotation_list,  # type: ignore
            lambda sublist: Foreach.create(sublist, lambda color: text(color)),
        )


def test_foreach_no_param_in_signature():
    """Test that the foreach component raises a TypeError if no parameters are passed."""
    with pytest.raises(ValidationError):
        Foreach.create(
            ForEachState.colors_list,  # type: ignore
            lambda: text("color"),
        )
