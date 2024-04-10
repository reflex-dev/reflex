"""To experiment with layout component, move them to reflex/components later."""

from reflex.components.component import Component, ComponentNamespace
from reflex.state import ComponentState

import reflex as rx


class Sidebar(ComponentState):
    """A component that renders the sidebar."""

    open: bool = True

    def toggle(self):
        self.open = not self.open

    @classmethod
    def get_component(cls, *children, **props):
        """Get the sidebar component."""
        style = props.setdefault(
            "style",
            {},
        )
        style["display"] = rx.cond(cls.open, "block", "none")
        style["border_right"] = f"1px solid {rx.color('accent', 12)}"
        style["background_color"] = rx.color("accent", 1)
        style["width"] = "20vw"
        style["height"] = "100vh"
        style["left"] = 0
        style["top"] = 0

        sidebar = rx.box(
            *children,
            **props,
        )
        return sidebar


class SidebarTrigger(Component):
    """A component that renders the sidebar trigger."""

    @classmethod
    def create(cls, sidebar: Component, **props):
        trigger_props = {
            **props,
            "position": "fixed",
            "z_index": "15",
            "top": "15",
            "left": rx.cond(sidebar.State.open, "calc(20vw - 32px)", "15"),
            "background_color": "transparent",
        }
        return rx.cond(
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


class Layout(Component):
    """A component that renders the layout."""

    @classmethod
    def create(
        cls,
        *children,
        sidebar: Component | None = None,
        content: Component,
        **props,
    ):
        if sidebar is None:
            return rx.container(content, **props)

        if not sidebar.State:
            sidebar_comp = Sidebar.create(
                rx.center(sidebar),
            )
        else:
            sidebar_comp = sidebar
        return rx.hstack(
            sidebar_comp,
            SidebarTrigger.create(
                sidebar=sidebar_comp,
            ),
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

    sidebar = staticmethod(Sidebar.create)
    __call__ = staticmethod(Layout.create)


layout = LayoutNamespace()
