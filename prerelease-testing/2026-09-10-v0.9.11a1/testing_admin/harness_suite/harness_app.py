"""The app under test plus shared Playwright helpers for the AppHarness suite.

Deliberately written the way a downstream project would: the app is a plain
function whose source AppHarness copies into a generated module.
"""

from __future__ import annotations

import contextlib
import os

import reflex

assert "/envs/" in reflex.__file__ and "/home/user/reflex/" not in reflex.__file__, (
    reflex.__file__
)

CHROMIUM = "/opt/pw-browsers/chromium"


def DemoApp():
    import asyncio
    import dataclasses

    import reflex as rx

    @dataclasses.dataclass
    class Item:
        name: str = ""
        qty: int = 0

    class DemoState(rx.State):
        count: int = 0
        items: list[str] = []
        meta: dict[str, int] = {}
        row: Item = Item(name="seed", qty=1)
        bg_ticks: int = 0

        @rx.var
        def summary(self) -> str:
            return f"{self.count}/{len(self.items)}/{self.row.qty}"

        @rx.event
        def bump(self):
            self.count += 1
            self.items.append(f"i{self.count}")
            self.meta[f"k{self.count}"] = self.count
            self.row.qty += 1

        @rx.event
        def chained(self):
            self.count += 10
            return DemoState.bump

        @rx.event(background=True)
        async def tick(self):
            for _ in range(3):
                async with self:
                    self.bg_ticks += 1
                await asyncio.sleep(0.05)

    def index():
        return rx.vstack(
            rx.text(DemoState.router.session.client_token, id="token"),
            rx.text(DemoState.summary, id="summary"),
            rx.text(DemoState.count.to_string(), id="count"),
            rx.text(DemoState.bg_ticks.to_string(), id="ticks"),
            rx.text(DemoState.items.length().to_string(), id="nitems"),
            rx.button("bump", on_click=DemoState.bump, id="bump"),
            rx.button("chain", on_click=DemoState.chained, id="chain"),
            rx.button("tick", on_click=DemoState.tick, id="tick"),
            rx.link("second", href="/second", id="tosecond"),
            rx.foreach(DemoState.items, lambda i: rx.text(i, class_name="item")),
        )

    def second():
        return rx.vstack(
            rx.text("second page", id="second"),
            rx.text(DemoState.count.to_string(), id="count2"),
        )

    app = rx.App()
    app.add_page(index, route="/")
    app.add_page(second, route="/second")


class PWText:
    """Duck-typed stand-in for a selenium WebElement, backed by a Playwright page.

    `AppHarness.poll_for_content` only touches `element.text`, so a Playwright
    locator can be polled with the documented helper.
    """

    def __init__(self, page, selector: str):
        self.page = page
        self.selector = selector

    @property
    def text(self) -> str:
        return self.page.locator(self.selector).inner_text()

    def __repr__(self) -> str:
        return f"<PWText {self.selector}>"


@contextlib.contextmanager
def browser():
    """Chromium with the agent proxy bypassed for the browser only."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch(
            executable_path=CHROMIUM,
            args=["--no-sandbox", "--no-proxy-server"],
        )
        try:
            yield b
        finally:
            b.close()


def new_page(b, console_sink: list, network_sink: list):
    page = b.new_page()
    page.on(
        "console",
        lambda m: console_sink.append({"type": m.type, "text": m.text}),
    )
    page.on("pageerror", lambda e: console_sink.append({"type": "pageerror", "text": str(e)}))
    page.on(
        "response",
        lambda r: network_sink.append({"status": r.status, "url": r.url})
        if r.status >= 400
        else None,
    )
    page.on(
        "requestfailed",
        lambda r: network_sink.append({"status": "failed", "url": r.url, "err": str(r.failure)}),
    )
    return page


def read_state(harness, token: str, attrs):
    """Read attributes of the app's DemoState for a live browser token.

    Must be called OUTSIDE a `sync_playwright()` block: the sync Playwright API
    owns an event loop in this thread, and `asyncio.run()` refuses to nest.
    """
    import asyncio

    import reflex as rx

    app = harness.app_instance
    state_cls = harness.app_module.DemoState  # pyright: ignore[reportOptionalMemberAccess]

    async def run():
        # NOTE: BaseStateToken.cls does NOT scope the lookup - get_state() always
        # returns the ROOT state for the ident, so navigate to the substate.
        from reflex.state import State

        root = await app.state_manager.get_state(rx.BaseStateToken(ident=token, cls=State))
        st = await root.get_state(state_cls)
        return {a: getattr(st, a) for a in attrs}

    return asyncio.run(run())


SHOTS = os.environ.get("TA_SHOTS", "/tmp")


def vite_client_status(frontend_url: str) -> int:
    """Dev (react-router/vite) serves /@vite/client; a prod static build 404s it."""
    import httpx

    with httpx.Client(trust_env=False, timeout=30) as c:
        return c.get(frontend_url.rstrip("/") + "/@vite/client").status_code
