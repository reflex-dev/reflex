"""Multi-page test app for the prod/export/preview cluster (reflex 0.9.9a1).

Pages:
- /            : counter + input + foreach + event chain + custom react-router component
- /about       : mostly-static page (good for prerender comparison)
- /post/[pid]  : dynamic route reading the path param
"""

import os

import reflex as rx


class State(rx.State):
    """Main app state."""

    count: int = 0
    text: str = ""
    items: list[str] = ["alpha", "beta"]
    chain_log: list[str] = []
    env_mode_seen: str = ""

    @rx.event
    def increment(self):
        """Increment the counter."""
        self.count += 1

    @rx.event
    def decrement(self):
        """Decrement the counter."""
        self.count -= 1

    @rx.event
    def set_text_val(self, value: str):
        """Set the text value.

        Args:
            value: New text value.
        """
        self.text = value

    @rx.event
    def add_item(self):
        """Add the current text as an item, then chain another handler."""
        if self.text:
            self.items.append(self.text)
            self.text = ""
        yield State.log_step("add_item done")

    @rx.event
    def log_step(self, msg: str):
        """Append a message to the chain log.

        Args:
            msg: The message.
        """
        self.chain_log.append(msg)

    @rx.event
    def load_env_mode(self):
        """Record REFLEX_ENV_MODE as seen by the backend process."""
        self.env_mode_seen = os.environ.get("REFLEX_ENV_MODE", "<unset>")


class PostState(rx.State):
    """State for the dynamic post page."""

    visits: int = 0

    @rx.event
    def on_load_post(self):
        """Count visits on page load."""
        self.visits += 1


class RRNavLink(rx.Component):
    """Custom component wrapping react-router's NavLink (library="react-router")."""

    library = "react-router"

    tag = "NavLink"

    to: rx.Var[str]

    end: rx.Var[bool]


class UseLocationSpan(rx.el.Span):
    """Span exercising a react-router hook import (useLocation) via add_imports."""

    def add_imports(self):
        """Import the useLocation hook from react-router.

        Returns:
            Import mapping.
        """
        return {"react-router": ["useLocation"]}

    def add_hooks(self):
        """Call useLocation in the component body.

        Returns:
            Hook lines.
        """
        return ["const routerLocation = useLocation();"]


def location_badge() -> rx.Component:
    """Render the current pathname via the custom react-router component.

    Returns:
        The component.
    """
    return UseLocationSpan.create(
        rx.Var("routerLocation.pathname").to(str),
        id="location-badge",
    )


def navbar() -> rx.Component:
    """Shared navigation bar.

    Returns:
        The component.
    """
    return rx.hstack(
        rx.link("Home", href="/", id="nav-home"),
        rx.link("About", href="/about", id="nav-about"),
        rx.link("Post 1", href="/post/1", id="nav-post1"),
        rx.link("Post 42", href="/post/42", id="nav-post42"),
        RRNavLink.create("NavAbout", to="/about", id="nav-navlink-about"),
        location_badge(),
        spacing="4",
        padding="1em",
    )


def index() -> rx.Component:
    """Index page.

    Returns:
        The component.
    """
    return rx.container(
        navbar(),
        rx.vstack(
            rx.heading("Prod/Export cluster app", id="main-heading"),
            rx.hstack(
                rx.button("-", on_click=State.decrement, id="btn-dec"),
                rx.text(State.count, id="count-display"),
                rx.button("+", on_click=State.increment, id="btn-inc"),
            ),
            rx.hstack(
                rx.input(
                    value=State.text,
                    on_change=State.set_text_val,
                    placeholder="new item",
                    id="item-input",
                ),
                rx.button("Add", on_click=State.add_item, id="btn-add"),
            ),
            rx.vstack(
                rx.foreach(
                    State.items,
                    lambda item, i: rx.text(item, class_name="item-row"),
                ),
                id="item-list",
            ),
            rx.text(
                "chain: ", State.chain_log.join(","), id="chain-log"
            ),
            rx.button(
                "Check env mode", on_click=State.load_env_mode, id="btn-envmode"
            ),
            rx.text("env_mode=", State.env_mode_seen, id="envmode-display"),
            rx.cond(
                State.count > 3,
                rx.badge("count is big", id="big-badge"),
                rx.badge("count is small", id="small-badge"),
            ),
            spacing="4",
        ),
    )


def about() -> rx.Component:
    """About page (mostly static).

    Returns:
        The component.
    """
    return rx.container(
        navbar(),
        rx.vstack(
            rx.heading("About page", id="about-heading"),
            rx.text("This page is mostly static content.", id="about-text"),
            rx.text("Marker: PRERENDER_CANARY_ABOUT", id="about-canary"),
        ),
    )


def post() -> rx.Component:
    """Dynamic post page.

    Returns:
        The component.
    """
    return rx.container(
        navbar(),
        rx.vstack(
            rx.heading("Post page", id="post-heading"),
            rx.text("pid=", PostState.pid, id="post-pid"),
            rx.text("visits=", PostState.visits, id="post-visits"),
        ),
    )


app = rx.App()
app.add_page(index, route="/", title="Home | prodapp")
app.add_page(about, route="/about", title="About | prodapp")
app.add_page(post, route="/post/[pid]", title="Post | prodapp", on_load=PostState.on_load_post)
