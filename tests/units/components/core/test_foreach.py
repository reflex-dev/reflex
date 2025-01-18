from typing import Dict, List, Sequence, Set, Tuple, Union

import pydantic.v1
import pytest

from reflex import el
from reflex.base import Base
from reflex.components.component import Component
from reflex.components.core.foreach import ForeachVarError, foreach
from reflex.components.radix.themes.layout.box import box
from reflex.components.radix.themes.typography.text import text
from reflex.state import BaseState, ComponentState
from reflex.utils.exceptions import VarTypeError
from reflex.vars.number import NumberVar
from reflex.vars.sequence import ArrayVar


class ForEachTag(Base):
    """A tag for testing the ForEach component."""

    name: str = ""


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

    default_factory_list: list[ForEachTag] = pydantic.v1.Field(default_factory=list)


class ComponentStateTest(ComponentState):
    """A test component state."""

    foo: bool

    @classmethod
    def get_component(cls, *children, **props) -> Component:
        """Get the component.

        Args:
            children: The children components.
            props: The component props.

        Returns:
            The component.
        """
        return el.div(*children, **props)


def display_color(color):
    assert color._var_type is str
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
    assert color._var_type is str
    return box(text(color))


def display_colors_set(color):
    assert color._var_type is str
    return box(text(color))


def display_nested_list_element(
    element: ArrayVar[Sequence[str]], index: NumberVar[int]
):
    assert element._var_type == List[str]
    assert index._var_type is int
    return box(text(element[index]))


def display_color_index_tuple(color):
    assert color._var_type == Union[int, str]
    return box(text(color))


seen_index_vars = set()


def test_foreach_bad_annotations():
    """Test that the foreach component raises a ForeachVarError if the iterable is of type Any."""
    with pytest.raises(ForeachVarError):
        foreach(
            ForEachState.bad_annotation_list,
            lambda sublist: foreach(sublist, lambda color: text(color)),
        )


def test_foreach_no_param_in_signature():
    """Test that the foreach component DOES NOT raise an error if no parameters are passed."""
    foreach(
        ForEachState.colors_list,
        lambda: text("color"),
    )


def test_foreach_with_index():
    """Test that the foreach component works with an index."""
    foreach(
        ForEachState.colors_list,
        lambda color, index: text(color, index),
    )


def test_foreach_too_many_params_in_signature():
    """Test that the foreach component raises a ForeachRenderError if too many parameters are passed."""
    with pytest.raises(VarTypeError):
        foreach(
            ForEachState.colors_list,
            lambda color, index, extra: text(color),
        )


def test_foreach_component_styles():
    """Test that the foreach component works with global component styles."""
    component = el.div(
        foreach(
            ForEachState.colors_list,
            display_color,
        )
    )
    component._add_style_recursive({box: {"color": "red"}})
    assert '{ ["css"] : ({ ["color"] : "red" }) }' in str(component)


def test_foreach_component_state():
    """Test that using a component state to render in the foreach raises an error."""
    with pytest.raises(TypeError):
        foreach(
            ForEachState.colors_list,
            ComponentStateTest.create,
        )


def test_foreach_default_factory():
    """Test that the default factory is called."""
    _ = foreach(
        ForEachState.default_factory_list,
        lambda tag: text(tag.name),
    )
