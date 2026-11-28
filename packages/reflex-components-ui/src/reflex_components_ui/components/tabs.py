"""Tabs: a list of buttons, and the panel of the selected one."""

from __future__ import annotations

import itertools
from collections.abc import Iterator
from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.components.tags import CommonTag
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.vars.base import LiteralVar, Var
from reflex_components_core.core.breakpoints import Responsive

from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.components._group import (
    choose,
    descendants,
    is_value,
    literal,
)
from reflex_components_ui.components._script import listen, script
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.tabs import TABS, TABS_CONTENT, TABS_LIST, TABS_TRIGGER
from reflex_components_ui.themes import LiteralAccentColor

# Numbers the tabs of an app: a trigger and its panel name each other by id.
_ids = itertools.count(1)


def _part_id(tabs: TabsRoot, part: str, value: Var | None) -> Any:
    """Get the id of the trigger or of the panel of a tab.

    Args:
        tabs: The tabs.
        part: Which of the two it is.
        value: The value of the tab.

    Returns:
        The id the part was given, or the one the tabs give it: a string
        when the value is known while compiling.
    """
    prefix = f"{tabs._name}-{part}-"
    known = literal(value)
    if not isinstance(known, Var):
        return tabs._ids.get((part, known), f"{prefix}{known}")
    return Var(
        f"({LiteralVar.create(prefix)!s} + {known!s})",
        _var_type=str,
        _var_data=known._get_all_var_data(),
    )


class TabsRoot(UIComponent):
    """Set of content sections to be displayed one at a time."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = TABS

    default_value: Var[str] = field(
        doc="The value of the tab that should be active when initially rendered. Use when you do not need to control the state of the tabs."
    )

    value: Var[str] = field(
        doc="The controlled value of the tab that should be active. Use when you need to control the state of the tabs."
    )

    orientation: Var[Literal["horizontal", "vertical"]] = field(
        doc="The orientation of the tabs."
    )

    dir: Var[Literal["ltr", "rtl"]] = field(doc="Reading direction of the tabs.")

    activation_mode: Var[Literal["automatic", "manual"]] = field(
        doc='The mode of activation for the tabs. "automatic" will activate the tab when focused. "manual" will activate the tab when clicked.'
    )

    on_change: EventHandler[passthrough_event_spec(str)] = field(
        doc="Fired when the value of the tabs changes."
    )

    def _post_init(self, *args, **kwargs):
        """Initialize the tabs, and give their parts what they share.

        Radix hands the parts of tabs their props through a context. Here
        the root finds its parts while compiling, and gives them what they
        render.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        super()._post_init(*args, **kwargs)
        self._name = f"rx-tabs-{next(_ids)}"
        self._selected = self.value if self.value is not None else self.default_value
        # Tab stops on the selected trigger, or on the first when none is.
        self._stop = None if self._selected is not None else False
        parts = list(descendants(self, TabsPart, TabsRoot))
        # The ids an app gave a trigger or a panel, which the other names.
        self._ids = {
            (part._kind, value): part.id
            for part in parts
            if part.id is not None
            and not isinstance(value := literal(getattr(part, "value", None)), Var)
        }
        for part in parts:
            part._join(self)

    def _exclude_props(self) -> list[str]:
        """Keep the props that are the ones of the parts off the element.

        Returns:
            The props read as styles, and what the tabs hand their parts.
        """
        return [
            *super()._exclude_props(),
            "value",
            "default_value",
            "activation_mode",
        ]

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the tabs, the script that selects one included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        yield script("tabs", "tabsEvent")

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the element around the tabs.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, which hears a press on a trigger and the focus moving
            to one: the script selects it, or says so to the state the
            tabs are bound to.
        """
        tag = super()._render(props)
        rendered = dict(tag.props)
        on_change = rendered.pop("onChange", None)
        tag = tag.set(props=rendered).add_props(**{
            "data-rx-tabs": "" if self.value is None else "bound",
            "data-activation": self.activation_mode,
        })
        return listen(
            tag,
            script("tabs", "tabsEvent"),
            "onClick",
            "onFocus",
            "onBlur",
            arguments=() if on_change is None else (on_change,),
        )


class TabsPart(UIComponent):
    """A part of tabs, which its root gives a state and an orientation."""

    # Which part it is, in the id the tabs give a trigger or a panel.
    _kind: ClassVar[str] = ""

    def _post_init(self, *args, **kwargs):
        """Initialize the part, as the one of horizontal tabs with no value.

        Args:
            *args: Args to initialize the component.
            **kwargs: Kwargs to initialize the component.
        """
        # What the style table reads as a variant, and the attributes the
        # tabs give the part: both are set by the root around it.
        self._orientation: Any = None
        self._tabs: dict[str, Any] = {}
        super()._post_init(*args, **kwargs)

    def _join(self, tabs: TabsRoot) -> None:
        """Take from the tabs what Radix hands their parts through a context.

        Args:
            tabs: The tabs the part is in.
        """
        self._orientation = tabs.orientation
        self._tabs = self._attributes(tabs)
        self._merge_styles()  # pyright: ignore[reportAttributeAccessIssue]

    def _attributes(self, tabs: TabsRoot) -> dict[str, Any]:
        """Work out the attributes the tabs give the part.

        Args:
            tabs: The tabs the part is in.

        Returns:
            The attributes.
        """
        return {}

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the part, those its tabs give it included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        for value in self._tabs.values():
            if isinstance(value, Var):
                yield value


class TabsList(TabsPart):
    """Contains the triggers that sit alongside the active content."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = TABS_LIST

    size: Var[Responsive[Literal["1", "2"]]] = field(doc='Tabs size "1" - "2"')

    loop: Var[bool] = field(doc="When true, the tabs will loop when reaching the end.")

    def _attributes(self, tabs: TabsRoot) -> dict[str, Any]:
        """Take the orientation of the tabs, which says which arrow keys move.

        Args:
            tabs: The tabs the list is in.

        Returns:
            The attributes.
        """
        return (
            {} if tabs.orientation is None else {"aria-orientation": tabs.orientation}
        )

    def _exclude_props(self) -> list[str]:
        """Keep the prop the script reads off the element.

        Returns:
            The props read as styles, and whether the arrow keys go around.
        """
        return [*super()._exclude_props(), "loop"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the list.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the role of a list of tabs, which the arrow keys
            move the focus through.
        """
        attributes: dict[str, Any] = {
            "role": "tablist",
            "aria-orientation": "horizontal",
            **self._tabs,
        }
        if self.loop is not None:
            attributes["data-loop"] = self.loop
        return listen(
            super()._render(props).add_props(**attributes),
            script("roving-focus", "rovingKeyDown"),
            "onKeyDown",
        )

    def _get_vars(
        self, include_children: bool = False, ignore_ids: set[int] | None = None
    ) -> Iterator[Var]:
        """Walk all Vars used in the list, the script of its keys included.

        Args:
            include_children: Whether to include Vars from children.
            ignore_ids: The ids to ignore.

        Yields:
            Each var referenced by the component.
        """
        yield from super()._get_vars(include_children, ignore_ids)
        yield script("roving-focus", "rovingKeyDown")


class TabsTrigger(TabsPart):
    """The button that activates its associated content."""

    tag = "button"

    styles: ClassVar[ComponentStyles] = TABS_TRIGGER

    value: Var[str] = field(doc="The value of the tab. Must be unique for each tab.")

    disabled: Var[bool] = field(doc="Whether the tab is disabled")

    color_scheme: Var[LiteralAccentColor] = field(
        doc="The color of the line under the tab when active."
    )

    _valid_parents: ClassVar[list[str]] = ["TabsList"]

    _kind: ClassVar[str] = "trigger"

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a TabsTrigger component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The TabsTrigger Component: a button around its text, twice.
        """
        return super().create(
            Part.create(*children, part="inner", tag="span"),
            Part.create(*children, part="hidden", tag="span"),
            **props,
        )

    def _attributes(self, tabs: TabsRoot) -> dict[str, Any]:
        """Say which panel the trigger shows, and whether it is selected.

        Args:
            tabs: The tabs the trigger is in.

        Returns:
            The attributes.
        """
        selected: Var | bool = (
            False if tabs._selected is None else is_value(tabs._selected, self.value)
        )
        stop = selected
        if tabs._stop is False and literal(self.disabled) is not True:
            tabs._stop = stop = True
        attributes: dict[str, Any] = {
            "aria-controls": _part_id(tabs, "content", self.value),
            "aria-selected": selected,
            "data-state": choose(selected, "active", "inactive"),
            "tabIndex": choose(stop, 0, -1),
        }
        if self.id is None:
            attributes["id"] = _part_id(tabs, "trigger", self.value)
        return attributes

    def _exclude_props(self) -> list[str]:
        """Keep the value off the button: a form is not to submit it.

        Returns:
            The props read as styles, and the value.
        """
        return [*super()._exclude_props(), "value"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the trigger.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag: a button with the role and the state of a tab.
        """
        return (
            super()
            ._render(props)
            .add_props(**{
                "type": "button",
                "role": "tab",
                "aria-selected": False,
                "data-state": "inactive",
                "tabIndex": -1,
                "data-value": self.value,
                **self._tabs,
            })
        )


class TabsContent(TabsPart):
    """Contains the content associated with each trigger."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = TABS_CONTENT

    value: Var[str] = field(doc="The value of the tab. Must be unique for each tab.")

    force_mount: Var[bool] = field(
        doc="Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries."
    )

    _kind: ClassVar[str] = "content"

    def _attributes(self, tabs: TabsRoot) -> dict[str, Any]:
        """Say which trigger names the panel, and whether it is shown.

        Args:
            tabs: The tabs the panel is in.

        Returns:
            The attributes.
        """
        selected: Var | bool = (
            False if tabs._selected is None else is_value(tabs._selected, self.value)
        )
        attributes: dict[str, Any] = {
            "aria-labelledby": _part_id(tabs, "trigger", self.value),
            "data-state": choose(selected, "active", "inactive"),
            "hidden": choose(selected, False, True),
        }
        if self.id is None:
            attributes["id"] = _part_id(tabs, "content", self.value)
        return attributes

    def _exclude_props(self) -> list[str]:
        """Keep the props of a panel off the element.

        Returns:
            The props read as styles, the value, and whether the panel stays
            mounted: every panel does.
        """
        return [*super()._exclude_props(), "value", "force_mount"]

    def _render(self, props: dict[str, Any] | None = None) -> CommonTag:
        """Render the panel.

        Args:
            props: The props to render (if None, then use get_props).

        Returns:
            The tag, with the role of the panel of a tab: hidden until its
            tab is selected.
        """
        return (
            super()
            ._render(props)
            .add_props(**{
                "role": "tabpanel",
                "tabIndex": 0,
                "data-state": "inactive",
                "hidden": True,
                "data-value": self.value,
                "data-rx-tabs-content": "",
                **self._tabs,
            })
        )


class Tabs(ComponentNamespace):
    """Set of content sections to be displayed one at a time."""

    root = __call__ = staticmethod(TabsRoot.create)
    list = staticmethod(TabsList.create)
    trigger = staticmethod(TabsTrigger.create)
    content = staticmethod(TabsContent.create)


tabs = Tabs()
