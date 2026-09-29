"""The content page: markdown, highlighted code, icons, dates and media players."""

import reflex as rx

from playground.layout import layout

MARKDOWN = """
## Markdown

Reflex renders **markdown** with *emphasis*, `inline code`, [links](/about) and lists:

1. State lives on the server.
2. Events travel over a websocket.
3. The page updates from the deltas.

| Page | Shows |
| --- | --- |
| Data | A table over sqlite |
| Room | A shared state |

> A quote, to round it off.
"""

CODE = """import reflex as rx


class CounterState(rx.State):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1
"""

ICONS = (
    "activity",
    "bell",
    "calendar",
    "camera",
    "cloud",
    "code",
    "database",
    "file-text",
    "globe",
    "heart",
    "image",
    "layers",
    "lock",
    "mail",
    "map",
    "music",
    "package",
    "search",
    "settings",
    "star",
    "sun",
    "user",
    "users",
    "zap",
)

DATES = (
    ("Release", "2026-01-15T09:30:00Z"),
    ("Launch", "2026-03-01T12:00:00Z"),
    ("Review", "2026-06-30T17:45:00Z"),
)


def content() -> rx.Component:
    """Render the content page.

    Returns:
        Markdown, a code block, an icon grid, formatted dates and media players.
    """
    return layout(
        rx.vstack(
            rx.heading("Content"),
            rx.box(rx.markdown(MARKDOWN), id="content-markdown"),
            rx.box(
                rx.code_block(CODE, language="python", show_line_numbers=True),
                id="content-code",
                width="100%",
            ),
            rx.heading("Icons", size="3"),
            rx.grid(
                *[
                    rx.tooltip(
                        rx.box(rx.icon(name, size=20), class_name="p-2"), content=name
                    )
                    for name in ICONS
                ],
                columns="8",
                spacing="2",
                id="content-icons",
            ),
            rx.heading("Dates", size="3"),
            rx.data_list.root(
                *[
                    rx.data_list.item(
                        rx.data_list.label(label),
                        rx.data_list.value(
                            rx.moment(date=date, format="YYYY-MM-DD HH:mm", tz="UTC")
                        ),
                    )
                    for label, date in DATES
                ],
                id="content-dates",
            ),
            rx.heading("Media", size="3"),
            rx.hstack(
                rx.box(
                    rx.audio(
                        src="/chime.wav", controls=True, width="16rem", height="3rem"
                    ),
                    id="content-audio",
                ),
                rx.box(
                    rx.video(
                        src="/chime.wav", controls=True, width="16rem", height="9rem"
                    ),
                    id="content-video",
                ),
                spacing="4",
                wrap="wrap",
            ),
            width="100%",
        )
    )
