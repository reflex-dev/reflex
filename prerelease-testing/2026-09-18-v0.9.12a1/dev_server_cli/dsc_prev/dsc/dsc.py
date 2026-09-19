"""dev_server_cli cluster test app."""

import asyncio
import logging
import os
import sys

import reflex as rx

assert "/home/user/reflex" not in rx.__file__, rx.__file__

from settings import MARKER_CLASS_ID, SettingsMarker  # noqa: E402

log = logging.getLogger("dsc.app")
log.warning(
    "APP_MODULE_IMPORT pid=%s marker_id=%s settings_id=%s nmods=%s",
    os.getpid(),
    MARKER_CLASS_ID,
    id(SettingsMarker),
    len(sys.modules),
)

HEADING = "dsc v5-reload"


class DscState(rx.State):
    """Main state."""

    count: int = 0
    items: list[str] = ["alpha", "beta"]
    bg_ticks: int = 0
    chained: str = ""

    @rx.event
    def inc(self):
        """Increment."""
        self.count += 1

    @rx.event
    def add_item(self):
        """Append an item and chain to another handler."""
        self.items = [*self.items, f"item-{self.count}"]
        return DscState.mark_chained

    @rx.event
    def mark_chained(self):
        """Second link of the chain."""
        self.chained = f"chained@{self.count}"

    @rx.event(background=True)
    async def bg(self):
        """Background task ticking 3 times."""
        for _ in range(3):
            await asyncio.sleep(0.3)
            async with self:
                self.bg_ticks += 1

    @rx.var
    def modules_report(self) -> str:
        """Report on backend worker sys.modules."""
        probes = ("sqlalchemy", "alembic", "starlette_admin", "pandas", "httpx", "reflex.compiler")
        present = [p for p in probes if p in sys.modules]
        try:
            rss = int(
                [x for x in open("/proc/self/status").read().splitlines() if x.startswith("VmRSS")][0].split()[1]
            )
        except Exception:
            rss = -1
        return f"pid={os.getpid()} nmods={len(sys.modules)} rss_kb={rss} present={','.join(present) or 'none'}"


cs = rx._x.client_state("cs_counter", 0)


@rx.memo
def memo_row(label: str, n: int) -> rx.Component:
    """A memoized row."""
    return rx.hstack(rx.text(label, id="memo-label"), rx.text(n))


class CounterCS(rx.ComponentState):
    """ComponentState counter."""

    v: int = 0

    @rx.event
    def bump(self):
        """Bump."""
        self.v += 1

    @classmethod
    def get_component(cls, **props):
        """Build."""
        return rx.hstack(
            rx.button("cs+", on_click=cls.bump, id=props.pop("bid", "cs-btn")),
            rx.text(cls.v, id=props.pop("vid", "cs-val")),
            **props,
        )


def index() -> rx.Component:
    """Index page."""
    return rx.vstack(
        rx.heading(HEADING, id="heading"),
        rx.text(DscState.count, id="count"),
        rx.button("inc", on_click=DscState.inc, id="inc"),
        rx.button("add", on_click=DscState.add_item, id="add"),
        rx.text(DscState.chained, id="chained"),
        rx.button("bg", on_click=DscState.bg, id="bg"),
        rx.text(DscState.bg_ticks, id="bg-ticks"),
        cs,
        rx.button("client+", on_click=cs.set_value(cs.value + 1), id="client-inc"),
        rx.text(cs.value, id="client-val"),
        memo_row(label="memo", n=DscState.count),
        CounterCS.create(),
        rx.foreach(DscState.items, lambda i: rx.text(i, class_name="item")),
        rx.cond(DscState.count > 2, rx.text("BIG", id="big"), rx.text("small", id="big")),
        rx.text(DscState.modules_report, id="modules"),
        rx.link("other", href="/other", id="to-other"),
        rx.link("dyn", href="/item/xyz", id="to-dyn"),
    )


def other() -> rx.Component:
    """Second page."""
    return rx.vstack(
        rx.heading("other page", id="heading"),
        rx.text(DscState.count, id="count"),
        rx.link("home", href="/", id="to-home"),
    )


def item() -> rx.Component:
    """Dynamic route page."""
    return rx.vstack(
        rx.heading("item", id="heading"),
        rx.text(DscState.router.url.path, id="iid"),
    )


app = rx.App()
app.add_page(index, route="/")
app.add_page(other, route="/other")
app.add_page(item, route="/item/[iid]")
