"""A progress bar: how far something is, or that it is under way."""

from __future__ import annotations

import math
from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, field
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.progress import DURATION, FILL, MAX, PROGRESS, VALUE
from reflex_components_ui.themes import LiteralAccentColor, LiteralRadius

# The maximum of a bar that is given none, or one that is not above zero.
DEFAULT_MAX = 100


def _is_number(value: Any) -> bool:
    """Tell whether a literal is a number, as JavaScript has them.

    Args:
        value: The literal.

    Returns:
        Whether it is an int or a float, and not NaN.
    """
    return (value.__class__ is int or value.__class__ is float) and not math.isnan(
        value
    )


def _state(value: Any, maximum: Any) -> dict[str, Any]:
    """Describe how far a bar is, the way Radix Themes says it.

    A value that is not a number between zero and the maximum is no value:
    the bar is then indeterminate, as it is without one.

    Args:
        value: The ``value`` prop: a number, a Var or None.
        maximum: The ``max`` prop: a number, a Var or None.

    Returns:
        The attributes of the element: ``max``, ``now``, ``text`` and
        ``state``, each a literal or a Var, ``now`` and ``text`` None for a
        bar that is known to have no value.
    """
    if isinstance(maximum, Var):
        limit = (
            f'(typeof {maximum!s} === "number" && {maximum!s} > 0 '
            f"? {maximum!s} : {DEFAULT_MAX})"
        )
        maximum_data = maximum._get_all_var_data()
    else:
        if not (_is_number(maximum) and maximum > 0):
            maximum = DEFAULT_MAX
        limit = str(LiteralVar.create(maximum))
        maximum_data = None
        if not isinstance(value, Var):
            if not (_is_number(value) and 0 <= value <= maximum):
                return {
                    "max": maximum,
                    "now": None,
                    "text": None,
                    "state": "indeterminate",
                }
            return {
                "max": maximum,
                "now": value,
                # Rounded as JavaScript rounds: a half goes up.
                "text": f"{math.floor(value / maximum * 100 + 0.5)}%",
                "state": "complete" if value == maximum else "loading",
            }
    if value is None:
        return {
            "max": Var(limit, _var_type=float, _var_data=maximum_data),
            "now": None,
            "text": None,
            "state": "indeterminate",
        }
    now = str(LiteralVar.create(value))
    valid = f'typeof {now} === "number" && {now} >= 0 && {now} <= {limit}'
    data = VarData.merge(
        value._get_all_var_data() if isinstance(value, Var) else None, maximum_data
    )
    return {
        "max": Var(limit, _var_type=float, _var_data=data),
        "now": Var(f"({valid} ? {now} : undefined)", _var_data=data),
        "text": Var(
            f'({valid} ? Math.round({now} / {limit} * 100) + "%" : undefined)',
            _var_data=data,
        ),
        "state": Var(
            f'({valid} ? ({now} === {limit} ? "complete" : "loading") '
            ': "indeterminate")',
            _var_type=str,
            _var_data=data,
        ),
    }


def _known(value: Any) -> Any:
    """Read a prop that may be known while compiling.

    Args:
        value: The value of the prop.

    Returns:
        The value a literal Var holds, or the value as given.
    """
    if isinstance(value, LiteralVar) and value._get_all_var_data() is None:
        return value._var_value
    return value


def _css_number(value: Any) -> Any:
    """Write a number as the value of a custom property.

    Args:
        value: A number, or a Var.

    Returns:
        The Var, or the number as text: a custom property takes no unit.
    """
    return value if isinstance(value, Var) else str(LiteralVar.create(value))


class Progress(UIComponent):
    """A progress bar component."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = PROGRESS

    value: Var[int] = field(doc="The value of the progress bar: 0 to max (default 100)")

    max: Var[int] = field(doc="The maximum progress value.")

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc='The size of the progress bar: "1" | "2" | "3"'
    )

    variant: Var[Literal["classic", "surface", "soft"]] = field(
        doc='The variant of the progress bar: "classic" | "surface" | "soft"'
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc="The color theme of the progress bar"
    )

    high_contrast: Var[bool] = field(
        doc="Whether to render the progress bar with higher contrast color against background"
    )

    radius: Var[LiteralRadius] = field(
        doc='Override theme radius for progress bar: "none" | "small" | "medium" | "large" | "full"'
    )

    duration: Var[str] = field(
        doc="The duration of the progress bar animation. Once the duration times out, the progress bar will start an indeterminate animation."
    )

    fill_color: Var[str] = field(doc="The color of the progress bar fill animation.")

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a Progress component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The Progress Component.
        """
        props.setdefault("width", "100%")
        value = _known(props.get("value"))
        maximum = _known(props.get("max"))
        state = _state(value, maximum)
        # The indicator reads how far it is from custom properties, so a
        # value bound to state moves it without a render of its own.
        if value is not None:
            props[VALUE] = _css_number(value)
        elif props.get("duration") is not None:
            props[DURATION] = props["duration"]
        if maximum is not None:
            props[MAX] = _css_number(maximum)
        if props.get("fill_color") is not None:
            props[FILL] = props["fill_color"]
        attrs = {
            "aria-valuemax": state["max"],
            "aria-valuemin": 0,
            "aria-valuenow": state["now"],
            "aria-valuetext": state["text"],
            "role": "progressbar",
            "data-state": state["state"],
            "data-value": state["now"],
            "data-max": state["max"],
        }
        props["custom_attrs"] = {
            **{
                name: attr
                for name, attr in attrs.items()
                if attr is not None and name.replace("-", "_") not in props
            },
            **props.get("custom_attrs", {}),
        }
        indicator = Part.create(
            part="indicator",
            tag="div",
            custom_attrs={
                name: attrs[name]
                for name in ("data-state", "data-value", "data-max")
                if attrs[name] is not None
            },
        )
        # Radix Themes renders the indicator alone, whatever the children.
        return super().create(indicator, **props)

    def _exclude_props(self) -> list[str]:
        """Keep the props that are not attributes off the element.

        Returns:
            The props read as styles, and the ones the custom properties and
            the ARIA attributes of the element are made from.
        """
        return [*super()._exclude_props(), "value", "max", "duration", "fill_color"]


progress = Progress.create
