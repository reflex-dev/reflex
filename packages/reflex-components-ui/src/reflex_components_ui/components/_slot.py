"""What the parts that are rendered as their child share: a trigger, a close button."""

from __future__ import annotations

import dataclasses
from typing import Any

from reflex_base.components.component import Component

from reflex_components_ui.base import UIComponent
from reflex_components_ui.layout.flex import Flex
from reflex_components_ui.style import StyleError


def held(children: tuple[Any, ...]) -> tuple[Any, ...]:
    """Get the children a part that acts on a press is created with.

    Such a part acts on a press, and so does a child with a handler of its
    own for one: that child is put in a flex container, which is then the
    part, as in the Radix components.

    Args:
        children: The children the part is given.

    Returns:
        The children, or the flex container around them.
    """
    for child in children:
        if "on_click" in getattr(child, "event_triggers", {}):
            return (Flex.create(*children),)
    return children


def become_child(part: UIComponent) -> None:
    """Have a part render as its only child.

    Args:
        part: The part, once it is initialized.

    Raises:
        StyleError: If the part does not have exactly one child that is an
            element.
    """
    children = part.children
    if (
        len(children) != 1
        or not isinstance(children[0], Component)
        or type(children[0]).render not in (Component.render, UIComponent.render)
    ):
        msg = (
            f"{type(part)._display_name()}: it is rendered as its child, so it "
            "needs exactly one child that is an element, such as a button."
        )
        raise StyleError(msg)
    part._as_child = True
    # The child has to stay the child: a compile would otherwise move one
    # that is bound to state into a component of its own.
    part._memoization_mode = dataclasses.replace(
        part._memoization_mode, recursive=False
    )
