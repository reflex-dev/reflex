"""Root-cause probe for the cross-tab logout regression: does a BOOT hydration that carries a stale
`latest_access_token_hash_ls` (localStorage, sync=True) trigger the enterprise reconciliation
(HTTPCookie.sync -> reconcile_tokens_after_sync) the way a normal client-storage update does?

Usage: stale_hash_probe.py <frontend_base> <label> [N]
Cases (each in a fresh browser context):
  anon_boot      anonymous tab on "/", write a bogus hash into localStorage, reload "/".
                 Correct: the backend notices hash != its own ("") and rewrites the browser value to "".
  loggedin_boot  Alice logged in on /dashboard, overwrite the hash with a bogus value, reload.
                 Correct: cookie sync + reconcile re-asserts Alice's real hash in localStorage.
  live_update    control: anonymous tab on "/", a SECOND tab writes the bogus hash (storage event,
                 no reload) -> update_vars_internal path. Correct: tab1 resets it to "".
"""

import json
import re
import sys
import time
import traceback

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import CHROMIUM, W, attach, login  # noqa: E402
from instrument import Recorder  # noqa: E402

BASE = sys.argv[1].rstrip("/")


def U(path):
    """URL matcher tolerant of the trailing slash prod static serving adds (307 /dashboard -> /dashboard/)."""
    return re.compile(re.escape(BASE + path) + r"/?(\?.*)?$")
LABEL = sys.argv[2]
N = int(sys.argv[3]) if len(sys.argv) > 3 else 3
T = 45_000
KEY = "reflex___state____state.reflex_enterprise___auth___oidc___state____generic_oidc_auth_state.latest_access_token_hash_ls_rx_state_"
BOGUS = "deadbeef" * 8


def ls(page):
    return page.evaluate("k => localStorage.getItem(k)", KEY)


def summarize(rec, since):
    ev = [e for e in rec.events if e["t"] >= since]
    return {
        "reconcile_sent": sum(1 for e in ev if e["kind"] == "ws.sent" and "reconcile_tokens_after_sync" in json.dumps(e.get("v"))),
        "cookie_syncs": sum(1 for e in ev if e["kind"] == "cookie-sync"),
        "hash_ls_writes": [e.get("v", "")[:12] for e in ev if e["kind"] == "ls.set" and e.get("k") == KEY],
        "sent": [e["v"]["name"].rsplit(".", 1)[-1] if isinstance(e.get("v"), dict) and e["v"].get("name") else str(e.get("v"))[:60] for e in ev if e["kind"] == "ws.sent"],
    }


def case_anon_boot(browser, obs):
    ctx = browser.new_context()
    rec = Recorder(ctx)
    page = ctx.new_page()
    page.set_default_timeout(T)
    rec.name(page, "tab1")
    attach(page, obs.setdefault("diag", {}))
    page.goto(BASE + "/")
    expect(page.locator("#anon")).to_be_visible(timeout=T)
    page.wait_for_timeout(1500)
    obs["ls_initial"] = ls(page)
    page.evaluate("([k, v]) => localStorage.setItem(k, v)", [KEY, BOGUS])
    t = rec._now()
    page.reload()
    expect(page.locator("#anon")).to_be_visible(timeout=T)
    page.wait_for_timeout(5000)
    obs["ls_after_boot"] = ls(page)
    obs.update(summarize(rec, t))
    obs["corrected"] = obs["ls_after_boot"] in ("", None)
    ctx.close()


def case_loggedin_boot(browser, obs):
    ctx = browser.new_context()
    rec = Recorder(ctx)
    page = ctx.new_page()
    page.set_default_timeout(T)
    rec.name(page, "tab1")
    attach(page, obs.setdefault("diag", {}))
    page.goto(BASE + "/dashboard")
    page.wait_for_url(re.compile("/login"), timeout=T)
    login(page, "alice")
    page.wait_for_url(U("/dashboard"), timeout=T)
    expect(page.locator("#user-name")).to_have_text("Alice Admin", timeout=T)
    page.wait_for_timeout(1500)
    real = ls(page)
    obs["ls_real_prefix"] = (real or "")[:12]
    page.evaluate("([k, v]) => localStorage.setItem(k, v)", [KEY, BOGUS])
    t = rec._now()
    page.reload()
    expect(page.locator("#user-name")).to_have_text("Alice Admin", timeout=T)
    page.wait_for_timeout(5000)
    after = ls(page)
    obs["ls_after_boot_prefix"] = (after or "")[:12]
    obs.update(summarize(rec, t))
    obs["corrected"] = after == real
    ctx.close()


def case_live_update(browser, obs):
    ctx = browser.new_context()
    rec = Recorder(ctx)
    page = ctx.new_page()
    page.set_default_timeout(T)
    rec.name(page, "tab1")
    attach(page, obs.setdefault("diag", {}))
    page.goto(BASE + "/")
    expect(page.locator("#anon")).to_be_visible(timeout=T)
    page.wait_for_timeout(1500)
    p2 = ctx.new_page()
    rec.name(p2, "tab2")
    p2.goto("about:blank")
    p2.goto(BASE + "/favicon.ico")  # same origin, no reflex app -> plain storage write
    t = rec._now()
    p2.evaluate("([k, v]) => localStorage.setItem(k, v)", [KEY, BOGUS])
    page.wait_for_timeout(5000)
    obs["ls_after"] = ls(page)
    obs.update(summarize(rec, t))
    obs["corrected"] = obs["ls_after"] in ("", None)
    ctx.close()


def main():
    res = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        for i in range(N):
            for c in ("anon_boot", "loggedin_boot", "live_update"):
                obs = {"case": c, "i": i}
                try:
                    globals()["case_" + c](browser, obs)
                except Exception:
                    obs["error"] = traceback.format_exc()[-1200:]
                res.append(obs)
                slim = {k: v for k, v in obs.items() if k != "diag"}
                slim["console_errors"] = [x["text"][:120] for x in obs.get("diag", {}).get("console", []) if x["type"] == "error" and "TUNNEL" not in x["text"]][:3]
                print(json.dumps(slim, default=str)[:900], flush=True)
        browser.close()
    (W / "logs" / f"stalehash-{LABEL}.json").write_text(json.dumps(res, indent=2, default=str))
    tally = {}
    for r in res:
        tally.setdefault(r["case"], [0, 0])
        tally[r["case"]][0] += bool(r.get("corrected"))
        tally[r["case"]][1] += 1
    print("CORRECTED", json.dumps(tally))


main()
