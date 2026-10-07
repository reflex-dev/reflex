"""Published reflex.testing.AppHarness: two different apps, sequentially and simultaneously, driven
with Playwright; checks for registration leakage between them.

Usage: <harness-venv>/bin/python harness_test.py <expected-venv-substring> <work_root> <out_json>
Run from a neutral directory. Uses OS-assigned ports (AppHarness has no port parameters).
"""

import json
import os
import sys
import time
import traceback
from pathlib import Path

import reflex

assert sys.argv[1] in reflex.__file__, reflex.__file__
from playwright.sync_api import sync_playwright

from reflex.testing import AppHarness

ROOT = Path(sys.argv[2])
OUT = Path(sys.argv[3])
CHROMIUM = "/opt/pw-browsers/chromium"
results: dict = {"reflex_file": reflex.__file__, "checks": [], "ports": {}, "frames": {}}


def AppOne():
    """First app: counter state, an @rx.memo component, a ComponentState, an extra page."""
    import reflex as rx

    class OneState(rx.State):
        count: int = 0

        @rx.event
        def incr(self):
            self.count += 1

    @rx.memo
    def one_badge(label: rx.Var[str]) -> rx.Component:
        return rx.text("memo:", label, id="one-badge")

    class OneCounter(rx.ComponentState):
        value: int = 0

        @rx.event
        def bump(self):
            self.value += 1

        @classmethod
        def get_component(cls, **props):
            return rx.button(cls.value, on_click=cls.bump, **props)

    def index():
        return rx.vstack(
            rx.heading("app one", id="title"),
            rx.text(OneState.count, id="count"),
            rx.button("incr", on_click=OneState.incr, id="incr"),
            one_badge(label="from-one"),
            OneCounter.create(id="cs-btn"),
        )

    def only_one():
        return rx.text("page only in one", id="only-one")

    app = rx.App()
    app.add_page(index)
    app.add_page(only_one, route="/only-one")


def AppTwo():
    """Second app: different state, decorated page."""
    import reflex as rx

    class TwoState(rx.State):
        name: str = "two"

        @rx.event
        def rename(self):
            self.name = "renamed"

    @rx.page(route="/")
    def index():
        return rx.vstack(
            rx.heading("app two", id="title"),
            rx.text(TwoState.name, id="name"),
            rx.button("rename", on_click=TwoState.rename, id="rename"),
        )

    app = rx.App()


def check(name, fn):
    t0 = time.time()
    try:
        detail = fn()
        results["checks"].append({"name": name, "ok": True, "detail": None if detail is None else str(detail)[:500], "s": round(time.time() - t0, 1)})
    except Exception as e:  # noqa: BLE001
        results["checks"].append({"name": name, "ok": False, "detail": f"{type(e).__name__}: {str(e)[:500]}", "s": round(time.time() - t0, 1)})


def backend_port(h):
    try:
        return h.backend.servers[0].sockets[0].getsockname()[1]
    except Exception as e:  # noqa: BLE001
        return f"unknown ({type(e).__name__})"


def open_page(browser, url, tag):
    page = browser.new_page()
    frames, console = [], []
    page.on("websocket", lambda ws: ws.on("framereceived", lambda f: frames.append(str(f)[:4000])))
    page.on("console", lambda m: console.append(f"{m.type}: {m.text[:300]}") if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: console.append(f"pageerror: {e}"[:300]))
    page.goto(url, wait_until="networkidle", timeout=120000)
    results["frames"].setdefault(tag, frames)
    results.setdefault("console", {})[tag] = console
    return page


def drive_one(browser, h, tag):
    page = open_page(browser, h.frontend_url, tag)
    check(f"{tag}: app one title", lambda: page.wait_for_selector("text=app one", timeout=60000) and None)
    def incr():
        page.click("#incr"); page.click("#incr")
        page.wait_for_function("document.querySelector('#count')?.textContent === '2'", timeout=20000)
    check(f"{tag}: app one event roundtrip", incr)
    check(f"{tag}: app one memo renders", lambda: page.locator("#one-badge").inner_text(timeout=10000))
    def cs():
        page.click("#cs-btn")
        page.wait_for_function("document.querySelector('#cs-btn')?.textContent === '1'", timeout=20000)
    check(f"{tag}: app one ComponentState", cs)
    check(f"{tag}: /only-one served", lambda: page.goto(h.frontend_url.rstrip('/') + "/only-one", wait_until="networkidle") and page.wait_for_selector("#only-one", timeout=30000) and None)
    return page


def drive_two(browser, h, tag):
    page = open_page(browser, h.frontend_url, tag)
    check(f"{tag}: app two title", lambda: page.wait_for_selector("text=app two", timeout=60000) and None)
    def rename():
        page.click("#rename")
        page.wait_for_function("document.querySelector('#name')?.textContent === 'renamed'", timeout=20000)
    check(f"{tag}: app two event roundtrip", rename)
    def no_leak_frames():
        joined = "\n".join(results["frames"].get(tag, []))
        assert "one_state" not in joined and "one_counter" not in joined, "app one state names appear in app two websocket frames"
        return f"{len(results['frames'].get(tag, []))} frames, no app-one state names"
    check(f"{tag}: no app-one states in app-two hydration/deltas", no_leak_frames)
    def no_only_one():
        page.goto(h.frontend_url.rstrip('/') + "/only-one", wait_until="networkidle")
        page.wait_for_timeout(1500)
        assert page.locator("#only-one").count() == 0, "app one's /only-one page is served by app two"
        return page.locator("body").inner_text()[:100].replace("\n", " ")
    check(f"{tag}: app one's page not served by app two", no_only_one)
    def compiled_clean():
        web = h.app_path / ".web"
        hits = []
        for f in web.rglob("*.js*"):
            if "node_modules" in f.parts or ".vite" in f.parts or "build" in f.parts:
                continue
            try:
                s = f.read_text(errors="ignore")
            except OSError:
                continue
            for needle in ("only-one", "one_badge", "One_badge", "one_state", "OneCounter", "one_counter"):
                if needle in s:
                    hits.append(f"{f.relative_to(web)}:{needle}")
        assert not hits, hits[:10]
        return "no app-one artifacts in app two .web sources"
    check(f"{tag}: app two compiled output has no app-one artifacts", compiled_clean)
    return page


def attrs(h, tag):
    results.setdefault("attrs", {})[tag] = {
        "app_instance": type(h.app_instance).__name__ if h.app_instance is not None else None,
        "has_poll_for_clients": hasattr(h, "poll_for_clients"),
        "has_app_state_manager": hasattr(h, "app_state_manager"),
        "has_token_manager": hasattr(h, "token_manager"),
        "has_poll_for_value": hasattr(h, "poll_for_value"),
        "pages": sorted(getattr(h.app_instance, "_pages", {}).keys()) if h.app_instance is not None else None,
    }


try:
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        # A: sequential
        with AppHarness.create(root=ROOT / "seq_one", app_source=AppOne) as h1:
            results["ports"]["seq_one"] = {"frontend": h1.frontend_url, "backend": backend_port(h1)}
            attrs(h1, "seq_one")
            drive_one(browser, h1, "seq_one")
        with AppHarness.create(root=ROOT / "seq_two", app_source=AppTwo) as h2:
            results["ports"]["seq_two"] = {"frontend": h2.frontend_url, "backend": backend_port(h2)}
            attrs(h2, "seq_two")
            drive_two(browser, h2, "seq_two")
        # B: simultaneous
        with AppHarness.create(root=ROOT / "sim_one", app_source=AppOne) as s1:
            results["ports"]["sim_one"] = {"frontend": s1.frontend_url, "backend": backend_port(s1)}
            p1 = drive_one(browser, s1, "sim_one")
            with AppHarness.create(root=ROOT / "sim_two", app_source=AppTwo) as s2:
                results["ports"]["sim_two"] = {"frontend": s2.frontend_url, "backend": backend_port(s2)}
                attrs(s2, "sim_two")
                drive_two(browser, s2, "sim_two")
                # app one must keep working while app two runs
                def one_still_works():
                    pg = open_page(browser, s1.frontend_url, "sim_one_again")
                    pg.wait_for_selector("text=app one", timeout=60000)
                    pg.click("#incr")
                    pg.wait_for_function("document.querySelector('#count')?.textContent === '1'", timeout=20000)
                    pg.click("#cs-btn")
                    pg.wait_for_function("document.querySelector('#cs-btn')?.textContent === '1'", timeout=20000)
                    joined = "\n".join(results["frames"].get("sim_one_again", []))
                    assert "two_state" not in joined, "app two state names in app one frames"
                check("sim: app one still works (event + ComponentState) after app two started", one_still_works)
        browser.close()
except Exception:  # noqa: BLE001
    results["fatal"] = traceback.format_exc()[-3000:]
OUT.write_text(json.dumps(results, indent=1, default=str))
print(json.dumps({k: results[k] for k in ("ports", "attrs") if k in results}, indent=1, default=str))
for c in results["checks"]:
    print(("PASS " if c["ok"] else "FAIL ") + c["name"] + (f" -- {c['detail']}" if c["detail"] else ""))
print("console:", json.dumps(results.get("console"), indent=0)[:1500])
if "fatal" in results:
    print("FATAL:", results["fatal"])
