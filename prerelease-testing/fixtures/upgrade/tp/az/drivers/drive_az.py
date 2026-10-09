"""Drive reflex-azure-auth against the mock IdP. Usage: drive_az.py <base> <label>

A deep link /protected?x=1&y=two  (anonymous) -> Guard on_load -> AzureAuthState.redirect_to_login -> IdP -> callback on_load
  (auth_callback reads code/state from self.router.url.query_parameters) -> back to /protected?x=1&y=two with a token.
B fresh context: / -> click "Login with Microsoft" (event) -> IdP -> callback -> back to /.
C signed in (from A): client nav / -> /protected?x=nav: Guard on_load sees /protected?x=nav, no redirect.
"""

import json
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import playwright  # VENV_GUARD

assert ("/envs/" + __import__("os").environ.get("DRIVER", "driver") + "/") in playwright.__file__, playwright.__file__
from playwright.sync_api import sync_playwright

IDP = "http://localhost:8638"
HERE = Path(__file__).resolve().parent
base, label = sys.argv[1], sys.argv[2]


PUMP = {}


def wait_for(fn, timeout=30.0):
    """Poll fn(); pumps Playwright's event loop between polls (time.sleep starves it: page.url would never update)."""
    end = time.time() + timeout
    while time.time() < end:
        try:
            v = fn()
            if v:
                return v
        except Exception:
            pass
        PUMP["page"].wait_for_timeout(250)
    return None


def txt(p, sel):
    try:
        return p.locator(sel).first.inner_text(timeout=1500)
    except Exception:
        return None


def capture(p, log, name):
    PUMP["page"] = p
    p.on("console", lambda m: m.type == "error" and log.append({"ctx": name, "kind": "console", "text": m.text[:200]}))
    p.on("pageerror", lambda e: log.append({"ctx": name, "kind": "pageerror", "text": str(e)[:200]}))
    p.on("response", lambda r: r.status >= 400 and log.append({"ctx": name, "kind": "http", "status": r.status, "url": r.url[:120]}))
    p.on("framenavigated", lambda f: f == p.main_frame and log.append({"ctx": name, "kind": "nav", "url": f.url[:160]}))


def authorize(p, user="alice"):
    p.wait_for_url(IDP + "/oauth2/authorize**", timeout=30000)
    q = dict(x.split("=", 1) for x in urlparse(p.url).query.split("&") if "=" in x)
    p.fill("#subject-input", user)
    p.get_by_role("button", name="Authorize", exact=True).click()
    return q.get("redirect_uri")


res = {}
log = []
with sync_playwright() as pw:
    b = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context()
    p = ctx.new_page()
    capture(p, log, "A")
    p.goto(base + "/protected?x=1&y=two")
    r = {"redirect_uri": authorize(p)}
    r["back"] = bool(wait_for(lambda: urlparse(p.url).path.rstrip("/") == "/protected" and txt(p, "#has_token") == "true", 40))
    r["final_url"] = p.url
    r["loads"] = txt(p, "#loads")
    r["error"] = txt(p, "#error")
    r["ok"] = r["back"] and urlparse(p.url).query == "x=1&y=two" and (r["redirect_uri"] or "").startswith("http%3A%2F%2Flocalhost")
    res["A_deeplink"] = r
    p.goto(base + "/")
    wait_for(lambda: txt(p, "#has_token") == "true", 20)
    p.click("#nav-protected")
    wait_for(lambda: "x=nav" in (txt(p, "#loads") or ""), 20)
    p.wait_for_timeout(1500)
    res["C_clientnav"] = {"url": p.url, "loads": txt(p, "#loads"), "ok": urlparse(p.url).path.rstrip("/") == "/protected" and (txt(p, "#loads") or "").replace("/protected/?", "/protected?").endswith("/protected?x=nav")}
    p.screenshot(path=str(HERE.parent / "shots" / f"{label}-A.png"))
    ctx.close()
    ctx = b.new_context()
    p = ctx.new_page()
    capture(p, log, "B")
    p.goto(base + "/")
    wait_for(lambda: txt(p, "#has_token") == "false", 20)
    p.wait_for_timeout(1000)
    p.get_by_role("button", name="Login with Microsoft").click()
    r = {"redirect_uri": authorize(p)}
    r["back"] = bool(wait_for(lambda: urlparse(p.url).path == "/" and txt(p, "#has_token") == "true", 40))
    r["final_url"] = p.url
    r["ok"] = r["back"]
    res["B_button"] = r
    ctx.close()
    b.close()
res["errors"] = [e for e in log if e["kind"] != "nav"]
res["navs"] = [e["url"] for e in log if e["kind"] == "nav"]
(HERE.parent / "logs" / f"{label}-az.json").write_text(json.dumps(res, indent=1))
print(json.dumps({k: (v.get("ok") if isinstance(v, dict) else len(v)) for k, v in res.items()}))
print(json.dumps(res["A_deeplink"])[:400])
print("SUMMARY", label, "A", res["A_deeplink"]["ok"], "B", res["B_button"]["ok"], "C", res["C_clientnav"]["ok"], "errors", len(res["errors"]))
