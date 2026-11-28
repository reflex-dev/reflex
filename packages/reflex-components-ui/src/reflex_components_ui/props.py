"""The values of the props many rx.ui components share."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Literal

from reflex_base.vars.base import LiteralVar

from reflex_components_ui.style.lower import PROP_BREAKPOINTS, prop_breakpoint

LiteralAlign = Literal["start", "center", "end", "baseline", "stretch"]
LiteralJustify = Literal["start", "center", "end", "between"]
LiteralSpacing = Literal["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]
LiteralVariant = Literal["classic", "solid", "soft", "surface", "outline", "ghost"]


def style_before(props: dict[str, Any], style: Mapping[str, Any]) -> None:
    """Put styles a component works out before the ones it is given.

    Args:
        props: The props a component is created with, changed in place: the
            ``style`` of the element wins over what is put before it.
        style: The styles the component works out.
    """
    written = props.get("style")
    if written is None:
        props["style"] = style
    elif isinstance(written, (list, tuple)):
        props["style"] = [style, *written]
    else:
        props["style"] = [style, written]


def style_props(name: str, props: dict[str, Any], names: tuple[str, ...]) -> None:
    """Move the props that stand for a CSS property into the style of an element.

    Radix Themes has such props (``width``, ``min_width``...) beside the ones
    that choose among listed values. A value per breakpoint applies at the
    breakpoints of Radix Themes, as every prop does, and the ``style`` of the
    element wins over them.

    Args:
        name: The display name of the component, for error messages.
        props: The props a component is created with, changed in place.
        names: The props to move: each one is named after its CSS property.
    """
    style: dict[str, Any] = {}
    for prop in names:
        value = props.pop(prop, None)
        if isinstance(value, LiteralVar) and value._get_all_var_data() is None:
            value = value._var_value
        if isinstance(value, Mapping):
            for breakpoint, item in value.items():
                condition = prop_breakpoint(name, prop, breakpoint)
                if condition == "default":
                    style[prop] = item
                else:
                    style.setdefault(condition, {})[prop] = item
        elif value is not None:
            style[prop] = value
    if not style:
        return
    # In the order of the breakpoints, whatever the order they are given in.
    ordered = {key: item for key, item in style.items() if key in names}
    ordered.update(
        (media, style[media]) for media in PROP_BREAKPOINTS.values() if media in style
    )
    style_before(props, ordered)


def literal_value(value: Any) -> Any:
    """Read a prop that has to be known while compiling.

    Args:
        value: The value of the prop.

    Returns:
        The value a literal Var holds, or the value as given.
    """
    if isinstance(value, LiteralVar) and value._get_all_var_data() is None:
        return value._var_value
    return value
