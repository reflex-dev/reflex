"""Concurrency: many handlers await the browser at once, and the tab stays live."""

import asyncio
import random

import reflex as rx

from .common import LogMixin, layout, row


class ConcurrentState(LogMixin, rx.State):
    """State for the concurrency page."""

    clicks: rx.Field[int] = rx.field(0)
    running: rx.Field[int] = rx.field(0)

    @rx.event
    def click(self):
        """A regular handler, to show it is not blocked by the awaiting ones."""
        self.clicks += 1

    @rx.event(background=True)
    async def one(self, i: int, delay_ms: int):
        """Await a promise with a known delay and log when it settles."""
        async with self:
            self.running += 1
        value = await rx.call_script(
            f"new Promise(r => setTimeout(() => r('task {i} after {delay_ms}ms'), {delay_ms}))"
        )
        async with self:
            self.running -= 1
            self.log(value)

    @rx.event(background=True)
    async def fan_out(self):
        """Start five awaiting handlers; they finish in delay order, not start order."""
        async with self:
            self.mark()
            self.log("starting 5 tasks with random delays")
        for i in range(5):
            # Queue each as its own background handler: five concurrent awaits.
            yield ConcurrentState.one(i, random.randint(200, 2000))

    @rx.event(background=True)
    async def gather(self):
        """asyncio.gather over awaited calls inside one handler."""
        async with self:
            self.mark()
        results = await asyncio.gather(
            *(
                rx.call_script(
                    f"new Promise(r => setTimeout(() => r({i}), {(5 - i) * 150}))"
                )
                for i in range(5)
            )
        )
        async with self:
            self.log(f"gather kept argument order: {results}")

    @rx.event(background=True)
    async def race(self):
        """asyncio.wait FIRST_COMPLETED: the losers are cancelled on the Python side."""
        async with self:
            self.mark()
        tasks = [
            asyncio.ensure_future(
                rx.call_script(f"new Promise(r => setTimeout(() => r('{name}'), {ms}))")
            )
            for name, ms in (("tortoise", 1500), ("hare", 300))
        ]
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for t in pending:
            t.cancel()
        async with self:
            self.log(f"winner: {done.pop().result()!r}; cancelled {len(pending)} other")

    @rx.event(background=True)
    async def long_poll(self):
        """Hold one await open for 8s while you click the counter."""
        async with self:
            self.mark()
            self.log("awaiting an 8s promise; click the counter meanwhile")
        value = await rx.call_script(
            "new Promise(r => setTimeout(() => r('done'), 8000))"
        )
        async with self:
            self.log(f"8s promise {value}, clicks seen meanwhile: {self.clicks}")


@rx.page(route="/concurrent", title="Await playground: concurrency")
def concurrent() -> rx.Component:
    """The concurrency page.

    Returns:
        The page.
    """
    return layout(
        ConcurrentState,
        "Concurrency",
        "Awaited calls are plain awaitables: gather them, race them, or run several "
        "handlers at once. None of them hold the state lock while waiting.",
        row(
            rx.button("Fan out 5 handlers", on_click=ConcurrentState.fan_out),
            rx.button("asyncio.gather 5 calls", on_click=ConcurrentState.gather),
            rx.button("Race two calls", on_click=ConcurrentState.race),
            rx.button("Hold an 8s await", on_click=ConcurrentState.long_poll),
        ),
        row(
            rx.button(
                f"clicks: {ConcurrentState.clicks}",
                on_click=ConcurrentState.click,
                variant="soft",
            ),
            rx.badge(f"awaiting handlers: {ConcurrentState.running}"),
        ),
    )
