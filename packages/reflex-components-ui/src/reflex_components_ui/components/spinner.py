"""A spinner: an animated sign that something is loading."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, field
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_core.base.fragment import Fragment
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.cond import cond

from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.spinner import SPINNER, SPINNER_WRAPPER

LiteralSpinnerSize = Literal["1", "2", "3"]

# How many leaves a spinner has.
LEAVES = 8


def leaves() -> list[Component]:
    """Create the leaves of a spinner, for the component whose part they are.

    Returns:
        The leaves.
    """
    return [Part.create(part="leaf", tag="span") for _ in range(LEAVES)]


def while_loading(loading: Any, shown: list[Any], otherwise: tuple[Any, ...]) -> Any:
    """Choose what a component shows by whether it is loading.

    Args:
        loading: The ``loading`` prop: a bool, or a Var holding one.
        shown: What is shown while loading.
        otherwise: What is shown the rest of the time.

    Returns:
        The children of the component.
    """
    if isinstance(loading, LiteralVar):
        loading = loading._var_value
    if isinstance(loading, Var):
        return [cond(loading, Fragment.create(*shown), Fragment.create(*otherwise))]
    return shown if loading else list(otherwise)


class SpinnerWrapper(UIComponent):
    """What a spinner with children renders: the spinner over their place."""

    tag = "span"

    styles: ClassVar[ComponentStyles] = SPINNER_WRAPPER


class Spinner(UIComponent):
    """A spinner component."""

    tag = "span"

    styles: ClassVar[ComponentStyles] = SPINNER

    loading: Var[bool] = field(
        doc="If set, show an rx.spinner instead of the component children."
    )

    size: Var[Responsive[LiteralSpinnerSize]] = field(doc="The size of the spinner.")

    def _exclude_props(self) -> list[str]:
        """Keep the props that are not attributes off the element.

        Returns:
            The props read as styles, and the one that chooses what is shown.
        """
        return [*super()._exclude_props(), "loading"]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a spinner, around the children it stands in for if any.

        Args:
            *children: What the spinner is shown in place of while loading.
            **props: The props of the spinner.

        Returns:
            The spinner, the children once they are no longer loading, or
            the element that shows the spinner over the place of the children.
        """
        loading = props.get("loading", True)
        spinner = super().create(*leaves(), **props)
        if children:
            shown: Any = SpinnerWrapper.create(
                Part.create(
                    *children,
                    part="content",
                    tag="span",
                    custom_attrs={"aria-hidden": True},
                ),
                Part.create(spinner, part="overlay", tag="span"),
            )
        else:
            shown = spinner
        (result,) = while_loading(loading, [shown], (Fragment.create(*children),))
        return result


spinner = Spinner.create
