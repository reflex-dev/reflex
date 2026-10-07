"""#7493 regression hunt with real packages: boot deltas of a LOGGED-IN session and a many-tab open.

#7493 re-marks client-storage vars dirty after hydrate_and_load so the boot delta carries them again. This driver
measures, per page load, every websocket frame the browser receives in the first BOOT_S seconds, whether the boot
delta carries the package's storage var (and its value), what localStorage holds afterwards, and whether any tab
keeps exchanging frames after boot (storage-sync echo / reconnect storm).

Usage: drive_boot_frames.py <base_url> <out_json> local <server_log_unused>
       drive_boot_frames.py <base_url> <out_json> magic <server_log>   (magic link read from the dev-flow server log)
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.parse

from playwright.sync_api import sync_playwright

BASE, OUT, MODE, LOG = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3], sys.argv[4]
BOOT_S, IDLE_S, NTABS = 4.0, 6.0, 5
SUF = str(int(time.time()))[-6:]
KEY = {"local": "auth_token", "magic": "session_token"}[MODE]
res: dict = {"mode": MODE, "loads": [], "console": [], "page_errors": []}


def attach(page, tag, frames):
    page.on("console", lambda m: m.type in ("error", "warning") and res["console"].append(f"{tag} {m.type}: {m.text[:200]}"))
    page.on("pageerror", lambda e: res["page_errors"].append(f"{tag}: {str(e)[:200]}"))

    def on_ws(ws):
        ws.on("framereceived", lambda p: frames.append(("recv", time.time(), str(p))))
        ws.on("framesent", lambda p: frames.append(("sent", time.time(), str(p))))
        ws.on("close", lambda w: frames.append(("close", time.time(), "")))

    page.on("websocket", on_ws)


def summarize(frames, t0, t1):
    win = [f for f in frames if t0 <= f[1] <= t1]
    deltas = [f[2] for f in win if f[0] == "recv" and '"delta"' in f[2]]
    key_vals = []
    for d in deltas:
        for m in re.finditer(rf'"{KEY}_rx_state_":("(?:[^"\\]|\\.)*")', d):
            key_vals.append(json.loads(m.group(1))[:12] + "...")
    return {"recv": sum(1 for f in win if f[0] == "recv"), "sent": sum(1 for f in win if f[0] == "sent"),
            "closes": sum(1 for f in win if f[0] == "close"), "deltas": len(deltas),
            "storage_key_in_boot_delta": key_vals, "first_delta": deltas[0][:600] if deltas else None,
            "all_frames": [(f[0], round(f[1] - t0, 3), f[2][:900]) for f in win]}


def storage(page):
    return page.evaluate("() => Object.fromEntries(Object.entries(localStorage))")


def login_local(page):
    page.goto(BASE + "/register", wait_until="networkidle")
    page.wait_for_selector("input#username")
    u, pw = f"boot{SUF}", "correct-horse-1"
    for k, v in {"username": u, "password": pw, "confirm_password": pw}.items():
        page.fill(f"input#{k}", v)
    page.get_by_role("button", name="Sign up").click()
    page.wait_for_url(re.compile(r"/login"), timeout=20000)
    page.wait_for_selector("input#username")
    page.fill("input#username", u)
    page.fill("input#password", pw)
    page.get_by_role("button", name="Sign in").click()
    page.wait_for_timeout(2500)
    return "/user-info", f"Username: {u}"


def login_magic(page):
    email = f"boot{SUF}@example.com"
    page.goto(BASE + "/", wait_until="networkidle")
    page.fill("input[name=email]", email)
    page.locator("button[type=submit], button:has-text('Send')").first.click()
    want = email.replace("@", "%40")
    link, deadline = None, time.time() + 25
    while time.time() < deadline and not link:
        m = re.findall(r"(https?://\S*otp=\S+)", open(LOG, errors="replace").read())
        link = next((x for x in reversed(m) if want in x), None)
        time.sleep(0.5)
    assert link, "magic link not found in server log"
    link = re.sub(r"https?://[^/]+", BASE, link.rstrip(".,'\")"))
    page.goto(link, wait_until="networkidle")
    page.wait_for_timeout(3000)
    return "/", email


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    frames: list = []
    page = ctx.new_page()
    attach(page, "t0", frames)
    path, marker = (login_local if MODE == "local" else login_magic)(page)
    res["after_login_storage"] = {k: (v[:12] + "...") for k, v in storage(page).items()}
    # 1) reload of the logged-in tab: boot frames
    for i in range(3):
        t0 = time.time()
        page.goto(BASE + path, wait_until="networkidle")
        page.wait_for_timeout(int(BOOT_S * 1000))
        body = page.locator("body").inner_text()
        res["loads"].append({"what": f"logged-in reload #{i + 1}", "logged_in_visible": marker in body,
                             **summarize(frames, t0, time.time()), "storage_after": sorted(storage(page))})
    # 2) many tabs in the same context
    tabs, tab_frames = [], []
    t0 = time.time()
    for i in range(NTABS):
        fr: list = []
        pg = ctx.new_page()
        attach(pg, f"t{i + 1}", fr)
        pg.goto(BASE + path, wait_until="networkidle")
        tabs.append(pg)
        tab_frames.append(fr)
    for pg in tabs:
        pg.wait_for_timeout(500)
    t_boot = time.time()
    time.sleep(BOOT_S)
    t_idle0 = time.time()
    time.sleep(IDLE_S)
    t_end = time.time()
    res["tabs"] = []
    for i, (pg, fr) in enumerate(zip(tabs, tab_frames)):
        body = pg.locator("body").inner_text()
        res["tabs"].append({"tab": i + 1, "logged_in_visible": marker in body,
                            "boot": summarize(fr, t0, t_idle0), "idle": summarize(fr, t_idle0, t_end)})
    res["tab0_during_tabs"] = summarize(frames, t0, t_end)
    res["final_storage_keys"] = sorted(storage(page))
    b.close()
json.dump(res, open(OUT, "w"), indent=1)
print(json.dumps({k: v for k, v in res.items() if k != "tabs"}, indent=1)[:4000])
for t in res["tabs"]:
    print("TAB", t["tab"], "logged_in", t["logged_in_visible"], "boot", {k: t["boot"][k] for k in ("recv", "sent", "closes", "deltas", "storage_key_in_boot_delta")},
          "idle", {k: t["idle"][k] for k in ("recv", "sent", "closes", "deltas")})
