"""Menu components."""

from typing import Set

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Menu(ChakraComponent):
    """The wrapper component provides context, state, and focus management."""

    tag = "Menu"

    # The padding required to prevent the arrow from reaching the very edge of the popper.
    arrow_padding: Var[int]

    # If true, the first enabled menu item will receive focus and be selected when the menu opens.
    auto_select: Var[bool]

    # The boundary area for the popper. Used within the preventOverflow modifier
    boundary: Var[str]

    # If true, the menu will close when you click outside the menu list
    close_on_blur: Var[bool]

    # If true, the menu will close when a menu item is clicked
    close_on_select: Var[bool]

    # If by default the menu is open.
    default_is_open: Var[bool]

    # If rtl, poper placement positions will be flipped i.e. 'top-right' will become 'top-left' and vice-verse ("ltr" | "rtl")
    direction: Var[str]

    # If true, the popper will change its placement and flip when it's about to overflow its boundary area.
    flip: Var[bool]

    # The distance or margin between the reference and popper. It is used internally to create an offset modifier. NB: If you define offset prop, it'll override the gutter.
    gutter: Var[int]

    # Performance 🚀: If true, the MenuItem rendering will be deferred until the menu is open.
    is_lazy: Var[bool]

    # Performance 🚀: The lazy behavior of menu's content when not visible. Only works when `isLazy={true}` - "unmount": The menu's content is always unmounted when not open. - "keepMounted": The menu's content initially unmounted, but stays mounted when menu is open.
    lazy_behavior: Var[str]

    # Determines if the menu is open or not.
    is_open: Var[bool]

    # If true, the popper will match the width of the reference at all times. It's useful for autocomplete, `date-picker` and select patterns.
    match_width: Var[bool]

    # The placement of the popper relative to its reference.
    placement: Var[str]

    # If true, will prevent the popper from being cut off and ensure it's visible within the boundary area.
    prevent_overflow: Var[bool]

    # The CSS positioning strategy to use. ("fixed" | "absolute")
    strategy: Var[str]

    @classmethod
    def get_triggers(cls) -> Set[str]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return super().get_triggers() | {"on_close", "on_open"}


class MenuButton(ChakraComponent):
    """The trigger for the menu list. Must be a direct child of Menu."""

    tag = "MenuButton"

    # The variant of the menu button.
    variant: Var[str]

    # The tag to use for the menu button.
    as_: Var[str]


class MenuList(ChakraComponent):
    """The wrapper for the menu items. Must be a direct child of Menu."""

    tag = "MenuList"


class MenuItem(Menu):
    """The trigger that handles menu selection. Must be a direct child of a MenuList."""

    tag = "MenuItem"

    # Overrides the parent menu's closeOnSelect prop.
    close_on_select: Var[bool]

    # Right-aligned label text content, useful for displaying hotkeys.
    command: Var[str]

    # The spacing between the command and menu item's label.
    command_spacing: Var[int]

    # If true, the menuitem will be disabled.
    is_disabled: Var[bool]

    # If true and the menuitem is disabled, it'll remain keyboard-focusable
    is_focusable: Var[bool]


class MenuItemOption(Menu):
    """The checkable menu item, to be used with MenuOptionGroup."""

    tag = "MenuItemOption"

    # Overrides the parent menu's closeOnSelect prop.
    close_on_select: Var[bool]

    # Right-aligned label text content, useful for displaying hotkeys.
    command: Var[str]

    # The spacing between the command and menu item's label.
    command_spacing: Var[int]

    # Determines if menu item is checked.
    is_checked: Var[bool]

    # If true, the menuitem will be disabled.
    is_disabled: Var[bool]

    # If true and the menuitem is disabled, it'll remain keyboard-focusable
    is_focusable: Var[bool]

    # "checkbox" | "radio"
    type_: Var[str]

    # Value of the menu item.
    value: Var[str]


class MenuGroup(Menu):
    """A wrapper to group related menu items."""

    tag = "MenuGroup"


class MenuOptionGroup(Menu):
    """A wrapper for checkable menu items (radio and checkbox)."""

    tag = "MenuOptionGroup"

    # "checkbox" | "radio"
    type_: Var[str]

    # Value of the option group.
    value: Var[str]


class MenuDivider(Menu):
    """A visual separator for menu items and groups."""

    tag = "MenuDivider"
