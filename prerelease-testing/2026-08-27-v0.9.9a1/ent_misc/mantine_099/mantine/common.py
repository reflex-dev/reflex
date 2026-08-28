"""Common components used by all demo pages."""

import dataclasses
import inspect
from functools import wraps
from pathlib import Path
from typing import Callable

import reflex as rx


@dataclasses.dataclass(frozen=True)
class DemoPage:
    """A demo page."""

    route: str
    title: str
    description: str


_DEMO_PAGES: dict[str, DemoPage] = {}


class DemoState(rx.State):
    """State for the demo pages."""

    @rx.var
    def pages(self) -> list[DemoPage]:
        """List of demo pages."""
        return [p for p in _DEMO_PAGES.values() if p.route != "/"]


def demo_dropdown():
    """Dropdown to navigate between demo pages."""
    return rx.select.root(
        rx.select.trigger(placeholder="Select Demo"),
        rx.select.content(
            rx.foreach(
                DemoState.pages,
                lambda page: rx.select.item(
                    rx.heading(page.title, size="3"), value=page.route
                ),
            )
        ),
        value=rx.cond(
            rx.State.router.page.path == "/",
            "",
            rx.State.router.page.path,
        ),
        on_change=rx.redirect,
    )


def demo_template(page: Callable):
    """Template for all demo pages."""
    page_data = _DEMO_PAGES[page.__name__]
    page_file = Path(inspect.getfile(page))
    page_source = page_file.read_text()
    relative_page_file = page_file.relative_to(
        Path(__file__, "..", "..", "..", "..").resolve()
    )

    return rx.container(
        rx.hstack(
            demo_dropdown(),
            rx.spacer(),
            rx.link(
                rx.heading("Mantine demo", size="4"),
                href="/",
            ),
            rx.color_mode.button(),
            width="100%",
            align="center",
        ),
        rx.text(page_data.description, margin_left="10px", margin_top="5px"),
        rx.tabs.root(
            rx.tabs.list(
                rx.tabs.trigger(
                    rx.hstack(rx.icon("eye"), rx.text("Example")), value="example"
                ),
                rx.tabs.trigger(
                    rx.hstack(rx.icon("code"), rx.text("Source")), value="source"
                ),
                margin_bottom="1em",
            ),
            rx.tabs.content(page(), value="example", height="fit-content"),
            rx.tabs.content(
                rx.card(
                    rx.inset(
                        rx.badge(
                            rx.code(str(relative_page_file)),
                            width="100%",
                            size="2",
                            height="3em",
                            radius="none",
                        ),
                        side="top",
                        pb="current",
                    ),
                    rx.code_block(
                        page_source, language="python", show_line_numbers=True
                    ),
                ),
                value="source",
            ),
            default_value="example",
            margin_top="1em",
        ),
        size="4",
    )


def demo(route: str, title: str, description: str, **kwargs):
    """Decorator to add the demo page to the demo registry."""

    def decorator(page: Callable):
        _DEMO_PAGES[page.__name__] = DemoPage(
            route=route, title=title, description=description
        )

        @rx.page(route=route, title=title, description=description, **kwargs)
        @wraps(page)
        def inner():
            return demo_template(page)

        return inner

    return decorator
