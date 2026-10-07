"""Protected client-storage vars across boot / new tab / logout / next user (vauthx app; #7493 hunt).

Usage: storx.py <base> <label> <N>
Per step records: the browser's localStorage `vx_draft` and cookie `vx_ck`, the values shown on the page,
and every write the frontend made to those keys during the step (tab, key, value).
Writes ../logs/<label>-storx.json.
"""

import json
import sys

import playwright  # VENV_GUARD

assert "/scratchpad/envs/driver/" in playwright.__file__, playwright.__file__
from playwright.sync_api import sync_playwright

from hunt import ALL_WRITES_JS, counts
from vdrv import CHROMIUM, IDP, OUT, SHOTS, Tab, login, new_context, pause, wait_for, wait_hydrated

KEYS = ("vx_draft", "vx_ck")


def snap(tab, log, since):
    p = tab.page
    return {
        "path": tab.path(),
        "who": tab.text("#who", 800),
        "shown_draft": tab.text("#draft", 800),
        "shown_ck": tab.text("#ck", 800),
        "ls_draft": p.evaluate("() => localStorage.getItem('vx_draft')"),
        "cookie_ck": next((c.split("=", 1)[1] for c in p.evaluate("() => document.cookie").split("; ") if c.startswith("vx_ck=")), None),
        "writes": [
            (e.get("tab"), e.get("key"), e.get("value"))
            for e in log[since:]
            if e.get("kind") in ("w_set", "w_rm", "w_cookie") and any(k in (e.get("key") or "") for k in KEYS)
        ],
        **{k: v for k, v in counts(log, since).items() if k.startswith(("cookie_sync", "sent:reconcile", "sent:update_vars", "sent:hydrate"))},
    }


def run(browser, base, label, rep):
    log = []
    ctx = new_context(browser, log)
    ctx.add_init_script(ALL_WRITES_JS)
    r = {"rep": rep, "steps": {}}
    try:
        t1 = Tab(ctx, "tab1", log)
        r["alice_login"] = login(t1, base, "alice")
        pause(2)
        i = len(log)
        t1.page.click("#set-draft")
        wait_for(lambda: t1.text("#draft", 500) == "draft-of-alice", 10)
        pause(2)
        r["steps"]["1 alice set_draft"] = snap(t1, log, i)
        i = len(log)
        t1.page.reload()
        wait_hydrated(t1)
        pause(4)
        r["steps"]["2 alice reload /vault"] = snap(t1, log, i)
        i = len(log)
        t2 = Tab(ctx, "tab2", log)
        t2.page.goto(base + "/vault")
        pause(6)
        r["steps"]["3 alice new tab /vault"] = snap(t2, log, i)
        t2.page.close()
        # boot of a PUBLIC page (no client navigation) in a new tab while signed in
        i = len(log)
        t3 = Tab(ctx, "tab3", log)
        t3.page.goto(base + "/")
        pause(6)
        r["steps"]["3b alice new tab / (public boot)"] = snap(t3, log, i)
        t3.page.close()
        vdrv_pump(t1)
        # client-side navigation between two PROTECTED pages (vauthx >= /vault2 variant)
        if t1.page.locator("#to-vault2").count():
            i = len(log)
            t1.page.click("#to-vault2")
            pause(4)
            r["steps"]["3c alice client nav /vault -> /vault2 (protected)"] = snap(t1, log, i)
            i = len(log)
            t1.page.click("#to-vault")
            pause(4)
            r["steps"]["3d alice client nav /vault2 -> /vault"] = snap(t1, log, i)
        i = len(log)
        t1.page.click("#to-home")
        pause(4)
        r["steps"]["4 alice client nav to /"] = snap(t1, log, i)
        i = len(log)
        t1.page.reload()
        wait_hydrated(t1)
        pause(4)
        r["steps"]["5 alice reload / (public)"] = snap(t1, log, i)
        t1.page.goto(base + "/vault")
        pause(3)
        i = len(log)
        t1.page.click("#logout")
        t1.page.wait_for_url(IDP + "/oauth2/end_session**", timeout=30000)
        t1.page.get_by_role("button", name="End session").click()
        wait_for(lambda: t1.page.url.startswith(base) and t1.path() == "/", 30)
        pause(4)
        r["steps"]["6 after logout on /"] = snap(t1, log, i)
        i = len(log)
        t1.page.reload()
        wait_hydrated(t1)
        pause(4)
        r["steps"]["7 anonymous reload /"] = snap(t1, log, i)
        i = len(log)
        r["bob_login"] = login(t1, base, "bob")
        pause(4)
        r["steps"]["8 bob logged in /vault"] = snap(t1, log, i)
        t1.page.screenshot(path=str(SHOTS / f"{label}-storx-{rep}.png"))
    except Exception as e:
        r["error"] = repr(e)[:300]
    finally:
        r["console_errors"] = [e for e in log if e.get("kind") == "pageerror" or (e.get("kind") == "console" and e.get("type") == "error" and "TUNNEL" not in (e.get("text") or ""))][:20]
        r["_full_log"] = log
        ctx.close()
    return r


def vdrv_pump(tab):
    import vdrv

    vdrv.PUMP["page"] = tab.page


def main():
    base, label, n = sys.argv[1].rstrip("/"), sys.argv[2], int(sys.argv[3])
    OUT.mkdir(exist_ok=True)
    SHOTS.mkdir(exist_ok=True)
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        try:
            for rep in range(n):
                res = run(browser, base, label, rep)
                results.append(res)
                print(f"== rep {rep} alice_login={res.get('alice_login')} bob_login={res.get('bob_login')} error={res.get('error')}")
                for name, s in res["steps"].items():
                    print(f"  {name}: {json.dumps(s, default=str)}")
                for e in res["console_errors"]:
                    print("  console:", e.get("tab"), (e.get("text") or "")[:160])
        finally:
            browser.close()
    out = OUT / f"{label}-storx.json"
    out.write_text(json.dumps(results, indent=1, default=str))
    print("wrote", out)


if __name__ == "__main__":
    main()
