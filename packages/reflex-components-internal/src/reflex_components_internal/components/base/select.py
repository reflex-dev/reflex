"""Custom select component."""

from typing import Any, Literal

from reflex_components_core.core.foreach import foreach

from reflex.components.component import Component, ComponentNamespace
from reflex.event import EventHandler, passthrough_event_spec
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var
from reflex_components_internal.components.base.button import (
    LiteralButtonVariant,
    button,
)
from reflex_components_internal.components.base_ui import PACKAGE_NAME, BaseUIComponent
from reflex_components_internal.components.icons.hugeicon import hi
from reflex_components_internal.components.icons.others import select_arrow
from reflex_components_internal.utils.twmerge import cn

LiteralSelectSize = Literal["xs", "sm", "md", "lg", "xl"]
LiteralAlign = Literal["start", "center", "end"]
LiteralSide = Literal["bottom", "inline-end", "inline-start", "left", "right", "top"]
LiteralPosition = Literal["absolute", "fixed"]
LiteralOrientation = Literal["horizontal", "vertical"]


class ClassNames:
    """Class names for select components."""

    LABEL = "block text-sm font-medium text-secondary-12"
    TRIGGER = "flex min-w-48 items-center justify-between gap-3 select-none text-sm [&>span]:line-clamp-1 cursor-pointer focus:outline-none focus-visible:ring-1 focus-visible:ring-primary-4 group/trigger"
    VALUE = "flex-1 text-left"
    ICON = "flex size-4 text-secondary-10 group-data-[disabled]/trigger:text-current"
    POPUP = "group/popup max-h-[17.25rem] overflow-y-auto origin-(--transform-origin) p-1 border border-secondary-a4 bg-secondary-1 shadow-large transition-[transform,scale,opacity] data-[ending-style]:scale-95 data-[starting-style]:scale-95 data-[ending-style]:opacity-0 data-[starting-style]:opacity-0 outline-none [scrollbar-width:thin]"
    ITEM = "grid min-w-(--anchor-width) grid-cols-[1fr_auto] items-center gap-2 text-sm select-none font-[450] group-data-[side=none]/popup:min-w-[calc(var(--anchor-width)+1rem)] data-[selected]:text-secondary-12 text-secondary-11 cursor-pointer placeholder:text-secondary-9 data-[selected]:font-medium outline-none data-[highlighted]:bg-secondary-3 scroll-m-1"
    ITEM_INDICATOR = "text-current"
    ITEM_TEXT = "text-start"
    GROUP = "p-1"
    GROUP_LABEL = "px-2 py-1.5 text-sm font-semibold"
    SEPARATOR = "-mx-1 my-1 h-px bg-muted"
    ARROW = "data-[side=bottom]:top-[-8px] data-[side=left]:right-[-13px] data-[side=left]:rotate-90 data-[side=right]:left-[-13px] data-[side=right]:-rotate-90 data-[side=top]:bottom-[-8px] data-[side=top]:rotate-180"
    POSITIONER = "outline-none"
    SCROLL_ARROW_UP = "top-0 z-[1] flex h-4 w-full cursor-default items-center justify-center rounded-ui-md bg-secondary-1 text-center text-xs before:absolute before:top-[-100%] before:left-0 before:h-full before:w-full before:content-[''] data-[direction=down]:bottom-0 data-[direction=down]:before:bottom-[-100%]"
    SCROLL_ARROW_DOWN = "bottom-0 z-[1] flex h-4 w-full cursor-default items-center justify-center rounded-ui-md bg-secondary-1 text-center text-xs before:absolute before:top-[-100%] before:left-0 before:h-full before:w-full before:content-[''] data-[direction=down]:bottom-0 data-[direction=down]:before:bottom-[-100%]"


class SelectBaseComponent(BaseUIComponent):
    """Base component for select components."""

    library = f"{PACKAGE_NAME}/select"

    @property
    def import_var(self):
        """Return the import variable for the select component."""
        return ImportVar(tag="Select", package_path="", install=False)


class SelectRoot(SelectBaseComponent):
    """Groups all parts of the select. Doesn't render its own HTML element."""

    tag = "Select.Root"

    # Identifies the field when a form is submitted.
    name: Var[str]

    # The uncontrolled value of the select when it's initially rendered.
    # To render a controlled select, use the `value` prop instead.
    default_value: Var[Any]

    # The value of the select
    value: Var[Any]

    # Callback fired when the value of the select changes. Use when controlled.
    on_value_change: EventHandler[passthrough_event_spec(str)]

    # Whether the select popup is initially open.
    # To render a controlled select popup, use the `open` prop instead.
    default_open: Var[bool]

    # Whether the select popup is currently open
    open: Var[bool]

    # Event handler called when the select popup is opened or closed
    on_open_change: EventHandler[passthrough_event_spec(bool)]

    # A ref to imperative actions.
    # When specified, the select will not be unmounted when closed.
    # Instead, the `unmount` function must be called to unmount the select manually.
    # Useful when the select's animation is controlled by an external library.
    actions_ref: Var[str]

    # Custom comparison logic used to determine if a select item value matches the current selected value.
    # Useful when item values are objects without matching referentially.
    # Defaults to `Object.is` comparison.
    is_item_equal_to_value: Var[Any]

    # When the item values are objects, this function converts the object value to a string representation for display in the trigger.
    # If the shape of the object is `{ value, label }`, the label will be used automatically without needing to specify this prop.
    item_to_string_label: Var[Any]

    # When the item values are objects, this function converts the object value to a string representation for form submission.
    # If the shape of the object is `{ value, label }`, the value will be used automatically without needing to specify this prop.
    item_to_string_value: Var[Any]

    # Data structure of the items rendered in the select popup.
    # When specified, `<Select.Value>` renders the label of the selected item instead of the raw value.
    items: Var[Any]

    # Determines if the select enters a modal state when open.
    # - True: user interaction is limited to the select: document page scroll is locked and pointer interactions on outside elements are disabled.
    # - False: user interaction with the rest of the document is allowed. Defaults to True.
    modal: Var[bool]

    # Whether multiple items can be selected. Defaults to False.
    multiple: Var[bool]

    # Event handler called after any animations complete when the select popup is opened or closed
    on_open_change_complete: EventHandler[passthrough_event_spec(bool)]

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # Whether the user should be unable to choose a different option from the select popup. Defaults to False.
    read_only: Var[bool]

    # Whether the user must choose a value before submitting a form. Defaults to False.
    required: Var[bool]

    # A ref to access the hidden input element.
    input_ref: Var[Any]

    # Enables explicit browser autofill support. Useful for select components that are part of a form.
    auto_complete: Var[str]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the select root component.

        Returns:
            The component.
        """
        props["data-slot"] = "select"
        return super().create(*children, **props)


class SelectLabel(SelectBaseComponent):
    """An accessible label for the select trigger."""

    tag = "Select.Label"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the select label component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-label"
        cls.set_class_name(ClassNames.LABEL, props)
        return super().create(*children, **props)


class SelectTrigger(SelectBaseComponent):
    """A button that opens the select menu."""

    tag = "Select.Trigger"

    # Whether the component should ignore user interaction. Defaults to False.
    disabled: Var[bool]

    # Whether the component renders a native <button> element when replacing it via the render prop.
    # Set to False if the rendered element is not a button (e.g. <div>). Defaults to True.
    native_button: Var[bool]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the select trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-trigger"
        cls.set_class_name(ClassNames.TRIGGER, props)
        return super().create(*children, **props)


class SelectValue(SelectBaseComponent):
    """Text label of the currently selected item."""

    tag = "Select.Value"

    # Placeholder text to display when no item is selected.
    placeholder: Var[str]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the dialog trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-value"
        cls.set_class_name(ClassNames.VALUE, props)
        return super().create(*children, **props)


class SelectBackdrop(SelectBaseComponent):
    """An overlay displayed beneath the menu popup."""

    tag = "Select.Backdrop"

    # The render prop
    render_: Var[Component]


class SelectPortal(SelectBaseComponent):
    """A portal element that moves the popup to a different part of the DOM.
    By default, the portal element is appended to <body>.
    """

    tag = "Select.Portal"

    # A parent element to render the portal element into.
    container: Var[str]


class SelectPositioner(SelectBaseComponent):
    """Positions the select menu popup."""

    tag = "Select.Positioner"

    # How to align the popup relative to the specified side. Defaults to "center".
    align: Var[LiteralAlign]

    # Additional offset along the alignment axis in pixels. Defaults to 0.
    align_offset: Var[int]

    # Which side of the anchor element to align the popup against. May automatically change to avoid collisions. Defaults to "bottom".
    side: Var[LiteralSide]

    # Minimum distance to maintain between the arrow and the edges of the popup.
    # Use it to prevent the arrow element from hanging out of the rounded corners of a popup. Defaults to 5.
    arrow_padding: Var[int]

    # Additional space to maintain from the edge of the collision boundary. Defaults to 5.
    collision_padding: Var[int | list[int]]

    # Whether to maintain the popup in the viewport after the anchor element was scrolled out of view. Defaults to False.
    sticky: Var[bool]

    # Determines which CSS position property to use. Defaults to "absolute".
    position_method: Var[LiteralPosition]

    # Whether the positioner overlaps the trigger so the selected item's text is aligned with the trigger's value text. This only applies to mouse input and is automatically disabled if there is not enough space. Defaults to False.
    align_item_with_trigger: Var[bool] = Var.create(False)

    # Whether to disable the popup tracking any layout shift of its positioning anchor. Defaults to False.
    disable_anchor_tracking: Var[bool]

    # Distance between the anchor and the popup in pixels. Defaults to 0.
    side_offset: Var[int]

    # Determines how to handle collisions when positioning the popup.
    collision_avoidance: Var[str]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the dialog trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-positioner"
        props.setdefault("side_offset", 4)
        cls.set_class_name(ClassNames.POSITIONER, props)
        return super().create(*children, **props)


class SelectPopup(SelectBaseComponent):
    """A container for the select items."""

    tag = "Select.Popup"

    # Determines the element to focus when the select popup is closed. By default, focus returns to the trigger.
    final_focus: Var[str]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the dialog trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-popup"
        cls.set_class_name(ClassNames.POPUP, props)
        return super().create(*children, **props)


class SelectList(SelectBaseComponent):
    """A list component that wraps select items. Renders a <div> element."""

    tag = "Select.List"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the select list component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-list"
        return super().create(*children, **props)


class SelectItem(SelectBaseComponent):
    """An individual option in the select menu."""

    tag = "Select.Item"

    # Overrides the text label to use on the trigger when this item is selected and when the item is matched during keyboard text navigation.
    label: Var[str]

    # A unique value that identifies this select item.
    value: Var[Any]

    # Whether the component should ignore user interaction.
    disabled: Var[bool]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the dialog trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-item"
        cls.set_class_name(ClassNames.ITEM, props)
        return super().create(*children, **props)


class SelectItemText(SelectBaseComponent):
    """A text label of the select item."""

    tag = "Select.ItemText"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the dialog trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-item-text"
        cls.set_class_name(ClassNames.ITEM_TEXT, props)
        return super().create(*children, **props)


class SelectItemIndicator(SelectBaseComponent):
    """Indicates whether the select item is selected."""

    tag = "Select.ItemIndicator"

    # Whether to keep the HTML element in the DOM when the item is not selected. Defaults to False.
    keep_mounted: Var[bool]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the dialog trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-item-indicator"
        cls.set_class_name(ClassNames.ITEM_INDICATOR, props)
        return super().create(*children, **props)


class SelectGroup(SelectBaseComponent):
    """Groups related select items with the corresponding label."""

    tag = "Select.Group"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the dialog trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-group"
        cls.set_class_name(ClassNames.GROUP, props)
        return super().create(*children, **props)


class SelectGroupLabel(SelectBaseComponent):
    """An accessible label that is automatically associated with its parent group."""

    tag = "Select.GroupLabel"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the dialog trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-group-label"
        cls.set_class_name(ClassNames.GROUP_LABEL, props)
        return super().create(*children, **props)


class SelectSeparator(SelectBaseComponent):
    """A separator element accessible to screen readers."""

    tag = "Select.Separator"

    # The orientation of the separator.
    orientation: Var[LiteralOrientation] = Var.create("horizontal")

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the dialog trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-separator"
        cls.set_class_name(ClassNames.SEPARATOR, props)
        return super().create(*children, **props)


class SelectIcon(SelectBaseComponent):
    """An icon that indicates that the trigger button opens a select menu."""

    tag = "Select.Icon"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the dialog trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-icon"
        cls.set_class_name(ClassNames.ICON, props)
        return super().create(*children, **props)


class SelectArrow(SelectBaseComponent):
    """Displays an element positioned against the select menu anchor."""

    tag = "Select.Arrow"

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the dialog trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-arrow"
        cls.set_class_name(ClassNames.ARROW, props)
        return super().create(*children, **props)


class SelectScrollUpArrow(SelectBaseComponent):
    """An element that scrolls the select menu up when hovered."""

    tag = "Select.ScrollUpArrow"

    # Whether to keep the component mounted when not visible. Defaults to False.
    keep_mounted: Var[bool]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the dialog trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-scroll-up-arrow"
        cls.set_class_name(ClassNames.SCROLL_ARROW_UP, props)
        return super().create(*children, **props)


class SelectScrollDownArrow(SelectBaseComponent):
    """An element that scrolls the select menu down when hovered."""

    tag = "Select.ScrollDownArrow"

    # Whether to keep the component mounted when not visible. Defaults to False.
    keep_mounted: Var[bool]

    # The render prop
    render_: Var[Component]

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create the dialog trigger component.

        Returns:
            The component.
        """
        props["data-slot"] = "select-scroll-down-arrow"
        cls.set_class_name(ClassNames.SCROLL_ARROW_DOWN, props)
        return super().create(*children, **props)


class HighLevelSelect(SelectRoot):
    """High level wrapper for the Select component."""

    # The list of items to display in the select dropdown
    items: Var[list[str]]

    # The placeholder text to display when no item is selected
    placeholder: Var[str]

    # The size of the select component. Defaults to "md".
    size: Var[LiteralSelectSize]

    # Props for different component parts
    _trigger_props = {"size", "trigger_variant"}
    _value_props = {"placeholder"}
    _items_props = {"items"}
    _positioner_props = {
        "align",
        "align_offset",
        "side",
        "arrow_padding",
        "collision_padding",
        "sticky",
        "position_method",
        "align_item_with_trigger",
        "disable_anchor_tracking",
        "side_offset",
        "collision_avoidance",
    }
    _portal_props = {"container"}

    @classmethod
    def create(cls, *children, **props) -> BaseUIComponent:
        """Create a select component.

        Args:
            *children: Additional children to include in the select.
            **props: Additional properties to apply to the select component.

        Returns:
            The select component.
        """
        # Extract props for different parts
        trigger_props = {k: props.pop(k) for k in cls._trigger_props & props.keys()}
        value_props = {k: props.pop(k) for k in cls._value_props & props.keys()}
        items_props = {k: props.pop(k) for k in cls._items_props & props.keys()}
        positioner_props = {
            k: props.pop(k) for k in cls._positioner_props & props.keys()
        }
        portal_props = {k: props.pop(k) for k in cls._portal_props & props.keys()}

        # Get extracted values with defaults
        size = trigger_props.get("size", "md")
        trigger_variant: LiteralButtonVariant = trigger_props.get(
            "trigger_variant", "outline"
        )
        items = items_props.get("items", [])

        # Create the items children
        if isinstance(items, Var):
            items_children = foreach(
                items,
                lambda item: SelectItem.create(
                    render_=button(
                        SelectItemText.create(item),
                        SelectItemIndicator.create(
                            hi(
                                "Tick02Icon",
                                class_name="size-4",
                            ),
                        ),
                        variant="ghost",
                        size=size,
                        type="button",
                        class_name=ClassNames.ITEM,
                        disabled=props.get("disabled", False),
                    ),
                    value=item,
                    key=item,
                ),
            )
        else:
            items_children = [
                SelectItem.create(
                    render_=button(
                        SelectItemText.create(item),
                        SelectItemIndicator.create(
                            hi(
                                "Tick02Icon",
                                class_name="size-4",
                            ),
                        ),
                        variant="ghost",
                        size=size,
                        type="button",
                        class_name=ClassNames.ITEM,
                    ),
                    value=item,
                    key=item,
                )
                for item in items
            ]

        return SelectRoot.create(
            SelectTrigger.create(
                render_=button(
                    SelectValue.create(**value_props),
                    SelectIcon.create(
                        select_arrow(class_name="size-4 text-secondary-9")
                    ),
                    variant=trigger_variant,
                    size=size,
                    type="button",
                    class_name=ClassNames.TRIGGER,
                    disabled=props.get("disabled", False),
                ),
            ),
            SelectPortal.create(
                SelectPositioner.create(
                    SelectPopup.create(
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


class Select(ComponentNamespace):
    """Namespace for Select components."""

    root = staticmethod(SelectRoot.create)
    label = staticmethod(SelectLabel.create)
    trigger = staticmethod(SelectTrigger.create)
    value = staticmethod(SelectValue.create)
    icon = staticmethod(SelectIcon.create)
    backdrop = staticmethod(SelectBackdrop.create)
    portal = staticmethod(SelectPortal.create)
    positioner = staticmethod(SelectPositioner.create)
    popup = staticmethod(SelectPopup.create)
    list = staticmethod(SelectList.create)
    arrow = staticmethod(SelectArrow.create)
    scroll_up_arrow = staticmethod(SelectScrollUpArrow.create)
    scroll_down_arrow = staticmethod(SelectScrollDownArrow.create)
    item = staticmethod(SelectItem.create)
    item_text = staticmethod(SelectItemText.create)
    item_indicator = staticmethod(SelectItemIndicator.create)
    group = staticmethod(SelectGroup.create)
    group_label = staticmethod(SelectGroupLabel.create)
    separator = staticmethod(SelectSeparator.create)
    class_names = ClassNames
    __call__ = staticmethod(HighLevelSelect.create)


select = Select()
