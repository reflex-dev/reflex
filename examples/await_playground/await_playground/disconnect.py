"""Disconnects: what happens to an awaited call when the tab goes away."""

import asyncio

import reflex as rx
from reflex.utils.exceptions import BrowserDisconnectedError

from .common import LogMixin, layout, row

# The frontend's socket is in scope of call_script. reconnect() reuses the tab's
# token, as the frontend does after a dropped connection. The awaited script
# itself drops the socket, so the call is already running in the tab when the
# connection goes: a call emitted while the socket is closing is lost in flight
# and waits for its timeout instead.
DROP_THEN_RESOLVE = """new Promise(resolve => {{
    socket.disconnect();
    setTimeout(() => socket.reconnect(), {reconnect_ms});
    setTimeout(() => resolve('settled at {resolve_ms}ms'), {resolve_ms});
}})"""

# Sends its result, then drops the socket on the next tick.
DROP_SOCKET = (
    "setTimeout(() => {{ socket.disconnect();"
    " setTimeout(() => socket.reconnect(), {ms}) }}, 0);"
    "'socket dropped for {ms}ms'"
)


class DisconnectState(LogMixin, rx.State):
    """State for the disconnects page."""

    @rx.event(background=True)
    async def wait_for_answer(self):
        """Await a promise only the 'Answer' button settles; reload or go offline first."""
        async with self:
            self.mark()
            self.log(
                "waiting for Answer (no timeout). Now reload, close, or drop the socket."
            )
        try:
            answer = await rx.call_script(
                "new Promise(resolve => { window.__answer = resolve })", timeout=None
            )
        except BrowserDisconnectedError as e:
            async with self:
                self.log(f"BrowserDisconnectedError: {e}")
        else:
            async with self:
                self.log(f"answer = {answer!r}")

    @rx.event(background=True)
    async def survive_short_drop(self):
        """Socket down 1s, result at 2s: under the 3s grace period, so it arrives."""
        async with self:
            self.mark()
            self.log("script drops the socket, reconnects at 1s, settles at 2s")
        value = await rx.call_script(
            DROP_THEN_RESOLVE.format(reconnect_ms=1000, resolve_ms=2000)
        )
        async with self:
            self.log(f"result after reconnect: {value!r}")

    @rx.event(background=True)
    async def exceed_grace(self):
        """Socket down 6s: the call fails at 3s, and the result settled at 2s is lost."""
        async with self:
            self.mark()
            self.log("script drops the socket, reconnects at 6s, settles at 2s")
        try:
            await rx.call_script(
                DROP_THEN_RESOLVE.format(reconnect_ms=6000, resolve_ms=2000)
            )
        except BrowserDisconnectedError as e:
            async with self:
                self.log(f"BrowserDisconnectedError: {e}")

    @rx.event(background=True)
    async def call_from_detached(self):
        """What a call sees when the tab is not connected at all when it starts."""
        async with self:
            self.mark()
        await rx.call_script(DROP_SOCKET.format(ms=1500))
        await asyncio.sleep(0.5)
        # The tab is gone when this call starts: it fails at once, no grace period.
        try:
            await rx.call_script("'immediate'")
        except BrowserDisconnectedError as e:
            outcome = f"BrowserDisconnectedError: {e}"
        else:
            outcome = "got 'immediate': the disconnect had not landed yet"
        async with self:
            self.log(outcome)


@rx.page(route="/disconnect", title="Await playground: disconnects")
def disconnect() -> rx.Component:
    """The disconnects page.

    Returns:
        The page.
    """
    return layout(
        DisconnectState,
        "Disconnects",
        "browser_call_grace_period is 3s in rxconfig.py. A tab that reconnects within it "
        "delivers its result; a reload fails the call as soon as the new page connects. "
        "Try DevTools > Network > Offline as well.",
        row(
            rx.button("Wait for Answer", on_click=DisconnectState.wait_for_answer),
            rx.button(
                "Answer",
                on_click=rx.call_script("window.__answer?.('42')"),
                variant="soft",
            ),
        ),
        row(
            rx.button(
                "Drop socket 1s, then await",
                on_click=DisconnectState.survive_short_drop,
            ),
            rx.button(
                "Drop socket 6s, exceed grace", on_click=DisconnectState.exceed_grace
            ),
            rx.button(
                "Call while dropped", on_click=DisconnectState.call_from_detached
            ),
        ),
        rx.text(
            "After a reload the log is kept (same client token), so the "
            "BrowserDisconnectedError from 'Wait for Answer' shows up on the new page.",
            size="2",
            color_scheme="gray",
        ),
    )
