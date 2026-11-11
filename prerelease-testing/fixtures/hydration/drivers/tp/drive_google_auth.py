"""Drive reflex-google-auth's upstream demo (no real Google login is possible here).

Usage: drive_google_auth.py <base_url> <out_dir> <label>
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from tpdrive import Capture, browser, wait_text

BASE = sys.argv[1].rstrip("/")
OUT = Path(sys.argv[2])
LABEL = sys.argv[3]
OUT.mkdir(parents=True, exist_ok=True)
cap = Capture(ws_frames=True)


def shot(page, name):
    page.screenshot(path=str(OUT / f"{LABEL}-{name}.png"), full_page=True)


def ls_dump(page):
    return page.evaluate("() => Object.fromEntries(Object.entries(window.localStorage))")


with browser() as b:
    ctx = b.new_context()
    page = cap.attach(ctx.new_page(), "main")
    cap.label = "index"
    page.goto(BASE + "/", wait_until="networkidle")
    cap.check("index renders", "Google OAuth" in wait_text(page, "body", "Google OAuth"))
    for name in ["Protected Page", "Partially Protected Page", "Custom Login Button", "Custom Scope"]:
        cap.check(f"index link {name}", page.get_by_role("link", name=name, exact=True).count() == 1)

    cap.label = "protected"
    page.goto(BASE + "/protected", wait_until="networkidle")
    page.wait_for_timeout(2500)
    html = page.content()
    cap.check("/protected anonymous: no protected content", "Nice to see you" not in html and "Logout" not in page.locator("body").inner_text())
    shot(page, "01-protected-anon")

    cap.label = "partially"
    page.goto(BASE + "/partially-protected", wait_until="networkidle")
    cap.check("/partially-protected renders", "partially protected" in wait_text(page, "body", "partially protected"))

    cap.label = "custom-button"
    page.goto(BASE + "/custom-button", wait_until="networkidle")
    t = wait_text(page, "body", "Google Login")
    cap.check("/custom-button shows custom login button", "Google Login" in t, t[:100])
    popups = []
    ctx.on("page", lambda p: popups.append(p.url))
    page.get_by_role("button", name="Google Login 🚀").click()
    page.wait_for_timeout(2500)
    cap.check("custom login button click handled (popup or no reflex error)", True, f"popups={popups}")
    shot(page, "02-custom-button")

    cap.label = "custom-scope"
    page.goto(BASE + "/custom-scope", wait_until="networkidle")
    t = wait_text(page, "body", "Login with Drive API scope")
    cap.check("/custom-scope (on_load DriveState + get_state(GoogleAuthState)) renders login button", "Login with Drive API scope" in t, t[:100])

    cap.label = "inject-bogus-token"
    page.goto(BASE + "/", wait_until="networkidle")
    page.wait_for_timeout(1000)
    keys_before = ls_dump(page)
    key = next((k for k in keys_before if k.endswith("token_response_json")), None)
    cap.check("token_response_json LocalStorage key discoverable", key is not None, json.dumps(keys_before)[:500])
    key = key or "reflex___state____state.reflex_google_auth___state____google_auth_state.token_response_json_rx_state_"
    bogus = json.dumps({"id_token": "abc.def.ghi", "access_token": "ya29.bogus", "scope": "openid email"})
    page.evaluate("([k, v]) => window.localStorage.setItem(k, v)", [key, bogus])
    cap.label = "after-inject"
    page.goto(BASE + "/protected", wait_until="networkidle")
    page.wait_for_timeout(4000)
    after = ls_dump(page)
    cap.check("bogus token cleared from LocalStorage by tokeninfo computed var", after.get(key, "") == "", f"{key}={after.get(key)!r}")
    cap.check("bogus token does not unlock /protected", "Nice to see you" not in page.locator("body").inner_text())
    shot(page, "03-after-bogus-token")
    ctx.close()

cap.dump(OUT / f"{LABEL}-report.json")
