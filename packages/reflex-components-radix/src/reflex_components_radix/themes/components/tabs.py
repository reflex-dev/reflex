"""Interactive components provided by @radix-ui/themes."""

from __future__ import annotations

from typing import Any, ClassVar, Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.constants.compiler import MemoizationMode
from reflex_base.event import EventHandler, passthrough_event_spec
from reflex_base.vars.base import Var
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.core.colors import color

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent

vertical_orientation_css = "&[data-orientation='vertical']"


class TabsRoot(RadixThemesComponent):
    """Set of content sections to be displayed one at a time."""

    tag = "Tabs.Root"

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

    # Props to rename
    _rename_props = {"onChange": "onValueChange"}

    on_change: EventHandler[passthrough_event_spec(str)] = field(
        doc="Fired when the value of the tabs changes."
    )

    def add_style(self) -> dict[str, Any] | None:
        """Add style for the component.

        Returns:
            The style to add.
        """
        return {
            vertical_orientation_css: {
                "display": "flex",
            }
        }


class TabsList(RadixThemesComponent):
    """Contains the triggers that sit alongside the active content."""

    tag = "Tabs.List"

    size: Var[Responsive[Literal["1", "2"]]] = field(doc='Tabs size "1" - "2"')

    loop: Var[bool] = field(doc="When true, the tabs will loop when reaching the end.")

    def add_style(self):
        """Add style for the component.

        Returns:
            The style to add.
        """
        return {
            vertical_orientation_css: {
                "display": "block",
                "box_shadow": f"inset -1px 0 0 0 {color('gray', 5, alpha=True)}",
            },
        }


class TabsTrigger(RadixThemesComponent):
    """The button that activates its associated content."""

    tag = "Tabs.Trigger"

    value: Var[str] = field(doc="The value of the tab. Must be unique for each tab.")

    disabled: Var[bool] = field(doc="Whether the tab is disabled")

    color_scheme: Var[LiteralAccentColor] = field(
        doc="The color of the line under the tab when active."
    )

    _valid_parents: ClassVar[list[str]] = ["TabsList"]

    _memoization_mode = MemoizationMode(recursive=False)

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a TabsTrigger component.

        Args:
            *children: The children of the component.
            **props: The properties of the component.

        Returns:
            The TabsTrigger Component.
        """
        if "color_scheme" in props:
            custom_attrs = props.setdefault("custom_attrs", {})
            custom_attrs["data-accent-color"] = props["color_scheme"]
        return super().create(*children, **props)

    def _exclude_props(self) -> list[str]:
        return ["color_scheme"]

    def add_style(self) -> dict[str, Any] | None:
        """Add style for the component.

        Returns:
            The style to add.
        """
        return {vertical_orientation_css: {"width": "100%"}}


class TabsContent(RadixThemesComponent):
    """Contains the content associated with each trigger."""

    tag = "Tabs.Content"

    value: Var[str] = field(doc="The value of the tab. Must be unique for each tab.")

    force_mount: Var[bool] = field(
        doc="Used to force mounting when more control is needed. Useful when controlling animation with React animation libraries."
    )

    def add_style(self) -> dict[str, Any] | None:
        """Add style for the component.

        Returns:
            The style to add.
        """
        return {
            vertical_orientation_css: {"width": "100%", "margin": None},
        }


class Tabs(ComponentNamespace):
    """Set of content sections to be displayed one at a time."""

    root = __call__ = staticmethod(TabsRoot.create)
    list = staticmethod(TabsList.create)
    trigger = staticmethod(TabsTrigger.create)
    content = staticmethod(TabsContent.create)


tabs = Tabs()
