"""Test app for the 0.10.1a1 state-schema mismatch / frontend error cluster."""

import datetime
import os
from pathlib import Path

import reflex

assert "/tmp/claude-0/-home-user-reflex/7eb9e30f-e96c-5de5-9b0e-4a12be91e0f3/scratchpad/prt/envs/" in reflex.__file__, reflex.__file__

import reflex as rx

# SCHEMA_VARIANT selects a backend-only change to the state tree:
#   ""           baseline
#   "body"       handler body changed only (schema hash must NOT change)
#   "backend"    backend-only var added (schema hash must NOT change)
#   "var"        new frontend var on a substate (schema hash changes)
#   "handler"    new event handler (schema hash changes)
#   "rename"     event handler renamed (schema hash changes)
VARIANT = os.environ.get("SCHEMA_VARIANT", "")
EXC_LOG = Path(os.environ.get("FE_EXC_LOG", "logs/frontend_exceptions.log"))


class State(rx.State):
    count: int = 0
    items: list[str] = ["alpha", "beta"]
    note: str = ""
    if VARIANT == "backend":
        _hidden: int = 0

    @rx.event
    def increment(self):
        self.count += 1

    @rx.event
    def add_item(self):
        self.items.append(f"item{len(self.items)}")

    @rx.event
    def set_note(self, value: str):
        self.note = value

    if VARIANT == "body":

        @rx.event
        def ping(self):
            self.note = "pong (variant body)"
    else:

        @rx.event
        def ping(self):
            self.note = "pong"

    if VARIANT == "handler":

        @rx.event
        def extra_handler(self):
            self.count += 100

    if VARIANT == "rename":

        @rx.event
        def increment_renamed(self):
            self.count += 1

    @rx.var
    def doubled(self) -> int:
        return self.count * 2


class Sub(State):
    sub_text: str = "sub"
    if VARIANT == "var":
        extra_var: str = "extra"

    @rx.event
    def toggle(self):
        self.sub_text = "SUB" if self.sub_text == "sub" else "sub"


class Tile(rx.ComponentState):
    clicks: int = 0

    @rx.event
    def click(self):
        self.clicks += 1

    @classmethod
    def get_component(cls, **props):
        return rx.button(f"tile clicks: {cls.clicks}", on_click=cls.click, id="tile", **props)


def nav():
    return rx.hstack(
        rx.link("home", href="/", id="nav-home"),
        rx.link("about", href="/about", id="nav-about"),
        rx.link("errors", href="/errors", id="nav-errors"),
        spacing="4",
    )


def index():
    return rx.vstack(
        nav(),
        rx.heading("schema-mismatch test app", id="title"),
        rx.text(f"count: {State.count}", id="count"),
        rx.text(f"doubled: {State.doubled}", id="doubled"),
        rx.button("increment", on_click=State.increment, id="inc"),
        rx.button("ping", on_click=State.ping, id="ping"),
        rx.text(f"note: {State.note}", id="note"),
        rx.input(value=State.note, on_change=State.set_note, id="note-input"),
        rx.foreach(State.items, lambda it: rx.text(it, class_name="item")),
        rx.button("add item", on_click=State.add_item, id="add-item"),
        rx.cond(State.count > 2, rx.text("count is big", id="big"), rx.text("count is small", id="small")),
        rx.text(Sub.sub_text, id="sub"),
        rx.button("toggle sub", on_click=Sub.toggle, id="toggle"),
        padding="2em",
    )


def about():
    return rx.vstack(
        nav(),
        rx.heading("about", id="title"),
        rx.text(f"count from home: {State.count}", id="count"),
        Tile.create(),
        padding="2em",
    )


RESIZE_LOOP_JS = """
(() => {
  const box = document.createElement('div');
  box.id = 'ro-box';
  box.style.cssText = 'width:100px;height:100px;background:#ccc';
  document.body.appendChild(box);
  let n = 0;
  const ro = new ResizeObserver((entries) => {
    // Mutating the observed element's size inside the callback forces
    // "ResizeObserver loop completed with undelivered notifications."
    n += 1;
    if (n < 50) { box.style.height = (100 + n) + 'px'; }
  });
  ro.observe(box);
  box.style.height = '120px';
})();
"""


def errors():
    return rx.vstack(
        nav(),
        rx.heading("frontend errors", id="title"),
        rx.text(f"count: {State.count}", id="count"),
        rx.button("increment", on_click=State.increment, id="inc"),
        rx.button(
            "throw plain string",
            on_click=rx.call_script("setTimeout(() => { throw 'plain string'; }, 0)"),
            id="throw-string",
        ),
        rx.button(
            "dispatch empty ErrorEvent",
            on_click=rx.call_script("window.dispatchEvent(new ErrorEvent('error', {}))"),
            id="empty-errorevent",
        ),
        rx.button(
            "dispatch ErrorEvent with message only",
            on_click=rx.call_script(
                "window.dispatchEvent(new ErrorEvent('error', {message: 'ResizeObserver loop completed with undelivered notifications.'}))"
            ),
            id="message-errorevent",
        ),
        rx.button("resize observer loop", on_click=rx.call_script(RESIZE_LOOP_JS), id="ro-loop"),
        rx.button(
            "throw Error object",
            on_click=rx.call_script("setTimeout(() => { throw new Error('real error'); }, 0)"),
            id="throw-error",
        ),
        rx.button(
            "unhandled rejection",
            on_click=rx.call_script("Promise.reject(new Error('rejected'))"),
            id="reject",
        ),
        padding="2em",
    )


def frontend_exception_handler(exception: Exception) -> None:
    """Record every frontend exception the backend receives."""
    EXC_LOG.parent.mkdir(parents=True, exist_ok=True)
    with EXC_LOG.open("a") as f:
        f.write(f"{datetime.datetime.now().isoformat()} {type(exception).__name__}: {exception!r}\n---\n")
    print(f"[frontend_exception_handler] {exception!r}", flush=True)


app = rx.App(frontend_exception_handler=frontend_exception_handler)
app.add_page(index, route="/")
app.add_page(about, route="/about")
app.add_page(errors, route="/errors")
