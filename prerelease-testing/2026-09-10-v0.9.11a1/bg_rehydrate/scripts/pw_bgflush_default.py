"""#6995 with the DEFAULT backend exception handler (server started with BGFLUSH_DEFAULT_HANDLER=1):
click the raising no-context bg handler and the flush-fails variant; verify the uncached var still refreshes,
the default handler's toast appears, and (via --log) the server log has the tracebacks but no
'Task exception was never retrieved'.

Usage: pw_bgflush_default.py --url http://localhost:3220 --api http://localhost:8220 --log logs/x.log --out logs/pw_x --shots shots/x
"""
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from playwright.sync_api import sync_playwright  # noqa: E402
from pwlib import RESULTS, Capture, dump, http_json, launch, rec, snapshot, wait_text  # noqa: E402

IDS = ["beat", "count", "note", "where"]


def num(t):
    return int(t.split("=", 1)[1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True); ap.add_argument("--api", required=True)
    ap.add_argument("--log", required=True); ap.add_argument("--out", required=True); ap.add_argument("--shots", required=True)
    args = ap.parse_args()
    out = Path(args.out); out.mkdir(parents=True, exist_ok=True)
    shots = Path(args.shots); shots.mkdir(parents=True, exist_ok=True)
    api = args.api.rstrip("/")
    http_json(f"{api}/api/reset")
    log_start = len(Path(args.log).read_text().splitlines())
    with sync_playwright() as p:
        browser = launch(p)
        page = browser.new_context(viewport={"width": 1100, "height": 800}).new_page()
        cap = Capture(page, "default_handler")
        page.goto(args.url + "/", wait_until="load")
        wait_text(page, "#beat", lambda t: t not in ("beat=0", "<missing>"), 20)
        time.sleep(0.5)
        b = snapshot(page, IDS); fi = len(cap.ws_frames)
        page.click("#b-noctx")
        a_text = wait_text(page, "#beat", lambda t: num(t) > num(b["beat"]), 6)
        time.sleep(1.5)
        a = snapshot(page, IDS); d = cap.deltas(fi)
        toasts = page.locator("[data-sonner-toast]").all_inner_texts()
        rec("bgflush_default.noctx_raise_flushes_delta", "pass" if num(a["beat"]) > num(b["beat"]) else "fail",
            f"before={b} after={a} deltas={len(d)} toasts={toasts}")
        rec("bgflush_default.default_handler_toast", "pass" if any("boom-noctx" in t for t in toasts) else "anomaly",
            f"toasts rendered by the default handler: {toasts}")
        page.screenshot(path=str(shots / "default_noctx.png"))
        fi = len(cap.ws_frames)
        page.click("#b-flushfail"); time.sleep(2.5)
        a2 = snapshot(page, IDS); d2 = cap.deltas(fi)
        toasts2 = page.locator("[data-sonner-toast]").all_inner_texts()
        rec("bgflush_default.flush_fails_variant", "pass" if any("boom-flush-fails" in t for t in toasts2) else "anomaly",
            f"after={a2} deltas={len(d2)} toasts={toasts2}")
        page.screenshot(path=str(shots / "default_flushfail.png"))
        page.click("#b-clearff"); time.sleep(1.0)
        an = cap.anomalies()
        rec("bgflush_default.browser_anomalies", "pass" if not any(an[k] for k in an if k != "label") else "anomaly", str(an))
        dump(out / "results.json", RESULTS); dump(out / "ws_frames.json", cap.ws_frames); dump(out / "console.json", cap.console)
        browser.close()
    time.sleep(1.0)
    new_log = "\n".join(Path(args.log).read_text().splitlines()[log_start:])
    tb = new_log.count("Traceback (most recent call last)")
    never = new_log.count("Task exception was never retrieved")
    flush_err = new_log.count("Error flushing delta")
    boom = len(re.findall(r"RuntimeError: boom-noctx", new_log)); boomff = len(re.findall(r"RuntimeError: boom-flush-fails", new_log))
    rec("bgflush_default.server_log", "pass" if never == 0 and boom >= 1 and boomff >= 1 and flush_err == 1 else "anomaly",
        f"new log lines={len(new_log.splitlines())} tracebacks={tb} 'Task exception was never retrieved'={never} 'Error flushing delta'={flush_err} boom-noctx={boom} boom-flush-fails={boomff}")
    dump(out / "results.json", RESULTS)
    (out / "server_log_excerpt.log").write_text(new_log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
