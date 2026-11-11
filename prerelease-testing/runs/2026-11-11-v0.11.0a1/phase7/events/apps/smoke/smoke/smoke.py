"""Phase 7 smoke: stacked @rx.event, client_state, background task, awaited handler, optional collection ops."""
import asyncio
import os

import reflex as rx

assert os.environ["EXPECT_VENV"] in rx.__file__, rx.__file__

draft = rx.client_state("", name="draft")
clicks = rx.client_state(0, name="clicks")


class Counter(rx.State):
    total: int = 0
    log: list[str] = []
    tags: set[str] | None = None
    ticks: int = 0
    status: str = "idle"

    @rx.event
    def add(self, amount: int) -> int:
        self.total += amount
        return self.total

    @rx.event
    async def add_twice(self, amount: int):
        first = await Counter.add(amount)
        second = await Counter.add(amount)
        self.log.append(f"awaited {first}->{second}")
        return rx.toast(f"total {second}")

    @rx.event(throttle=300)
    @rx.event
    def stacked_throttled(self, text: str):
        self.log.append(f"throttled:{text}")
        self.tags = (self.tags or set()) | {text or "empty"}

    @rx.event
    @rx.event(background=True)
    async def ticker(self, n: int):
        async with self:
            self.status = "running"
        for _ in range(n):
            await asyncio.sleep(0.2)
            async with self:
                self.ticks += 1
        r = await Counter.add(100)
        async with self:
            self.status = f"done total={r}"

    @rx.event
    def clear_tags(self):
        self.tags = None


def index():
    return rx.vstack(
        rx.heading("SMOKE"),
        rx.text("total=", Counter.total, id="total"),
        rx.text("ticks=", Counter.ticks, id="ticks"),
        rx.text("status=", Counter.status, id="status"),
        rx.text("has_hello=", Counter.tags.contains("hello").to_string(), id="has_hello"),
        rx.text("ntags=", Counter.tags.length().to_string(), id="ntags"),
        rx.text("clicks=", clicks.value.to_string(), id="clicks"),
        rx.input(value=draft.value, on_change=draft.set, id="draft"),
        rx.button("add twice", on_click=[Counter.add_twice(2), clicks.set(clicks.value + 1)], id="add_twice"),
        rx.button("throttled", on_click=Counter.stacked_throttled(draft.value), id="throttled"),
        rx.button("ticker", on_click=Counter.ticker(3), id="ticker"),
        rx.button("clear tags", on_click=Counter.clear_tags, id="clear"),
        rx.foreach(Counter.log, lambda x: rx.text(x, class_name="log")),
        rx.link("other", href="/other"),
    )


def other():
    return rx.vstack(rx.text("OTHER total=", Counter.total, id="o_total"), rx.text("clicks=", clicks.value.to_string(), id="o_clicks"), rx.link("home", href="/"))


app = rx.App()
app.add_page(index, route="/")
app.add_page(other, route="/other")
