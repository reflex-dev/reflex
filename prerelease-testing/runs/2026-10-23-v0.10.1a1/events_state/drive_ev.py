"""Drive evapp: EVT-06 filtered var, #7415 on_load cancellation, #7585 expired-session background task, #7500 UI.

Usage: drive_ev.py <base_url> <out.json> <ev_log.jsonl> [scenarios: filtered,onload,expire,dictviews]
"""

import json
import re
import sys
import time

from playwright.sync_api import sync_playwright

CHROMIUM = "/opt/pw-browsers/chromium"
BENIGN = re.compile(r"Hey developer|HydrateFallback|\[vite\]|React DevTools|favicon|Disconnect websocket on page navigation")


def read_log(path, n0):
    try:
        lines = open(path).read().splitlines()
    except FileNotFoundError:
        return []
    return [json.loads(x) for x in lines[n0:]]


def log_len(path):
    try:
        return len(open(path).read().splitlines())
    except FileNotFoundError:
        return 0


def txt(page, sel):
    return page.locator(sel).inner_text()


def wait_text(page, sel, pred, timeout=10):
    end = time.time() + timeout
    while time.time() < end:
        v = txt(page, sel)
        if pred(v):
            return v
        page.wait_for_timeout(100)
    return txt(page, sel)


def main():
    base, out, logpath = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
    scen = sys.argv[4].split(",") if len(sys.argv) > 4 else ["filtered", "onload", "expire", "dictviews", "foreach_arg"]
    rep = {"base": base, "console": [], "errors": [], "scenarios": {}}
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)

        def new_page():
            ctx = browser.new_context()
            page = ctx.new_page()
            page.on("console", lambda m: rep["console"].append(f"[{m.type}] {m.text}") if not BENIGN.search(m.text) else None)
            page.on("pageerror", lambda e: rep["errors"].append(str(e)))
            return ctx, page

        if "filtered" in scen:
            r = {}
            ctx, page = new_page()
            page.goto(base + "/filtered")
            page.wait_for_selector("#bump")
            page.wait_for_timeout(1500)
            r["initial"] = {"n": txt(page, "#n"), "tick": txt(page, "#tick")}
            page.click("#bump")
            r["after_bump1"] = {"n": wait_text(page, "#n", lambda v: v == "1"), "tick": wait_text(page, "#tick", lambda v: v == "100", 3)}
            page.click("#won")
            wait_text(page, "#withhold", lambda v: v == "true", 3)
            page.click("#bump")
            wait_text(page, "#n", lambda v: v == "2")
            page.wait_for_timeout(800)
            r["after_bump2_withheld"] = {"n": txt(page, "#n"), "tick": txt(page, "#tick")}
            page.click("#woff")
            wait_text(page, "#withhold", lambda v: v == "false", 3)
            r["after_release"] = {"n": txt(page, "#n"), "tick": wait_text(page, "#tick", lambda v: v == "200", 3)}
            page.click("#bump")
            wait_text(page, "#n", lambda v: v == "3")
            r["after_bump3"] = {"n": txt(page, "#n"), "tick": wait_text(page, "#tick", lambda v: v == "300", 3)}
            r["verdict"] = "PASS" if r["after_bump3"]["tick"] == "300" and r["after_release"]["tick"] == "200" else "FAIL (stale tick after release)"
            ctx.close()
            rep["scenarios"]["filtered"] = r

        if "onload" in scen:
            for variant in ("navigate", "close", "plain_close", "bg_close", "bg_navigate"):
                r = {}
                n0 = log_len(logpath)
                ctx, page = new_page()
                route = "/onload_plain" if variant == "plain_close" else ("/onload_bg" if variant.startswith("bg_") else "/onload")
                page.goto(base + route)
                page.wait_for_selector("#steps", state="attached")
                page.wait_for_timeout(700)
                r["steps_before_leave"] = txt(page, "#steps")
                if variant in ("navigate", "bg_navigate"):
                    page.click("#home")
                    page.wait_for_timeout(300)
                    r["url_after"] = page.url
                else:
                    ctx.close()
                time.sleep(14)
                if variant in ("navigate", "bg_navigate"):
                    ctx.close()
                r["server_log_after_leave"] = read_log(logpath, n0)
                r["slow_load_steps_logged"] = [x.get("step") for x in r["server_log_after_leave"] if x.get("who") in ("slow_load", "plain_slow_load")]
                r["bg_steps_logged"] = [x.get("step") for x in r["server_log_after_leave"] if x.get("who") == "bg_from_load"]
                rep["scenarios"][f"onload_{variant}"] = r

        if "expire" in scen:
            r = {}
            n0 = log_len(logpath)
            ctx, page = new_page()
            page.goto(base + "/expire")
            page.wait_for_selector("#start8")
            r["loads_initial"] = wait_text(page, "#loads", lambda v: v == "1", 5)
            page.click("#setpref")
            r["pref"] = wait_text(page, "#pref", lambda v: v == "chosen", 3)
            page.click("#start2")
            r["short_task"] = {"status": wait_text(page, "#status", lambda v: v == "done", 6), "count": txt(page, "#count")}
            page.wait_for_timeout(500)
            page.click("#start8")
            r["long_started"] = {"status": wait_text(page, "#status", lambda v: v == "started", 3), "count": txt(page, "#count")}
            page.wait_for_timeout(10500)
            r["after_long"] = {"status": txt(page, "#status"), "count": txt(page, "#count"), "loads": txt(page, "#loads"), "pref": txt(page, "#pref"), "url": page.url}
            r["storage_ev_pref"] = page.evaluate("() => window.localStorage.getItem('ev_pref')")
            page.click("#manual")
            page.wait_for_timeout(2500)
            r["after_next_event"] = {"status": txt(page, "#status"), "count": txt(page, "#count"), "loads": txt(page, "#loads"), "pref": txt(page, "#pref"), "url": page.url}
            page.reload()
            page.wait_for_selector("#start8")
            page.wait_for_timeout(2500)
            r["after_reload"] = {"status": txt(page, "#status"), "count": txt(page, "#count"), "loads": txt(page, "#loads"), "pref": txt(page, "#pref")}
            r["server_log"] = read_log(logpath, n0)
            ctx.close()
            rep["scenarios"]["expire"] = r

        if "dictviews" in scen:
            r = {}
            ctx, page = new_page()
            page.goto(base + "/dictviews")
            page.wait_for_selector("#values")
            page.wait_for_timeout(1200)
            r["initial"] = {"summary": txt(page, "#summary"), "d": txt(page, "#d")}
            page.click("#values")
            r["after_values"] = {"summary": wait_text(page, "#summary", lambda v: v == "a=2;b=2", 3), "d": txt(page, "#d")}
            page.click("#items")
            r["after_items"] = {"summary": wait_text(page, "#summary", lambda v: v == "a=3;b=3", 3), "d": txt(page, "#d")}
            page.click("#setitem")
            r["after_setitem"] = {"summary": wait_text(page, "#summary", lambda v: v.startswith("a=4"), 3), "d": txt(page, "#d")}
            r["verdict"] = "PASS" if r["after_values"]["summary"] == "a=2;b=2" and r["after_items"]["summary"] == "a=3;b=3" else "FAIL (UI stale after view mutation)"
            ctx.close()
            rep["scenarios"]["dictviews"] = r
        if "foreach_arg" in scen:
            r = {}
            ctx, page = new_page()
            n_err = len(rep["errors"])
            page.goto(base + "/foreach_arg")
            page.wait_for_timeout(2500)
            r["page_errors"] = rep["errors"][n_err:]
            try:
                page.locator("form").first.locator("button[type=submit]").click(timeout=3000)
                r["got"] = wait_text(page, "#got", lambda v: v != "", 4)
            except Exception as e:  # noqa: BLE001
                r["submit_error"] = str(e)[:200]
            ctx.close()
            rep["scenarios"]["foreach_arg"] = r
        browser.close()
    json.dump(rep, open(out, "w"), indent=1, default=str)
    for k, v in rep["scenarios"].items():
        print(k, json.dumps({kk: vv for kk, vv in v.items() if kk not in ("server_log", "server_log_after_leave")}, default=str)[:900])
    print("console:", rep["console"][:10], "errors:", rep["errors"][:5])


if __name__ == "__main__":
    main()
