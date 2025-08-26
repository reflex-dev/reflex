import pydantic.v1
import pytest

import reflex as rx
from reflex import el
from reflex.base import Base
from reflex.components.component import Component
from reflex.components.core.foreach import (
    Foreach,
    ForeachRenderError,
    ForeachVarError,
    foreach,
)
from reflex.components.radix.themes.layout.box import box
from reflex.components.radix.themes.typography.text import text
from reflex.constants.state import FIELD_MARKER
from reflex.state import BaseState, ComponentState
from reflex.vars.number import NumberVar
from reflex.vars.sequence import ArrayVar


class ForEachTag(Base):
    """A tag for testing the ForEach component."""

    name: str = ""


class ForEachState(BaseState):
    """A state for testing the ForEach component."""

    colors_list: list[str] = ["red", "yellow"]
    nested_colors_list: list[list[str]] = [["red", "yellow"], ["blue", "green"]]
    colors_dict_list: list[dict[str, str]] = [
        {
            "name": "red",
        },
        {"name": "yellow"},
    ]
    colors_nested_dict_list: list[dict[str, list[str]]] = [{"shades": ["light-red"]}]
    primary_color: dict[str, str] = {"category": "primary", "name": "red"}
    color_with_shades: dict[str, list[str]] = {
        "red": ["orange", "yellow"],
        "yellow": ["orange", "green"],
    }
    nested_colors_with_shades: dict[str, dict[str, list[dict[str, str]]]] = {
        "primary": {"red": [{"shade": "dark"}]}
    }
    color_tuple: tuple[str, str] = (
        "red",
        "yellow",
    )
    colors_set: set[str] = {"red", "green"}
    bad_annotation_list: list = [["red", "orange"], ["yellow", "blue"]]
    color_index_tuple: tuple[int, str] = (0, "red")

    default_factory_list: list[ForEachTag] = pydantic.v1.Field(default_factory=list)

    optional_list: rx.Field[list[str] | None] = rx.field(None)
    optional_list_value: rx.Field[list[str] | None] = rx.field(["red", "yellow"])
    optional_dict: rx.Field[dict[str, str] | None] = rx.field(None)
    optional_dict_value: rx.Field[dict[str, str] | None] = rx.field({"name": "red"})


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
    assert color._var_type == dict[str, str]
    return box(text(color["name"]))


def display_shade(color):
    assert color._var_type == dict[str, list[str]]
    return box(text(color["shades"][0]))


def display_primary_colors(color):
    assert color._var_type == tuple[str, str]
    return box(text(color[0]), text(color[1]))


def display_color_with_shades(color):
    assert color._var_type == tuple[str, list[str]]
    return box(text(color[0]), text(color[1][0]))


def display_nested_color_with_shades(color):
    assert color._var_type == tuple[str, dict[str, list[dict[str, str]]]]
    return box(text(color[0]), text(color[1]["red"][0]["shade"]))


def show_shade(item):
    return text(item[1][0]["shade"])


def display_nested_color_with_shades_v2(color):
    assert color._var_type == tuple[str, dict[str, list[dict[str, str]]]]
    return box(text(foreach(color[1], show_shade)))


def display_color_tuple(color):
    assert color._var_type is str
    return box(text(color))


def display_colors_set(color):
    assert color._var_type is str
    return box(text(color))


def display_nested_list_element(element: ArrayVar[list[str]], index: NumberVar[int]):
    assert element._var_type == list[str]
    assert index._var_type is int
    return box(text(element[index]))


def display_color_index_tuple(color):
    assert color._var_type == int | str
    return box(text(color))


@pytest.mark.parametrize(
    ("state_var", "render_fn", "render_dict"),
    [
        (
            ForEachState.colors_list,
            display_color,
            {
                "iterable_state": f"{ForEachState.get_full_name()}.colors_list"
                + FIELD_MARKER,
            },
        ),
        (
            ForEachState.colors_dict_list,
            display_color_name,
            {
                "iterable_state": f"{ForEachState.get_full_name()}.colors_dict_list"
                + FIELD_MARKER,
            },
        ),
        (
            ForEachState.colors_nested_dict_list,
            display_shade,
            {
                "iterable_state": f"{ForEachState.get_full_name()}.colors_nested_dict_list"
                + FIELD_MARKER,
            },
        ),
        (
            ForEachState.primary_color,
            display_primary_colors,
            {
                "iterable_state": f"Object.entries({ForEachState.get_full_name()}.primary_color{FIELD_MARKER})",
            },
        ),
        (
            ForEachState.color_with_shades,
            display_color_with_shades,
            {
                "iterable_state": f"Object.entries({ForEachState.get_full_name()}.color_with_shades{FIELD_MARKER})",
            },
        ),
        (
            ForEachState.nested_colors_with_shades,
            display_nested_color_with_shades,
            {
                "iterable_state": f"Object.entries({ForEachState.get_full_name()}.nested_colors_with_shades{FIELD_MARKER})",
            },
        ),
        (
            ForEachState.nested_colors_with_shades,
            display_nested_color_with_shades_v2,
            {
                "iterable_state": f"Object.entries({ForEachState.get_full_name()}.nested_colors_with_shades{FIELD_MARKER})",
            },
        ),
        (
            ForEachState.color_tuple,
            display_color_tuple,
            {
                "iterable_state": f"{ForEachState.get_full_name()}.color_tuple"
                + FIELD_MARKER,
            },
        ),
        (
            ForEachState.colors_set,
            display_colors_set,
            {
                "iterable_state": f"{ForEachState.get_full_name()}.colors_set"
                + FIELD_MARKER,
            },
        ),
        (
            ForEachState.nested_colors_list,
            lambda el, i: display_nested_list_element(el, i),
            {
                "iterable_state": f"{ForEachState.get_full_name()}.nested_colors_list"
                + FIELD_MARKER,
            },
        ),
        (
            ForEachState.color_index_tuple,
            display_color_index_tuple,
            {
                "iterable_state": f"{ForEachState.get_full_name()}.color_index_tuple"
                + FIELD_MARKER,
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

    # Make sure the index vars are unique.
    arg_index = rend["arg_index"]
    assert isinstance(arg_index, str)


def test_foreach_bad_annotations():
    """Test that the foreach component raises a ForeachVarError if the iterable is of type Any."""
    with pytest.raises(ForeachVarError):
        Foreach.create(
            ForEachState.bad_annotation_list,
            lambda sublist: Foreach.create(sublist, lambda color: text(color)),
        )


def test_foreach_no_param_in_signature():
    """Test that the foreach component raises a ForeachRenderError if no parameters are passed."""
    with pytest.raises(ForeachRenderError):
        Foreach.create(
            ForEachState.colors_list,
            lambda: text("color"),
        )


def test_foreach_too_many_params_in_signature():
    """Test that the foreach component raises a ForeachRenderError if too many parameters are passed."""
    with pytest.raises(ForeachRenderError):
        Foreach.create(
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
    assert 'css:({ ["color"] : "red" })' in str(component)


def test_foreach_component_state():
    """Test that using a component state to render in the foreach raises an error."""
    with pytest.raises(TypeError):
        Foreach.create(
            ForEachState.colors_list,
            ComponentStateTest.create,
        )


def test_foreach_default_factory():
    """Test that the default factory is called."""
    _ = Foreach.create(
        ForEachState.default_factory_list,
        lambda tag: text(tag.name),
    )


def test_optional_list():
    """Test that the foreach component works with optional lists."""
    Foreach.create(
        ForEachState.optional_list,
        lambda color: text(color),
    )

    Foreach.create(
        ForEachState.optional_list_value,
        lambda color: text(color),
    )

    Foreach.create(
        ForEachState.optional_dict,
        lambda color: text(color[0], color[1]),
    )

    Foreach.create(
        ForEachState.optional_dict_value,
        lambda color: text(color[0], color[1]),
    )
