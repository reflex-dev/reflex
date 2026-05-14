"""Interactive components provided by @radix-ui/themes."""

from collections.abc import Sequence
from typing import ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.event import EventHandler, no_args_event_spec, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.foreach import foreach

from reflex_components_radix.themes.base import (
    LiteralAccentColor,
    LiteralRadius,
    RadixThemesComponent,
)


class SelectRoot(RadixThemesComponent):
    """Displays a list of options for the user to pick from, triggered by a button."""

    tag = "Select.Root"

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(
        doc=(
            'The size of the select trigger. Defaults to `"2"` (medium). '
            'Use `"1"` for compact UIs like data tables, toolbars, or dense forms '
            'with many fields. Use `"3"` for prominent calls-to-action or main '
            "page elements where the dropdown is the primary focus."
        )
    )

    default_value: Var[str] = field(
        doc=(
            "The value that's selected when the dropdown first renders. Use this "
            "when you want the select to start with a specific option but don't "
            "need to track the user's choice in app state. The value must match "
            "one of the options in the list. If both `value` and `default_value` "
            "are provided, `value` takes precedence."
        )
    )

    value: Var[str] = field(
        doc=(
            "The currently selected value of the dropdown. When set, the component "
            "reflects this value and you must update it via an `on_change` event "
            "handler. Use this when you need the selected value to drive other "
            "parts of your app, like filtering a table, updating a chart, or "
            "saving to a database. For a simpler pattern where you only need to "
            "set the initial value, use `default_value` instead."
        )
    )

    default_open: Var[bool] = field(
        doc=(
            "Whether the dropdown menu is open when the component first renders. "
            "Defaults to `False`. Useful for guided onboarding flows, tutorial "
            "overlays, or when you want the menu visible immediately on page load "
            "to draw user attention."
        )
    )

    open: Var[bool] = field(
        doc=(
            "Controls whether the dropdown menu is currently open. When set, you "
            "must update this prop via an `on_open_change` event handler. Use "
            "this to programmatically open or close the dropdown. For example, "
            "opening it automatically when a user clicks a related button "
            "elsewhere on the page, or closing it after a successful selection "
            "in a multi-step form."
        )
    )

    name: Var[str] = field(
        doc=(
            "The name attribute used when the select is submitted as part of an "
            "HTML form. This becomes the key in the submitted form data. If "
            "omitted, the select's value won't be included in form submissions. "
            "See [Forms](/docs/library/forms/form) for more on integrating "
            "selects with form validation and submission."
        )
    )

    disabled: Var[bool] = field(
        doc=(
            "When `True`, the user cannot interact with the select. The trigger "
            "appears in a muted style and clicking has no effect. Defaults to "
            "`False`. Useful for forms where a field shouldn't be editable based "
            "on other state, like a confirmation step, a permission-restricted "
            "view, or a field that's locked while data is loading. To disable "
            "individual options instead of the entire select, use the "
            "[low-level Select API](/docs/library/forms/select/low) and set "
            "`disabled` on specific `rx.select.item` components."
        )
    )

    required: Var[bool] = field(
        doc=(
            "When `True` and the select is inside an `rx.form.root`, the form "
            "cannot be submitted until the user selects a value. Defaults to "
            "`False`. Pairs with `name` to enforce required form fields. Note: "
            "this does not affect the select's visual appearance. For visual "
            "indication that a field is required, add a label with an asterisk "
            "yourself."
        )
    )

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    on_change: EventHandler[passthrough_event_spec(str)] = field(
        doc=(
            "Fires when the user selects a different option from the dropdown. "
            "The handler receives the new value as a string. Use this with "
            "`value` to create a fully reactive select bound to state. The event "
            "also fires when the value is updated programmatically via state, so "
            "it's a reliable signal for any value change, not just user clicks."
        )
    )

    on_open_change: EventHandler[passthrough_event_spec(bool)] = field(
        doc=(
            "Fires when the dropdown menu opens or closes. The handler receives "
            "a boolean, `True` when opening, `False` when closing. Useful for "
            "triggering analytics events, prefetching data for the dropdown "
            "options when the menu opens, or animating related UI elements "
            "(like a sidebar or tooltip) when the menu appears."
        )
    )


class SelectTrigger(RadixThemesComponent):
    """The button that toggles the select."""

    tag = "Select.Trigger"

    variant: Var[Literal["classic", "surface", "soft", "ghost"]] = field(
        doc=(
            "The visual style of the trigger. Same options and behavior as the "
            "`variant` prop on `rx.select.root`. Setting it here allows "
            "different visual styles between the trigger and content when "
            "composing custom selects."
        )
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc=(
            "The text color of the trigger label. Accepts any Reflex color "
            "token. Use to make the trigger text stand out. For example, a red "
            "trigger color for an error state, or muted gray for a "
            "placeholder-like appearance."
        )
    )

    radius: Var[LiteralRadius] = field(
        doc=(
            "The border radius of the trigger. Same behavior as the `radius` "
            "prop on `rx.select.root`, but scoped to just the trigger button "
            "when using the low-level API."
        )
    )

    placeholder: Var[str] = field(
        doc=(
            "The text displayed in the trigger button when no option is "
            "selected. Same behavior as the `placeholder` prop on "
            "`rx.select.root`, but set on the trigger directly in the low-level "
            "API. Hidden automatically once a value is selected."
        )
    )

    _valid_parents: ClassVar[list[str]] = ["SelectRoot"]

    _memoization_mode = MemoizationMode(recursive=False)


class SelectContent(RadixThemesComponent):
    """The component that pops out when the select is open."""

    tag = "Select.Content"

    variant: Var[Literal["solid", "soft"]] = field(
        doc=(
            "The visual style of the dropdown menu surface. Defaults to "
            '`"solid"`. Use `"soft"` for a more subtle, translucent menu '
            "background. Particularly effective on colored or image backgrounds."
        )
    )

    color_scheme: Var[LiteralAccentColor] = field(
        doc=(
            "Overrides the theme's accent color for the dropdown menu "
            "specifically. Affects the highlight color when hovering or "
            "arrow-key-navigating through items. Can differ from the trigger's "
            "`color_scheme` for stylistic effect."
        )
    )

    high_contrast: Var[bool] = field(
        doc=(
            "When `True`, increases the contrast inside the dropdown menu. "
            "Particularly useful when the menu opens over a busy background. "
            "Defaults to `False`."
        )
    )

    position: Var[Literal["item-aligned", "popper"]] = field(
        doc=(
            "Controls how the dropdown menu positions itself relative to the "
            "trigger. Same behavior as `position` on `rx.select.root`. Defaults "
            'to `"item-aligned"`. Set to `"popper"` when placing the select '
            "inside a Drawer, Dialog, or Popover."
        )
    )

    side: Var[Literal["top", "right", "bottom", "left"]] = field(
        doc=(
            "Which side of the trigger the dropdown should appear on when using "
            '`position="popper"`. Defaults to `"bottom"`. Useful when the '
            "trigger is near the bottom of the viewport and the default "
            "placement would cause the menu to be clipped."
        )
    )

    side_offset: Var[int] = field(
        doc=(
            "The distance in pixels between the trigger and the dropdown menu "
            'when `position="popper"`. Defaults to `0`. Increase for visual '
            "separation between the trigger and menu."
        )
    )

    align: Var[Literal["start", "center", "end"]] = field(
        doc=(
            "Horizontal alignment of the dropdown menu relative to the trigger "
            'when `position="popper"`. Defaults to `"start"`. Use `"end"` for '
            "right-aligned dropdowns in RTL layouts or when the trigger is on "
            "the right side of a container."
        )
    )

    align_offset: Var[int] = field(
        doc=(
            'Pixel offset for the alignment when `position="popper"`. Defaults '
            "to `0`. Use to fine-tune the dropdown's horizontal position."
        )
    )

    on_close_auto_focus: EventHandler[no_args_event_spec] = field(
        doc="Fired when the select content is closed."
    )

    on_escape_key_down: EventHandler[no_args_event_spec] = field(
        doc="Fired when the escape key is pressed."
    )

    on_pointer_down_outside: EventHandler[no_args_event_spec] = field(
        doc="Fired when a pointer down event happens outside the select content."
    )


class SelectGroup(RadixThemesComponent):
    """Used to group multiple items."""

    tag = "Select.Group"

    _valid_parents: ClassVar[list[str]] = ["SelectContent"]


class SelectItem(RadixThemesComponent):
    """The component that contains the select items."""

    tag = "Select.Item"

    value: Var[str] = field(
        doc=(
            "The value associated with this option. Required. When this item is "
            "selected, the select's `on_change` handler receives this value. "
            "The display label is set via the item's children. Separating value "
            "from label is the main reason to use the low-level Select API "
            "instead of the high-level `rx.select`."
        )
    )

    disabled: Var[bool] = field(
        doc=(
            "When `True`, this specific item cannot be selected. It appears "
            "muted and clicking does nothing. Defaults to `False`. Useful for "
            "showing options that exist conceptually but aren't currently "
            "available (e.g., out-of-stock products, locked features behind a "
            "paywall, or options requiring elevated permissions)."
        )
    )

    _valid_parents: ClassVar[list[str]] = ["SelectGroup", "SelectContent"]


class SelectLabel(RadixThemesComponent):
    """Used to render the label of a group, it isn't focusable using arrow keys."""

    tag = "Select.Label"

    _valid_parents: ClassVar[list[str]] = ["SelectGroup"]


class SelectSeparator(RadixThemesComponent):
    """Used to visually separate items in the Select."""

    tag = "Select.Separator"


class HighLevelSelect(SelectRoot):
    """High level wrapper for the Select component."""

    items: Var[Sequence[str]] = field(doc="The items of the select.")

    placeholder: Var[str] = field(
        doc=(
            "The text shown in the trigger button when no option has been "
            "selected. Defaults to an empty string. The placeholder is "
            "automatically hidden once `value` or `default_value` is set, so it "
            "only appears in the initial empty state. Use placeholders to guide "
            'the user toward the right choice (e.g., "Choose a country…" or '
            '"Pick a category").'
        )
    )

    label: Var[str] = field(doc="The label of the select.")

    color_scheme: Var[LiteralAccentColor] = field(
        doc=(
            "Overrides the theme's accent color for this specific select. "
            'Accepts any Reflex color token (`"blue"`, `"green"`, `"red"`, '
            '`"purple"`, `"crimson"`, `"orange"`, etc.). Useful for '
            "status-specific dropdowns. For example, a destructive action "
            'select in `"red"`, or a success-state filter in `"green"`. Affects '
            "the focus ring, active item highlight, and the dropdown arrow icon."
        )
    )

    high_contrast: Var[bool] = field(
        doc=(
            "When `True`, increases the contrast between the select's text and "
            "background for better readability. Defaults to `False`. Useful for "
            "accessibility compliance (WCAG AA/AAA) or for selects placed on "
            "busy or colored backgrounds where the default contrast may be "
            "insufficient."
        )
    )

    variant: Var[Literal["classic", "surface", "soft", "ghost"]] = field(
        doc=(
            'The visual style of the trigger button. Defaults to `"surface"`. '
            'Options: `"classic"` for a bordered button with a subtle '
            'background, `"surface"` for a filled background with a thin '
            'border, `"soft"` for a tinted background with no border, `"ghost"` '
            "for minimal chrome that only appears on hover. Match the variant "
            "to the visual weight you want the select to have in the "
            "surrounding UI."
        )
    )

    radius: Var[LiteralRadius] = field(
        doc=(
            "The border radius of the trigger button. Inherits from the theme "
            'by default. Use `"none"` for sharp corners, `"full"` for a '
            "pill-shaped trigger, or pick a specific value to match your app's "
            "design system. Doesn't affect the dropdown menu radius, only the "
            "trigger button."
        )
    )

    width: Var[str] = field(doc="The width of the select.")

    position: Var[Literal["item-aligned", "popper"]] = field(
        doc=(
            "Controls how the dropdown menu positions itself relative to the "
            'trigger. Defaults to `"item-aligned"`, which aligns the currently '
            'selected option with the trigger button. Use `"popper"` when '
            "placing the select inside a [Drawer](/docs/library/overlay/drawer), "
            "[Dialog](/docs/library/overlay/dialog), "
            "[Popover](/docs/library/overlay/popover), or any portal-based "
            "container. This prevents the menu from being clipped or misaligned "
            "by the overlay."
        )
    )

    @classmethod
    def create(cls, items: list[str] | Var[list[str]], **props) -> Component:
        """Create a select component.

        Args:
            items: The items of the select.
            **props: Additional properties to apply to the select component.

        Returns:
            The select component.
        """
        trigger_prop_list = [
            "id",
            "placeholder",
            "variant",
            "radius",
            "width",
            "flex_shrink",
            "custom_attrs",
        ]

        content_props = {
            prop: props.pop(prop)
            for prop in ["high_contrast", "position"]
            if prop in props
        }

        trigger_props = {
            prop: props.pop(prop) for prop in trigger_prop_list if prop in props
        }

        color_scheme = props.pop("color_scheme", None)

        if color_scheme is not None:
            content_props["color_scheme"] = color_scheme
            trigger_props["color_scheme"] = color_scheme

        label = props.pop("label", None)

        if isinstance(items, Var):
            child = [foreach(items, lambda item: SelectItem.create(item, value=item))]
        else:
            child = [SelectItem.create(item, value=item) for item in items]

        return SelectRoot.create(
            SelectTrigger.create(
                **trigger_props,
            ),
            SelectContent.create(
                SelectGroup.create(
                    SelectLabel.create(label) if label is not None else "",
                    *child,
                ),
                **content_props,
            ),
            **props,
        )


class Select(ComponentNamespace):
    """Select components namespace."""

    root = staticmethod(SelectRoot.create)
    trigger = staticmethod(SelectTrigger.create)
    content = staticmethod(SelectContent.create)
    group = staticmethod(SelectGroup.create)
    item = staticmethod(SelectItem.create)
    separator = staticmethod(SelectSeparator.create)
    label = staticmethod(SelectLabel.create)
    __call__ = staticmethod(HighLevelSelect.create)


select = Select()
