"""Client-error cluster test app.

Exercises the new `client_error` socket event (#6827): a delta the frontend
cannot dispatch is reported to the backend and treated as fatal for the session.
"""

import asyncio

import reflex as rx
from reflex.state import StateUpdate

from rxconfig import config

# A substate name that has no dispatch function in any compiled frontend.
GHOST_SUBSTATE = "reflex___state____state____ghost_state"


class State(rx.State):
    """The app state."""

    counter: int = 0
    log: list[str] = []

    @rx.event
    def bump(self):
        """Normal event: bumps a counter (verifies the socket works)."""
        self.counter += 1
        self.log = [*self.log, f"bump -> {self.counter}"]

    @rx.event
    def chain_bump(self):
        """Event chain: bump twice via yielded handler."""
        self.counter += 1
        yield State.bump

    @rx.event
    async def send_unprocessable_delta(self):
        """Emit a delta whose substate the frontend can't dispatch."""
        assert app.event_namespace is not None
        await app.event_namespace.emit_update(
            StateUpdate(delta={GHOST_SUBSTATE: {"value": 1}}),
            self.router.session.client_token,
        )

    @rx.event(background=True)
    async def bg_then_break(self):
        """Background task that bumps, waits, then emits an unprocessable delta."""
        async with self:
            self.counter += 1
        await asyncio.sleep(0.3)
        assert app.event_namespace is not None
        await app.event_namespace.emit_update(
            StateUpdate(delta={GHOST_SUBSTATE: {"value": 2}}),
            self.router.session.client_token,
        )


def index() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("client_error cluster", size="7"),
            rx.text("counter=", rx.text.span(State.counter, id="counter")),
            rx.input(
                value=State.router.session.client_token,
                read_only=True,
                id="token",
            ),
            rx.button("bump", on_click=State.bump, id="bump-btn"),
            rx.button("chain bump", on_click=State.chain_bump, id="chain-btn"),
            rx.button(
                "break (unprocessable delta)",
                on_click=State.send_unprocessable_delta,
                id="break-btn",
            ),
            rx.button(
                "bg then break",
                on_click=State.bg_then_break,
                id="bg-break-btn",
            ),
            rx.foreach(State.log, lambda item: rx.text(item, class_name="logline")),
            spacing="4",
            min_height="85vh",
        ),
    )


app = rx.App()
app.add_page(index)
