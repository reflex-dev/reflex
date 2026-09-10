"""Minimal repro: does rx.moment on_change fire at mount?

Two moments on one page:
  * #interval  : interval=3000 (ticking clock)            -> on_change=State.tick
  * #static    : no interval, fixed date, on_change       -> on_change=State.static_change
  * #zero      : interval=0 (docs demo pattern), on_change -> on_change=State.zero_change
Every handler call is printed to stdout with a monotonic sequence number and the
server wall-clock so the server log can be correlated with the frontend frames.
"""

import datetime
import sys
import time

import reflex

assert "/envs/verify_up_counter_todo_clock_0/" in reflex.__file__, reflex.__file__

import reflex as rx  # noqa: E402

SEQ = 0


def _log(kind: str, date: str) -> None:
    global SEQ
    SEQ += 1
    now = datetime.datetime.now().strftime("%H:%M:%S.%f")[:-3]
    print(f"EVT seq={SEQ} kind={kind} payload={date!r} server_time={now}", flush=True)


class State(rx.State):
    tick_count: int = 0
    static_count: int = 0
    zero_count: int = 0
    tick_log: list[str] = []
    static_log: list[str] = []
    zero_log: list[str] = []

    def tick(self, date: str):
        self.tick_count += 1
        self.tick_log.append(date)
        _log("interval", date)

    def static_change(self, date: str):
        self.static_count += 1
        self.static_log.append(date)
        _log("static", date)

    def zero_change(self, date: str):
        self.zero_count += 1
        self.zero_log.append(date)
        _log("interval0", date)


def index() -> rx.Component:
    return rx.vstack(
        rx.heading("moment on_change probe", id="title"),
        rx.hstack(
            rx.text("interval clock:"),
            rx.box(rx.moment(interval=3000, format="HH:mm:ss", on_change=State.tick), id="interval"),
        ),
        rx.hstack(
            rx.text("static date:"),
            rx.box(
                rx.moment(
                    date="2020-01-02T03:04:05Z",
                    format="YYYY-MM-DD HH:mm",
                    on_change=State.static_change,
                ),
                id="static",
            ),
        ),
        rx.hstack(
            rx.text("interval=0 clock (docs pattern):"),
            rx.box(rx.moment(interval=0, format="HH:mm:ss", on_change=State.zero_change), id="zero"),
        ),
        rx.text("tick_count=", State.tick_count, id="tick_count"),
        rx.text("zero_count=", State.zero_count, id="zero_count"),
        rx.text("zero_log=", State.zero_log.join(","), id="zero_log"),
        rx.text("static_count=", State.static_count, id="static_count"),
        rx.text("tick_log=", State.tick_log.join(","), id="tick_log"),
        rx.text("static_log=", State.static_log.join(","), id="static_log"),
        rx.link("go to /other", href="/other", id="to_other"),
        padding="2em",
    )


def other() -> rx.Component:
    return rx.vstack(
        rx.heading("other page", id="other_title"),
        rx.link("back to /", href="/", id="to_index"),
        padding="2em",
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(other, route="/other")
