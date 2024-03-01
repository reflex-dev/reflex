"""Menu components."""
from __future__ import annotations

from typing import Any, List, Optional, Union

from reflex.components.chakra import (
    ChakraComponent,
    LiteralChakraDirection,
    LiteralMenuOption,
    LiteralMenuStrategy,
)
from reflex.components.chakra.forms.button import Button
from reflex.components.component import Component
from reflex.vars import Var


class Menu(ChakraComponent):
    """The wrapper component provides context, state, and focus management."""

    tag: str = "Menu"

    # The padding required to prevent the arrow from reaching the very edge of the popper.
    arrow_padding: Optional[Var[int]] = None

    # If true, the first enabled menu item will receive focus and be selected when the menu opens.
    auto_select: Optional[Var[bool]] = None

    # The boundary area for the popper. Used within the preventOverflow modifier
    boundary: Optional[Var[str]] = None

    # If true, the menu will close when you click outside the menu list
    close_on_blur: Optional[Var[bool]] = None

    # If true, the menu will close when a menu item is clicked
    close_on_select: Optional[Var[bool]] = None

    # If by default the menu is open.
    default_is_open: Optional[Var[bool]] = None

    # If rtl, popper placement positions will be flipped i.e. 'top-right' will become 'top-left' and vice-verse ("ltr" | "rtl")
    direction: Optional[Var[LiteralChakraDirection]] = None

    # If true, the popper will change its placement and flip when it's about to overflow its boundary area.
    flip: Optional[Var[bool]] = None

    # The distance or margin between the reference and popper. It is used internally to create an offset modifier. NB: If you define offset prop, it'll override the gutter.
    gutter: Optional[Var[int]] = None

    # Performance 🚀: If true, the MenuItem rendering will be deferred until the menu is open.
    is_lazy: Optional[Var[bool]] = None

    # Performance 🚀: The lazy behavior of menu's content when not visible. Only works when `isLazy={true}` - "unmount": The menu's content is always unmounted when not open. - "keepMounted": The menu's content initially unmounted, but stays mounted when menu is open.
    lazy_behavior: Optional[Var[str]] = None

    # Determines if the menu is open or not.
    is_open: Optional[Var[bool]] = None

    # If true, the popper will match the width of the reference at all times. It's useful for autocomplete, `date-picker` and select patterns.
    match_width: Optional[Var[bool]] = None

    # The placement of the popper relative to its reference.
    placement: Optional[Var[str]] = None

    # If true, will prevent the popper from being cut off and ensure it's visible within the boundary area.
    prevent_overflow: Optional[Var[bool]] = None

    # The CSS positioning strategy to use. ("fixed" | "absolute")
    strategy: Optional[Var[LiteralMenuStrategy]] = None

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_close": lambda: [],
            "on_open": lambda: [],
        }

    @classmethod
    def create(
        cls,
        *children,
        button: Optional[Component] = None,
        items: Optional[List] = None,
        **props,
    ) -> Component:
        """Create a menu component.

        Args:
            *children: The children of the component.
            button: the button that open the menu.
            items (list): The items of the menu.
            **props: The properties of the component.

        Returns:
            The menu component.
        """
        if len(children) == 0:
            children = []

            if button:
                if not isinstance(button, (MenuButton, Button)):
                    children.append(MenuButton.create(button))
                else:
                    children.append(button)
            if not items:
                items = []
            children.append(MenuList.create(items=items))
        return super().create(*children, **props)


class MenuButton(ChakraComponent):
    """The trigger for the menu list. Must be a direct child of Menu."""

    tag: str = "MenuButton"

    # The variant of the menu button.
    variant: Optional[Var[str]] = None

    # Components that are not allowed as children.
    _invalid_children: List[str] = ["Button", "MenuButton"]

    # The tag to use for the menu button.
    as_: Optional[Var[str]] = None


class MenuList(ChakraComponent):
    """The wrapper for the menu items. Must be a direct child of Menu."""

    tag: str = "MenuList"

    @classmethod
    def create(cls, *children, items: Optional[list] = None, **props) -> Component:
        """Create a MenuList component, and automatically wrap in MenuItem if not already one.

        Args:
            *children: The children of the component.
            items: A list of item to add as child of the component.
            **props: The properties of the component.

        Returns:
            The MenuList component.
        """
        if len(children) == 0:
            if items is None:
                items = []
            children = [
                child if isinstance(child, MenuItem) else MenuItem.create(child)
                for child in items
            ]
        return super().create(*children, **props)


class MenuItem(ChakraComponent):
    """The trigger that handles menu selection. Must be a direct child of a MenuList."""

    tag: str = "MenuItem"

    # Overrides the parent menu's closeOnSelect prop.
    close_on_select: Optional[Var[bool]] = None

    # Right-aligned label text content, useful for displaying hotkeys.
    command: Optional[Var[str]] = None

    # The spacing between the command and menu item's label.
    command_spacing: Optional[Var[int]] = None

    # If true, the menuitem will be disabled.
    is_disabled: Optional[Var[bool]] = None

    # If true and the menuitem is disabled, it'll remain keyboard-focusable
    is_focusable: Optional[Var[bool]] = None


class MenuItemOption(ChakraComponent):
    """The checkable menu item, to be used with MenuOptionGroup."""

    tag: str = "MenuItemOption"

    # Overrides the parent menu's closeOnSelect prop.
    close_on_select: Optional[Var[bool]] = None

    # Right-aligned label text content, useful for displaying hotkeys.
    command: Optional[Var[str]] = None

    # The spacing between the command and menu item's label.
    command_spacing: Optional[Var[int]] = None

    # Determines if menu item is checked.
    is_checked: Optional[Var[bool]] = None

    # If true, the menuitem will be disabled.
    is_disabled: Optional[Var[bool]] = None

    # If true and the menuitem is disabled, it'll remain keyboard-focusable
    is_focusable: Optional[Var[bool]] = None

    # "checkbox" | "radio"
    type_: Optional[Var[LiteralMenuOption]] = None

    # Value of the menu item.
    value: Optional[Var[str]] = None


class MenuGroup(ChakraComponent):
    """A wrapper to group related menu items."""

    tag: str = "MenuGroup"


class MenuOptionGroup(ChakraComponent):
    """A wrapper for checkable menu items (radio and checkbox)."""

    tag: str = "MenuOptionGroup"

    # "checkbox" | "radio"
    type_: Optional[Var[LiteralMenuOption]] = None

    # Value of the option group.
    value: Optional[Var[str]] = None


class MenuDivider(ChakraComponent):
    """A visual separator for menu items and groups."""

    tag: str = "MenuDivider"
