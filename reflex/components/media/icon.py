"""An icon component."""

from reflex.components.component import Component
from reflex.utils import format


class ChakraIconComponent(Component):
    """A component that wraps a Chakra icon component."""

    library = "@chakra-ui/icons"


class Icon(ChakraIconComponent):
    """An image icon."""

    tag = "None"

    @classmethod
    def create(cls, *children, **props):
        """Initialize the Icon component.

        Run some additional checks on Icon component.

        Args:
            children: The positional arguments
            props: The keyword arguments

        Raises:
            AttributeError: The errors tied to bad usage of the Icon component.
            ValueError: If the icon tag is invalid.

        Returns:
            The created component.
        """
        if children:
            raise AttributeError(
                f"Passing children to Icon component is not allowed: remove positional arguments {children} to fix"
            )
        if "tag" not in props.keys():
            raise AttributeError("Missing 'tag' keyword-argument for Icon")
        if type(props["tag"]) != str or props["tag"].lower() not in ICON_LIST:
            raise ValueError(
                f"Invalid icon tag: {props['tag']}. Please use one of the following: {ICON_LIST}"
            )
        props["tag"] = format.to_title_case(props["tag"]) + "Icon"
        return super().create(*children, **props)


# List of all icons.
ICON_LIST = [
    "add",
    "arrow_back",
    "arrow_down",
    "arrow_forward",
    "arrow_left",
    "arrow_right",
    "arrow_up",
    "arrow_up_down",
    "at_sign",
    "attachment",
    "bell",
    "calendar",
    "check_circle",
    "check",
    "chevron_down",
    "chevron_left",
    "chevron_right",
    "chevron_up",
    "close",
    "copy",
    "delete",
    "download",
    "drag_handle",
    "edit",
    "email",
    "external_link",
    "hamburger",
    "info",
    "info_outline",
    "link",
    "lock",
    "minus",
    "moon",
    "not_allowed",
    "phone",
    "plus_square",
    "question",
    "question_outline",
    "repeat",
    "repeat_clock",
    "search",
    "search2",
    "settings",
    "small_add",
    "small_close",
    "spinner",
    "star",
    "sun",
    "time",
    "triangle_down",
    "triangle_up",
    "unlock",
    "up_down",
    "view",
    "view_off",
    "warning",
    "warning_two",
]
