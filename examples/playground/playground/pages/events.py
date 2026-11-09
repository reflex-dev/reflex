"""The events page: one button per kind of event handler, and the log they write."""

from typing import Any

import reflex as rx

from playground.layout import layout
from playground.states.events import EventsState


def event_button(label: str, handler: Any, id: str) -> rx.Component:
    """Render a button firing one handler.

    Args:
        label: The button's text.
        handler: What it fires: a handler, or a handler called with arguments.
        id: The element id.

    Returns:
        The button.
    """
    return rx.button(label, on_click=handler, id=id, variant="soft")


def events() -> rx.Component:
    """Render the events page.

    Returns:
        The handler buttons, the total, the progress and the log.
    """
    return layout(
        rx.vstack(
            rx.heading("Events"),
            rx.text(
                "Each button runs a different kind of event handler; the log below "
                "records what ran."
            ),
            rx.hstack(
                rx.text(
                    "Total: ", rx.text.strong(EventsState.total, id="events-total")
                ),
                rx.text("Log entries: ", EventsState.log_size, id="events-log-size"),
                spacing="4",
            ),
            rx.grid(
                event_button("sync +1", EventsState.add_one, "events-sync"),
                event_button("args +5", EventsState.add(5), "events-args"),
                event_button("async +10", EventsState.async_add, "events-async"),
                event_button("generator", EventsState.count_up, "events-generator"),
                event_button(
                    "background", EventsState.background_count, "events-background"
                ),
                event_button("chain x2", EventsState.chain_start, "events-chain"),
                event_button(
                    "repeat x3", EventsState.repeat("ping", 3), "events-repeat"
                ),
                event_button("toast", EventsState.notify, "events-toast"),
                event_button("call script", EventsState.measure_title, "events-script"),
                event_button(
                    "download log", EventsState.download_log, "events-download"
                ),
                event_button("read tasks", EventsState.read_tasks, "events-sibling"),
                event_button("redirect home", EventsState.go_home, "events-redirect"),
                event_button("clear", EventsState.clear_log, "events-clear"),
                columns="4",
                spacing="2",
                width="100%",
            ),
            rx.progress(value=EventsState.progress, id="events-progress", width="100%"),
            rx.cond(
                EventsState.running,
                rx.badge("running", color_scheme="orange", id="events-running"),
                rx.badge("idle", id="events-running"),
            ),
            rx.text(EventsState.script_result, id="events-script-result"),
            rx.text(EventsState.sibling_summary, id="events-sibling-summary"),
            rx.scroll_area(
                rx.ordered_list(
                    rx.foreach(EventsState.log, lambda entry: rx.list_item(entry)),
                    id="events-log",
                ),
                type="auto",
                style={"max_height": "12rem"},
            ),
            spacing="3",
            width="100%",
        )
    )
