"""Drive the SHIPPED reflex-enterprise demos/oidc app against the fake IdP.

Covers: anonymous index, Do Nothing, Cookie Sync (FINDING-026), Okta login
through the IdP, userinfo card, Log AT, reload persistence, Databricks login
(offline_access + access-token-hash badges), and RP-initiated logout.

Usage: python drive_oidc_demo.py <frontend_port> <backend_port> <idp_port> <label> <shotdir>
"""

import json
import sys
import time

from playwright.sync_api import sync_playwright

FPORT, BPORT, IDPPORT = int(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
LABEL = sys.argv[4]
SHOTS = sys.argv[5]
BASE = f"http://localhost:{FPORT}"
IDP = f"http://localhost:{IDPPORT}"

OUT = {
    "label": LABEL,
    "steps": [],
    "console": [],
    "pageerrors": [],
    "failed_requests": [],
    "http_errors": [],
    "requests": [],
}


def step(name, **kw):
    """Record and print one step."""
    OUT["steps"].append({"step": name, **kw})
    print(f"[{name}] " + json.dumps(kw, default=str)[:500], flush=True)


def body_text(page):
    """Whole-page text, trimmed."""
    try:
        return page.locator("body").inner_text(timeout=5000)
    except Exception as e:  # noqa: BLE001
        return f"<absent:{type(e).__name__}>"


with sync_playwright() as p:
    br = p.chromium.launch(
        executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox"]
    )
    ctx = br.new_context(viewport={"width": 1280, "height": 900})
    page = ctx.new_page()
    page.on(
        "console",
        lambda m: OUT["console"].append({"type": m.type, "text": m.text[:300]}),
    )
    page.on("pageerror", lambda e: OUT["pageerrors"].append(str(e)[:300]))
    page.on(
        "requestfailed",
        lambda r: OUT["failed_requests"].append(
            {"url": r.url[:200], "err": str(r.failure)[:200]}
        ),
    )
    page.on(
        "response",
        lambda r: OUT["http_errors"].append({"url": r.url[:250], "status": r.status})
        if r.status >= 400
        else None,
    )
    page.on("request", lambda r: OUT["requests"].append(r.url[:250]))

    def shot(name):
        """Screenshot into the shot directory."""
        page.screenshot(path=f"{SHOTS}/{name}.png", full_page=True)

    # 1. anonymous index
    page.goto(f"{BASE}/", wait_until="networkidle")
    page.wait_for_timeout(2000)
    t = body_text(page)
    step(
        "index_anon",
        has_okta_btn="Okta" in t,
        has_dbx_btn="Databricks" in t,
        buttons=page.locator("button").count(),
        text=t[:300],
    )
    shot("01_index_anon")

    # 2. Do Nothing (plain event round trip)
    n_err_before = len(OUT["pageerrors"])
    page.get_by_role("button", name="Do Nothing").click()
    page.wait_for_timeout(1000)
    step("do_nothing", new_page_errors=len(OUT["pageerrors"]) - n_err_before)

    # 3. Cookie Sync -> FINDING-026 check
    before = len(OUT["http_errors"])
    page.get_by_role("button", name="Cookie Sync").click()
    page.wait_for_timeout(1500)
    sync_calls = [u for u in OUT["requests"] if "cookies/sync" in u]
    sync_errs = [e for e in OUT["http_errors"] if "cookies/sync" in e["url"]]
    step(
        "cookie_sync",
        requests=sync_calls[-3:],
        http_errors=sync_errs[-3:],
        new_http_errors=len(OUT["http_errors"]) - before,
    )

    # 4. Okta login
    page.get_by_role("button", name="Login with Okta").click()
    page.wait_for_timeout(4000)
    try:
        page.wait_for_url(lambda u: "localhost:%d" % FPORT in u, timeout=20000)
    except Exception:  # noqa: BLE001
        pass
    page.wait_for_timeout(3000)
    t = body_text(page)
    step(
        "okta_after_login",
        url=page.url,
        has_userinfo="Okta User Info" in t,
        has_email="alice@example.test" in t,
        has_logout="Logout" in t,
        text=t[:400],
    )
    shot("02_okta_logged_in")

    # 5. Log AT (server-side token access)
    logat = page.get_by_role("button", name="Log AT")
    step("log_at_buttons", count=logat.count())
    if logat.count():
        logat.first.click()
        page.wait_for_timeout(1500)
        step("log_at_clicked", page_errors=len(OUT["pageerrors"]))

    # 6. reload persistence
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(3000)
    t = body_text(page)
    step(
        "after_reload",
        still_logged_in="alice@example.test" in t,
        has_login_btn="Login with Okta" in t,
    )
    shot("03_after_reload")

    # 7. Databricks login (offline_access + refresh-hash badges)
    dbx = page.get_by_role("button", name="Login with Databricks")
    if dbx.count():
        dbx.first.click()
        page.wait_for_timeout(5000)
        page.wait_for_timeout(2000)
        t = body_text(page)
        step(
            "databricks_after_login",
            url=page.url,
            has_dbx_userinfo="Databricks User Info" in t,
            both_logged_in=t.count("alice@example.test") >= 2,
            text=t[:600],
        )
        shot("04_both_logged_in")

    # 8. second tab shares the session
    page2 = ctx.new_page()
    page2.goto(f"{BASE}/", wait_until="networkidle")
    page2.wait_for_timeout(2500)
    t2 = body_text(page2)
    step("second_tab", logged_in="alice@example.test" in t2)
    page2.close()

    # 9. logout (Okta card)
    logouts = page.get_by_role("button", name="Logout")
    step("logout_buttons", count=logouts.count())
    if logouts.count():
        logouts.first.click()
        page.wait_for_timeout(5000)
        t = body_text(page)
        step(
            "after_logout",
            url=page.url,
            has_login_btn="Login with Okta" in t,
            okta_userinfo_gone="Okta User Info" not in t,
            text=t[:300],
        )
        shot("05_after_logout")

    # 10. /iframe route renders
    page.goto(f"{BASE}/iframe", wait_until="networkidle")
    page.wait_for_timeout(2500)
    frames = [f.url for f in page.frames]
    step("iframe_route", frames=frames, text=body_text(page)[:200])
    shot("06_iframe")

    OUT["end_time"] = time.strftime("%H:%M:%S")
    br.close()

with open(f"{SHOTS}/results_{LABEL}.json", "w") as fh:
    json.dump(OUT, fh, indent=1)
print(
    "\nSUMMARY console_errors=",
    sum(1 for c in OUT["console"] if c["type"] == "error"),
    "pageerrors=",
    len(OUT["pageerrors"]),
    "http_errors=",
    len(OUT["http_errors"]),
    "failed_requests=",
    len(OUT["failed_requests"]),
)
for e in OUT["http_errors"][:15]:
    print("  HTTP", e["status"], e["url"])
for c in OUT["console"]:
    if c["type"] in ("error", "warning"):
        print("  CONSOLE", c["type"], c["text"][:200])
