"""Dev-mode hot reload while a tab is open (memory state manager): does the UI resync with the backend?

Usage: hmr_desync.py <base_url> <run_app_file> <out_json>
Edits a compiled default in the RUN copy of the app (not the canonical source) and restores it after.
"""

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from hydcommon import CHROMIUM, Recorder, summarize_frames, text, wait_hydrated, wait_text  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

base, app_file, out = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
orig = app_file.read_text()
OLD = 'bg_status: str = "idle"'
NEW = 'bg_status: str = "idle-edited"'
assert OLD in orig
r: dict = {}
rec = Recorder()
try:
    with sync_playwright() as pw:
        b = pw.chromium.launch(executable_path=CHROMIUM)
        ctx = b.new_context()
        p = ctx.new_page()
        rec.attach(p, "hmr")
        p.goto(base + "/bgload")
        wait_hydrated(p)
        wait_text(p, "#bg-status", "done", 10000)
        for _ in range(3):
            p.click("#inc")
        wait_text(p, "#counter", "3")
        origin0 = p.evaluate("performance.timeOrigin")
        p.evaluate("window.__marker = 'still-same-document'")
        r["before"] = {"counter": text(p, "#counter"), "bg": text(p, "#bg-status")}
        n0 = len(rec.ws_frames)
        app_file.write_text(orig.replace(OLD, NEW))
        t0 = time.time()
        # Wait for the backend reload + HMR to settle.
        p.wait_for_timeout(25000)
        r["same_document"] = p.evaluate("window.__marker === 'still-same-document'")
        r["full_reload"] = p.evaluate("performance.timeOrigin") != origin0
        r["after_edit"] = {"counter": text(p, "#counter"), "bg": text(p, "#bg-status"), "hyd": text(p, "#hyd-flag")}
        frames = summarize_frames(rec.ws_frames[n0:], "hmr")
        r["boot_events_after_edit"] = [f for f in frames if f["kind"] == "connect" and f["dir"] == "out"]
        r["frames_after_edit"] = [f for f in frames if f["kind"] not in ("eio",)][:20]
        p.click("#inc")
        p.wait_for_timeout(1500)
        r["after_click"] = {"counter": text(p, "#counter")}
        p.reload()
        wait_hydrated(p)
        p.wait_for_timeout(500)
        r["after_reload"] = {"counter": text(p, "#counter"), "bg": text(p, "#bg-status")}
        r["console"] = [c for c in rec.console if c["type"] in ("error", "warning")][:20]
        r["elapsed"] = round(time.time() - t0, 1)
        b.close()
finally:
    app_file.write_text(orig)
out.write_text(json.dumps(r, indent=1, default=str))
print(json.dumps({k: v for k, v in r.items() if k not in ("frames_after_edit", "console")}, default=str, indent=1)[:4000])
