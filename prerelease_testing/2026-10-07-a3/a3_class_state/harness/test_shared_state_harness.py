"""AppHarness: three apps started one after the other in ONE pytest process, all using shared_state.SharedCfg.
App A configures `SharedCfg.count = 10; SharedCfg.theme = "dark-a"`, app B does not configure anything, app C sets 20/"dark-c".
What does each app render on a fresh browser, and does the configured LocalStorage var keep persisting?

Run (from this directory): H_VENV=<venv> H_FP=3110 H_BP=8110 PYTHONPATH=$PWD/shared <venv>/bin/python -m pytest -x -s -p no:cacheprovider test_shared_state_harness.py
"""
from __future__ import annotations

import os
import time

import pytest

import reflex
import reflex.utils.processes
from reflex.testing import AppHarness

VENV = os.environ["H_VENV"]
assert f"/scratchpad/envs/{VENV}/" in reflex.__file__, reflex.__file__
FP, BP = int(os.environ["H_FP"]), int(os.environ["H_BP"])
CHROMIUM = "/opt/pw-browsers/chromium"
RESULTS: dict[str, dict] = {}


class PinnedHarness(AppHarness):
    def _start_backend(self, port: int = 0):
        return super()._start_backend(port=BP)

    def _start_frontend(self):
        orig = reflex.utils.processes.new_process

        def pinned(args, **kwargs):
            env = kwargs.get("env")
            if env is not None and env.get("PORT") == "0":
                env["PORT"] = str(FP)
            return orig(args, **kwargs)

        reflex.utils.processes.new_process = pinned
        try:
            super()._start_frontend()
        finally:
            reflex.utils.processes.new_process = orig


def AppA():
    import reflex as rx
    from shared_state import SharedCfg

    import os

    if os.environ.get("H_ASSIGN", "1") == "1":
        SharedCfg.count = 10
        SharedCfg.theme = "dark-a"

    def index():
        return rx.vstack(rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd"), rx.text(SharedCfg.count, id="count"),
                         rx.text(SharedCfg.theme, id="theme"), rx.button("bump", on_click=SharedCfg.bump, id="bump"))

    app = rx.App()
    app.add_page(index)


def AppB():
    import reflex as rx
    from shared_state import SharedCfg

    def index():
        return rx.vstack(rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd"), rx.text(SharedCfg.count, id="count"),
                         rx.text(SharedCfg.theme, id="theme"), rx.button("bump", on_click=SharedCfg.bump, id="bump"))

    app = rx.App()
    app.add_page(index)


def AppC():
    import reflex as rx
    from shared_state import SharedCfg

    import os

    if os.environ.get("H_ASSIGN", "1") == "1":
        SharedCfg.count = 20
        SharedCfg.theme = "dark-c"

    def index():
        return rx.vstack(rx.text(rx.cond(rx.State.is_hydrated, "H:yes", "H:no"), id="hyd"), rx.text(SharedCfg.count, id="count"),
                         rx.text(SharedCfg.theme, id="theme"), rx.button("bump", on_click=SharedCfg.bump, id="bump"))

    app = rx.App()
    app.add_page(index)


def _drive(h, tag):
    from playwright.sync_api import sync_playwright

    from shared_state import SharedCfg

    f = SharedCfg.get_fields()
    rec = {"field_defaults": (f["count"].default, repr(f["theme"].default), type(f["theme"].default).__name__),
           "is_client_storage": SharedCfg._is_client_storage("theme")}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROMIUM)
        ctx = b.new_context()
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("console", lambda m: m.type == "error" and errs.append(m.text))
        pg.goto(h.frontend_url)
        pg.wait_for_function("() => document.querySelector('#hyd')?.textContent === 'H:yes'", timeout=60000)
        time.sleep(1)
        rec["initial"] = (pg.inner_text("#count"), pg.inner_text("#theme"))
        pg.click("#bump")
        time.sleep(1.5)
        rec["after_bump"] = (pg.inner_text("#count"), pg.inner_text("#theme"))
        rec["localStorage_h_theme"] = pg.evaluate("() => localStorage.getItem('h_theme')")
        pg2 = ctx.new_page()
        pg2.goto(h.frontend_url)
        pg2.wait_for_function("() => document.querySelector('#hyd')?.textContent === 'H:yes'", timeout=60000)
        time.sleep(1)
        rec["new_tab"] = (pg2.inner_text("#count"), pg2.inner_text("#theme"))
        rec["errors"] = errs
        b.close()
    RESULTS[tag] = rec
    print(f"\nRESULT {tag}: {rec}", flush=True)


@pytest.mark.parametrize("tag,src", [("A", AppA), ("B", AppB), ("C", AppC)])
def test_app(tmp_path_factory, tag, src):
    with PinnedHarness.create(root=tmp_path_factory.mktemp(f"h{tag}"), app_source=src, app_name=f"happ{tag.lower()}") as h:
        _drive(h, tag)
