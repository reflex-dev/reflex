"""A skeleton: a placeholder with the size of what is loading."""

from __future__ import annotations

import dataclasses
from typing import Any, ClassVar

from reflex_base.components.component import Component, field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.vars.base import Var
from reflex_components_core.base.fragment import Fragment
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_ui.base import UIComponent
from reflex_components_ui.components.spinner import while_loading
from reflex_components_ui.props import style_props
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.skeleton import SKELETON

# The props that are the CSS property of the same name.
_SIZE_PROPS = (
    "width",
    "min_width",
    "max_width",
    "height",
    "min_height",
    "max_height",
)


class Skeleton(UIComponent):
    """Skeleton component."""

    tag = "span"

    styles: ClassVar[ComponentStyles] = SKELETON

    loading: Var[bool] = field(
        doc="If set, show an rx.spinner instead of the component children."
    )

    width: Var[Responsive[str]] = field(doc="The width of the skeleton")

    min_width: Var[Responsive[str]] = field(doc="The minimum width of the skeleton")

    max_width: Var[Responsive[str]] = field(doc="The maximum width of the skeleton")

    height: Var[Responsive[str]] = field(doc="The height of the skeleton")

    min_height: Var[Responsive[str]] = field(doc="The minimum height of the skeleton")

    max_height: Var[Responsive[str]] = field(doc="The maximum height of the skeleton")

    _memoization_mode = MemoizationMode(recursive=False)

    # The element a skeleton is rendered as keeps its own styles: it is also
    # what shows once it is no longer loading.
    _merges_slot: ClassVar[bool] = False

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a skeleton in the place of its children while they load.

        A skeleton around one element is that element, with the look of a
        skeleton over its own: it has its size. Around anything else it is a
        span.

        Args:
            *children: What the skeleton stands in for.
            **props: The props of the skeleton.

        Returns:
            The skeleton, or the children once they are no longer loading.
        """
        loading = props.pop("loading", True)
        sized = any(prop in props for prop in _SIZE_PROPS)
        style_props("rx.ui.skeleton", props, _SIZE_PROPS)
        if sized and _is_element(children):
            # The size of the skeleton is over the one of the element it is
            # rendered as, which has class names of its own.
            style = props["style"]
            sizes = style[0] if isinstance(style, list) else style
            important = _important(sizes)
            props["style"] = (
                [important, *style[1:]] if isinstance(style, list) else important
            )
        skeleton = super().create(
            *children,
            custom_attrs={
                "aria-hidden": True,
                "tabIndex": -1,
                "inert": True,
                "data-rx-skeleton": "",
                **props.pop("custom_attrs", {}),
            },
            **props,
        )
        (shown,) = while_loading(loading, [skeleton], (Fragment.create(*children),))
        return shown

    def _post_init(self, *args, **kwargs):
        """Initialize the skeleton, rendered as its child when that is an element.

        The child keeps its own styles and the skeleton adds its own beside
        them, most of them important: the child is also what shows once it
        is no longer loading.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        children = kwargs.get("children", ())
        # What the style table reads as variants: whether the skeleton is
        # around text rather than rendered as an element, and whether it
        # rounds its corners.
        self._inline = not _is_element(children)
        self._rounded = self._inline or not _has_radius(children[0])
        super()._post_init(*args, **kwargs)
        if not self._inline:
            self._as_child = True
            # The child has to stay the child: a compile would otherwise
            # move one that is bound to state into a component of its own.
            self._memoization_mode = dataclasses.replace(
                self._memoization_mode, recursive=False
            )

    def _exclude_props(self) -> list[str]:
        """Keep the props that are not attributes off the element.

        Returns:
            The props read as styles, and the one that chooses what is shown.
        """
        return [*super()._exclude_props(), "loading"]


def _important(style: dict[str, Any]) -> dict[str, Any]:
    """Make the literal values of a style win over any other class name.

    Args:
        style: The style, with blocks under media queries.

    Returns:
        The style, each of its strings important.
    """
    return {
        key: _important(value)
        if isinstance(value, dict)
        else f"{value} !important"
        if value.__class__ is str
        else value
        for key, value in style.items()
    }


def _has_radius(child: Any) -> bool:
    """Whether an rx.ui element rounds its own corners.

    Args:
        child: The element a skeleton is rendered as.

    Returns:
        True if the styles of the element set its radius.
    """
    element_styles = getattr(child, "_element_styles", None)
    if element_styles is None:
        return False
    style = element_styles().style.style
    return "borderRadius" in style or "borderTopLeftRadius" in style


def _is_element(children: Any) -> bool:
    """Whether a skeleton has one child that renders an element.

    Args:
        children: The children of the skeleton.

    Returns:
        True if the skeleton is rendered as its child.
    """
    return (
        len(children) == 1
        and isinstance(children[0], Component)
        and type(children[0]).render in (Component.render, UIComponent.render)
    )


skeleton = Skeleton.create
