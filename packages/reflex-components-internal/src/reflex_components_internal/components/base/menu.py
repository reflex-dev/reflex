"""Custom menu component."""

from typing import Literal

from reflex_components_core.core.foreach import foreach

from reflex.components.component import Component, ComponentNamespace
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var
from reflex_components_internal.components.base.button import button
from reflex_components_internal.components.base_ui import PACKAGE_NAME, BaseUIComponent
from reflex_components_internal.components.icons.others import select_arrow
from reflex_components_internal.utils.twmerge import cn

LiteralOpenChangeReason = Literal[
    "arrowKey",
    "escapeKey",
    "select",
    "hover",
    "click",
    "focus",
    "dismiss",
    "typeahead",
    "tab",
]
LiteralMenuOrientation = Literal["vertical", "horizontal"]
LiteralSide = Literal["top", "right", "bottom", "left"]
LiteralAlign = Literal["start", "center", "end"]
LiteralPositionMethod = Literal["absolute", "fixed"]
LiteralCollisionAvoidance = Literal["flip", "shift", "auto"]
LiteralMenuSize = Literal["xs", "sm", "md", "lg", "xl"]


class ClassNames:
    """Class names for menu components."""

    TRIGGER = "flex min-w-48 items-center justify-between gap-3 select-none text-sm [&>span]:line-clamp-1 cursor-pointer focus:outline-none focus-visible:ring-1 focus-visible:ring-primary-4 group/trigger"
    PORTAL = "relative"
    ICON = "flex size-4 text-secondary-10 group-data-[disabled]/trigger:text-current"
    POPUP = "group/popup max-h-[17.25rem] overflow-y-auto origin-(--transform-origin) p-1 border border-secondary-a4 bg-secondary-1 shadow-large transition-[transform,scale,opacity] data-[ending-style]:scale-95 data-[starting-style]:scale-95 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0 outline-none [scrollbar-width:thin]"
    ITEM = "grid min-w-(--anchor-width) grid-cols-[1fr_auto] items-center gap-2 text-sm select-none font-medium group-data-[side=none]/popup:min-w-[calc(var(--anchor-width)+1rem)] text-secondary-12 cursor-pointer outline-none data-[highlighted]:bg-secondary-3 scroll-m-1 text-start"
    ITEM_INDICATOR = "text-current"
    ITEM_TEXT = "text-start"
    GROUP = "p-1"
    GROUP_LABEL = "px-2 py-1.5 text-sm font-semibold"
    SEPARATOR = "-mx-1 my-1 h-px bg-muted"
    ARROW = "data-[side=bottom]:top-[-8px] data-[side=left]:right-[-13px] data-[side=left]:rotate-90 data-[side=right]:left-[-13px] data-[side=right]:-rotate-90 data-[side=top]:bottom-[-8px] data-[side=top]:rotate-180"
    POSITIONER = "outline-none"
    RADIO_GROUP = ""
    RADIO_ITEM = "grid min-w-(--anchor-width) grid-cols-[1fr_auto] items-center gap-2 text-sm select-none font-[450] group-data-[side=none]/popup:min-w-[calc(var(--anchor-width)+1rem)] text-secondary-11 cursor-pointer outline-none data-[highlighted]:bg-secondary-3 scroll-m-1"
    RADIO_ITEM_INDICATOR = "text-current"
    CHECKBOX_ITEM = "grid min-w-(--anchor-width) grid-cols-[1fr_auto] items-center gap-2 text-sm select-none font-[450] group-data-[side=none]/popup:min-w-[calc(var(--anchor-width)+1rem)] text-secondary-11 cursor-pointer outline-none data-[highlighted]:bg-secondary-3 scroll-m-1"
    CHECKBOX_ITEM_INDICATOR = "text-current"
    SUBMENU_TRIGGER = "grid min-w-(--anchor-width) grid-cols-[1fr_auto] items-center gap-2 text-sm select-none font-[450] group-data-[side=none]/popup:min-w-[calc(var(--anchor-width)+1rem)] text-secondary-11 cursor-pointer outline-none data-[highlighted]:bg-secondary-3 scroll-m-1"


class MenuBaseComponent(BaseUIComponent):
    """Base component for menu components."""

    library = f"{PACKAGE_NAME}/menu"

    @property
    def import_var(self):
        """Return the import variable for the menu component."""
        return ImportVar(tag="Menu", package_path="", install=False)


class MenuRoot(MenuBaseComponent):
    """Groups all parts of the menu. Doesn't render its own HTML element."""

    tag = "Menu.Root"

    # Whether the menu is initially open. To render a controlled menu, use the open prop instead. Defaults to False.
    default_open: Var[bool]

    # Whether the menu is currently open.
    open: Var[bool]

    # Event handler called when the menu is opened or closed.
    on_open_change: EventHandler[passthrough_event_spec(bool, dict)]

    # Event handler called after any animations complete when the menu is closed.
    on_open_change_complete: EventHandler[passthrough_event_spec(bool)]

    # When in a submenu, determines whether pressing the Escape key closes the entire menu, or only the current child menu. Defaults to True.
    close_parent_on_esc: Var[bool]

    # Determines if the menu enters a modal state when open. Defaults to True.
    # - True: user interaction is limited to the menu: document page scroll is locked and and pointer interactions on outside elements are disabled.
    # - False: user interaction with the rest of the document is allowed.
    modal: Var[bool]

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # Whether to loop keyboard focus back to the first item when the end of the list is reached while using the arrow keys. Defaults to True.
    loop_focus: Var[bool]

    # The visual orientation of the menu. Controls whether roving focus uses up/down or left/right arrow keys. Defaults to 'vertical'.
    orientation: Var[LiteralMenuOrientation]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu root component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu"
        return super().create(*children, **props)


class MenuTrigger(MenuBaseComponent):
    """A button that opens the menu. Renders a <button> element."""

    tag = "Menu.Trigger"

    # Whether the component renders a native <button> element when replacing it via the render prop. Set to false if the rendered element is not a button (e.g. <div>). Defaults to True.
    native_button: Var[bool]

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # Whether the menu should also open when the trigger is hovered.
    open_on_hover: Var[bool]

    # How long to wait before the menu may be opened on hover. Specified in milliseconds. Requires the open_on_hover prop. Defaults to 100.
    delay: Var[int]

    # How long to wait before closing the menu that was opened on hover. Specified in milliseconds. Requires the open_on_hover prop. Defaults to 0.
    close_delay: Var[int]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-trigger"
        cls.set_class_name(ClassNames.TRIGGER, props)
        return super().create(*children, **props)


class MenuPortal(MenuBaseComponent):
    """A portal element that moves the popup to a different part of the DOM. By default, the portal element is appended to <body>."""

    tag = "Menu.Portal"

    # A parent element to render the portal element into.
    container: Var[str]

    # Whether to keep the portal mounted in the DOM while the popup is hidden. Defaults to False.
    keep_mounted: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu portal component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-portal"
        cls.set_class_name(ClassNames.PORTAL, props)
        return super().create(*children, **props)


class MenuPositioner(MenuBaseComponent):
    """Positions the menu popup against the trigger. Renders a <div> element."""

    tag = "Menu.Positioner"

    # Determines how to handle collisions when positioning the popup.
    collision_avoidance: Var[bool | LiteralCollisionAvoidance]

    # How to align the popup relative to the specified side. Defaults to "center".
    align: Var[LiteralAlign]

    # Additional offset along the alignment axis in pixels. Defaults to 0.
    align_offset: Var[int]

    # Which side of the anchor element to align the popup against. May automatically change to avoid collisions. Defaults to "bottom".
    side: Var[LiteralSide]

    # Distance between the anchor and the popup in pixels. Defaults to 0.
    side_offset: Var[int]

    # Minimum distance to maintain between the arrow and the edges of the popup. Use it to prevent the arrow element from hanging out of the rounded corners of a popup. Defaults to 5.
    arrow_padding: Var[int]

    # Additional space to maintain from the edge of the collision boundary. Defaults to 5.
    collision_padding: Var[int]

    # An element or a rectangle that delimits the area that the popup is confined to. Defaults to the "clipping-ancestors".
    collision_boundary: Var[str]

    # Whether to maintain the popup in the viewport after the anchor element was scrolled out of view. Defaults to False.
    sticky: Var[bool]

    # Whether to disable the popup tracking any layout shift of its positioning anchor. Defaults to False.
    disable_anchor_tracking: Var[bool]

    # Determines which CSS position property to use. Defaults to "absolute".
    position_method: Var[LiteralPositionMethod]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu positioner component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-positioner"
        props.setdefault("side_offset", 4)
        cls.set_class_name(ClassNames.POSITIONER, props)
        return super().create(*children, **props)


class MenuPopup(MenuBaseComponent):
    """A container for the menu items. Renders a <div> element."""

    tag = "Menu.Popup"

    # Determines the element to focus when the menu is closed. By default, focus returns to the trigger.
    final_focus: Var[str]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu popup component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-popup"
        cls.set_class_name(ClassNames.POPUP, props)
        return super().create(*children, **props)


class MenuArrow(MenuBaseComponent):
    """Displays an element positioned against the menu anchor. Renders a <div> element."""

    tag = "Menu.Arrow"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu arrow component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-arrow"
        cls.set_class_name(ClassNames.ARROW, props)
        return super().create(*children, **props)


class MenuItem(MenuBaseComponent):
    """An individual interactive item in the menu. Renders a <div> element."""

    tag = "Menu.Item"

    # Overrides the text label to use when the item is matched during keyboard text navigation.
    label: Var[str]

    # Whether to close the menu when the item is clicked. Defaults to True.
    close_on_click: Var[bool]

    # Whether the component renders a native <button> element when replacing it via the render prop. Set to false if the rendered element is not a button (e.g. <div>). Defaults to False.
    native_button: Var[bool]

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu item component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-item"
        cls.set_class_name(ClassNames.ITEM, props)
        return super().create(*children, **props)


class MenuLinkItem(MenuBaseComponent):
    """A menu item that renders as a link. Renders an <a> element."""

    tag = "Menu.LinkItem"

    # Overrides the text label to use when the item is matched during keyboard text navigation.
    label: Var[str]

    # The URL the link points to.
    href: Var[str]

    # Whether to close the menu when the item is clicked. Defaults to True.
    close_on_click: Var[bool]

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu link item component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-link-item"
        cls.set_class_name(ClassNames.ITEM, props)
        return super().create(*children, **props)


class MenuSubMenuRoot(MenuBaseComponent):
    """Groups all parts of a submenu. Doesn't render its own HTML element."""

    tag = "Menu.SubMenuRoot"

    # Whether the menu is initially open. To render a controlled menu, use the open prop instead. Defaults to False.
    default_open: Var[bool]

    # Whether the menu is currently open.
    open: Var[bool]

    # Event handler called when the menu is opened or closed.
    on_open_change: EventHandler[passthrough_event_spec(bool, dict)]

    # When in a submenu, determines whether pressing the Escape key closes the entire menu, or only the current child menu. Defaults to True.
    close_parent_on_esc: Var[bool]

    # Event handler called after any animations complete when the menu is closed.
    on_open_change_complete: EventHandler[passthrough_event_spec(bool)]

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # Whether to loop keyboard focus back to the first item when the end of the list is reached while using the arrow keys. Defaults to True.
    loop_focus: Var[bool]

    # The visual orientation of the menu. Controls whether roving focus uses up/down or left/right arrow keys. Defaults to 'vertical'.
    orientation: Var[LiteralMenuOrientation]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu submenu root component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-submenu-root"
        cls.set_class_name(ClassNames.ITEM_TEXT, props)
        return super().create(*children, **props)


class MenuSubMenuTrigger(MenuBaseComponent):
    """A menu item that opens a submenu."""

    tag = "Menu.SubMenuTrigger"

    # Overrides the text label to use when the item is matched during keyboard text navigation.
    label: Var[str]

    # Whether the component renders a native <button> element when replacing it via the render prop. Set to false if the rendered element is not a button (e.g. <div>). Defaults to False.
    native_button: Var[bool]

    # Whether the menu should also open when the trigger is hovered. Defaults to True.
    open_on_hover: Var[bool]

    # How long to wait before the menu may be opened on hover. Specified in milliseconds. Requires the open_on_hover prop. Defaults to 100.
    delay: Var[int]

    # How long to wait before closing the menu that was opened on hover. Specified in milliseconds. Requires the open_on_hover prop. Defaults to 0.
    close_delay: Var[int]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu submenu trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-submenu-trigger"
        cls.set_class_name(ClassNames.SUBMENU_TRIGGER, props)
        return super().create(*children, **props)


class MenuGroup(MenuBaseComponent):
    """Groups related menu items with the corresponding label. Renders a <div> element."""

    tag = "Menu.Group"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu group component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-group"
        cls.set_class_name(ClassNames.GROUP, props)
        return super().create(*children, **props)


class MenuGroupLabel(MenuBaseComponent):
    """An accessible label that is automatically associated with its parent group. Renders a <div> element."""

    tag = "Menu.GroupLabel"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu group label component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-group-label"
        cls.set_class_name(ClassNames.GROUP_LABEL, props)
        return super().create(*children, **props)


class MenuRadioGroup(MenuBaseComponent):
    """Groups related radio items. Renders a <div> element."""

    tag = "Menu.RadioGroup"

    # The uncontrolled value of the radio item that should be initially selected. To render a controlled radio group, use the value prop instead.
    default_value: Var[str | int]

    # The controlled value of the radio item that should be currently selected. To render an uncontrolled radio group, use the defaultValue prop instead.
    value: Var[str | int]

    # Function called when the selected value changes.
    on_value_change: EventHandler[passthrough_event_spec(str | int, dict)]

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu radio group component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-radio-group"
        cls.set_class_name(ClassNames.RADIO_GROUP, props)
        return super().create(*children, **props)


class MenuRadioItem(MenuBaseComponent):
    """A menu item that works like a radio button in a given group. Renders a <div> element."""

    tag = "Menu.RadioItem"

    # Overrides the text label to use when the item is matched during keyboard text navigation.
    label: Var[str]

    # Value of the radio item. This is the value that will be set in the MenuRadioGroup when the item is selected.
    value: Var[str | int]

    # Whether to close the menu when the item is clicked. Defaults to False.
    close_on_click: Var[bool]

    # Whether the component renders a native <button> element when replacing it via the render prop. Set to false if the rendered element is not a button (e.g. <div>). Defaults to False.
    native_button: Var[bool]

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu radio item component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-radio-item"
        cls.set_class_name(ClassNames.RADIO_ITEM, props)
        return super().create(*children, **props)


class MenuRadioItemIndicator(MenuBaseComponent):
    """Indicates whether the radio item is selected. Renders a <div> element."""

    tag = "Menu.RadioItemIndicator"

    # Whether to keep the HTML element in the DOM when the radio item is inactive. Defaults to False.
    keep_mounted: Var[bool]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu radio item indicator component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-radio-item-indicator"
        cls.set_class_name(ClassNames.RADIO_ITEM_INDICATOR, props)
        return super().create(*children, **props)


class MenuCheckboxItem(MenuBaseComponent):
    """A menu item that toggles a setting on or off. Renders a <div> element."""

    tag = "Menu.CheckboxItem"

    # Overrides the text label to use when the item is matched during keyboard text navigation.
    label: Var[str]

    # Whether the checkbox item is initially ticked. To render a controlled checkbox item, use the checked prop instead. Defaults to False.
    default_checked: Var[bool]

    # Whether the checkbox item is ticked. To render an uncontrolled checkbox item, use the default_checked prop instead.
    checked: Var[bool]

    # Event handler called when the checkbox item is ticked or unticked.
    on_checked_change: EventHandler[passthrough_event_spec(bool, dict)]

    # Whether to close the menu when the item is clicked. Defaults to False.
    close_on_click: Var[bool]

    # Whether the component renders a native <button> element when replacing it via the render prop. Set to false if the rendered element is not a button (e.g. <div>). Defaults to False.
    native_button: Var[bool]

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # The render prop.
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu checkbox item component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-checkbox-item"
        cls.set_class_name(ClassNames.CHECKBOX_ITEM, props)
        return super().create(*children, **props)


class MenuCheckboxItemIndicator(MenuBaseComponent):
    """Indicates whether the checkbox item is ticked. Renders a <div> element."""

    tag = "Menu.CheckboxItemIndicator"

    # Whether to keep the HTML element in the DOM when the checkbox item is not checked. Defaults to False.
    keep_mounted: Var[bool]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu checkbox item indicator component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-checkbox-item-indicator"
        cls.set_class_name(ClassNames.CHECKBOX_ITEM_INDICATOR, props)
        return super().create(*children, **props)


class MenuSeparator(MenuBaseComponent):
    """A separator element accessible to screen readers. Renders a <div> element."""

    tag = "Menu.Separator"

    # The orientation of the separator. Defaults to 'horizontal'.
    orientation: Var[LiteralMenuOrientation]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the menu separator component.

        Returns:
            The component.
        """
        props["data-slot"] = "menu-separator"
        cls.set_class_name(ClassNames.SEPARATOR, props)
        return super().create(*children, **props)


class HighLevelMenu(MenuRoot):
    """High level wrapper for the Menu component."""

    # The trigger component to use for the menu
    trigger: Var[Component | None]

    # The list of items to display in the menu dropdown - can be strings or tuples of (label, on_click_handler)
    items: Var[list[str | tuple[str, EventHandler]]]

    # The placeholder text to display when no item is selected
    placeholder: Var[str]

    # The size of the menu. Defaults to "md".
    size: Var[LiteralMenuSize]

    # Whether to close the menu when the item is clicked. Defaults to True.
    close_on_click: Var[bool]

    # Props for different component parts
    _item_props = {"close_on_click"}
    _trigger_props = {"open_on_hover", "delay", "close_delay", "trigger_variant"}
    _positioner_props = {
        "align",
        "align_offset",
        "side",
        "arrow_padding",
        "collision_padding",
        "sticky",
        "position_method",
        "disable_anchor_tracking",
        "side_offset",
        "collision_avoidance",
    }
    _portal_props = {"container"}

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create a menu component.

        Args:
            *children: Additional children to include in the menu.
            **props: Additional properties to apply to the menu component.

        Returns:
            The menu component.
        """
        # Extract props for different parts
        item_props = {k: props.pop(k) for k in cls._item_props & props.keys()}
        trigger_props = {k: props.pop(k) for k in cls._trigger_props & props.keys()}
        positioner_props = {
            k: props.pop(k) for k in cls._positioner_props & props.keys()
        }
        portal_props = {k: props.pop(k) for k in cls._portal_props & props.keys()}

        trigger = props.pop("trigger", None)
        items = props.pop("items", [])
        size = props.pop("size", "md")
        trigger_label = props.pop("placeholder", "Open Menu")
        trigger_variant = trigger_props.pop("trigger_variant", "outline")

        def create_menu_item(item: str | tuple[str, EventHandler]) -> BaseUIComponent:
            if isinstance(item, tuple):
                label, on_click_handler = item
                return MenuItem.create(
                    render_=button(
                        label,
                        variant="ghost",
                        class_name=ClassNames.ITEM,
                        disabled=props.get("disabled", False),
                        on_click=on_click_handler,
                        size=size,
                        type="button",
                    ),
                    key=label,
                    **item_props,
                )
            return MenuItem.create(
                render_=button(
                    item,
                    variant="ghost",
                    class_name=ClassNames.ITEM,
                    disabled=props.get("disabled", False),
                    size=size,
                    type="button",
                ),
                key=item,
                **item_props,
            )

        if isinstance(items, Var):
            items_children = foreach(items, create_menu_item)
        else:
            items_children = [create_menu_item(item) for item in items]

        return MenuRoot.create(
            MenuTrigger.create(
                render_=(
                    trigger
                    or button(
                        trigger_label,
                        select_arrow(class_name="size-4 text-secondary-9"),
                        variant=trigger_variant,
                        class_name=ClassNames.TRIGGER,
                        disabled=props.get("disabled", False),
                        size=size,
                        type="button",
                    )
                ),
                **trigger_props,
            ),
            MenuPortal.create(
                MenuPositioner.create(
                    MenuPopup.create(
                        items_children,
                        class_name=cn(
                            ClassNames.POPUP,
                            f"rounded-[calc(var(--radius-ui-{size})+0.25rem)]",
                        ),
                    ),
                    **positioner_props,
                ),
                **portal_props,
            ),
            *children,
            **props,
        )


class Menu(ComponentNamespace):
    """Namespace for Menu components."""

    root = staticmethod(MenuRoot.create)
    trigger = staticmethod(MenuTrigger.create)
    portal = staticmethod(MenuPortal.create)
    positioner = staticmethod(MenuPositioner.create)
    popup = staticmethod(MenuPopup.create)
    arrow = staticmethod(MenuArrow.create)
    item = staticmethod(MenuItem.create)
    link_item = staticmethod(MenuLinkItem.create)
    separator = staticmethod(MenuSeparator.create)
    group = staticmethod(MenuGroup.create)
    group_label = staticmethod(MenuGroupLabel.create)
    radio_group = staticmethod(MenuRadioGroup.create)
    radio_item = staticmethod(MenuRadioItem.create)
    radio_item_indicator = staticmethod(MenuRadioItemIndicator.create)
    checkbox_item = staticmethod(MenuCheckboxItem.create)
    checkbox_item_indicator = staticmethod(MenuCheckboxItemIndicator.create)
    submenu_root = staticmethod(MenuSubMenuRoot.create)
    submenu_trigger = staticmethod(MenuSubMenuTrigger.create)
    class_names = ClassNames
    __call__ = staticmethod(HighLevelMenu.create)


menu = Menu()
