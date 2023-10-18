"""Chakra Tag Component."""
from typing import Optional

from reflex.components.component import Component
from reflex.components.libs.chakra import (
    ChakraComponent,
    LiteralTagColorScheme,
    LiteralTagSize,
    LiteralVariant,
)
from reflex.vars import Var


class TagLabel(ChakraComponent):
    """The label of the tag."""

    tag = "TagLabel"


class TagLeftIcon(ChakraComponent):
    """The left icon of the tag."""

    tag = "TagLeftIcon"


class TagRightIcon(ChakraComponent):
    """The right icon of the tag."""

    tag = "TagRightIcon"


class TagCloseButton(ChakraComponent):
    """The close button of the tag."""

    tag = "TagCloseButton"


class Tag(ChakraComponent):
    """The parent wrapper that provides context for its children."""

    tag = "Tag"

    # The visual color appearance of the tag.
    # options: "gray" | "red" | "orange" | "yellow" | "green" | "teal" | "blue" |
    #  "cyan" | "purple" | "pink"
    # default: "gray"
    color_scheme: Var[LiteralTagColorScheme]

    # The size of the tag
    # options: "sm" | "md" | "lg"
    # default: "md"
    size: Var[LiteralTagSize]

    # The variant of the tag
    # options: "solid" | "subtle" | "outline"
    # default: "solid"
    variant: Var[LiteralVariant]

    @classmethod
    def create(
        cls,
        label: Component,
        *,
        left_icon: Optional[Component] = None,
        right_icon: Optional[Component] = None,
        close_button: Optional[Component] = None,
        **props,
    ) -> Component:
        """Creates a Chakra Tag with a label and optionally left_icon, right_icon, and close_button, and returns it.

        Args:
            label (Component): The label of the Tag that will be created.
            left_icon (Optional[Component]): Should be a rx.TagLeftIcon instance.
            right_icon (Optional[Component]): Should be a rx.TagRightIcon instance.
            close_button (Optional[Component]): Should be a rx.TagCloseButton instance.
            props: The properties to be passed to the component.

        Returns:
            The `create()` method returns a Tag object.
        """
        children = [
            x for x in (left_icon, label, right_icon, close_button) if x is not None
        ]
        return super().create(*children, **props)
