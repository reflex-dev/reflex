"""#7460 x enterprise auth: what the browser's auth storage sees across boot hydrations.

Usage: hydration_token_probe.py <frontend_base> <label> [scenario,...]
Scenarios:
  reload_writes   login, reload protected page x2, public nav + reload, client nav back; flag any write of an
                  EMPTY latest_access_token_hash_ls or a Set-Cookie deleting token cookies while logged in.
  newtab_writes   login in tab1, open tab2 on "/" and tab3 on /dashboard; flag empty-hash writes / storage
                  events reaching tab1 and check tab1 is still authorized afterwards.
  garbage_protected  fresh browser with garbage access/id/refresh token cookies, open /dashboard.
  garbage_public     same cookies, open "/" (public page) and then /dashboard.
  garbage_id_refresh valid login, then overwrite only the id_token cookie with garbage and reload /dashboard
                     (the userinfo computed var must refresh tokens or log out, during hydration).
  garbage_all_after_login valid login, overwrite access+id+refresh with garbage, reload /dashboard.
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
SCEN = sys.argv[3].split(",") if len(sys.argv) > 3 else ["reload_writes", "newtab_writes", "garbage_protected", "garbage_public", "garbage_id_refresh", "garbage_all_after_login"]
T = 45_000
HK = "latest_access_token_hash_ls"
TOKEN_COOKIES = ["_oidc_generic_access_token_data_partitioned", "_oidc_generic_id_token_partitioned",
                 "_oidc_generic_refresh_token_partitioned", "_oidc_generic_granted_scopes_partitioned"]


def cookie_summary(ctx):
    return {c["name"]: {"len": len(c["value"]), "partitionKey": c.get("partitionKey"), "sameSite": c.get("sameSite"),
                        "secure": c.get("secure"), "httpOnly": c.get("httpOnly")}
            for c in ctx.cookies() if c["name"].startswith("_oidc_")}


def violations(rec, since, logged_in_tabs):
    """Empty-hash writes / token-cookie deletions recorded after `since` on tabs that should stay logged in."""
    out = []
    for e in rec.events:
        if e["t"] < since or e.get("tab") not in logged_in_tabs:
            continue
        if e["kind"] in ("ls.set", "storage.event") and HK in str(e.get("k")) and e.get("v") in ("", None):
            out.append(e)
        if e["kind"] == "cookie-sync" and any(c["max_age_0"] and c["name"] in TOKEN_COOKIES[:3] for c in e["set_cookie"]):
            out.append(e)
    return out


def new_page(ctx, rec, obs, name):
    page = ctx.new_page()
    page.set_default_timeout(T)
    rec.name(page, name)
    attach(page, obs.setdefault(name + "_diag", {}))
    return page


def do_login(page, path="/dashboard"):
    page.goto(BASE + path)
    page.wait_for_url(re.compile("/login"), timeout=T)
    login(page, "alice")
    page.wait_for_url(U(path), timeout=T)
    if path == "/dashboard":
        expect(page.locator("#user-name")).to_have_text("Alice Admin", timeout=T)


def scen_reload_writes(browser, obs):
    ctx = browser.new_context()
    rec = Recorder(ctx)
    page = new_page(ctx, rec, obs, "tab1")
    do_login(page)
    expect(page.locator("#async-admin-view")).to_have_text("async-admin-data", timeout=T)
    page.wait_for_timeout(1500)
    t_logged = rec._now()
    obs["cookies_after_login"] = cookie_summary(ctx)
    steps = []
    for i in range(2):
        page.reload()
        expect(page.locator("#user-name")).to_have_text("Alice Admin", timeout=T)
        expect(page.locator("#async-admin-view")).to_have_text("async-admin-data", timeout=T)
        page.wait_for_timeout(1500)
        steps.append({"reload": i, "cookies": sorted(cookie_summary(ctx))})
    page.locator("#nav-public").click()
    page.wait_for_url(BASE + "/", timeout=T)
    expect(page.locator("#signed-in")).to_contain_text("alice", timeout=T)
    page.reload()
    expect(page.locator("#signed-in")).to_contain_text("alice", timeout=T)
    expect(page.locator("#admin-view")).to_have_text("admin-data", timeout=T)
    page.locator("#nav-dashboard").click()
    page.wait_for_url(U("/dashboard"), timeout=T)
    expect(page.locator("#user-name")).to_have_text("Alice Admin", timeout=T)
    page.locator("#reveal").click()
    expect(page.locator("#secret")).to_have_text("revealed-alice", timeout=T)
    page.wait_for_timeout(1500)
    steps.append({"after_public_roundtrip": True, "cookies": sorted(cookie_summary(ctx))})
    obs["steps"] = steps
    obs["violations"] = violations(rec, t_logged, {"tab1"})
    obs["all_hash_writes"] = [e for e in rec.events if HK in str(e.get("k"))]
    obs["sync_responses"] = [e for e in rec.events if e["kind"] == "cookie-sync"]
    obs["ok"] = not obs["violations"] and len(steps[-1]["cookies"]) >= 3
    ctx.close()


def scen_newtab_writes(browser, obs):
    ctx = browser.new_context()
    rec = Recorder(ctx)
    p1 = new_page(ctx, rec, obs, "tab1")
    do_login(p1, "/list")
    expect(p1.locator("#list-user")).to_have_text("alice", timeout=T)
    p1.wait_for_timeout(1500)
    t_logged = rec._now()
    p2 = new_page(ctx, rec, obs, "tab2")
    p2.goto(BASE + "/")
    expect(p2.locator("#signed-in")).to_contain_text("alice", timeout=T)
    p3 = new_page(ctx, rec, obs, "tab3")
    p3.goto(BASE + "/dashboard")
    expect(p3.locator("#user-name")).to_have_text("Alice Admin", timeout=T)
    p3.wait_for_timeout(3000)
    p1.locator("#add").click()
    expect(p1.locator(".item")).to_have_count(1, timeout=10_000)
    obs["tab1_url_after_click"] = p1.url
    obs["violations"] = violations(rec, t_logged, {"tab1", "tab2", "tab3"})
    obs["all_hash_writes"] = [e for e in rec.events if HK in str(e.get("k"))]
    obs["cookies_end"] = sorted(cookie_summary(ctx))
    obs["ok"] = not obs["violations"] and "/list" in p1.url and len(obs["cookies_end"]) >= 3
    ctx.close()


def garbage_cookies(refresh=True, which=("access", "id", "refresh")):
    vals = {
        "access": ("_oidc_generic_access_token_data_partitioned", "access_token=garbage-access&expires_at=9999999999.0"),
        "id": ("_oidc_generic_id_token_partitioned", "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiJtYWxsb3J5In0.garbage-signature"),
        "refresh": ("_oidc_generic_refresh_token_partitioned", "garbage-refresh"),
    }
    out = []
    for w in which:
        name, value = vals[w]
        # Same attributes as the real enterprise cookies (CHIPS-partitioned, Secure, SameSite=None, HttpOnly).
        out.append({"name": name, "value": value, "domain": "localhost", "path": "/", "httpOnly": True, "secure": True,
                    "sameSite": "None", "partitionKey": "http://localhost"})
    return out


def settle_auth(page, seconds=10):
    """Sample where the page ends up and what it shows."""
    samples = []
    for i in range(seconds * 2):
        page.wait_for_timeout(500)
        txt = page.inner_text("body")[:200] if page.url else ""
        samples.append([round((i + 1) / 2, 1), page.url.replace(BASE, ""), txt.replace("\n", " | ")[:120]])
    return samples


def scen_garbage_protected(browser, obs):
    ctx = browser.new_context()
    rec = Recorder(ctx)
    ctx.add_cookies(garbage_cookies())
    obs["cookies_injected"] = cookie_summary(ctx)
    page = new_page(ctx, rec, obs, "tab1")
    page.goto(BASE + "/dashboard")
    obs["samples"] = settle_auth(page, 8)
    obs["final_url"] = page.url
    obs["cookies_end"] = cookie_summary(ctx)
    obs["body_has_alice_or_mallory"] = any(w in page.inner_text("body").lower() for w in ("alice", "mallory"))
    obs["sync_responses"] = [e for e in rec.events if e["kind"] == "cookie-sync"]
    obs["hash_writes"] = [e for e in rec.events if HK in str(e.get("k"))]
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-garbage-protected.png"))
    obs["ok"] = "/login" in page.url and not obs["cookies_end"] and not obs["body_has_alice_or_mallory"]
    ctx.close()


def scen_garbage_public(browser, obs):
    ctx = browser.new_context()
    rec = Recorder(ctx)
    ctx.add_cookies(garbage_cookies())
    page = new_page(ctx, rec, obs, "tab1")
    page.goto(BASE + "/")
    obs["samples_public"] = settle_auth(page, 6)
    obs["public_signed_in_visible"] = page.locator("#signed-in").count() > 0
    obs["public_anon_visible"] = page.locator("#anon").count() > 0
    obs["cookies_after_public"] = cookie_summary(ctx)
    page.locator("#reveal").click()
    page.wait_for_timeout(4000)
    obs["after_protected_click_url"] = page.url
    obs["secret_after_click"] = page.locator("#secret").inner_text() if page.locator("#secret").count() else None
    obs["sync_responses"] = [e for e in rec.events if e["kind"] == "cookie-sync"]
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-garbage-public.png"))
    obs["ok"] = obs["public_anon_visible"] and not obs["cookies_after_public"] and "/login" in page.url
    ctx.close()


def scen_garbage_id_refresh(browser, obs):
    ctx = browser.new_context()
    rec = Recorder(ctx)
    page = new_page(ctx, rec, obs, "tab1")
    do_login(page)
    page.wait_for_timeout(1500)
    before = {c["name"]: c["value"] for c in ctx.cookies()}
    ctx.add_cookies(garbage_cookies(which=("id",)))
    after = {c["name"]: c["value"] for c in ctx.cookies()}
    obs["id_cookie_replaced"] = before.get(TOKEN_COOKIES[1]) != after.get(TOKEN_COOKIES[1])
    obs["n_id_cookies"] = sum(1 for c in ctx.cookies() if c["name"] == TOKEN_COOKIES[1])
    t_inject = rec._now()
    page.reload()
    obs["samples"] = settle_auth(page, 8)
    obs["final_url"] = page.url
    end = {c["name"]: c["value"] for c in ctx.cookies()}
    obs["id_cookie_end_is_garbage"] = "garbage" in end.get(TOKEN_COOKIES[1], "")
    obs["id_cookie_end_present"] = TOKEN_COOKIES[1] in end
    obs["access_changed"] = before.get(TOKEN_COOKIES[0]) != end.get(TOKEN_COOKIES[0])
    obs["sync_responses"] = [e for e in rec.events if e["kind"] == "cookie-sync" and e["t"] >= t_inject]
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-garbage-id-refresh.png"))
    # acceptable outcomes: refreshed (still on dashboard as Alice, id cookie no longer garbage) or logged out to /login
    on_dash = "/dashboard" in page.url and page.locator("#user-name").count() and page.locator("#user-name").inner_text() == "Alice Admin"
    obs["outcome"] = "refreshed-logged-in" if on_dash and not obs["id_cookie_end_is_garbage"] else (
        "logged-out" if "/login" in page.url and not obs["id_cookie_end_present"] else "INCONSISTENT")
    obs["ok"] = obs["outcome"] != "INCONSISTENT"
    ctx.close()


def scen_garbage_all_after_login(browser, obs):
    ctx = browser.new_context()
    rec = Recorder(ctx)
    page = new_page(ctx, rec, obs, "tab1")
    do_login(page)
    page.locator("#reveal").click()
    expect(page.locator("#secret")).to_have_text("revealed-alice", timeout=T)
    page.wait_for_timeout(1500)
    ctx.add_cookies(garbage_cookies())
    t_inject = rec._now()
    page.reload()
    obs["samples"] = settle_auth(page, 8)
    obs["final_url"] = page.url
    obs["cookies_end"] = cookie_summary(ctx)
    obs["body_has_alice"] = "alice" in page.inner_text("body").lower()
    obs["sync_responses"] = [e for e in rec.events if e["kind"] == "cookie-sync" and e["t"] >= t_inject]
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-garbage-all-after-login.png"))
    # The server-side copy of the old valid tokens may legitimately win (cookie values are only re-read on sync),
    # so record the outcome rather than asserting one.
    obs["outcome"] = "logged-out" if "/login" in page.url else ("still-alice" if obs["body_has_alice"] else "other")
    obs["ok"] = True
    ctx.close()


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        for sc in SCEN:
            obs = {"scenario": sc, "label": LABEL}
            t0 = time.time()
            try:
                globals()["scen_" + sc](browser, obs)
            except Exception:
                obs["ok"] = False
                obs["traceback"] = traceback.format_exc()[-2500:]
            obs["duration"] = round(time.time() - t0, 1)
            results.append(obs)
            slim = {k: v for k, v in obs.items() if not k.endswith("_diag") and k not in ("all_hash_writes",)}
            errs = []
            for k, v in obs.items():
                if k.endswith("_diag"):
                    errs += [c for c in v.get("console", []) if c["type"] == "error"] + [{"pageerror": e} for e in v.get("page_errors", [])]
            slim["console_errors"] = errs[:8]
            print(json.dumps(slim, default=str)[:4000], flush=True)
        browser.close()
    (W / "logs" / f"hydtoken-{LABEL}.json").write_text(json.dumps(results, indent=2, default=str))
    print("SUMMARY", {r["scenario"]: r.get("ok") for r in results})


main()
