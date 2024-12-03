"""To experiment with layout component, move them to reflex/components later."""

from __future__ import annotations

from typing import Any, List

from reflex import color, cond
from reflex.components.base.fragment import Fragment
from reflex.components.component import Component, ComponentNamespace, MemoizationLeaf
from reflex.components.radix.primitives.drawer import DrawerRoot, drawer
from reflex.components.radix.themes.components.icon_button import IconButton
from reflex.components.radix.themes.layout.box import Box
from reflex.components.radix.themes.layout.container import Container
from reflex.components.radix.themes.layout.stack import HStack
from reflex.event import run_script
from reflex.experimental import hooks
from reflex.state import ComponentState
from reflex.style import Style
from reflex.vars.base import Var


class Sidebar(Box, MemoizationLeaf):
    """A component that renders the sidebar."""

    @classmethod
    def create(cls, *children, **props):
        """Create the sidebar component.

        Args:
            children: The children components.
            props: The properties of the sidebar.

        Returns:
            The sidebar component.
        """
        return super().create(
            Box.create(*children, **props),  # sidebar for content
            Box.create(width=props.get("width")),  # spacer for layout
        )

    def add_style(self) -> dict[str, Any] | None:
        """Add style to the component.

        Returns:
            The style of the component.
        """
        sidebar: Component = self.children[-2]  # type: ignore
        spacer: Component = self.children[-1]  # type: ignore
        open = (
            self.State.open  # type: ignore
            if self.State
            else Var(_js_expr="open")
        )
        sidebar.style["display"] = spacer.style["display"] = cond(open, "block", "none")

        return Style(
            {
                "position": "fixed",
                "border_right": f"1px solid {color('accent', 12)}",
                "background_color": color("accent", 1),
                "width": "20vw",
                "height": "100vh",
            }
        )

    def add_hooks(self) -> List[Var]:
        """Get the hooks to render.

        Returns:
            The hooks for the sidebar.
        """
        return [hooks.useState("open", "true")] if not self.State else []


class StatefulSidebar(ComponentState):
    """Bind a state to a sidebar component."""

    open: bool = True

    def toggle(self):
        """Toggle the sidebar."""
        self.open = not self.open

    @classmethod
    def get_component(cls, *children, **props):
        """Get the stateful sidebar component.

        Args:
            children: The children components.
            props: The properties of the sidebar.

        Returns:
            The stateful sidebar component.
        """
        return Sidebar.create(*children, **props)


class DrawerSidebar(DrawerRoot):
    """A component that renders a drawer sidebar."""

    @classmethod
    def create(cls, *children, **props):
        """Create the sidebar component.

        Args:
            children: The children components.
            props: The properties of the sidebar.

        Returns:
            The drawer sidebar component.
        """
        direction = props.pop("direction", "left")
        props.setdefault("border_right", f"1px solid {color('accent', 12)}")
        props.setdefault("background_color", color("accent", 1))
        props.setdefault("width", "20vw")
        props.setdefault("height", "100vh")
        return super().create(
            drawer.trigger(
                IconButton.create(
                    "arrow-right-from-line",
                    background_color="transparent",
                ),
                position="absolute",
                top="15",
                left="15",
            ),
            drawer.portal(
                drawer.content(
                    *children,
                    **props,
                )
            ),
            direction=direction,
        )


sidebar_trigger_style = {
    "position": "fixed",
    "z_index": "15",
    "color": color("accent", 12),
    "background_color": "transparent",
    "padding": "0",
}


class SidebarTrigger(Fragment):
    """A component that renders the sidebar trigger."""

    @classmethod
    def create(cls, sidebar: Component, **props):
        """Create the sidebar trigger component.

        Args:
            sidebar: The sidebar component.
            props: The properties of the sidebar trigger.

        Returns:
            The sidebar trigger component.
        """
        trigger_props = {**props, **sidebar_trigger_style}

        inner_sidebar: Component = sidebar.children[0]  # type: ignore
        sidebar_width = inner_sidebar.style.get("width")

        if sidebar.State:
            open, toggle = sidebar.State.open, sidebar.State.toggle  # type: ignore
        else:
            open, toggle = (
                Var(_js_expr="open"),
                run_script("setOpen(!open)"),
            )

        trigger_props["left"] = cond(open, f"calc({sidebar_width} - 32px)", "0")

        trigger = cond(
            open,
            IconButton.create(
                "arrow-left-from-line",
                on_click=toggle,
                **trigger_props,
            ),
            IconButton.create(
                "arrow-right-from-line",
                on_click=toggle,
                **trigger_props,
            ),
        )
        return super().create(trigger)


class Layout(Box):
    """A component that renders the layout."""

    @classmethod
    def create(
        cls,
        *content: Component,
        sidebar: Component | None = None,
        **props,
    ):
        """Create the layout component.

        Args:
            content: The content component.
            sidebar: The sidebar component.
            props: The properties of the layout.

        Returns:
            The layout component.
        """
        layout_root = HStack.create

        if sidebar is None:
            return Container.create(*content, **props)

        if isinstance(sidebar, DrawerSidebar):
            return super().create(
                sidebar,
                Container.create(*content, height="100%"),
                **props,
                width="100vw",
                min_height="100vh",
            )

        if not isinstance(sidebar, Sidebar):
            sidebar = Sidebar.create(sidebar)

        # Add the sidebar trigger to the sidebar as first child to not mess up the rendering.
        sidebar.children.insert(0, SidebarTrigger.create(sidebar))

        return super().create(
            layout_root(
                sidebar,
                Container.create(*content, height="100%"),
                **props,
                width="100vw",
                min_height="100vh",
            )
        )


class LayoutNamespace(ComponentNamespace):
    """Namespace for layout components."""

    drawer_sidebar = staticmethod(DrawerSidebar.create)
    stateful_sidebar = staticmethod(StatefulSidebar.create)
    sidebar = staticmethod(Sidebar.create)
    __call__ = staticmethod(Layout.create)


layout = LayoutNamespace()
