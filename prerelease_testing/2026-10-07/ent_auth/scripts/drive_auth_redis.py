"""Enterprise OIDC flows on Redis (dev or prod / multi-worker).

Usage: drive_auth_redis.py <base_url> <label> [cases,comma,separated]
Cases: cycle (alice->bob same browser), pubnav (protected computed vars after
public nav + 2 reloads, fresh context), twotab (second tab same cookies),
extrascope (login + refresh with extra scopes; run with AUTH_EXTRA_SCOPES=1 server)
"""

import json
import re
import sys
import time
import traceback

from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import CHROMIUM, W, attach, end_session, login, redis_dump, save, storage_snapshot  # noqa: E402

BASE = sys.argv[1].rstrip("/")
LABEL = sys.argv[2]
CASES = sys.argv[3].split(",") if len(sys.argv) > 3 else ["cycle", "pubnav", "twotab"]
T = 45_000


def shot(page, name):
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-{name}.png"))


def check_alice_dashboard(page, obs):
    expect(page.locator("#user-name")).to_have_text("Alice Admin", timeout=T)
    expect(page.locator("#secret")).to_have_text("initial-secret", timeout=T)
    expect(page.locator("#secret-view")).to_have_text("computed:initial-secret", timeout=T)
    expect(page.locator("#admin-view")).to_have_text("admin-data", timeout=T)
    expect(page.locator("#async-admin-view")).to_have_text("async-admin-data", timeout=T)


def case_cycle(browser, obs):
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(T)
    attach(page, obs)
    steps = obs.setdefault("steps", [])
    t0 = time.time()
    page.goto(BASE + "/dashboard")
    page.wait_for_url(re.compile("/login"), timeout=T)
    login(page, "alice")
    page.wait_for_url(BASE + "/dashboard", timeout=T)
    steps.append(["alice_login", round(time.time() - t0, 2)])
    check_alice_dashboard(page, obs)
    page.locator("#reveal").click()
    expect(page.locator("#secret")).to_have_text("revealed-alice", timeout=T)
    expect(page.locator("#secret-view")).to_have_text("computed:revealed-alice", timeout=T)
    page.locator("#async-admin").click()
    expect(page.locator("#async-log")).to_have_text("async-ran", timeout=T)
    page.locator("#ping").click()
    expect(page.locator("#last-pid")).not_to_have_text("", timeout=T)
    obs["pid_dashboard"] = page.locator("#last-pid").inner_text()
    steps.append(["alice_protected_events", round(time.time() - t0, 2)])
    shot(page, "alice-dashboard")
    # reload: protected values must come back from Redis
    page.reload()
    expect(page.locator("#user-name")).to_have_text("Alice Admin", timeout=T)
    expect(page.locator("#secret")).to_have_text("revealed-alice", timeout=T)
    expect(page.locator("#async-admin-view")).to_have_text("async-admin-data", timeout=T)
    page.locator("#ping").click()
    page.wait_for_timeout(500)
    obs["pid_after_reload"] = page.locator("#last-pid").inner_text()
    steps.append(["alice_reload_ok", round(time.time() - t0, 2)])
    # background task mutating the inherited list
    page.locator("#nav-list").click()
    page.wait_for_url(BASE + "/list", timeout=T)
    expect(page.locator("#list-user")).to_have_text("alice", timeout=T)
    page.locator("#fill").click()
    try:
        expect(page.locator("#progress")).to_have_text("5", timeout=12_000)
        expect(page.locator(".item")).to_have_count(5, timeout=5_000)
        expect(page.locator("#item-count")).to_have_text("5", timeout=5_000)
        obs["bg_live"] = "updated-live"
    except AssertionError:
        obs["bg_live"] = "NOT-UPDATED-LIVE progress=%s item_count=%s items=%s" % (
            page.locator("#progress").inner_text(), page.locator("#item-count").inner_text(),
            page.locator(".item").all_inner_texts())
        shot(page, "bg-not-live")
    obs["bg_pid"] = page.locator("#bg-pid").inner_text()
    obs["items_live"] = page.locator(".item").all_inner_texts()
    page.wait_for_timeout(1500)
    page.reload()
    expect(page.locator(".item")).to_have_count(5, timeout=T)
    obs["items_after_reload"] = page.locator(".item").all_inner_texts()
    assert obs["items_after_reload"] == [f"alice-bg-{i}" for i in range(5)], obs["items_after_reload"]
    page.locator("#add").click()
    expect(page.locator(".item")).to_have_count(6, timeout=T)
    steps.append(["bg_list_ok", round(time.time() - t0, 2)])
    shot(page, "alice-list")
    obs["storage_alice"] = storage_snapshot(page)
    obs["cookie_names_alice"] = sorted(c["name"] for c in ctx.cookies())
    # public navigation then reload: protected computed vars must survive (#252)
    page.locator("#nav-public").click()
    page.wait_for_url(BASE + "/", timeout=T)
    expect(page.locator("#secret")).to_have_text("revealed-alice", timeout=T)
    expect(page.locator("#secret-view")).to_have_text("computed:revealed-alice", timeout=T)
    expect(page.locator("#admin-view")).to_have_text("admin-data", timeout=T)
    expect(page.locator("#async-admin-view")).to_have_text("async-admin-data", timeout=T)
    page.reload()
    expect(page.locator("#signed-in")).to_contain_text("alice", timeout=T)
    expect(page.locator("#secret")).to_have_text("revealed-alice", timeout=T)
    expect(page.locator("#secret-view")).to_have_text("computed:revealed-alice", timeout=T)
    expect(page.locator("#admin-view")).to_have_text("admin-data", timeout=T)
    expect(page.locator("#async-admin-view")).to_have_text("async-admin-data", timeout=T)
    steps.append(["public_nav_reload_ok", round(time.time() - t0, 2)])
    # logout
    page.locator("#user-logout").click()
    end_session(page)
    page.wait_for_url(lambda u: u.split("?")[0] == BASE + "/", timeout=T)
    expect(page.locator("#anon")).to_be_visible(timeout=T)
    page.wait_for_timeout(1500)
    obs["after_logout"] = {
        "secret": page.locator("#secret").inner_text(),
        "secret_view": page.locator("#secret-view").inner_text(),
        "admin_view": page.locator("#admin-view").inner_text(),
        "async_admin_view": page.locator("#async-admin-view").inner_text(),
        "body_has_alice": "alice" in page.inner_text("body").lower(),
    }
    shot(page, "logged-out")
    obs["storage_logged_out"] = storage_snapshot(page)
    obs["cookie_names_logged_out"] = sorted(c["name"] for c in ctx.cookies())
    steps.append(["logout_ok", round(time.time() - t0, 2)])
    # Bob on the same browser
    page.goto(BASE + "/dashboard")
    page.wait_for_url(re.compile("/login"), timeout=T)
    login(page, "bob")
    page.wait_for_url(BASE + "/dashboard", timeout=T)
    expect(page.locator("#user-name")).to_have_text("Bob Member", timeout=T)
    expect(page.locator("#secret")).to_have_text("initial-secret", timeout=T)
    expect(page.locator("#admin-view")).to_have_text("admin-placeholder", timeout=T)
    expect(page.locator("#async-admin-view")).to_have_text("async-admin-placeholder", timeout=T)
    page.locator("#nav-list").click()
    page.wait_for_url(BASE + "/list", timeout=T)
    expect(page.locator("#list-user")).to_have_text("bob", timeout=T)
    expect(page.locator("#item-count")).to_have_text("0", timeout=T)
    page.wait_for_timeout(1000)
    obs["bob_items"] = page.locator(".item").all_inner_texts()
    body = page.inner_text("body")
    obs["bob_body_has_alice"] = "alice" in body.lower()
    page.locator("#fill").click()
    page.wait_for_timeout(3000)
    obs["bob_items_live_after_fill"] = page.locator(".item").all_inner_texts()
    page.reload()
    expect(page.locator(".item")).to_have_count(5, timeout=T)
    obs["bob_items_after_fill"] = page.locator(".item").all_inner_texts()
    page.locator("#nav-public").click()
    page.wait_for_url(BASE + "/", timeout=T)
    page.locator("#reveal").click()
    expect(page.locator("#secret")).to_have_text("revealed-bob", timeout=T)
    shot(page, "bob")
    obs["storage_bob"] = storage_snapshot(page)
    obs["storage_bob_has_alice"] = "alice" in json.dumps(obs["storage_bob"]).lower()
    # Redis: what does the server still hold for this token?
    token = obs["storage_bob"]["session"].get("token") or ""
    obs["client_token_tail"] = token[-6:]
    dump = redis_dump(f"{token}*") if token else {}
    obs["redis_keys_for_token"] = sorted(dump)
    obs["redis_alice_mentions"] = sorted(k for k, v in dump.items() if "alice" in v.lower())
    assert not obs["bob_body_has_alice"], "Alice data visible to Bob"
    assert obs["bob_items_after_fill"] == [f"bob-bg-{i}" for i in range(5)], obs["bob_items_after_fill"]
    steps.append(["bob_ok", round(time.time() - t0, 2)])
    ctx.close()


def case_pubnav(browser, obs):
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(T)
    attach(page, obs)
    page.goto(BASE + "/dashboard")
    page.wait_for_url(re.compile("/login"), timeout=T)
    login(page, "alice")
    page.wait_for_url(BASE + "/dashboard", timeout=T)
    check_alice_dashboard(page, obs)
    page.locator("#nav-public").click()
    page.wait_for_url(BASE + "/", timeout=T)
    vals = []
    for i in range(3):
        if i:
            page.reload()
        expect(page.locator("#signed-in")).to_contain_text("alice", timeout=T)
        expect(page.locator("#async-admin-view")).to_have_text("async-admin-data", timeout=T)
        expect(page.locator("#admin-view")).to_have_text("admin-data", timeout=T)
        expect(page.locator("#secret-view")).to_have_text("computed:initial-secret", timeout=T)
        page.locator("#ping").click()
        page.wait_for_timeout(400)
        vals.append({"pid": page.locator("#last-pid").inner_text(), "seen": page.locator("#seen-pids").inner_text()})
    obs["reloads"] = vals
    shot(page, "pubnav")
    ctx.close()


def case_twotab(browser, obs):
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(T)
    attach(page, obs)
    page.goto(BASE + "/dashboard")
    page.wait_for_url(re.compile("/login"), timeout=T)
    login(page, "alice")
    page.wait_for_url(BASE + "/dashboard", timeout=T)
    check_alice_dashboard(page, obs)
    page.locator("#reveal").click()
    expect(page.locator("#secret")).to_have_text("revealed-alice", timeout=T)
    page2 = ctx.new_page()
    page2.set_default_timeout(T)
    sink2 = obs.setdefault("tab2", {})
    attach(page2, sink2)
    page2.goto(BASE + "/dashboard")
    expect(page2.locator("#user-name")).to_have_text("Alice Admin", timeout=T)
    expect(page2.locator("#async-admin-view")).to_have_text("async-admin-data", timeout=T)
    # tab2 has its own client token, so FlowState.secret is per-tab
    obs["tab2_secret"] = page2.locator("#secret").inner_text()
    page2.locator("#ping").click()
    page.locator("#ping").click()
    page.wait_for_timeout(800)
    obs["tab1_pid"] = page.locator("#last-pid").inner_text()
    obs["tab2_pid"] = page2.locator("#last-pid").inner_text()
    # logout from tab 2 -> tab 1 protected action must be refused
    page2.locator("#user-logout").click()
    end_session(page2)
    page2.wait_for_url(lambda u: u.split("?")[0] == BASE + "/", timeout=T)
    expect(page2.locator("#anon")).to_be_visible(timeout=T)
    page.locator("#reveal").click()
    try:
        page.wait_for_url(re.compile("/login"), timeout=20_000)
        obs["tab1_after_tab2_logout"] = "redirected-to-login"
    except Exception:
        obs["tab1_after_tab2_logout"] = "stayed:" + page.url + " secret=" + page.locator("#secret").inner_text()
    shot(page, "twotab-tab1")
    ctx.close()


def case_xtab(browser, obs):
    """Logout in tab 2; is tab 1 (same browser, own client token) still authorized?"""
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(T)
    attach(page, obs)
    page.goto(BASE + "/list")
    page.wait_for_url(re.compile("/login"), timeout=T)
    login(page, "alice")
    page.wait_for_url(BASE + "/list", timeout=T)
    expect(page.locator("#list-user")).to_have_text("alice", timeout=T)
    expect(page.locator("#item-count")).not_to_have_text("-1", timeout=T)
    obs["tab1_items_before"] = page.locator("#item-count").inner_text()
    page2 = ctx.new_page()
    page2.set_default_timeout(T)
    attach(page2, obs.setdefault("tab2", {}))
    page2.goto(BASE + "/dashboard")
    expect(page2.locator("#user-name")).to_have_text("Alice Admin", timeout=T)
    obs["ls_before"] = [storage_snapshot(page)["local"], storage_snapshot(page2)["local"]]
    page2.locator("#user-logout").click()
    end_session(page2)
    page2.wait_for_url(lambda u: u.split("?")[0] == BASE + "/", timeout=T)
    expect(page2.locator("#anon")).to_be_visible(timeout=T)
    page.wait_for_timeout(6000)
    obs["tab1_url_6s_after_logout"] = page.url
    obs["tab1_user_6s_after_logout"] = page.locator("#list-user").inner_text() if page.locator("#list-user").count() else None
    obs["ls_after"] = [storage_snapshot(page)["local"], storage_snapshot(page2)["local"]]
    obs["cookies_after"] = sorted(c["name"] for c in ctx.cookies())
    if page.url.split("?")[0] == BASE + "/list":
        page.locator("#add").click()
        page.wait_for_timeout(3000)
        obs["tab1_url_after_protected_click"] = page.url
        obs["tab1_items_after_click"] = page.locator(".item").all_inner_texts() if "/list" in page.url else None
        page.wait_for_timeout(1000)
        page.reload()
        page.wait_for_timeout(4000)
        obs["tab1_url_after_reload"] = page.url
    shot(page, "xtab-tab1")
    ctx.close()


def case_extrascope(browser, obs):
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(T)
    attach(page, obs)
    authz_urls = []
    page.on("request", lambda r: authz_urls.append(r.url) if "/oauth2/authorize" in r.url and r.method == "GET" else None)
    page.goto(BASE + "/dashboard")
    page.wait_for_url(re.compile("/login"), timeout=T)
    login(page, "alice")
    page.wait_for_url(BASE + "/dashboard", timeout=T)
    check_alice_dashboard(page, obs)
    obs["authorize_scope"] = [re.search(r"scope=([^&]+)", u).group(1) for u in authz_urls if "scope=" in u]
    page.locator("#force-refresh").click()
    expect(page.locator("#refresh-result")).to_have_text("refreshed", timeout=T)
    page.reload()
    expect(page.locator("#user-name")).to_have_text("Alice Admin", timeout=T)
    expect(page.locator("#refresh-result")).to_have_text("refreshed", timeout=T)
    obs["cookie_names"] = sorted(c["name"] for c in ctx.cookies())
    shot(page, "extrascope")
    ctx.close()


def main():
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        for case in CASES:
            obs = {"case": case, "label": LABEL}
            t0 = time.time()
            try:
                globals()["case_" + case](browser, obs)
                obs["passed"] = True
            except Exception:
                obs["passed"] = False
                obs["traceback"] = traceback.format_exc()[-3000:]
            obs["duration"] = round(time.time() - t0, 1)
            results.append(obs)
            summary = {k: v for k, v in obs.items() if k not in ("console", "storage_alice", "storage_bob", "storage_logged_out", "tab2")}
            summary["console_errors"] = [c for c in obs.get("console", []) if c["type"] in ("error", "warning")][:20]
            print(json.dumps(summary, default=str)[:6000], flush=True)
        browser.close()
    save(f"auth-{LABEL}.json", results)
    print("ALL_PASSED" if all(r["passed"] for r in results) else "SOME_FAILED")


if __name__ == "__main__":
    main()
