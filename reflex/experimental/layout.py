"""To experiment with layout component, move them to reflex/components later."""

import reflex as rx
from reflex.components.base.fragment import Fragment
from reflex.components.component import Component, ComponentNamespace
from reflex.components.radix.primitives.drawer import drawer, DrawerRoot
from reflex.components.radix.themes.components.icon_button import IconButton
from reflex.components.radix.themes.layout import Box
from reflex.state import ComponentState


class Sidebar(Box):
    """A component that renders the sidebar."""

    @classmethod
    def create(cls, *children, standalone: bool = False, **props):
        """Create the sidebar component."""
        # if standalone:
        #     props.setdefault("position", "fixed")
        #     props.setdefault("z_index", 10)
        props.setdefault("border_right", f"1px solid {rx.color('accent', 12)}")
        props.setdefault("background_color", rx.color("accent", 1))
        props.setdefault("width", "20vw")
        props.setdefault("height", "100vh")
        props.setdefault("left", 0)
        props.setdefault("top", 0)
        sidebar = super().create(*children, **props)
        sidebar._standalone = standalone
        return sidebar


class StatefulSidebar(ComponentState):
    """Bind a state to a sidebar component."""

    open: bool = True

    def toggle(self):
        """Toggle the sidebar."""
        self.open = not self.open

    @classmethod
    def get_component(cls, *children, **props):
        """Get the stateful sidebar component."""
        return Sidebar.create(*children, **props)


class DrawerSidebar(DrawerRoot):
    """A component that renders a drawer sidebar."""

    @classmethod
    def create(cls, *children, **props):
        """Create the sidebar component."""
        # style = props.setdefault("style", {})
        # style["background_color"] = rx.color("accent", 1)
        # style["width"] = "20vw"
        # style["height"] = "100vh"
        # style["left"] = 0
        # style["top"] = 0
        direction = props.pop("direction", "left")
        props.setdefault("border_right", f"1px solid {rx.color('accent', 12)}")
        props.setdefault("background_color", rx.color("accent", 1))
        props.setdefault("width", "20vw")
        props.setdefault("height", "100vh")
        return super().create(
            drawer.trigger(SidebarTrigger.create()),
            drawer.portal(
                drawer.content(
                    *children,
                    **props,
                )
            ),
            direction=direction,
        )


class SidebarTrigger(Fragment):
    """A component that renders the sidebar trigger."""

    @classmethod
    def create(cls, sidebar: Component | None = None, **props):

        trigger_props = {
            **props,
            "position": "absolute",
            "z_index": "15",
            "top": "15",
            "background_color": "transparent",
        }
        if sidebar:
            ...  # make stuff working with stateful sidebar
            trigger_props["left"] = rx.cond(
                sidebar.State.open, "calc(20vw - 32px)", "15"
            )
            trigger = rx.cond(
                sidebar.State.open,
                rx.icon_button(
                    "arrow-left-from-line",
                    on_click=sidebar.State.toggle,
                    **trigger_props,
                ),
                rx.icon_button(
                    "arrow-right-from-line",
                    on_click=sidebar.State.toggle,
                    **trigger_props,
                ),
            )
        else:
            ...  # make stuff working with stateless sidebar
            trigger_props["left"] = "15"
            trigger = IconButton.create("Placeholder", **trigger_props)

        return super().create(trigger, **props)


class Layout(Box):
    """A component that renders the layout."""

    @classmethod
    def create(
        cls,
        content: Component,
        sidebar: Component | None = None,
        **props,
    ):
        """Create the layout component."""
        layout_root = rx.hstack

        if sidebar is None:
            return rx.container(content, **props)

        if isinstance(sidebar, Sidebar):
            if sidebar.State:
                ...  # make stuff working with stateful sidebar
            else:
                ...  # make stuff working with stateless sidebar
        else:
            sidebar = Sidebar.create(sidebar)
        return layout_root(
            sidebar,
            # SidebarTrigger.create(
            #     sidebar=sidebar_comp,
            # ),
            rx.container(
                content,
                height="100%",
            ),
            **props,
            width="100vw",
            height="100vh",
        )


class LayoutNamespace(ComponentNamespace):
    """Namespace for layout components."""

    drawer_sidebar = staticmethod(DrawerSidebar.create)
    stateful_sidebar = staticmethod(StatefulSidebar.create)
    sidebar = staticmethod(Sidebar.create)
    __call__ = staticmethod(Layout.create)


layout = LayoutNamespace()
