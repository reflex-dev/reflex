"""A select: a button, and the popup of options it opens."""

from __future__ import annotations

import functools
import itertools
from collections.abc import Iterator, Sequence
from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.components.tags import CommonTag
from reflex_base.event import (
    EventHandler,
    input_event,
    no_args_event_spec,
    passthrough_event_spec,
)
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.foreach import foreach
from reflex_components_core.el import elements

from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.components._group import descendants, is_value, literal
from reflex_components_ui.constants import WEB_DIR
from reflex_components_ui.props import style_before
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.popup import OFFSET, SHIFT
from reflex_components_ui.styles.select import (
    SELECT,
    SELECT_CONTENT,
    SELECT_ITEM,
    SELECT_LABEL,
    SELECT_SEPARATOR,
    SELECT_TRIGGER,
    SELECT_VALUE,
)
from reflex_components_ui.themes import LiteralAccentColor

_SCRIPT = f"$/{WEB_DIR}/behaviors/listbox.js"
_POPUP_SCRIPT = f"$/{WEB_DIR}/behaviors/popup.js"


@functools.cache
def _script(name: str, module: str = _SCRIPT) -> Var:
    """Name a function of the script of a select, or of a popup.

    Args:
        name: The name the script exports it under.
        module: The script.

    Returns:
        The function, with its import.
    """
    return Var(name, _var_data=VarData(imports={module: [ImportVar(tag=name)]}))


# The events of the popup as they are rendered, by the name the script
# calls each under.
_POPUP_EVENTS = {
    "onOpenChange": "open",
    "onCloseAutoFocus": "close",
    "onEscapeKeyDown": "escape",
    "onPointerDownOutside": "outside",
}

# Numbers the popups and the labels, which are found by their ids.
_ids = itertools.count(1)

_CHEVRON = (
    "M0.135232 3.15803C0.324102 2.95657 0.640521 2.94637 0.841971 3.13523"
    "L4.5 6.56464L8.158 3.13523C8.3595 2.94637 8.6759 2.95657 8.8648 3.15803"
    "C9.0536 3.35949 9.0434 3.67591 8.842 3.86477L4.84197 7.6148"
    "C4.64964 7.7951 4.35036 7.7951 4.15803 7.6148L0.158031 3.86477"
    "C-0.0434285 3.67591 -0.0536285 3.35949 0.135232 3.15803Z"
)
_CHECK = (
    "M8.53547 0.62293C8.88226 0.849446 8.97976 1.3142 8.75325 1.66099"
    "L4.5083 8.1599C4.38833 8.34356 4.19397 8.4655 3.9764 8.49358"
    "C3.75883 8.52167 3.53987 8.45309 3.3772 8.30591L0.616113 5.80777"
    "C0.308959 5.52987 0.285246 5.05559 0.563148 4.74844"
    "C0.84105 4.44128 1.31533 4.41757 1.62249 4.69547L3.73256 6.60459"
    "L7.49741 0.840706C7.72393 0.493916 8.18868 0.396414 8.53547 0.62293Z"
)


def _icon(part: str, path: str, **attributes: Any) -> Component:
    """Create one of the icons Radix Themes draws in a select.

    Args:
        part: The part of the style table that sizes it.
        path: The outline of the icon.
        **attributes: The attributes of the path.

    Returns:
        The icon, which is nothing to assistive technology.
    """
    return Part.create(
        elements.svg.path(d=path, custom_attrs=attributes),
        part=part,
        tag="svg",
        custom_attrs={
            "width": "9",
            "height": "9",
            "viewBox": "0 0 9 9",
            "fill": "currentcolor",
            "xmlns": "http://www.w3.org/2000/svg",
            "aria-hidden": True,
        },
    )


def _pixels(amount: Any) -> Any:
    """Write a number of pixels as a length.

    Args:
        amount: The number, or a Var of it.

    Returns:
        The length: a string when the number is known while compiling.
    """
    amount = literal(amount)
    if not isinstance(amount, Var):
        return f"{amount}px"
    return Var(
        f'(({amount!s}) + "px")', _var_type=str, _var_data=amount._get_all_var_data()
    )


class SelectValue(UIComponent, elements.Input):
    """The input that holds the value of a select, which a form submits."""

    tag = "input"

    styles: ClassVar[ComponentStyles] = SELECT_VALUE

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the input.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: nothing to assistive technology, and not reached
            with Tab.
        """
        return (
            super()
            ._render(props)
            .add_props(**{
                "data-rx-select-value": "",
                "aria-hidden": True,
                "tabIndex": -1,
            })
        )


class SelectRoot(UIComponent):
    """Displays a list of options for the user to pick from, triggered by a button."""

    tag = "span"

    styles: ClassVar[ComponentStyles] = SELECT

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

    on_change: EventHandler[input_event] = field(
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

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a SelectRoot.

        Radix hands the parts of a select its props through a context. Here
        the root finds its parts while compiling, and gives them what they
        render. The value is the one of an input after them, which is what
        a form reads.

        Args:
            *children: The trigger and the content of the select.
            **props: The properties of the component.

        Returns:
            The SelectRoot component.
        """
        value, open_ = props.get("value"), props.get("open")
        shown = value if value is not None else props.get("default_value")
        arguments = [LiteralVar.create(argument) for argument in (value, open_)]
        held: dict[str, Any] = {
            key: props[key] for key in ("name", "required", "disabled") if key in props
        }
        if shown is not None:
            held["default_value"] = shown
        holder = SelectValue.create(
            **held,
            custom_attrs={
                # Called whenever the page renders: a select bound to state
                # takes its value, and whether it is open, from there.
                "ref": Var(
                    f"((holder) => syncSelect(holder, {arguments[0]!s}, "
                    f"{arguments[1]!s}))",
                    _var_data=VarData.merge(
                        _script("syncSelect")._get_all_var_data(),
                        *(argument._get_all_var_data() for argument in arguments),
                    ),
                ),
                "onFocus": _script("selectFocus"),
            },
        )
        attributes = props.setdefault("custom_attrs", {})
        attributes.setdefault("onKeyDown", _script("selectKeyDown"))
        attributes.setdefault("onClick", _script("selectClick"))
        attributes.setdefault("onPointerMove", _script("selectPointerMove"))
        return super().create(*children, holder, **props)

    def _post_init(self, *args, **kwargs):
        """Initialize the select, and give its parts what they share.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        super()._post_init(*args, **kwargs)
        selected = self.value if self.value is not None else self.default_value
        items = list(descendants(self, SelectItem))
        for item in items:
            item._join(selected)
        popup = f"rx-select-{next(_ids)}"
        on_open_change = self.event_triggers.pop("on_open_change", None)
        for content in descendants(self, SelectContent):
            popup = content._join(self, popup, on_open_change)
        for trigger in descendants(self, SelectTrigger):
            trigger._join(self, popup, selected, items)

    def _exclude_props(self) -> list[str]:
        """Keep the props that are the ones of the parts off the element.

        Returns:
            The props read as styles, and what the select hands its parts.
        """
        return [
            *super()._exclude_props(),
            "size",
            "value",
            "default_value",
            "default_open",
            "open",
            "name",
            "disabled",
            "required",
        ]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the element around the select.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, marked for the script of the select, which opens a
            select that starts open.
        """
        tag = super()._render(props).add_props(**{"data-rx-select": ""})
        if self.default_open is not None:
            tag = tag.add_props(**{"data-default-open": self.default_open})
        return tag


def _shown(
    selected: Var | None, placeholder: Var | None, items: list[SelectItem]
) -> Any:
    """Work out what the trigger of a select shows before any script runs.

    Args:
        selected: The value of the select, or None.
        placeholder: What the trigger shows when nothing is chosen, or None.
        items: The options of the select.

    Returns:
        The text of the chosen option, where it is known while compiling or
        can be read from the value, and the placeholder otherwise: the
        script of the select shows the text when it runs.
    """
    empty = "" if placeholder is None else placeholder
    if selected is None:
        return empty
    texts = [(item.value, item._text) for item in items]
    value = literal(selected)
    if not isinstance(value, Var):
        for item_value, text in texts:
            if literal(item_value) == value and text is not None:
                return text
        return empty
    fallback = LiteralVar.create(empty)
    data = [selected._get_all_var_data(), fallback._get_all_var_data()]
    if texts and all(
        text is not None and str(text) == str(item_value) for item_value, text in texts
    ):
        # Each option shows its value: so does the trigger.
        return Var(
            f"({selected!s} || {fallback!s})",
            _var_type=str,
            _var_data=VarData.merge(*data),
        )
    known = {literal(item_value): text for item_value, text in texts}
    if texts and not any(
        isinstance(item, Var) or item is None for pair in known.items() for item in pair
    ):
        # The text of each option is known: the one of the value is read
        # from them.
        return Var(
            f"({LiteralVar.create(known)!s}[{selected!s}] ?? {fallback!s})",
            _var_type=str,
            _var_data=VarData.merge(*data),
        )
    return empty


class SelectTrigger(UIComponent):
    """The button that toggles the select."""

    tag = "button"

    styles: ClassVar[ComponentStyles] = SELECT_TRIGGER

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

    radius: Var[Literal["none", "small", "medium", "large", "full"]] = field(
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

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a SelectTrigger.

        Args:
            *children: What the trigger shows in place of the chosen option.
            **props: The properties of the component.

        Returns:
            The SelectTrigger component: a button around what it shows and
            the icon of a select.
        """
        return super().create(
            Part.create(*children, part="shown", tag="span"),
            _icon("icon", _CHEVRON),
            **props,
        )

    def _post_init(self, *args, **kwargs):
        """Initialize the trigger, with the look of a select without props.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # What the style table reads as a variant, and the attributes the
        # select gives its trigger: both are set by the select around it.
        self._size: Any = None
        self._select: dict[str, Any] = {}
        super()._post_init(*args, **kwargs)

    def _join(
        self,
        select: SelectRoot,
        popup: Any,
        selected: Var | None,
        items: list[SelectItem],
    ) -> None:
        """Take from a select what Radix hands its trigger through a context.

        Args:
            select: The select the trigger is in.
            popup: The id of the popup it opens.
            selected: The value of the select, or None.
            items: The options of the select.
        """
        self._size = select.size
        attributes: dict[str, Any] = {"popovertarget": popup, "aria-controls": popup}
        if select.disabled is not None:
            attributes["disabled"] = select.disabled
        if not self.children[0].children:
            mark: dict[str, Any] = {"data-rx-select-shown": ""}
            if self.placeholder is not None:
                mark["data-placeholder"] = self.placeholder
            self.children[0] = Part.create(
                _shown(selected, self.placeholder, items),
                part="shown",
                tag="span",
                custom_attrs=mark,
            )
            if selected is None:
                attributes["data-placeholder"] = ""
            elif isinstance(literal(selected), Var):
                attributes["data-placeholder"] = Var(
                    f'({selected!s} ? undefined : "")',
                    _var_data=selected._get_all_var_data(),
                )
        self._select = attributes
        # The parts take their styles again: the size is one of theirs.
        for part in descendants(self, Part):
            part._merged = None  # pyright: ignore[reportAttributeAccessIssue]
        self._merge_styles()  # pyright: ignore[reportAttributeAccessIssue]

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the trigger, those its select gives it included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        for value in self._select.values():
            if isinstance(value, Var):
                yield value

    def _exclude_props(self) -> list[str]:
        """Keep the placeholder off the button: the text inside it shows it.

        Returns:
            The props read as styles, and the placeholder.
        """
        return [*super()._exclude_props(), "placeholder"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the trigger.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: a button that opens its popup without a script, with
            the role and the state Radix gives the trigger of a select.
        """
        return (
            super()
            ._render(props)
            .add_props(**{
                "type": "button",
                "role": "combobox",
                "aria-expanded": "false",
                "aria-haspopup": "listbox",
                "aria-autocomplete": "none",
                "data-state": "closed",
                **self._select,
            })
        )


class SelectContent(UIComponent):
    """The component that pops out when the select is open."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = SELECT_CONTENT

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

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a SelectContent.

        Args:
            *children: The options of the select.
            **props: The properties of the component.

        Returns:
            The SelectContent component.
        """
        distances = {
            name: _pixels(props[prop])
            for prop, name in (("side_offset", OFFSET), ("align_offset", SHIFT))
            if props.get(prop) is not None
        }
        if distances:
            style_before(props, distances)
        return super().create(*children, **props)

    def _post_init(self, *args, **kwargs):
        """Initialize the content, with the look of a select without props.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # What the style table reads as a variant: the select sets it.
        self._size: Any = None
        super()._post_init(*args, **kwargs)

    def _join(self, select: SelectRoot, popup: str, on_open_change: Any) -> Any:
        """Take from a select what Radix hands its content through a context.

        Args:
            select: The select the content is in.
            popup: The id of a popup that is given none.
            on_open_change: What the select does when it opens or closes.

        Returns:
            The id of the popup.
        """
        self._size = select.size
        if self.id is None:
            self.id = LiteralVar.create(popup)
        if on_open_change is not None:
            self.event_triggers["on_open_change"] = on_open_change
        self._merge_styles()  # pyright: ignore[reportAttributeAccessIssue]
        return self.id

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the popup, what follows its toggle included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        yield _script("selectToggle")
        yield _script("popupBeforeToggle", _POPUP_SCRIPT)

    def _exclude_props(self) -> list[str]:
        """Keep the props that say where the popup goes off the element.

        Returns:
            The props read as styles, and the ones a style is made from.
            The position is one of them: the popup is beside its trigger
            whatever it says.
        """
        return [*super()._exclude_props(), "position", "side_offset", "align_offset"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the popup.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: a popover the browser opens and closes, which says so
            to the script of the select, and through it to the events.
        """
        tag = super()._render(props)
        rendered = dict(tag.props)
        handlers = {
            name: LiteralVar.create(rendered.pop(event))
            for event, name in _POPUP_EVENTS.items()
            if event in rendered
        }
        tag = tag.set(props=rendered)
        toggle = _script("selectToggle")
        if handlers:
            called = ", ".join([
                f"{name}: {handler!s}" for name, handler in handlers.items()
            ])
            toggle = Var(
                f"((event) => selectToggle(event, ({{ {called} }})))",
                _var_data=VarData.merge(
                    _script("selectToggle")._get_all_var_data(),
                    *(handler._get_all_var_data() for handler in handlers.values()),
                ),
            )
        return tag.add_props(**{
            "popover": "auto",
            "role": "listbox",
            "tabIndex": -1,
            "data-rx-popup": "",
            # Before it is first drawn, the popup is put on whole pixels.
            "onBeforeToggle": _script("popupBeforeToggle", _POPUP_SCRIPT),
            "onToggle": toggle,
        })


class SelectGroup(UIComponent):
    """Used to group multiple items."""

    tag = "div"

    _valid_parents: ClassVar[list[str]] = ["SelectContent"]

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a SelectGroup.

        Args:
            *children: The label and the options of the group.
            **props: The properties of the component.

        Returns:
            The SelectGroup component, named by its label.
        """
        for child in children:
            if isinstance(child, SelectLabel):
                if child.id is None:
                    child.id = LiteralVar.create(f"rx-select-label-{next(_ids)}")
                props.setdefault("aria_labelledby", child.id)
                break
        return super().create(*children, **props)

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the group.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the role of a group.
        """
        return super()._render(props).add_props(role="group")


class SelectItem(UIComponent):
    """The component that contains the select items."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = SELECT_ITEM

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

    @classmethod
    def create(cls, *children: Any, **props: Any) -> Component:
        """Create a SelectItem.

        Args:
            *children: What the option shows.
            **props: The properties of the component.

        Returns:
            The SelectItem component: the check of the chosen option, and
            what the option shows.
        """
        return super().create(
            Part.create(
                _icon("check", _CHECK, fillRule="evenodd", clipRule="evenodd"),
                part="indicator",
                tag="span",
            ),
            elements.span(*children, custom_attrs={"data-rx-select-text": ""}),
            **props,
        )

    def _post_init(self, *args, **kwargs):
        """Initialize the option of a select that has no value.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # Whether the select around the option has chosen it.
        self._selected: Any = False
        super()._post_init(*args, **kwargs)

    @property
    def _text(self) -> Any:
        """What the option shows, when it is one string.

        Returns:
            The text, or None for an option that shows anything else.
        """
        shown = self.children[1].children
        if len(shown) != 1:
            return None
        contents = getattr(shown[0], "contents", None)
        if contents is None or not issubclass(contents._var_type, str):
            return None
        return literal(contents)

    def _join(self, selected: Var | None) -> None:
        """Take from a select whether it has chosen the option.

        Args:
            selected: The value of the select, or None.
        """
        self._selected = False if selected is None else is_value(selected, self.value)

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the option, what its select gives it included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        if isinstance(self._selected, Var):
            yield self._selected

    def _exclude_props(self) -> list[str]:
        """Keep the props of an option off the element: it is no input.

        Returns:
            The props read as styles, the value and whether it is disabled.
        """
        return [*super()._exclude_props(), "value", "disabled"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the option.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the role and the state of an option: it takes
            the focus from the script of the select, not from Tab.
        """
        selected = self._selected
        attributes: dict[str, Any] = {
            "role": "option",
            "tabIndex": -1,
            "data-value": self.value,
            "aria-selected": (
                Var(
                    f'({selected!s} ? "true" : "false")',
                    _var_data=selected._get_all_var_data(),
                )
                if isinstance(selected, Var)
                else str(selected).lower()
            ),
        }
        if self.disabled is not None:
            attributes["aria-disabled"] = self.disabled
        return super()._render(props).add_props(**attributes)


class SelectLabel(UIComponent):
    """Used to render the label of a group, it isn't focusable using arrow keys."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = SELECT_LABEL

    _valid_parents: ClassVar[list[str]] = ["SelectGroup"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the label.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, marked for the rule that keeps it from the option
            before it.
        """
        return super()._render(props).add_props(**{"data-rx-select-label": ""})


class SelectSeparator(UIComponent):
    """Used to visually separate items in the Select."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = SELECT_SEPARATOR

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the separator.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, which is nothing to assistive technology.
        """
        return super()._render(props).add_props(**{"aria-hidden": True})


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

    radius: Var[Literal["none", "small", "medium", "large", "full"]] = field(
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
                    *([] if label is None else [SelectLabel.create(label)]),
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
