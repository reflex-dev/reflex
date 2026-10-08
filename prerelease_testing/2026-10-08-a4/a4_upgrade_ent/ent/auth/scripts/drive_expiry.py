"""Token expiry / provider revocation / provider restart against a running app.

The driver owns the mock OIDC provider process (port 8638): it (re)starts it with the
token lifetime each scenario needs.  Usage:
  drive_expiry.py <frontend_base> <label> <scenario,...>
Scenarios: proactive, expire_norefresh, expire_closed_tab, revoke, restart_provider
"""

import json
import os
import re
import signal
import subprocess
import sys
import time
import traceback

import httpx
from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import CHROMIUM, W, attach, login, save  # noqa: E402

BASE = sys.argv[1].rstrip("/")


def U(path):
    """URL matcher tolerant of the trailing slash prod static serving adds (307 /dashboard -> /dashboard/)."""
    return re.compile(re.escape(BASE + path) + r"/?(\?.*)?$")
LABEL = sys.argv[2]
SCEN = sys.argv[3].split(",")
SB = "/tmp/claude-0/-home-user-reflex/bd1e0d91-2710-5ba9-a996-a9166a939428/scratchpad"
T = 45_000
results = []


def stop_mock():
    subprocess.run(["pkill", "-f", str(W / "scripts" / "mock_oidc.py")])
    for _ in range(50):
        if subprocess.run(["pgrep", "-f", str(W / "scripts" / "mock_oidc.py")], capture_output=True).returncode != 0:
            break
        time.sleep(0.2)


EXTERNAL = os.environ.get("EXPIRY_MOCK_EXTERNAL") == "1"


def start_mock(max_age=3600, no_refresh=False, tag="", force=False):
    """(Re)start the mock IdP.  With EXPIRY_MOCK_EXTERNAL=1 the wrapper (expiry_matrix.sh) has already
    started it with this scenario's parameters AND restarted the app afterwards: the app caches the IdP's
    JWKS, and every mock process signs with a fresh RSA key, so a mock restart under a running app makes
    every later login fail (InvalidKeyIdError).  Only restart_provider restarts it on purpose (force=True)."""
    if EXTERNAL and not force:
        return None
    stop_mock()
    env = dict(os.environ, MOCK_OIDC_PORT="8638", MOCK_OIDC_MAX_AGE=str(max_age))
    env.pop("MOCK_OIDC_NO_REFRESH", None)
    if no_refresh:
        env["MOCK_OIDC_NO_REFRESH"] = "1"
    log = open(W / "logs" / f"mock-oidc-{LABEL}-{tag}.log", "w")
    proc = subprocess.Popen([f"{SB}/envs/alpha2-ent/bin/python", str(W / "scripts" / "mock_oidc.py")], env=env, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(100):
        try:
            if httpx.get("http://localhost:8638/.well-known/openid-configuration", timeout=2).status_code == 200:
                return proc
        except Exception:
            pass
        time.sleep(0.2)
    raise RuntimeError("mock did not start")


def fresh_login(browser, obs, user="alice"):
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(T)
    attach(page, obs)
    page.goto(BASE + "/dashboard")
    page.wait_for_url(re.compile("/login"), timeout=T)
    login(page, user)
    page.wait_for_url(U("/dashboard"), timeout=T)
    expect(page.locator("#user-name")).to_have_text("Alice Admin" if user == "alice" else "Bob Member", timeout=T)
    return ctx, page


def try_reveal(page, obs, key):
    page.locator("#reveal").click()
    t0 = time.time()
    outcome = None
    while time.time() - t0 < 20:
        if "/login" in page.url:
            outcome = "redirected-to-login"
            break
        if page.locator("#secret").count() and page.locator("#secret").inner_text() == "revealed-alice":
            outcome = "allowed:revealed-alice"
            break
        page.wait_for_timeout(250)
    obs[key] = outcome or ("timeout url=" + page.url)
    obs[key + "_toasts"] = page.locator("[data-sonner-toast]").all_inner_texts()


def scen_proactive(browser, obs):
    start_mock(max_age=75, tag="proactive")
    ctx, page = fresh_login(browser, obs)
    samples = []
    for i in range(12):
        page.wait_for_timeout(10_000)
        samples.append([10 * (i + 1), page.url.replace(BASE, ""), page.locator("#user-name").inner_text() if page.locator("#user-name").count() else None])
    obs["samples"] = samples
    try_reveal(page, obs, "reveal_after_120s")
    page.goto(BASE + "/dashboard")
    page.wait_for_timeout(3000)
    obs["reload_after_120s_url"] = page.url
    obs["cookie_names"] = sorted(c["name"] for c in ctx.cookies())
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-expiry-proactive.png"))
    ctx.close()


def scen_expire_norefresh(browser, obs):
    start_mock(max_age=30, no_refresh=True, tag="norefresh")
    ctx, page = fresh_login(browser, obs)
    page.wait_for_timeout(40_000)
    obs["url_after_40s_idle"] = page.url
    try_reveal(page, obs, "reveal_after_expiry")
    page.wait_for_timeout(2000)
    obs["final_url"] = page.url
    obs["final_text"] = page.inner_text("body")[:300]
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-expiry-norefresh.png"))
    # log back in after expiry
    if "/login" in page.url:
        login(page, "alice")
        page.wait_for_url(re.compile(r"/dashboard|/$"), timeout=T)
        page.wait_for_timeout(2000)
        obs["relogin_url"] = page.url
        obs["relogin_user"] = page.locator("#user-name").inner_text() if page.locator("#user-name").count() else None
    ctx.close()


def scen_expire_closed_tab(browser, obs):
    start_mock(max_age=40, tag="closedtab")
    ctx, page = fresh_login(browser, obs)
    page.close()
    time.sleep(50)
    page = ctx.new_page()
    attach(page, obs.setdefault("page2", {}))
    page.goto(BASE + "/dashboard")
    page.wait_for_timeout(8000)
    obs["url_on_return"] = page.url
    obs["text_on_return"] = page.inner_text("body")[:300]
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-expiry-closedtab.png"))
    ctx.close()


def scen_revoke(browser, obs):
    start_mock(max_age=3600, tag="revoke")
    ctx, page = fresh_login(browser, obs)
    r = httpx.post("http://localhost:8638/users/alice/revoke-tokens")
    obs["revoke_status"] = r.status_code
    try_reveal(page, obs, "reveal_after_provider_revoke")
    page.goto(BASE + "/dashboard")
    page.wait_for_timeout(3000)
    obs["reload_after_revoke_url"] = page.url
    if "/dashboard" in page.url:
        page.locator("#force-refresh").click()
        page.wait_for_timeout(6000)
        obs["force_refresh_url"] = page.url
        obs["force_refresh_result"] = page.locator("#refresh-result").inner_text() if page.locator("#refresh-result").count() else None
        page.goto(BASE + "/dashboard")
        page.wait_for_timeout(4000)
        obs["reload_after_refresh_fail_url"] = page.url
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-revoke.png"))
    ctx.close()


def scen_restart_provider(browser, obs):
    start_mock(max_age=3600, tag="restart-a")
    ctx, page = fresh_login(browser, obs)
    start_mock(max_age=3600, tag="restart-b", force=True)  # new process: new signing key, empty token store
    page.reload()
    page.wait_for_timeout(5000)
    obs["reload_after_restart_url"] = page.url
    try_reveal(page, obs, "reveal_after_restart") if "/dashboard" in page.url else None
    if "/dashboard" in page.url:
        page.locator("#force-refresh").click()
        page.wait_for_timeout(6000)
        obs["force_refresh_after_restart"] = page.locator("#refresh-result").inner_text() if page.locator("#refresh-result").count() else page.url
    ctx.close()
    # brand-new browser logging in after the provider restart (JWKS cached by the app?)
    obs2 = obs.setdefault("fresh_after_restart", {})
    ctx2 = browser.new_context()
    p2 = ctx2.new_page()
    attach(p2, obs2)
    p2.goto(BASE + "/dashboard")
    p2.wait_for_url(re.compile("/login"), timeout=T)
    login(p2, "alice")
    p2.wait_for_timeout(10_000)
    obs["fresh_login_after_restart_url"] = p2.url
    obs["fresh_login_after_restart_text"] = p2.inner_text("body")[:400]
    p2.screenshot(path=str(W / "screenshots" / f"{LABEL}-restart-fresh-login.png"))
    ctx2.close()


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROMIUM)
        for sc in SCEN:
            obs = {"scenario": sc, "label": LABEL}
            t0 = time.time()
            try:
                globals()["scen_" + sc](browser, obs)
                obs["ran"] = True
            except Exception:
                obs["ran"] = False
                obs["traceback"] = traceback.format_exc()[-2500:]
            obs["duration"] = round(time.time() - t0, 1)
            results.append(obs)
            slim = {k: v for k, v in obs.items() if k not in ("console", "page2", "fresh_after_restart")}
            slim["console_errors"] = [c for c in obs.get("console", []) if c["type"] == "error" and "TUNNEL" not in c["text"]][:10]
            print(json.dumps(slim, default=str)[:5000], flush=True)
        browser.close()
    if not EXTERNAL:
        start_mock(max_age=3600, tag="final")
    save(f"expiry-{LABEL}-{'_'.join(SCEN)}.json", results)


main()
