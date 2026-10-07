"""Exercise session isolation, background writes, and twenty changed substates."""

import asyncio
import os
from pathlib import Path

import reflex as rx

assert Path(rx.__file__).is_relative_to(
    Path(os.environ["SB"]) / "envs" / os.environ["QA_ENV"]
), rx.__file__


class Dashboard(rx.State):
    """Track independent foreground and background work for one browser."""

    identity: str = "unset"
    foreground: int = 0
    background: int = 0
    batch: int = 0
    finished: bool = False

    @rx.event
    def rename(self, identity: str):
        """Set this session's identity.

        Args:
            identity: Distinct label supplied by the browser.
        """
        self.identity = identity

    @rx.event
    def increment(self):
        """Record one foreground event."""
        self.foreground += 1

    @rx.event(background=True)
    async def run_background(self):
        """Persist twenty background updates while foreground events arrive."""
        for _ in range(20):
            async with self:
                self.background += 1
            await asyncio.sleep(0.04)
        async with self:
            self.finished = True

    @rx.event
    async def update_all(self):
        """Update twenty distinct substates in one foreground event."""
        for state_class in LEAF_STATES:
            state = await self.get_state(state_class)
            state.value += 1
        self.batch += 1


class Leaf00(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf01(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf02(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf03(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf04(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf05(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf06(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf07(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf08(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf09(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf10(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf11(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf12(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf13(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf14(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf15(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf16(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf17(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf18(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


class Leaf19(Dashboard):
    """Persist one independently serialized state."""

    value: int = 0


LEAF_STATES = [
    Leaf00,
    Leaf01,
    Leaf02,
    Leaf03,
    Leaf04,
    Leaf05,
    Leaf06,
    Leaf07,
    Leaf08,
    Leaf09,
    Leaf10,
    Leaf11,
    Leaf12,
    Leaf13,
    Leaf14,
    Leaf15,
    Leaf16,
    Leaf17,
    Leaf18,
    Leaf19,
]


def index():
    """Render independently verifiable values for each session and substate.

    Returns:
        Redis work dashboard.
    """
    return rx.vstack(
        rx.heading("Redis session work"),
        rx.input(
            value=Dashboard.identity, on_change=Dashboard.rename, id="identity-input"
        ),
        rx.text(Dashboard.identity, id="identity"),
        rx.hstack(
            rx.text("Foreground:"), rx.text(Dashboard.foreground, id="foreground")
        ),
        rx.hstack(
            rx.text("Background:"), rx.text(Dashboard.background, id="background")
        ),
        rx.text(Dashboard.finished.to_string(), id="finished"),
        rx.text(Dashboard.batch, id="batch"),
        rx.hstack(
            rx.button("Increment", on_click=Dashboard.increment, id="increment"),
            rx.button(
                "Background", on_click=Dashboard.run_background, id="start-background"
            ),
            rx.button("Update twenty", on_click=Dashboard.update_all, id="update-all"),
        ),
        rx.grid(
            *[
                rx.text(state.value, id=f"leaf-{index}")
                for index, state in enumerate(LEAF_STATES)
            ],
            columns="5",
            spacing="2",
        ),
        padding="24px",
    )


app = rx.App()
app.add_page(index)
