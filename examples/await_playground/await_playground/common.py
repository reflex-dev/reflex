"""Shared layout and the log mixin every page state uses."""

import time

import reflex as rx

PAGES = [
    ("/", "Basics"),
    ("/dialogs", "Ask the user"),
    ("/errors", "Errors"),
    ("/concurrent", "Concurrency"),
    ("/disconnect", "Disconnects"),
]


class LogMixin(rx.State, mixin=True):
    """A timestamped log, newest entry last. Each page state gets its own."""

    lines: rx.Field[list[str]] = rx.field([])
    started: rx.Field[float] = rx.field(0.0)

    def log(self, text: str):
        """Append a line with seconds elapsed since the last `mark()`.

        Call inside `async with self` from a background handler.

        Args:
            text: The line to append.
        """
        self.lines.append(f"[{time.monotonic() - self.started:6.2f}s] {text}")

    def mark(self):
        """Reset the elapsed clock so following log lines count from now."""
        self.started = time.monotonic()

    @rx.event
    def clear(self):
        """Empty the log."""
        self.lines = []


def layout(state: type[rx.State], title: str, blurb: str, *children) -> rx.Component:
    """Wrap a page in the nav bar, a heading, its controls and its log.

    Args:
        state: The page's state, which carries the log.
        title: The page heading.
        blurb: One or two sentences on what the page shows.
        *children: The page's controls.

    Returns:
        The page component.
    """
    return rx.container(
        rx.hstack(
            *[rx.link(name, href=path, weight="bold") for path, name in PAGES],
            spacing="5",
            padding_y="3",
        ),
        rx.heading(title, size="7"),
        rx.text(blurb, color_scheme="gray"),
        rx.vstack(*children, spacing="4", align="start", width="100%"),
        rx.divider(),
        rx.hstack(
            rx.heading("Log", size="4"),
            rx.button("Clear", on_click=state.clear, size="1", variant="soft"),
        ),
        rx.code_block(
            state.lines.join("\n"),
            language="text",
            width="100%",
            wrap_long_lines=True,
        ),
        size="3",
        padding_y="4",
    )


def row(*children) -> rx.Component:
    """Lay controls out in a wrapping row.

    Args:
        *children: The controls.

    Returns:
        The row.
    """
    return rx.flex(*children, gap="3", wrap="wrap", align="center")
