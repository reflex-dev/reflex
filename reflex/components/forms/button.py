"""A button component."""

from reflex.components.libs.chakra import ChakraComponent
from reflex.vars import Var


class Button(ChakraComponent):
    """The Button component is used to trigger an event or event, such as submitting a form, opening a dialog, canceling an event, or performing a delete operation."""

    tag = "Button"

    # The space between the button icon and label.
    icon_spacing: Var[int]

    # If true, the button will be styled in its active state.
    is_active: Var[bool]

    # If true, the button will be styled in its disabled state.
    is_disabled: Var[bool]

    # If true, the button will take up the full width of its container.
    is_full_width: Var[bool]

    # If true, the button will show a spinner.
    is_loading: Var[bool]

    # The label to show in the button when isLoading is true If no text is passed, it only shows the spinner.
    loading_text: Var[str]

    # "lg" | "md" | "sm" | "xs"
    size: Var[str]

    # "ghost" | "outline" | "solid" | "link" | "unstyled"
    variant: Var[str]

    # Built in color scheme for ease of use.
    # Options:
    # "whiteAlpha" | "blackAlpha" | "gray" | "red" | "orange" | "yellow" | "green" | "teal" | "blue" | "cyan"
    # | "purple" | "pink" | "linkedin" | "facebook" | "messenger" | "whatsapp" | "twitter" | "telegram"
    color_scheme: Var[str]

    # The type of button.
    type_: Var[str]


class ButtonGroup(ChakraComponent):
    """A group of buttons."""

    tag = "ButtonGroup"

    # If true, the borderRadius of button that are direct children will be altered to look flushed together.
    is_attached: Var[bool]

    # If true, all wrapped button will be disabled.
    is_disabled: Var[bool]

    # The spacing between the buttons.
    spacing: Var[int]
