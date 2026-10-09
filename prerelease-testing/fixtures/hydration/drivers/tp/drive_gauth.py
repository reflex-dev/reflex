"""reflex-google-auth 0.2.0 demo: does GoogleAuthState.tokeninfo's cleanup of a bogus token reach localStorage?

Usage: drive_gauth.py <base_url> <out_json> <label>
"""
import json
import sys
import time

from playwright.sync_api import sync_playwright

import os  # noqa: E402
assert f"/envs/{os.environ.get('DRV_VENV', 'driver')}/" in sys.executable, sys.executable
BASE, OUT, LABEL = sys.argv[1].rstrip("/"), sys.argv[2], sys.argv[3]
KEY = "reflex___state____state.reflex_google_auth___state____google_auth_state.token_response_json_rx_state_"
BOGUS = json.dumps({"id_token": "abc.def.ghi", "access_token": "ya29.bogus", "scope": "openid email"})
frames, phase, res = [], {"p": "initial"}, {}
t0 = time.time()


def on_ws(ws):
    ws.on("framesent", lambda d: frames.append({"t": round(time.time() - t0, 3), "phase": phase["p"], "dir": "sent", "data": str(d)[:6000]}))
    ws.on("framereceived", lambda d: frames.append({"t": round(time.time() - t0, 3), "phase": phase["p"], "dir": "recv", "data": str(d)[:6000]}))


with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    page = b.new_context().new_page()
    page.on("websocket", on_ws)
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(1500)
    res["keys_before"] = sorted(page.evaluate("() => Object.keys(localStorage)"))
    page.evaluate("([k, v]) => localStorage.setItem(k, v)", [KEY, BOGUS])
    phase["p"] = "reload-protected"
    page.goto(BASE + "/protected", wait_until="networkidle")
    page.wait_for_timeout(4000)
    res["after_reload"] = page.evaluate("(k) => localStorage.getItem(k)", KEY)
    res["protected_unlocked"] = "Nice to see you" in page.locator("body").inner_text()
    phase["p"] = "reload-index"
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(2500)
    res["after_reload_index"] = page.evaluate("(k) => localStorage.getItem(k)", KEY)
    phase["p"] = "client-nav"
    page.get_by_role("link", name="Protected Page", exact=True).click()
    page.wait_for_url(BASE + "/protected", timeout=10000)
    page.wait_for_timeout(3000)
    res["after_client_nav"] = page.evaluate("(k) => localStorage.getItem(k)", KEY)
    phase["p"] = "reload2"
    page.reload(wait_until="networkidle")
    page.wait_for_timeout(3000)
    res["after_reload2"] = page.evaluate("(k) => localStorage.getItem(k)", KEY)
    b.close()
short = {k: ("BOGUS" if v == BOGUS else v) for k, v in res.items()}
print("GAUTH", LABEL, json.dumps(short))
json.dump({"result": res, "frames": frames}, open(OUT, "w"), indent=1)
