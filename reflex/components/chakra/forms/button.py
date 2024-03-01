"""A button component."""
from typing import List, Optional

from reflex.components.chakra import (
    ChakraComponent,
    LiteralButtonSize,
    LiteralButtonVariant,
    LiteralColorScheme,
    LiteralSpinnerPlacement,
)
from reflex.vars import Var


class Button(ChakraComponent):
    """The Button component is used to trigger an event or event, such as submitting a form, opening a dialog, canceling an event, or performing a delete operation."""

    tag: str = "Button"

    # The space between the button icon and label.
    icon_spacing: Optional[Var[int]] = None

    # If true, the button will be styled in its active state.
    is_active: Optional[Var[bool]] = None

    # If true, the button will be styled in its disabled state.
    is_disabled: Optional[Var[bool]] = None

    # If true, the button will take up the full width of its container.
    is_full_width: Optional[Var[bool]] = None

    # If true, the button will show a spinner.
    is_loading: Optional[Var[bool]] = None

    # The label to show in the button when isLoading is true If no text is passed, it only shows the spinner.
    loading_text: Optional[Var[str]] = None

    # "lg" | "md" | "sm" | "xs"
    size: Optional[Var[LiteralButtonSize]] = None

    # "ghost" | "outline" | "solid" | "link" | "unstyled"
    variant: Optional[Var[LiteralButtonVariant]] = None

    # Built in color scheme for ease of use.
    # Options:
    # "whiteAlpha" | "blackAlpha" | "gray" | "red" | "orange" | "yellow" | "green" | "teal" | "blue" | "cyan"
    # | "purple" | "pink" | "linkedin" | "facebook" | "messenger" | "whatsapp" | "twitter" | "telegram"
    color_scheme: Optional[Var[LiteralColorScheme]] = None

    # Position of the loading spinner.
    # Options:
    # "start" | "end"
    spinner_placement: Optional[Var[LiteralSpinnerPlacement]] = None

    # The type of button.
    type_: Optional[Var[str]] = None

    # Components that are not allowed as children.
    _invalid_children: List[str] = ["Button", "MenuButton"]

    # The name of the form field
    name: Optional[Var[str]] = None


class ButtonGroup(ChakraComponent):
    """A group of buttons."""

    tag: str = "ButtonGroup"

    # If true, the borderRadius of button that are direct children will be altered to look flushed together.
    is_attached: Optional[Var[bool]] = None

    # If true, all wrapped button will be disabled.
    is_disabled: Optional[Var[bool]] = None

    # The spacing between the buttons.
    spacing: Optional[Var[int]] = None

    # "lg" | "md" | "sm" | "xs"
    size: Optional[Var[LiteralButtonSize]] = None

    # "ghost" | "outline" | "solid" | "link" | "unstyled"
    variant: Optional[Var[LiteralButtonVariant]] = None
