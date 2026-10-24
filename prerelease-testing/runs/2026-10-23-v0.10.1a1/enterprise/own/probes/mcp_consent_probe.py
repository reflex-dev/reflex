"""Focused repro for the MCP OAuth consent flow on Redis (rxe 0.9.8): navigation timeline after the IdP login.

Usage (cwd = $WORK/auth/scripts so common/mcp_common import): mcp_consent_probe.py <backend_base> <frontend_base> <label>
Registers an OAuth client, opens the authorization URL in Chromium, logs in at the mock IdP, then records every main-frame
navigation, websocket event name sent, console error and the final URL/text for 20 s. Expected: /agent-consent with an
Approve button. Writes ../logs/mcp-consent-<label>.json and ../screenshots/<label>-mcp-consent-final.png.
"""
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CHROMIUM, W, login  # noqa: E402

BASE, FRONT, LABEL = sys.argv[1].rstrip("/"), sys.argv[2].rstrip("/"), sys.argv[3]
RESOURCE = BASE + "/_reflex/mcp"
CALLBACK = "http://localhost:8638/mcp-return"
out = {"label": LABEL, "nav": [], "ws_sent": [], "console": [], "http_errors": []}
t0 = time.time()


def ts():
    return round(time.time() - t0, 2)


with httpx.Client(timeout=30) as client:
    md = client.get(BASE + "/.well-known/oauth-authorization-server").json()
    reg = client.post(md["registration_endpoint"], json={"client_name": "consent probe", "redirect_uris": [CALLBACK],
                      "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
                      "token_endpoint_auth_method": "client_secret_post", "scope": "profile:read items:write"}).json()
url = md["authorization_endpoint"] + "?" + urlencode({"client_id": reg["client_id"], "redirect_uri": CALLBACK, "response_type": "code",
      "code_challenge": "E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM", "code_challenge_method": "S256", "state": "st-probe",
      "resource": RESOURCE, "scope": "profile:read items:write"})
with sync_playwright() as pw:
    browser = pw.chromium.launch(executable_path=CHROMIUM)
    ctx = browser.new_context()
    ctx.route(CALLBACK + "**", lambda route: route.fulfill(status=200, content_type="text/html", body="<p>cb</p>"))
    page = ctx.new_page()
    page.on("framenavigated", lambda f: f == page.main_frame and out["nav"].append((ts(), f.url[:160])))
    page.on("console", lambda m: m.type == "error" and out["console"].append((ts(), m.text[:160])))
    page.on("response", lambda r: r.status >= 400 and out["http_errors"].append((ts(), r.status, r.url[:120])))

    def on_ws(ws):
        def sent(payload):
            for m in re.finditer(r'"name":\s*"([^"]+)"', payload if isinstance(payload, str) else payload.decode("utf-8", "replace")):
                out["ws_sent"].append((ts(), m.group(1).split(".")[-1]))
        ws.on("framesent", sent)
    page.on("websocket", on_ws)
    page.goto(url)
    page.wait_for_url(re.compile("/login"), timeout=30000)
    out["login_url"] = page.url[:300]
    login(page, "alice")
    page.wait_for_timeout(20000)
    out["final_url"] = page.url[:300]
    out["final_text"] = page.inner_text("body")[:300]
    out["approve_buttons"] = page.get_by_role("button", name="Approve", exact=True).count()
    out["cookies"] = sorted(c["name"] for c in ctx.cookies())
    out["session_storage"] = page.evaluate("() => Object.fromEntries(Object.entries(sessionStorage).map(([k,v]) => [k, v.slice(0, 40)]))")
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-mcp-consent-final.png"))
    browser.close()
(W / "logs" / f"mcp-consent-{LABEL}.json").write_text(json.dumps(out, indent=1, default=str))
print("NAV:", json.dumps(out["nav"]))
print("WS_SENT:", json.dumps(out["ws_sent"]))
print("CONSOLE:", json.dumps(out["console"][:6]))
print("HTTP>=400:", json.dumps(out["http_errors"][:6]))
print(f"FINAL url={out['final_url']} approve_buttons={out['approve_buttons']} cookies={out['cookies']} ss_keys={list(out['session_storage'])}")
print(f"RESULT {LABEL}: {'PASS' if '/agent-consent' in out['final_url'] and out['approve_buttons'] else 'FAIL'}")
