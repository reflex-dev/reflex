"""A slider: native range inputs over a track that Radix Themes draws."""

from __future__ import annotations

import functools
from collections.abc import Sequence
from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, field
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler, JavascriptInputEvent
from reflex_base.utils.imports import ImportVar
from reflex_base.utils.types import typehint_issubclass
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_base.vars.object import ObjectVar
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.foreach import foreach
from reflex_components_core.el import elements

from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.components._group import literal
from reflex_components_ui.constants import WEB_DIR
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.slider import END, SLIDER, START
from reflex_components_ui.themes import LiteralAccentColor

_SCRIPT = f"$/{WEB_DIR}/behaviors/slider.js"

# What follows the thumbs of a slider: its `onInputCapture` draws the filled
# part of the track and keeps several thumbs in order, and the
# `onMouseDown` of a slider with several moves the nearest one.
_SLIDE = Var("slide", _var_data=VarData(imports={_SCRIPT: [ImportVar(tag="slide")]}))
_PRESS = Var("press", _var_data=VarData(imports={_SCRIPT: [ImportVar(tag="press")]}))

# The keys that move a thumb: a thumb is released when one of them is.
_KEYS = (
    '["ArrowLeft", "ArrowRight", "ArrowUp", "ArrowDown", '
    '"Home", "End", "PageUp", "PageDown"]'
)


def _values(event: Var, kind: type) -> Var:
    """Read the values of the thumbs of a slider from an event inside it.

    Args:
        event: The event, as it reaches the slider.
        kind: The type of the list of values.

    Returns:
        The value of each thumb, in the order of the thumbs.
    """
    return Var(
        f'Array.from({event!s}.currentTarget.querySelectorAll("input"), '
        "(input) => input.valueAsNumber)",
        _var_type=kind,
    )


def float_values_event(
    e: ObjectVar[JavascriptInputEvent],
) -> tuple[Var[list[float]]]:
    """Get the values of a slider from a change of one of its thumbs.

    Args:
        e: The change, as it reaches the slider.

    Returns:
        The value of each thumb.
    """
    return (_values(e, list[float]),)


def int_values_event(e: ObjectVar[JavascriptInputEvent]) -> tuple[Var[list[int]]]:
    """Get the whole values of a slider from a change of one of its thumbs.

    Args:
        e: The change, as it reaches the slider.

    Returns:
        The value of each thumb.
    """
    return (_values(e, list[int]),)


on_value_event_spec = (float_values_event, int_values_event)


def _share(value: Any, low: Any, high: Any) -> Any:
    """Say how far along the track of a slider a value is.

    Args:
        value: The value.
        low: The minimum of the slider, or None for 0.
        high: Its maximum, or None for 100.

    Returns:
        The share of the track as a percentage: a string when everything is
        known while compiling.
    """
    low = 0 if low is None else literal(low)
    high = 100 if high is None else literal(high)
    value = literal(value)
    if not any(isinstance(item, Var) for item in (value, low, high)):
        return f"{(value - low) / (high - low) * 100:g}%" if high > low else "0%"
    parts = [LiteralVar.create(item) for item in (value, low, high)]
    amount, start, end = (str(part) for part in parts)
    return Var(
        f'(((({amount}) - ({start})) / (({end}) - ({start})) * 100) + "%")',
        _var_type=str,
        _var_data=VarData.merge(*(part._get_all_var_data() for part in parts)),
    )


def _label(index: int, count: int) -> dict[str, str]:
    """Name a thumb of a slider with several, as Radix does.

    Args:
        index: Which thumb it is, from 0.
        count: How many thumbs the slider has.

    Returns:
        The label of the thumb, or nothing for the only thumb of a slider:
        its name is the one the slider is given.
    """
    if count == 1:
        return {}
    if count == 2:
        return {"aria_label": ("Minimum", "Maximum")[index]}
    return {"aria_label": f"Value {index + 1} of {count}"}


class SliderThumb(Part, elements.Input):
    """A thumb of a slider: a native range input."""

    tag = "input"

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the input.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the type of a range.
        """
        return super()._render(props).add_props(type="range")


class Slider(UIComponent):
    """Provides user selection from a range of values."""

    tag = "span"

    styles: ClassVar[ComponentStyles] = SLIDER

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(doc='Button size "1" - "3"')

    variant: Var[Literal["classic", "surface", "soft"]] = field(doc="Variant of button")

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    high_contrast: Var[bool] = field(
        doc="Whether to render the button with higher contrast color against background"
    )

    radius: Var[Literal["none", "small", "full"]] = field(
        doc='Override theme radius for button: "none" | "small" | "full"'
    )

    default_value: Var[Sequence[float | int] | float | int] = field(
        doc="The value of the slider when initially rendered. Use when you do not need to control the state of the slider."
    )

    value: Var[Sequence[float | int]] = field(
        doc="The controlled value of the slider. Must be used in conjunction with onValueChange."
    )

    name: Var[str] = field(
        doc="The name of the slider. Submitted with its owning form as part of a name/value pair."
    )

    width: Var[str | None] = field(
        default=Var.create("100%"), doc="The width of the slider."
    )

    min: Var[float | int] = field(doc="The minimum value of the slider.")

    max: Var[float | int] = field(doc="The maximum value of the slider.")

    step: Var[float | int] = field(doc="The step value of the slider.")

    disabled: Var[bool] = field(doc="Whether the slider is disabled")

    orientation: Var[Literal["horizontal", "vertical"]] = field(
        doc="The orientation of the slider."
    )

    on_change: EventHandler[on_value_event_spec] = field(
        doc="Fired when the value of the slider changes."
    )

    on_value_commit: EventHandler[on_value_event_spec] = field(
        doc="Fired when a thumb is released after being dragged."
    )

    @classmethod
    @functools.cache
    def _literal_props(cls) -> dict[str, tuple[str, ...]]:
        """Get the props that take listed values.

        Returns:
            The values of each such prop, the radius among them: a slider
            has fewer than a theme.
        """
        return {**super()._literal_props(), "radius": ("none", "small", "full")}

    @classmethod
    def create(
        cls,
        *children,
        **props,
    ) -> Component:
        """Create a Slider component.

        A slider has a thumb for each of its values: a native range input,
        which takes the ``id`` and the name of the slider. The ``aria_*``
        attributes of a slider with one thumb are the ones of its thumb;
        with several, they are the ones of the group the thumbs are.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The component.
        """
        default_value = props.pop("default_value", [50])
        width = props.pop("width", "100%")
        if isinstance(default_value, Var):
            if typehint_issubclass(default_value._var_type, int | float):
                default_value = [default_value]
        elif isinstance(default_value, (int, float)):
            default_value = [default_value]

        value = props.get("value")
        values = default_value if value is None else value
        low, high = props.get("min"), props.get("max")
        shared = {
            key: props[key]
            for key in ("min", "max", "step", "disabled")
            if props.get(key) is not None
        }
        named = {key: props[key] for key in props if key.startswith("aria_")}
        attribute = "default_value" if value is None else "value"
        name = props.get("name")
        thumbs: list[Any]
        if isinstance(values, Var) or len(values) > 1:
            # Several thumbs are a group with the name of the slider, each
            # with a name of its own.
            if named:
                props.setdefault("custom_attrs", {}).setdefault("role", "group")
        else:
            # The only thumb has the name of the slider.
            shared.update({key: props.pop(key) for key in named})
        if isinstance(values, Var):
            # The thumbs of a list in state are counted in the browser.
            several: Any = True
            thumbs = [
                foreach(
                    values,
                    lambda item: SliderThumb.create(
                        part="thumb", **shared, **{attribute: item}
                    ),
                )
            ]
            first = values[0]  # pyright: ignore[reportIndexIssue]
            start, end = _share(first, low, high), _share(values[-1], low, high)  # pyright: ignore[reportIndexIssue]
        else:
            several = len(values) > 1
            if name is not None and several:
                # As Radix names the inputs of a slider with several values.
                name = Var.create(name) + "[]"
            if name is not None:
                shared["name"] = name
            thumbs = [
                SliderThumb.create(
                    part="thumb",
                    **{**_label(index, len(values)), **shared, attribute: item},
                )
                for index, item in enumerate(values)
            ]
            if thumbs and "id" in props:
                thumbs[0].id = Var.create(props.pop("id"))
            start = _share(values[0], low, high) if several else "0%"
            end = _share(values[-1], low, high) if values else "0%"
        handlers = props.setdefault("custom_attrs", {})
        handlers.setdefault("onInputCapture", _SLIDE)
        if several:
            handlers.setdefault("onMouseDown", _PRESS)
        placement = {"width": width, START: start, END: end}
        style = props.get("style")
        if style is None:
            props["style"] = placement
        elif isinstance(style, (list, tuple)):
            props["style"] = [placement, *style]
        else:
            props["style"] = [placement, style]
        return super().create(
            Part.create(
                Part.create(part="range", tag="span"), part="track", tag="span"
            ),
            *thumbs,
            *children,
            _several=several,
            **props,
        )

    def _post_init(self, *args, **kwargs):
        """Initialize the slider.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component. ``_several`` says
                whether the slider has more than one thumb.
        """
        # What the style table reads as a variant.
        self._several = kwargs.pop("_several", False)
        super()._post_init(*args, **kwargs)

    def _set_slot(self) -> None:
        """Render the slider itself: it has no child to be rendered as."""

    def _exclude_props(self) -> list[str]:
        """Keep the props that are the ones of the thumbs off the element.

        Returns:
            The props read as styles, and what the slider hands its inputs.
        """
        return [
            *super()._exclude_props(),
            "disabled",
            "default_value",
            "value",
            "name",
            "min",
            "max",
            "step",
            "width",
        ]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the slider.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag. A thumb is released when the pointer or a key that
            moves it is: Radix says so with ``on_value_commit``.
        """
        tag = super()._render(props)
        orientation = self.orientation
        tag = tag.add_props(**{
            "data-orientation": "horizontal" if orientation is None else orientation
        })
        commit = tag.props.get("onValueCommit")
        if commit is None:
            return tag
        commit = LiteralVar.create(commit)
        var_data = commit._get_all_var_data()
        return tag.remove_props("onValueCommit").add_props(
            on_pointer_up=commit,
            on_key_up=Var(
                f"((event) => {{ if ({_KEYS}.includes(event.key)) "
                f"({commit!s})(event); }})",
                _var_data=var_data,
            ),
        )


slider = Slider.create
