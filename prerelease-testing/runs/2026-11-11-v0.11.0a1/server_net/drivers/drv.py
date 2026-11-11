"""Playwright driver for the server_net netapp.

usage: drv.py <base_url> <scenario> <out_json> [--shots DIR]
scenarios:
  basic    load /, inc, client nav about/About/items, upload + downloads
  connect  load / only; report whether the websocket connected and count works
  routes   direct loads of mixed-case urls (each a fresh page load)
  big      load /, set window.__NA_BIG, click big, then check reconnect + inc
  block    /block: click the blocking buttons in turn
Every run records console messages, page errors, failed requests, >=400 responses,
websocket opens/closes and frame counts.
"""

import json
import os
import sys
import time
from pathlib import Path

assert "/envs/driver/" in sys.executable, sys.executable

from playwright.sync_api import sync_playwright  # noqa: E402

CHROMIUM = "/opt/pw-browsers/chromium"
base, scenario, out = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
shots = None
if "--shots" in sys.argv:
    shots = Path(sys.argv[sys.argv.index("--shots") + 1])
    shots.mkdir(parents=True, exist_ok=True)
BIG = int(os.environ.get("NA_BIG", "2000000"))

rec = {
    "base": base,
    "scenario": scenario,
    "steps": [],
    "console": [],
    "pageerrors": [],
    "failed": [],
    "bad_status": [],
    "ws": [],
    "downloads": [],
    "requests": [],
}


def step(name, fn):
    t0 = time.time()
    try:
        val = fn()
        rec["steps"].append({"step": name, "ok": True, "val": val, "dt": round(time.time() - t0, 2)})
        return val
    except Exception as e:  # noqa: BLE001
        rec["steps"].append({"step": name, "ok": False, "err": repr(e)[:400], "dt": round(time.time() - t0, 2)})
        return None


def text(page, sel):
    return page.locator(sel).first.inner_text(timeout=5000)


def wait_text(page, sel, needle, timeout=15000):
    page.wait_for_function(
        "([s, n]) => { const e = document.querySelector(s); return e && e.innerText.includes(n); }",
        arg=[sel, needle],
        timeout=timeout,
    )
    return text(page, sel)


def shot(page, name):
    if shots:
        page.screenshot(path=str(shots / f"{name}.png"), full_page=True)


with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context(accept_downloads=True)
    page = ctx.new_page()
    page.on("console", lambda m: rec["console"].append(f"{m.type}: {m.text}"[:600]))
    page.on("pageerror", lambda e: rec["pageerrors"].append(str(e)[:600]))
    page.on(
        "requestfailed",
        lambda r: rec["failed"].append(f"{r.method} {r.url} {r.failure}"[:400]),
    )

    def on_resp(r):
        if r.status >= 400:
            rec["bad_status"].append(f"{r.status} {r.request.method} {r.url}"[:300])
        if "/_event" in r.url or "/_upload" in r.url or "/api" in r.url:
            h = r.headers
            rec["requests"].append({
                "url": r.url[:200],
                "status": r.status,
                "acao": h.get("access-control-allow-origin"),
                "acac": h.get("access-control-allow-credentials"),
            })

    page.on("response", on_resp)

    def on_ws(ws):
        entry = {"url": ws.url[:200], "opened": round(time.time(), 2), "recv": 0, "sent": 0, "closed": None}
        rec["ws"].append(entry)
        ws.on("framereceived", lambda f: entry.__setitem__("recv", entry["recv"] + 1))
        ws.on("framesent", lambda f: entry.__setitem__("sent", entry["sent"] + 1))
        ws.on("close", lambda w: entry.__setitem__("closed", round(time.time(), 2)))
        ws.on("socketerror", lambda e: entry.__setitem__("error", str(e)[:200]))

    page.on("websocket", on_ws)
    page.on("download", lambda d: rec["downloads"].append({"url": d.url[:200], "name": d.suggested_filename}))

    def load(path, needle="index"):
        page.goto(base + path, wait_until="domcontentloaded", timeout=30000)
        return wait_text(page, "#page", needle)

    def inc_ok():
        before = text(page, "#count")
        page.click("#inc")
        n = int(before.split("=")[-1]) + 1
        return wait_text(page, "#count", f"count={n}", timeout=8000)

    if scenario == "connect":
        step("load", lambda: load("/"))
        step("inc", inc_ok)
        step("loads", lambda: text(page, "#loads"))
        shot(page, "connect")
    elif scenario == "basic":
        step("load", lambda: load("/"))
        step("inc", inc_ok)
        step("onload_index", lambda: wait_text(page, "#loads", "index"))
        step("nav_about", lambda: (page.click("#nav-about"), wait_text(page, "#page", "about"), wait_text(page, "#loads", "about"))[2])
        step("nav_About", lambda: (page.click("#nav-About"), wait_text(page, "#page", "about"), page.wait_for_timeout(800), text(page, "#loads"), text(page, "#router_path"))[3:])
        step("nav_item", lambda: (page.click("#nav-item"), wait_text(page, "#item_id", "A1"), text(page, "#router_path"))[1:])
        step("nav_ITEMS", lambda: (page.click("#nav-ITEMS"), page.wait_for_timeout(1500), text(page, "#page"), text(page, "#loads"), text(page, "#router_path"))[2:])
        step("goto_upload", lambda: load("/upload", "upload"))
        tmpf = Path(out).with_suffix(".upload.txt")
        tmpf.write_text("netapp upload payload\n")
        step("upload", lambda: (page.set_input_files("#up input[type=file]", str(tmpf)), page.click("#send"), wait_text(page, "#uploaded", tmpf.name))[2])
        step("dl_data", lambda: (page.click("#dl_data"), page.wait_for_timeout(1500), list(rec["downloads"]))[2])
        step("dl_uploaded", lambda: (page.click("#dl_up"), page.wait_for_timeout(1500), list(rec["downloads"]))[2])
        shot(page, "basic_end")
    elif scenario == "routes":
        for path, needle in [("/about", "about"), ("/About", "about"), ("/ABOUT", "about"), ("/items/A1", "item"), ("/ITEMS/b2", "item"), ("/Items/C3/", "item"), ("/nonexistent", "404")]:
            def one(path=path, needle=needle):
                resp = page.goto(base + path, wait_until="domcontentloaded", timeout=30000)
                st = resp.status if resp else None
                try:
                    wait_text(page, "#page", needle, timeout=10000)
                    pg = text(page, "#page")
                except Exception:  # noqa: BLE001
                    pg = page.inner_text("body")[:120]
                page.wait_for_timeout(1000)
                vals = {}
                for sel in ("#loads", "#router_path", "#path_seen", "#item_id"):
                    try:
                        vals[sel] = page.locator(sel).first.inner_text(timeout=500)
                    except Exception:  # noqa: BLE001
                        pass
                return {"http": st, "page": pg, **vals, "url": page.url}
            step(f"direct {path}", one)
        if os.environ.get("NA_CASE_DUP"):
            for path in ["/Foo", "/foo", "/FOO"]:
                def one(path=path):
                    resp = page.goto(base + path, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_timeout(2000)
                    return {"http": resp.status if resp else None, "body": page.inner_text("body")[:80], "loads": page.evaluate("() => document.querySelector('#loads')?.innerText")}
                step(f"dup {path}", one)
    elif scenario == "big":
        step("load", lambda: load("/"))
        step("inc", inc_ok)
        page.evaluate(f"window.__NA_BIG = {BIG}")
        step("click_big", lambda: page.click("#big"))
        page.wait_for_timeout(int(os.environ.get("NA_BIG_WAIT", "6000")))
        step("big_len", lambda: text(page, "#big_len"))
        step("inc_after_big", inc_ok)
        step("small_after", lambda: (page.evaluate("window.__NA_BIG = 10"), page.click("#big"), wait_text(page, "#big_len", "big_len=10", 15000))[2])
        shot(page, "big_end")
    elif scenario == "bigstorage":
        step("load", lambda: load("/"))
        step("inc", inc_ok)
        page.evaluate(f"localStorage.setItem('na_big', 'y'.repeat({BIG}))")
        n0 = len(rec["requests"]) ; ws0 = len(rec["ws"])
        step("reload", lambda: (page.reload(wait_until="domcontentloaded"), wait_text(page, "#page", "index"))[1])
        page.wait_for_timeout(int(os.environ.get("NA_BIG_WAIT", "20000")))
        rec["after_reload"] = {"event_requests": len(rec["requests"]) - n0, "ws_opens": len(rec["ws"]) - ws0,
                               "statuses": sorted({r["status"] for r in rec["requests"][n0:]})}
        step("after_reload", lambda: rec["after_reload"])
        step("count_after", lambda: text(page, "#count"))
        step("stored_len", lambda: text(page, "#stored_len"))
        step("inc_after", inc_ok)
        shot(page, "bigstorage")
        page.evaluate("localStorage.removeItem('na_big')")
        step("reload_clean", lambda: (page.reload(wait_until="domcontentloaded"), page.wait_for_timeout(3000), inc_ok())[2])
    elif scenario == "block":
        step("load", lambda: load("/block", "block"))
        for b in os.environ.get("NA_BLOCK_BUTTONS", "short_block,ok_async,block_sync,block_async,cpu_bg").split(","):
            step(b, lambda b=b: (page.click(f"#{b}"), wait_text(page, "#msg", f"{b} done", 20000))[1])
        step("inc", inc_ok)
    page.wait_for_timeout(500)
    browser.close()

Path(out).write_text(json.dumps(rec, indent=1))
ok = sum(s["ok"] for s in rec["steps"])
print(f"{scenario}: {ok}/{len(rec['steps'])} steps ok; ws opens={len(rec['ws'])}; console={len(rec['console'])}; bad_status={len(rec['bad_status'])}; failed={len(rec['failed'])}")
for s in rec["steps"]:
    print("  ", "OK " if s["ok"] else "ERR", s["step"], json.dumps(s.get("val", s.get("err")), default=str)[:300])
for c in rec["console"][:15]:
    print("   console:", c[:250])
for c in (rec["bad_status"] + rec["failed"] + rec["pageerrors"])[:10]:
    print("   net/err:", c[:250])
