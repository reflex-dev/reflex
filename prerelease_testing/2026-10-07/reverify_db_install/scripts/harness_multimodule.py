"""AppHarness #7359: the FIRST app keeps a state in a second module (optionally an rx.dynamic widget that
registers an always-dirty computed var); a SECOND app then starts in the same process and must work.

Usage: <harness-venv>/bin/python harness_multimodule.py <expected-venv-substring> <work_root> <out_json> <scenario>
scenario: plain  -> app one: state in a second module, no rx.dynamic
          dynamic-> app one: state in a second module + rx.dynamic widget
          dynamic-same -> as dynamic, then app one is started AGAIN (same name) after app two
          plain-restart / dynamic-restart -> app one is started twice in a row (no app two)
Run from a neutral directory; AppHarness picks ephemeral ports. Pass/fail is recorded in the JSON; exit 0 always.
"""
import json
import sys
import textwrap
import time
import traceback
from pathlib import Path

import reflex

assert sys.argv[1] in reflex.__file__, reflex.__file__
from playwright.sync_api import sync_playwright

from reflex.testing import AppHarness

ROOT, OUT, SCENARIO = Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
CHROMIUM = "/opt/pw-browsers/chromium"
res: dict = {"reflex": reflex.__file__, "scenario": SCENARIO, "checks": []}


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(textwrap.dedent(text))


def make_app_one(root: Path, dynamic: bool):
    name = root.name
    write(root / "rxconfig.py", f'import reflex as rx\nconfig = rx.Config(app_name="{name}", telemetry_enabled=False)\n')
    write(root / name / "__init__.py", "")
    write(root / name / "states.py", """
        import reflex as rx


        class WidgetState(rx.State):
            n: int = 0

            @rx.event
            def bump(self):
                self.n += 1
    """)
    if dynamic:
        write(root / name / "widgets.py", f"""
            import reflex as rx

            from {name}.states import WidgetState


            @rx.dynamic
            def dyn(state: WidgetState):
                return rx.text("widget:", state.n, id="widget")
        """)
        extra_import, extra_child = f"from {name}.widgets import dyn", "dyn(),"
    else:
        extra_import, extra_child = "", 'rx.text("widget:", WidgetState.n, id="widget"),'
    write(root / name / f"{name}.py", f"""
        import reflex as rx

        from {name}.states import WidgetState
        {extra_import}


        def index():
            return rx.vstack(
                rx.heading("app one", id="title"),
                {extra_child}
                rx.button("bump", on_click=WidgetState.bump, id="bump"),
            )


        app = rx.App()
        app.add_page(index)
    """)


def two_source():
    import reflex as rx

    class TwoState(rx.State):
        name: str = "two"

        @rx.event
        def rename(self):
            self.name = "renamed"

    def index():
        return rx.vstack(
            rx.heading("app two", id="title"),
            rx.text(TwoState.name, id="name"),
            rx.button("rename", on_click=TwoState.rename, id="rename"),
        )

    app = rx.App()
    app.add_page(index)


def check(name, fn):
    t0 = time.time()
    try:
        d = fn()
        res["checks"].append({"name": name, "ok": True, "detail": None if d is None else str(d)[:600], "s": round(time.time() - t0, 1)})
        print(f"[PASS] {name}: {d}", flush=True)
    except Exception as e:  # noqa: BLE001
        res["checks"].append({"name": name, "ok": False, "detail": f"{type(e).__name__}: {str(e)[:600]}", "s": round(time.time() - t0, 1)})
        print(f"[FAIL] {name}: {type(e).__name__}: {str(e)[:300]}", flush=True)


def page_for(browser, url, tag):
    page = browser.new_page()
    frames, cons = [], []
    page.on("websocket", lambda ws: ws.on("framereceived", lambda f: frames.append(str(f)[:3000])))
    page.on("console", lambda m: cons.append(f"{m.type}: {m.text[:300]}") if m.type == "error" else None)
    page.goto(url, wait_until="networkidle", timeout=120000)
    res.setdefault("frames", {})[tag] = frames
    res.setdefault("console_errors", {})[tag] = cons
    return page


def drive_one(browser, h, tag):
    page = page_for(browser, h.frontend_url, tag)
    check(f"{tag}: app one renders", lambda: page.wait_for_selector("text=app one", timeout=60000) and page.inner_text("#widget"))

    def bump():
        page.click("#bump")
        page.click("#bump")
        page.wait_for_function("document.querySelector('#widget')?.textContent?.replace(/\\s/g,'').endsWith('2')", timeout=20000)
        return page.inner_text("#widget")

    check(f"{tag}: app one event roundtrip (state from 2nd module)", bump)
    page.close()


def drive_two(browser, h, tag):
    page = page_for(browser, h.frontend_url, tag)
    check(f"{tag}: app two renders", lambda: page.wait_for_selector("text=app two", timeout=60000) and None)

    def rename():
        page.click("#rename")
        page.wait_for_function("document.querySelector('#name')?.textContent === 'renamed'", timeout=20000)
        return "renamed"

    check(f"{tag}: app two event roundtrip", rename)

    def no_app_one_frames():
        joined = "\n".join(res["frames"][tag])
        assert "widget_state" not in joined and "mm_one" not in joined, [l for l in joined.splitlines() if "widget_state" in l][:2]
        assert "KeyError" not in joined
        return f"{len(res['frames'][tag])} frames, no app-one state names"

    check(f"{tag}: no app-one state names / KeyError in app-two frames", no_app_one_frames)
    toast = page.query_selector_all("[data-sonner-toast]")
    check(f"{tag}: no error toast", lambda: (_ for _ in ()).throw(AssertionError(page.inner_text("[data-sonner-toast]")[:300])) if toast else "none")
    page.close()


try:
    dynamic = SCENARIO.startswith("dynamic")
    one_root = ROOT / "mm_one"
    make_app_one(one_root, dynamic)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        with AppHarness.create(root=one_root) as h1:
            drive_one(browser, h1, "one")
        res["after_one_stop"] = {
            "always_dirty_substates_on_root": sorted(reflex.State._always_dirty_substates),
        }
        print("after app one stopped: State._always_dirty_substates =", res["after_one_stop"], flush=True)
        if SCENARIO.endswith("-restart"):
            with AppHarness.create(root=one_root) as h3:
                drive_one(browser, h3, "one_again")
        else:
            with AppHarness.create(root=ROOT / "mm_two", app_source=two_source) as h2:
                drive_two(browser, h2, "two")
        if SCENARIO == "dynamic-same":
            with AppHarness.create(root=one_root) as h3:
                drive_one(browser, h3, "one_again")
        browser.close()
except Exception as e:  # noqa: BLE001
    res["fatal"] = "".join(traceback.format_exception(e))[-2500:]
    print("FATAL", res["fatal"], flush=True)
res["all_ok"] = "fatal" not in res and all(c["ok"] for c in res["checks"])
OUT.write_text(json.dumps(res, indent=1))
print("ALL_OK" if res["all_ok"] else "SOME_FAILED", flush=True)
