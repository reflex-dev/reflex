"""SegmentedControl from Radix Themes."""

from __future__ import annotations

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, field
from reflex_base.event import EventHandler
from reflex_base.vars.base import CustomVarOperationReturn, Var, var_operation
from reflex_base.vars.sequence import ArrayVar, LiteralArrayVar
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.foreach import Foreach

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent

_COUNT_VAR = "--rx-sc-count"
_IDX_VAR = "--rx-sc-idx"


def on_value_change(
    value: Var[str | list[str]],
) -> tuple[Var[str | list[str]]]:
    """Handle the on_value_change event.

    Args:
        value: The value of the event.

    Returns:
        The value of the event.
    """
    return (value,)


def _collect_item_values(children: Sequence[Any]) -> ArrayVar | None:
    """Collect item `value` props as an ArrayVar, or None if unsupported.

    Args:
        children: The children passed to `SegmentedControlRoot.create`.

    Returns:
        An ArrayVar of values for a single `rx.foreach` producing items, or
        for a flat list of `SegmentedControlItem`. None for anything else so
        the caller skips the fix and Radix's default behavior applies.
    """
    if len(children) == 1 and isinstance(children[0], Foreach):
        foreach = children[0]
        iterable = foreach.iterable
        if not isinstance(iterable, ArrayVar) or not isinstance(
            foreach.render_fn(iterable[0]), SegmentedControlItem
        ):
            return None
        return iterable.foreach(lambda element: foreach.render_fn(element).value)  # pyright: ignore[reportAttributeAccessIssue]

    values: list[Var] = []
    for child in children:
        if not isinstance(child, SegmentedControlItem):
            return None
        value = getattr(child, "value", None)
        if value is None:
            return None
        values.append(value)
    return LiteralArrayVar.create(values) if values else None


@var_operation
def _array_index_of_operation(
    haystack: ArrayVar, needle: Var
) -> CustomVarOperationReturn[int]:
    """Build a JS `haystack.indexOf(needle)` expression as a Var.

    Args:
        haystack: The array to search.
        needle: The value to find.

    Returns:
        A NumberVar that evaluates to the 0-based index or -1.
    """
    return CustomVarOperationReturn.create(
        js_expression=f"({haystack}.indexOf({needle}))",
        _var_type=int,
    )


class SegmentedControlRoot(RadixThemesComponent):
    """Root element for a SegmentedControl component."""

    tag = "SegmentedControl.Root"

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc='The size of the segmented control: "1" | "2" | "3"'
    )

    variant: Var[Literal["classic", "surface"]] = field(
        doc='Variant of button: "classic" | "surface"'
    )

    type: Var[Literal["single", "multiple"]] = field(
        doc='The type of the segmented control, either "single" for selecting one option or "multiple" for selecting multiple options.'
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    radius: Var[Literal["none", "small", "medium", "large", "full"]] = field(
        doc='The radius of the segmented control: "none" | "small" | "medium" | "large" | "full"'
    )

    default_value: Var[str | Sequence[str]] = field(
        doc="The default value of the segmented control."
    )

    value: Var[str | Sequence[str]] = field(
        doc="The current value of the segmented control."
    )

    on_change: EventHandler[on_value_change] = field(
        doc="Handles the `onChange` event for the SegmentedControl component."
    )

    _rename_props = {"onChange": "onValueChange"}

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a SegmentedControlRoot.

        Radix Themes 3.3.0 hardcodes indicator width/translate CSS rules for up
        to 10 items (see radix-ui/themes#730). When there are more items the
        indicator collapses to zero width. Work around that by exposing the
        selected item's index and the item count as CSS custom properties on
        the root so the style override in `add_style` can position the
        indicator using `calc()` regardless of item count.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The SegmentedControlRoot component.
        """
        if props.get("type") != "multiple":
            values_var = _collect_item_values(children)
            selected = props.get("value", props.get("default_value"))
            if values_var is not None and selected is not None:
                selected_var = Var.create(selected)
                style = dict(props.get("style") or {})
                style.setdefault(_COUNT_VAR, values_var.length())
                style.setdefault(
                    _IDX_VAR, _array_index_of_operation(values_var, selected_var)
                )
                props["style"] = style
        return super().create(*children, **props)

    def add_style(self) -> dict[str, Any] | None:
        """Override Radix's hardcoded nth-child indicator rules.

        Returns:
            Style targeting the indicator so its width and translation depend
            on the custom properties set in `create`, or ``None`` when those
            properties were not injected — in which case Radix's default
            nth-child rules still apply (correct for ≤10 items).
        """
        if _COUNT_VAR not in self.style:
            return None
        return {
            "& .rt-SegmentedControlIndicator": {
                "width": f"calc(100% / var({_COUNT_VAR}))",
                "transform": f"translateX(calc(var({_IDX_VAR}) * 100%))",
            },
        }


class SegmentedControlItem(RadixThemesComponent):
    """An item in the SegmentedControl component."""

    tag = "SegmentedControl.Item"

    value: Var[str] = field(doc="The value of the item.")

    _valid_parents: ClassVar[list[str]] = ["SegmentedControlRoot"]


class SegmentedControl(SimpleNamespace):
    """SegmentedControl components namespace."""

    root = staticmethod(SegmentedControlRoot.create)
    item = staticmethod(SegmentedControlItem.create)


segmented_control = SegmentedControl()
