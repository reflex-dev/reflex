"""Cross-tab logout probe (same browser context, two tabs) with storage-write capture.

Usage: xtab_probe.py <frontend_base> <label>
Tab1 logs in on /list, tab2 opens /dashboard, tab2 logs out (IdP end_session).
Records: every localStorage/sessionStorage/cookie write and storage event per tab, ws deltas touching
latest_access_token_hash_ls / is_hydrated, cookie-sync Set-Cookie headers, and whether tab1 is still
authorized afterwards (protected click, reload, fresh tab).
"""

import json
import re
import sys
import time
import traceback

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import CHROMIUM, W, attach, end_session, login, storage_snapshot  # noqa: E402
from instrument import Recorder  # noqa: E402

BASE = sys.argv[1].rstrip("/")


def U(path):
    """URL matcher tolerant of the trailing slash prod static serving adds (307 /dashboard -> /dashboard/)."""
    return re.compile(re.escape(BASE + path) + r"/?(\?.*)?$")
LABEL = sys.argv[2]
T = 45_000
HASH_KEY_PART = "latest_access_token_hash_ls"


def redis_oidc(page, port=8349):
    """Inspect the Redis-pickled OIDC provider state of this tab's client token (names only, never values)."""
    import subprocess
    tok = page.evaluate("() => sessionStorage.getItem('token')") or ""
    if not tok:
        return {"token": None}
    keys = subprocess.run(["redis-cli", "-p", str(port), "--scan", "--pattern", f"{tok}*generic_oidc_auth_state*"], capture_output=True, text=True).stdout.split()
    out = {"token_tail": tok[-6:], "keys": [k.rsplit(".", 1)[-1] for k in keys]}
    for k in keys:
        raw = subprocess.run(["redis-cli", "-p", str(port), "--raw", "get", k], capture_output=True).stdout
        out[k.rsplit(".", 1)[-1]] = {
            "bytes": len(raw),
            "has_http_cookie_access_attr": b"_http_cookie__access_token_data" in raw,
            "has_http_cookie_id_attr": b"_http_cookie__id_token" in raw,
            "has_access_token_value": b"access_token=" in raw,
            "has_dirty_flag": b"_is_dirty" in raw,
        }
    return out


def ls_hash(page):
    snap = storage_snapshot(page)["local"]
    return next((v for k, v in snap.items() if HASH_KEY_PART in k), "<absent>")


N = int(sys.argv[3]) if len(sys.argv) > 3 else 1


def main():
    runs = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        for i in range(N):
            runs.append(run_once(browser, i))
        browser.close()
    if N > 1:
        summary = [{"i": r["i"], "tab1_logged_out": r.get("tab1_after_reload", {}).get("url", "").find("/login") >= 0,
                    "ls_hash_6s_after_logout_empty": r.get("ls_hash_6s_after_logout") == "",
                    "tab1_sync_req_cookies": [e.get("req_cookies_nonempty") for e in r["events"] if e["kind"] == "cookie-sync" and e["tab"] == "tab1" and e["t"] > r.get("t_logout_click", 1e9)][:3]}
                   for r in runs]
        (W / "logs" / f"xtab-{LABEL}-summary.json").write_text(json.dumps(summary, indent=2))
        for s in summary:
            print(json.dumps(s))
        print("TAB1_LOGGED_OUT", sum(s["tab1_logged_out"] for s in summary), "/", len(summary))


def run_once(browser, i):
    obs = {"label": LABEL, "i": i}
    if True:
        ctx = browser.new_context()
        rec = Recorder(ctx)
        try:
            page1 = ctx.new_page()
            page1.set_default_timeout(T)
            rec.name(page1, "tab1")
            attach(page1, obs.setdefault("tab1_diag", {}))
            page1.goto(BASE + "/list")
            page1.wait_for_url(re.compile("/login"), timeout=T)
            login(page1, "alice")
            page1.wait_for_url(U("/list"), timeout=T)
            expect(page1.locator("#list-user")).to_have_text("alice", timeout=T)
            expect(page1.locator("#item-count")).not_to_have_text("-1", timeout=T)
            obs["t_login_done"] = rec._now()
            page2 = ctx.new_page()
            page2.set_default_timeout(T)
            rec.name(page2, "tab2")
            attach(page2, obs.setdefault("tab2_diag", {}))
            page2.goto(BASE + "/dashboard")
            expect(page2.locator("#user-name")).to_have_text("Alice Admin", timeout=T)
            page2.wait_for_timeout(1000)
            obs["ls_hash_before_logout"] = ls_hash(page1)
            obs["redis_tab1_before_logout"] = redis_oidc(page1)
            obs["t_logout_click"] = rec._now()
            page2.locator("#user-logout").click()
            end_session(page2)
            page2.wait_for_url(lambda u: u.split("?")[0] == BASE + "/", timeout=T)
            expect(page2.locator("#anon")).to_be_visible(timeout=T)
            obs["t_tab2_anon"] = rec._now()
            page1.wait_for_timeout(6000)
            obs["ls_hash_6s_after_logout"] = ls_hash(page1)
            obs["redis_tab1_6s_after_logout"] = redis_oidc(page1)
            obs["redis_tab2_6s_after_logout"] = redis_oidc(page2)
            obs["cookies_after_logout"] = sorted(c["name"] for c in ctx.cookies())
            obs["tab1_url_6s"] = page1.url
            obs["tab1_user_6s"] = page1.locator("#list-user").inner_text() if page1.locator("#list-user").count() else None
            if "/list" in page1.url:
                before = page1.locator(".item").count()
                page1.locator("#add").click()
                page1.wait_for_timeout(3000)
                obs["tab1_after_protected_click"] = {"url": page1.url, "items_before": before,
                                                      "items_after": page1.locator(".item").all_inner_texts() if "/list" in page1.url else None}
                page1.reload()
                page1.wait_for_timeout(5000)
                obs["tab1_after_reload"] = {"url": page1.url,
                                            "user": page1.locator("#list-user").inner_text() if page1.locator("#list-user").count() else None,
                                            "items": page1.locator(".item").all_inner_texts() if page1.locator(".item").count() else []}
            page3 = ctx.new_page()
            page3.set_default_timeout(T)
            rec.name(page3, "tab3")
            page3.goto(BASE + "/list")
            page3.wait_for_timeout(6000)
            obs["fresh_tab3_url"] = page3.url
            obs["fresh_tab3_user"] = page3.locator("#list-user").inner_text() if page3.locator("#list-user").count() else None
            page1.screenshot(path=str(W / "screenshots" / f"{LABEL}-xtab-tab1-final.png"))
            obs["passed_run"] = True
        except Exception:
            obs["passed_run"] = False
            obs["traceback"] = traceback.format_exc()[-3000:]
        obs["events"] = rec.events
        ctx.close()
    obs["hash_writes"] = [e for e in obs["events"] if HASH_KEY_PART in str(e.get("k", "")) or (e["kind"] == "ws.recv" and any("latest" in k for k in e.get("v", {})))]
    (W / "logs" / f"xtab-{LABEL}{'-' + str(i) if N > 1 else ''}.json").write_text(json.dumps(obs, indent=2, default=str))
    if N == 1:
        slim = {k: v for k, v in obs.items() if k not in ("events", "tab1_diag", "tab2_diag", "hash_writes")}
        print(json.dumps(slim, indent=1, default=str))
        print("HASH WRITES / WS hash deltas:")
        for e in obs["hash_writes"]:
            print("  ", json.dumps(e, default=str)[:300])
    return obs


main()
