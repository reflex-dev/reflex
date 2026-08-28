"""State & event-loop concurrency hammer app for reflex 0.9.9a1 pre-release testing.

Exercises:
- #6920: background task completion must not discard concurrent foreground writes.
- #6920 follow-up: background handler that never enters ``async with self`` still
  flushes one delta (under the lock), refreshing uncached computed vars.
- #6734: interim updates from a sync generator handler still flush per-yield
  (event-loop tick after emit), so streaming UIs update incrementally.
- Mixed client/server updates via rx._x.client_state.
"""

import asyncio
import time

import reflex as rx
from reflex.experimental.client_state import ClientStateVar


class RaceState(rx.State):
    """State hammered by concurrent foreground clicks and background tasks."""

    counter: int = 0  # foreground button increments
    bg_ticks: int = 0  # background one-shot increments (inside async with self)
    bg_runs: int = 0  # completed bg_once invocations
    poller_ticks: int = 0  # long-running poller increments
    poller_running: bool = False
    widen: bool = True  # arm the resolution-widening sleep in `window`

    @rx.var(cache=False)
    async def window(self) -> int:
        """Uncached async computed var recomputed on every delta.

        Suspends during delta resolution (when armed), widening any unlocked
        snapshot->clean window a-la the #6920 unit regression test.

        Returns:
            Sum of background counters.
        """
        if self.widen:
            await asyncio.sleep(0.02)
        return self.bg_ticks + self.poller_ticks

    @rx.event
    def inc(self):
        """Foreground increment."""
        self.counter += 1

    @rx.event
    async def inc_io(self):
        """Foreground increment followed by I/O (suspension after the write).

        The await after the mutation opens the pre-#6920 window: a background
        task's unlocked trailing snapshot/clean could interleave here and wipe
        the dirty flag before this handler's trailing delta harvests it.
        """
        self.counter += 1
        await asyncio.sleep(0.025)

    @rx.event
    def set_widen(self, value: bool):
        """Toggle the resolution-widening sleep."""
        self.widen = value

    @rx.event
    def reset_all(self):
        """Reset all counters."""
        self.counter = 0
        self.bg_ticks = 0
        self.bg_runs = 0
        self.poller_ticks = 0

    @rx.event(background=True)
    async def bg_once(self):
        """One-shot background task: two locked writes, a long tail, return.

        Pre-#6920 the handler return triggered an unlocked trailing
        snapshot/clean of the root state -- the race window.
        """
        for _ in range(2):
            async with self:
                self.bg_ticks += 1
            await asyncio.sleep(0.03)
        await asyncio.sleep(0.05)  # long tail outside the lock
        async with self:
            self.bg_runs += 1

    @rx.event(background=True)
    async def run_poller(self):
        """Long-running poller: 40 ticks at 10 Hz, like a status poller."""
        async with self:
            if self.poller_running:
                return
            self.poller_running = True
        for _ in range(40):
            async with self:
                self.poller_ticks += 1
            await asyncio.sleep(0.1)
        async with self:
            self.poller_running = False


class NoCtxState(rx.State):
    """Background handlers that never enter ``async with self``."""

    illegal_error: str = ""

    @rx.var(cache=False)
    def heartbeat(self) -> str:
        """Uncached computed var; refreshed by every delta flush.

        Returns:
            Current monotonic time, so any delta changes the rendered text.
        """
        return f"{time.monotonic():.6f}"

    @rx.event(background=True)
    async def bg_nudge(self):
        """Background handler with no context enter and no writes."""
        await asyncio.sleep(0.05)

    @rx.event(background=True)
    async def bg_illegal_write(self):
        """Mutate state WITHOUT ``async with self`` (expected to fail)."""
        self.illegal_error = "wrote-without-lock"


class StreamState(rx.State):
    """Sync generator handler streaming interim updates (#6734)."""

    progress: int = 0
    stream_done: bool = False

    @rx.event
    def stream(self):
        """Yield 10 interim updates, blocking the event loop between yields.

        The post-yield ``time.sleep`` blocks the asyncio loop on purpose: the
        flush tick after each emit is the only thing letting the websocket
        writer send the interim packet before the loop is blocked again.

        Yields:
            None after each interim progress write.
        """
        self.progress = 0
        self.stream_done = False
        yield
        for i in range(10):
            self.progress = i + 1
            yield
            time.sleep(0.12)
        self.stream_done = True


cs_clicks = ClientStateVar.create(var_name="csclicks", default=0, global_ref=True)


def stat(label: str, value, elem_id: str) -> rx.Component:
    """One labeled stat line with a stable DOM id."""
    return rx.hstack(
        rx.text(label, width="14em", weight="bold"),
        rx.text(value, id=elem_id),
    )


def index() -> rx.Component:
    """Race hammer page."""
    return rx.container(
        cs_clicks,
        rx.vstack(
            rx.heading("State concurrency hammer", size="6"),
            stat("counter", RaceState.counter, "counter"),
            stat("bg_ticks", RaceState.bg_ticks, "bg-ticks"),
            stat("bg_runs", RaceState.bg_runs, "bg-runs"),
            stat("poller_ticks", RaceState.poller_ticks, "poller-ticks"),
            stat("poller_running", RaceState.poller_running.to_string(), "poller-running"),
            stat("window", RaceState.window, "window"),
            stat("cs_clicks", cs_clicks.value, "cs-clicks"),
            rx.hstack(
                rx.button("inc", on_click=RaceState.inc, id="btn-inc"),
                rx.button(
                    "inc both",
                    on_click=[cs_clicks.set_value(cs_clicks.value + 1), RaceState.inc],
                    id="btn-inc-both",
                ),
                rx.button(
                    "inc both io",
                    on_click=[
                        cs_clicks.set_value(cs_clicks.value + 1),
                        RaceState.inc_io,
                    ],
                    id="btn-inc-both-io",
                ),
                rx.button("bg once", on_click=RaceState.bg_once, id="btn-bg-once"),
                rx.button("poller", on_click=RaceState.run_poller, id="btn-poller"),
                rx.button("reset", on_click=RaceState.reset_all, id="btn-reset"),
            ),
            rx.hstack(
                rx.button("widen on", on_click=RaceState.set_widen(True), id="btn-widen-on"),
                rx.button("widen off", on_click=RaceState.set_widen(False), id="btn-widen-off"),
            ),
            spacing="2",
        ),
    )


def noctx() -> rx.Component:
    """Background-without-context page."""
    return rx.container(
        rx.vstack(
            rx.heading("Background without async-with-self", size="6"),
            stat("heartbeat", NoCtxState.heartbeat, "heartbeat"),
            stat("illegal_error", NoCtxState.illegal_error, "illegal-error"),
            rx.hstack(
                rx.button("nudge", on_click=NoCtxState.bg_nudge, id="btn-nudge"),
                rx.button(
                    "illegal write",
                    on_click=NoCtxState.bg_illegal_write,
                    id="btn-illegal",
                ),
            ),
            spacing="2",
        ),
    )


def stream() -> rx.Component:
    """Streaming yields page."""
    return rx.container(
        rx.vstack(
            rx.heading("Sync generator streaming", size="6"),
            stat("progress", StreamState.progress, "progress"),
            stat("done", StreamState.stream_done.to_string(), "stream-done"),
            rx.button("stream", on_click=StreamState.stream, id="btn-stream"),
            spacing="2",
        ),
    )


app = rx.App()
app.add_page(index)
app.add_page(noctx, route="/noctx")
app.add_page(stream, route="/stream")
