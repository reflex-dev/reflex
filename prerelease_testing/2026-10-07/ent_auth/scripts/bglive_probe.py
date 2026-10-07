"""Protected substate + background task: are deltas delivered live after login / client-side navigation?

Usage: bglive_probe.py <frontend_base> <label>
Case nav:    login on /dashboard, client-side nav to /list, record item-count/progress, click fill, sample 5 s.
Case direct: login landing on /list, click fill, sample 5 s.
Case navback: login on /list, nav to "/" (public) and back to /list via links, click fill, sample.
Records ws frames that mention list_worker / list_base.
"""

import json
import re
import sys
import time
import traceback

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import CHROMIUM, W, attach, login  # noqa: E402

BASE = sys.argv[1].rstrip("/")
LABEL = sys.argv[2]
CASES = sys.argv[3].split(",") if len(sys.argv) > 3 else ["nav", "direct", "navback"]
T = 45_000


def sample(page, secs=5.0):
    out = []
    t0 = time.time()
    while time.time() - t0 < secs:
        out.append([round(time.time() - t0, 1), page.locator("#progress").inner_text(), page.locator("#item-count").inner_text(), page.locator(".item").count()])
        page.wait_for_timeout(500)
    return out


def run(browser, case):
    obs = {"case": case}
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(T)
    attach(page, obs)
    frames = []

    def on_ws(ws):
        ws.on("framereceived", lambda p: frames.append([round(time.time(), 2), p[:300]]) if isinstance(p, str) and ("list_worker" in p or "list_base" in p) else None)
    page.on("websocket", on_ws)
    start = "/dashboard" if case == "nav" else "/list"
    page.goto(BASE + start)
    page.wait_for_url(re.compile("/login"), timeout=T)
    login(page, "alice")
    page.wait_for_url(BASE + start, timeout=T)
    if case == "nav":
        expect(page.locator("#user-name")).to_have_text("Alice Admin", timeout=T)
        page.locator("#nav-list").click()
        page.wait_for_url(BASE + "/list", timeout=T)
    if case == "navback":
        expect(page.locator("#list-user")).to_have_text("alice", timeout=T)
        page.locator("#nav-public").click()
        page.wait_for_url(BASE + "/", timeout=T)
        expect(page.locator("#signed-in")).to_contain_text("alice", timeout=T)
        page.locator("#nav-list").click()
        page.wait_for_url(BASE + "/list", timeout=T)
    expect(page.locator("#list-user")).to_have_text("alice", timeout=T)
    page.wait_for_timeout(2000)
    obs["before_fill"] = {"progress": page.locator("#progress").inner_text(), "item_count": page.locator("#item-count").inner_text()}
    n_frames_before = len(frames)
    page.locator("#fill").click()
    obs["samples"] = sample(page, 5)
    obs["live_ok"] = obs["samples"][-1][1] == "5" and obs["samples"][-1][3] == 5
    obs["list_frames_during_fill"] = len(frames) - n_frames_before
    obs["frames_tail"] = frames[-3:]
    page.reload()
    expect(page.locator("#list-user")).to_have_text("alice", timeout=T)
    page.wait_for_timeout(2000)
    obs["after_reload"] = {"progress": page.locator("#progress").inner_text(), "item_count": page.locator("#item-count").inner_text(), "items": page.locator(".item").count()}
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-bglive-{case}.png"))
    ctx.close()
    return obs


def main():
    res = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        for c in CASES:
            try:
                o = run(browser, c)
            except Exception:
                o = {"case": c, "error": traceback.format_exc()[-1500:]}
            res.append(o)
            slim = {k: v for k, v in o.items() if k not in ("console", "failed_requests", "http_errors", "ws_frames", "frames_tail")}
            slim["console_errors"] = [x for x in o.get("console", []) if x["type"] == "error"][:4]
            print(json.dumps(slim, default=str)[:2500], flush=True)
        browser.close()
    (W / "logs" / f"bglive-{LABEL}.json").write_text(json.dumps(res, indent=2, default=str))


main()
