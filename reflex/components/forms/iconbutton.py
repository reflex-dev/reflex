"""An icon button component."""

# from reflex.components.typography.text import Text
from reflex.components.tags import Tag
from reflex.vars import Var
from reflex.components.libs.chakra import ChakraComponent
from reflex.components.component import Component
from reflex.utils import format
from reflex.components.media.icon import Icon

class ChakraIconComponent(Component):
    """A component that wraps a Chakra icon component."""

    library = "@chakra-ui/icons"

class IconButton(ChakraIconComponent):
    """A button with an icon."""

    tag = "IconButton"

    # The type of button.
    type: Var[str]

    #  A label that describes the button
    aria_label: Var[str]

    # The icon to be used in the button.
    icon: Var[str]

    # If true, the button will be styled in its active state.
    is_active: Var[bool]

    # If true, the button will be disabled.
    is_disabled: Var[bool]

    # If true, the button will show a spinner.
    is_loading: Var[bool]

    # If true, the button will be perfectly round. Else, it'll be slightly round
    is_round: Var[bool]

    # Replace the spinner component when isLoading is set to true
    spinner: Var[str]

    @classmethod
    def create(cls, **props):
        if "icon" not in props or "aria_label" not in props:
            raise AttributeError("Missing 'icon' or 'aria_label' keyword-argument for IconButton")
        icon_tag = props["icon"]
        if type(icon_tag) != str or icon_tag.lower() not in ICON_LIST:
            raise ValueError(
                f"Invalid icon tag: {icon_tag}. Please use one of the following: {ICON_LIST}"
            )
        icon_tag = format.to_title_case(props["icon"]) + "Icon"
        props["tag"] = "button"
        icon = Icon(tag=icon_tag)
        button = super().create(icon, **props)
        return button


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