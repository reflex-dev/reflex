"""Minimal mixed-fleet / rollback app: identical source and identical defaults on reflex 0.9.12, 0.10.0a1, 0.10.0a2.

The only thing that changes between server restarts is the reflex version (and FLEET_DEFAULT when testing a default change).
"""

import os
from importlib.metadata import version

import reflex as rx

VER = version("reflex")


class FleetState(rx.State):
    count: int = int(os.environ.get("FLEET_DEFAULT", "5"))
    user: str = ""
    history: list[str] = []
    _visits: int = 0

    @rx.event
    def login(self):
        self.user = "alice"

    @rx.event
    def incr(self):
        self.count += 1
        self._visits += 1
        self.history.append(f"{VER}:{self.count}:v{self._visits}")


def index():
    return rx.vstack(
        rx.text(f"server={VER}", id="server"),
        rx.text(FleetState.user, id="user"),
        rx.text(FleetState.count, id="count"),
        rx.text(FleetState.history.join(" | "), id="history"),
        rx.button("login", on_click=FleetState.login, id="login"),
        rx.button("incr", on_click=FleetState.incr, id="incr"),
    )


app = rx.App()
app.add_page(index)
