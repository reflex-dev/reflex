"""Drive dtapp: initial load (on_load=State.load), Add aware, Add naive, reload.

Usage: NO_PROXY=localhost,127.0.0.1 $SB/envs/driver/bin/python drive_dtapp.py <url> <outdir> <tag> [label]
The browser context runs in America/New_York so rx.moment shows how the serialized
created_at string is interpreted by the browser (aware '+00:00' vs naive -> local).
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from harness import CHROMIUM, Run, guard_driver_python, wait_for  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

guard_driver_python()
url, outdir, tag = sys.argv[1:4]
label = sys.argv[4] if len(sys.argv) > 4 else tag
run = Run(tag, outdir)


SEEN_TOASTS = []


def watch(page, cond, timeout=8.0):
    """Poll until cond() or timeout, collecting every toast text seen meanwhile."""
    end = time.time() + timeout
    while time.time() < end:
        for t in page.query_selector_all("[data-sonner-toast]"):
            try:
                txt = t.inner_text().replace("\n", " | ")[:400]
            except Exception:  # noqa: BLE001
                continue
            if txt and txt not in SEEN_TOASTS:
                SEEN_TOASTS.append(txt)
                print(f"--- TOAST: {txt}", flush=True)
        try:
            if cond():
                return True
        except Exception:  # noqa: BLE001
            pass
        time.sleep(0.2)
    return False


def snap(page, step):
    time.sleep(1.5)
    d = {
        "status": page.inner_text("#status"),
        "rows": [r.inner_text().replace("\n", " | ") for r in page.query_selector_all(".post")],
        "ages": [a.inner_text() for a in page.query_selector_all(".age")],
        "toasts_seen_so_far": list(SEEN_TOASTS),
    }
    run.notes[step] = d
    run.shot(page, step)
    print(f"--- {step}: {json.dumps(d)}", flush=True)
    return d


with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    ctx = b.new_context(timezone_id="America/New_York", viewport={"width": 1100, "height": 800})
    page = ctx.new_page()
    run.attach(page)
    dialogs = run.notes.setdefault("dialogs", [])

    def on_dialog(dlg):
        dialogs.append({"t": run._t(), "type": dlg.type, "msg": dlg.message})
        print(f"--- DIALOG {dlg.type}: {dlg.message!r}", flush=True)
        dlg.accept()

    page.on("dialog", on_dialog)
    page.goto(url)
    page.wait_for_selector("#status", timeout=60000)
    watch(page, lambda: page.inner_text("#status") != "idle", 15)
    watch(page, lambda: False, 2)
    d0 = snap(page, "01_initial_load")
    run.check("initial on_load handler completed", d0["status"].startswith("loaded"), d0["status"])
    page.click("#add_aware")
    watch(page, lambda: page.inner_text("#status") != d0["status"], 8)
    watch(page, lambda: False, 2)
    d1 = snap(page, "02_add_aware")
    run.check("add aware persisted a row and reloaded the list", d1["status"].startswith("loaded") and len(d1["rows"]) == len(d0["rows"]) + 1, d1)
    page.click("#add_naive")
    watch(page, lambda: page.inner_text("#status") != d1["status"], 8)
    watch(page, lambda: False, 2)
    d2 = snap(page, "03_add_naive")
    run.check("add naive persisted a row and reloaded the list", d2["status"].startswith("loaded") and len(d2["rows"]) == len(d1["rows"]) + 1, d2)
    page.reload()
    page.wait_for_selector("#status", timeout=60000)
    watch(page, lambda: page.inner_text("#status") != "idle", 15)
    watch(page, lambda: False, 2)
    d3 = snap(page, "04_after_reload")
    run.check("on_load after reload completed", d3["status"].startswith("loaded"), d3)
    run.check("no error dialogs", not dialogs, dialogs)
    run.notes["toasts"] = SEEN_TOASTS
    run.check("no error toasts", not SEEN_TOASTS, SEEN_TOASTS)
    run.notes["error_frames"] = [f["payload"][:600] for f in run.ws if f["dir"] == "in" and ("rror" in f["payload"] or "TypeError" in f["payload"])]
    run.notes["created_at_frames"] = [f["payload"][:900] for f in run.ws if f["dir"] == "in" and "created_at" in f["payload"]][:3]
    b.close()
sys.exit(run.finish())
