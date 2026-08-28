"""Test (c) addendum: dynamic components under AppHarness (in-process backend).

Under AppHarness the backend thread runs with a copied contextvars context, so the
runtime serializer sees the same RegistrationContext that compiled the frontend
(radix bundled) -> dynamic components should resolve @radix-ui/themes from
window.__reflex, needing NO CDN access.

Run:
    REFLEX_TELEMETRY_ENABLED=false <rcx-venv>/bin/python -m pytest \
        test_appharness_dynamic.py -x -s -q
"""

import time

import pytest
from playwright.sync_api import sync_playwright

from reflex.testing import AppHarness

CHROMIUM = "/opt/pw-browsers/chromium"


def DynHarnessApp():
    import reflex as rx

    class DynHarnessState(rx.State):
        label: str = "start"

        @rx.event
        def relabel(self):
            self.label = "clicked"

        @rx.var
        def dyn_block(self) -> rx.Component:
            return rx.vstack(
                rx.text(f"label: {self.label}", id="dyn-label"),
                rx.button("relabel", id="dyn-relabel", on_click=DynHarnessState.relabel),
            )

    def index():
        return rx.vstack(
            rx.heading("DYNHARNESS", id="marker"),
            DynHarnessState.dyn_block,
        )

    app = rx.App()
    app.add_page(index)


@pytest.fixture(scope="module")
def harness(tmp_path_factory):
    with AppHarness.create(
        root=tmp_path_factory.mktemp("dynharness"), app_source=DynHarnessApp
    ) as h:
        yield h


def test_dynamic_component_no_cdn(harness):
    console, cdn_requests, failed = [], [], []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        page = browser.new_page()
        page.on("console", lambda m: console.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: console.append(f"[pageerror] {e}"))
        page.on(
            "request",
            lambda r: cdn_requests.append(r.url) if "cdn.jsdelivr" in r.url else None,
        )
        page.on(
            "requestfailed",
            lambda r: failed.append(f"{r.url} -> {r.failure}"),
        )
        base = harness.frontend_url.rstrip("/")
        page.goto(base + "/", wait_until="load", timeout=60000)
        page.wait_for_selector("#marker", timeout=60000)

        # computed dynamic component must render (from window.__reflex, no CDN)
        page.wait_for_selector("#dyn-label", timeout=30000)
        assert page.inner_text("#dyn-label") == "label: start"

        # event handler inside the dynamic component
        page.click("#dyn-relabel")
        deadline = time.time() + 15
        while time.time() < deadline and page.inner_text("#dyn-label") != "label: clicked":
            time.sleep(0.2)
        assert page.inner_text("#dyn-label") == "label: clicked"

        page.screenshot(path="dynharness.png", full_page=True)
        browser.close()

    print("\nCDN requests:", cdn_requests or "(none)")
    print("failed requests:", failed or "(none)")
    print("console:", *console, sep="\n  ")
    assert not cdn_requests, f"dynamic component hit CDN under AppHarness: {cdn_requests}"
