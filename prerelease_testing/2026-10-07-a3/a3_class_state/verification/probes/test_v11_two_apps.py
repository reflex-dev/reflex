"""Verifier repro for a3_class_state-11: second AppHarness app rendering a state from a shared module.

Two generated apps (one, two) are started one after the other in ONE pytest process. Both
`from vshared_state import SharedCounter` (a plain top-level module next to this file, not
part of either app package) and render its count plus a button that increments it. Each app
also has a local state, to show whether the rest of the page works.

Env:
  EXPECT_VENV   venv dir name (guard)
  V_PREIMPORT   1 = this test module imports vshared_state before any app starts
  V_PORT_BASE   first frontend port; backend = +5000 (app one uses base, app two base+1)
  V_OUT         directory for screenshots / json results

Run (from this dir): EXPECT_VENV=verify_class_state-a3 V_PREIMPORT=0 V_PORT_BASE=3600 V_OUT=out \
  <venv>/bin/python -I -m pytest -s -p no:cacheprovider -p no:randomly test_v11_two_apps.py
"""

import json
import os
import time
from pathlib import Path

import pytest

import reflex

assert f"/envs/{os.environ['EXPECT_VENV']}/" in reflex.__file__, reflex.__file__

import reflex.utils.processes  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402
from reflex.testing import AppHarness  # noqa: E402

VERSION = reflex.__file__.split("/envs/")[1].split("/")[0]
PORT_BASE = int(os.environ.get("V_PORT_BASE", "3600"))
OUT = Path(os.environ.get("V_OUT", "out")).absolute()
OUT.mkdir(parents=True, exist_ok=True)
PREIMPORT = os.environ.get("V_PREIMPORT", "0") == "1"

if PREIMPORT:
    import vshared_state  # noqa: F401


class PinnedHarness(AppHarness):
    """AppHarness that binds the frontend/backend to fixed ports in the verifier's range."""

    fport: int = 0
    bport: int = 0

    def _start_backend(self, port: int = 0):
        super()._start_backend(port=self.bport)

    def _start_frontend(self):
        orig = reflex.utils.processes.new_process

        def new_process(*args, env=None, **kwargs):
            if env is not None and "PORT" in env:
                env = {**env, "PORT": str(self.fport)}
            return orig(*args, env=env, **kwargs)

        reflex.utils.processes.new_process = new_process
        try:
            super()._start_frontend()
        finally:
            reflex.utils.processes.new_process = orig


def AppOne():
    import reflex as rx
    from vshared_state import SharedCounter

    class LocalOne(rx.State):
        hits: int = 0

        @rx.event
        def hit(self):
            self.hits += 1

    def index():
        return rx.vstack(
            rx.text("app one", id="title"),
            rx.text(SharedCounter.count, id="shared"),
            rx.button("inc shared", id="inc", on_click=SharedCounter.inc),
            rx.text(LocalOne.hits, id="local"),
            rx.button("hit local", id="hit", on_click=LocalOne.hit),
        )

    app = rx.App()
    app.add_page(index)


def AppTwo():
    import reflex as rx
    from vshared_state import SharedCounter

    class LocalTwo(rx.State):
        hits: int = 0

        @rx.event
        def hit(self):
            self.hits += 1

    def index():
        return rx.vstack(
            rx.text("app two", id="title"),
            rx.text(SharedCounter.count, id="shared"),
            rx.button("inc shared", id="inc", on_click=SharedCounter.inc),
            rx.text(LocalTwo.hits, id="local"),
            rx.button("hit local", id="hit", on_click=LocalTwo.hit),
        )

    app = rx.App()
    app.add_page(index)


def _drive(harness, label):
    res = {"version": VERSION, "preimport": PREIMPORT, "app": label, "console": [], "pageerrors": []}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-proxy-server"])
        try:
            page = browser.new_context().new_page()
            page.on("console", lambda m: res["console"].append(f"{m.type}: {m.text[:300]}"))
            page.on("pageerror", lambda e: res["pageerrors"].append(str(e)[:400]))
            page.goto(harness.frontend_url, timeout=120_000)
            deadline = time.time() + 60
            while time.time() < deadline:
                if page.locator("#shared").count() and page.locator("#local").count():
                    break
                time.sleep(0.5)
            res["title_visible"] = page.locator("#title").count() > 0
            res["shared_text"] = page.locator("#shared").inner_text() if page.locator("#shared").count() else None
            res["local_text"] = page.locator("#local").inner_text() if page.locator("#local").count() else None
            if res["shared_text"] is not None:
                page.click("#inc")
                page.click("#hit")
                time.sleep(3)
                res["shared_after_click"] = page.locator("#shared").inner_text()
                res["local_after_click"] = page.locator("#local").inner_text()
            page.screenshot(path=str(OUT / f"v11-{VERSION}-pre{int(PREIMPORT)}-{label}.png"))
            res["body_text"] = page.locator("body").inner_text()[:300]
        finally:
            browser.close()
    ctx = harness.app_path / ".web" / "utils" / "context.js"
    ctx = ctx if ctx.exists() else ctx.with_suffix(".jsx")
    if ctx.exists():
        res["context_has_shared"] = "vshared_state" in ctx.read_text()
    (OUT / f"v11-{VERSION}-pre{int(PREIMPORT)}-{label}.json").write_text(json.dumps(res, indent=2))
    print(f"\n[{VERSION} pre={int(PREIMPORT)}] {label}: " + json.dumps({k: v for k, v in res.items() if k != 'console'}))
    return res


@pytest.mark.parametrize(
    ("label", "source", "offset"), [("one", AppOne, 0), ("two", AppTwo, 1)]
)
def test_app(label, source, offset, tmp_path_factory):
    PinnedHarness.fport = PORT_BASE + offset
    PinnedHarness.bport = PORT_BASE + 5000 + offset
    with PinnedHarness.create(
        root=tmp_path_factory.mktemp(f"v11_{label}"), app_source=source, app_name=f"v11app_{label}"
    ) as harness:
        res = _drive(harness, label)
    assert res["shared_text"] == "0", res
    assert res.get("shared_after_click") == "1", res
    assert res.get("local_after_click") == "1", res
