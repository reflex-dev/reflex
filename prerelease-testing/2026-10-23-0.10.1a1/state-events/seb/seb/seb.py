"""App B: thousands of programmatically generated substates (#7441 shared state store)."""

import os

import reflex as rx

N_STATES = int(os.environ.get("SEB_N_STATES", "2500"))
N_SHOWN = int(os.environ.get("SEB_N_SHOWN", "300"))


class Root(rx.State):
    clicks: int = 0

    @rx.event
    def click(self):
        self.clicks += 1


def _make_state(i: int) -> type[rx.State]:
    ns = {
        "__module__": __name__,
        "__annotations__": {"value": int, "label": str},
        "value": i,
        "label": f"state-{i}",
    }

    def bump(self):
        self.value += 1

    ns["bump"] = rx.event(bump)
    return type(f"Sub{i}", (rx.State,), ns)


STATES = [_make_state(i) for i in range(N_STATES)]
# register as module attributes so pickle (disk state manager) can find them
globals().update({cls.__name__: cls for cls in STATES})


def index() -> rx.Component:
    return rx.vstack(
        rx.heading(f"{N_STATES} substates, {N_SHOWN} shown"),
        rx.text("clicks: ", Root.clicks, id="clicks"),
        rx.button("root click", on_click=Root.click, id="btn-root"),
        rx.button("bump Sub7", on_click=STATES[7].bump, id="btn-bump7"),
        rx.button("bump Sub2499", on_click=STATES[N_STATES - 1].bump, id="btn-bumplast"),
        rx.text("ready", id="ready"),
        rx.box(
            *[
                rx.text(f"s{i}=", STATES[i].value, " ", STATES[i].label, id=f"s-{i}")
                for i in range(N_SHOWN)
            ],
            rx.text("last=", STATES[N_STATES - 1].value, id="s-last"),
            id="grid",
        ),
    )


def other() -> rx.Component:
    return rx.vstack(rx.heading("other page"), rx.text("v1000=", STATES[1000].value, id="s-1000"), rx.link("home", href="/"))


app = rx.App()
app.add_page(index, route="/")
app.add_page(other, route="/other")
