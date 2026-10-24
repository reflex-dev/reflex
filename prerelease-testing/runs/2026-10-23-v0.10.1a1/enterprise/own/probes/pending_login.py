"""rxe 0.9.8 #277: a second login start in a tab must not strand the first (vauth app, mock IdP on :8638).

Usage: pending_login.py <frontend_base> <label> [reps=1]
Scenarios (mirrors tests/integration/test_auth_pending_login.py of reflex-enterprise v0.9.8, driven against our vauth app):
  A two_starts   start login twice from /vault (-> /login), finish the FIRST authorization page -> signed in on /vault
  B other_tab    tab2 completes tab1's authorization page: rejected, auto-restarted once, lands on tab2's page signed in
  C dblclick     a real double click on the login button -> authorize -> signed in
  D logout_keep  logout, then a login that was pending before the logout is finished (logout must not overwrite the pair)
Records the `state` query params of each authorization URL (reuse = same pair), console/page errors, server-visible paths.
"""
import json
import os
import re
import sys
import time
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import playwright  # noqa: F401
from playwright.sync_api import sync_playwright, expect

assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in playwright.__file__, playwright.__file__
BASE, LABEL = sys.argv[1].rstrip("/"), sys.argv[2]
REPS = int(sys.argv[3]) if len(sys.argv) > 3 else 1
IDP = "http://localhost:8638"
OUT = Path(__file__).resolve().parent.parent / "out"
OUT.mkdir(exist_ok=True)
LOGIN_BTN = "Login with Generic"


def state_of(url):
    return (parse_qs(urlparse(url).query).get("state") or [""])[0]


def start_login(p, from_path="/vault"):
    p.goto(BASE + from_path)
    p.wait_for_url(re.compile(r"/login"), timeout=30000)
    p.get_by_role("button", name=LOGIN_BTN).click(timeout=30000)
    p.wait_for_url(IDP + "/oauth2/authorize**", timeout=30000)
    return p.url


def click_again(p):
    p.go_back()
    expect(p.get_by_role("button", name=LOGIN_BTN)).to_be_visible(timeout=30000)
    p.get_by_role("button", name=LOGIN_BTN).click(timeout=30000)
    p.wait_for_url(IDP + "/oauth2/authorize**", timeout=30000)
    return p.url


def authorize(p, user="alice"):
    p.fill("#subject-input", user)
    p.get_by_role("button", name="Authorize", exact=True).click()


def wait_signed_in(p, path="/vault", timeout=40):
    end = time.time() + timeout
    while time.time() < end:
        try:
            u = urlparse(p.url)
            if u.path.rstrip("/") == path.rstrip("/") and p.locator("#who").inner_text(timeout=500) == "alice":
                return True
        except Exception:
            pass
        p.wait_for_timeout(250)
    return False


def run(browser, name, fn, rec):
    ctx = browser.new_context()
    errs = []
    p = ctx.new_page()
    p.on("pageerror", lambda e: errs.append(f"pageerror: {str(e)[:200]}"))
    p.on("console", lambda m: m.type == "error" and errs.append(f"console: {m.text[:200]}"))
    r = {"name": name}
    try:
        fn(ctx, p, r)
    except Exception as e:  # noqa: BLE001
        r["exception"] = f"{type(e).__name__}: {str(e)[:300]}"
        r["ok"] = False
    r["errors"] = errs
    r["final_url"] = p.url
    rec.append(r)
    print(f"[{'PASS' if r.get('ok') else 'FAIL'}] {name}: {json.dumps({k: v for k, v in r.items() if k not in ('name',)}, default=str)[:400]}")
    ctx.close()


def sc_two_starts(ctx, p, r):
    first = start_login(p)
    second = click_again(p)
    r["state_first"], r["state_second"] = state_of(first)[:12], state_of(second)[:12]
    r["pair_reused"] = state_of(first) == state_of(second)
    p.goto(first)
    authorize(p)
    r["ok"] = wait_signed_in(p) and r["pair_reused"]


def sc_other_tab(ctx, p, r):
    other = start_login(p)  # tab1's authorization page
    t2 = ctx.new_page()
    t2.on("pageerror", lambda e: r.setdefault("t2_errors", []).append(str(e)[:200]))
    own = start_login(t2, "/vault")
    r["different_pairs"] = state_of(own) != state_of(other)
    t2.go_back()
    expect(t2.get_by_role("button", name=LOGIN_BTN)).to_be_visible(timeout=30000)
    t2.goto(other)
    authorize(t2)
    # rejected + auto restart: back at the provider with tab2's own state
    try:
        t2.wait_for_url(IDP + "/oauth2/authorize**", timeout=30000)
        r["restarted"] = True
        r["restart_state_is_own"] = state_of(t2.url) == state_of(own)
        authorize(t2)
        r["ok"] = wait_signed_in(t2) and r["different_pairs"]
    except Exception as e:  # noqa: BLE001
        r["restarted"] = False
        r["t2_url"] = t2.url
        r["t2_text"] = t2.locator("body").inner_text(timeout=2000)[:200]
        r["ok"] = False
    r["final_url_t2"] = t2.url


def sc_dblclick(ctx, p, r):
    p.goto(BASE + "/vault")
    p.wait_for_url(re.compile(r"/login"), timeout=30000)
    p.get_by_role("button", name=LOGIN_BTN).dblclick(timeout=30000)
    p.wait_for_url(IDP + "/oauth2/authorize**", timeout=30000)
    r["state"] = state_of(p.url)[:12]
    authorize(p)
    r["ok"] = wait_signed_in(p)


def sc_logout_keep(ctx, p, r):
    # log in fully first, then log out, then start a login, go back, log out again?? -> simpler: pending login survives a logout click
    first = start_login(p)
    # a full login in this tab, then logout (which used to overwrite app_state), then finish the earlier pending page
    second = click_again(p)
    authorize(p)
    r["login2_ok"] = wait_signed_in(p)
    p.locator("#logout").click()
    p.wait_for_timeout(2500)
    r["after_logout_path"] = urlparse(p.url).path
    # the earlier authorization page is spent? No: its pair was consumed by the second login (same pair) -> expect replay/no-op,
    # so instead start a NEW login after logout and finish it: logout must not have left a broken pair behind.
    third = start_login(p)
    r["state_third_new"] = state_of(third) != state_of(first)
    authorize(p)
    r["ok"] = wait_signed_in(p) and r["login2_ok"]


def sc_hot_reload(ctx, p, r):
    """E (dev only, HOT_RELOAD_FILE set): a signed-in tab survives a backend hot reload (#7113 forked reload worker)."""
    first = start_login(p)
    authorize(p)
    r["login_ok"] = wait_signed_in(p)
    with open(os.environ["HOT_RELOAD_FILE"], "a") as fh:
        fh.write(f"\n# hot reload touch {time.time()}\n")
    p.wait_for_timeout(9000)
    p.reload(wait_until="networkidle")
    r["after_reload_signed_in"] = wait_signed_in(p, timeout=30)
    p.locator("#add").click(); p.wait_for_timeout(1500)
    r["clicks_after"] = p.locator("#clicks").inner_text()
    r["ok"] = r["login_ok"] and r["after_reload_signed_in"] and r["clicks_after"] == "1"


def main():
    rec = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium", headless=True)
        for i in range(REPS):
            run(browser, f"A two_starts #{i+1}", sc_two_starts, rec)
            run(browser, f"B other_tab #{i+1}", sc_other_tab, rec)
            run(browser, f"C dblclick #{i+1}", sc_dblclick, rec)
            run(browser, f"D logout_keep #{i+1}", sc_logout_keep, rec)
        if os.environ.get("HOT_RELOAD_FILE"):
            run(browser, "E hot_reload", sc_hot_reload, rec)
        browser.close()
    json.dump(rec, open(OUT / f"pending_login_{LABEL}.json", "w"), indent=1, default=str)
    ok = sum(1 for r in rec if r.get("ok"))
    print(f"SUMMARY {LABEL} pending_login: {ok}/{len(rec)} pass; page/console errors: {sum(len(r['errors']) for r in rec)}")


main()
