"""Debug: follow the MCP OAuth authorize -> login -> IdP -> consent navigation chain."""
import json, re, sys, time
from urllib.parse import urlencode
import httpx
from playwright.sync_api import sync_playwright
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import CHROMIUM, W, attach, save
from mcp_common import pkce

BASE = sys.argv[1].rstrip("/"); LABEL = sys.argv[2]
CALLBACK = "http://localhost:8358/mcp-return"
md = httpx.get(BASE + "/.well-known/oauth-authorization-server").json()
reg = httpx.post(md["registration_endpoint"], json={"client_name": "dbg", "redirect_uris": [CALLBACK], "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"], "token_endpoint_auth_method": "client_secret_post", "scope": "profile:read items:write"}).json()
v, ch = pkce()
url = md["authorization_endpoint"] + "?" + urlencode({"client_id": reg["client_id"], "redirect_uri": CALLBACK, "response_type": "code", "code_challenge": ch, "code_challenge_method": "S256", "state": "s", "resource": BASE + "/_reflex/mcp", "scope": "profile:read items:write"})
navs = []
obs = {}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROMIUM)
    ctx = b.new_context()
    ctx.route(CALLBACK + "**", lambda r: r.fulfill(status=200, content_type="text/html", body="<p>cb</p>"))
    page = ctx.new_page()
    attach(page, obs)
    page.on("framenavigated", lambda f: navs.append([round(time.time(), 2), f.url[:220]]) if f == page.main_frame else None)
    page.goto(url)
    page.wait_for_url(re.compile(r"localhost:3340/login"), timeout=45000)
    page.get_by_role("button", name="Login with Generic").click()
    page.wait_for_url(re.compile("/oauth2/authorize"), timeout=45000)
    page.locator('button[name="sub"][value="alice"]').click()
    page.wait_for_timeout(15000)
    obs["final_url"] = page.url
    obs["final_text"] = page.inner_text("body")[:300]
    obs["session_storage"] = page.evaluate("() => Object.fromEntries(Object.entries(sessionStorage))")
    page.screenshot(path=str(W / "screenshots" / f"{LABEL}-consent-nav.png"))
    b.close()
obs["navs"] = navs
save(f"debug-consent-nav-{LABEL}.json", obs)
for n in navs: print(n)
print("FINAL", obs["final_url"], "|", obs["final_text"][:200].replace("\n", " "))
print("console errors:", [c for c in obs["console"] if c["type"] in ("error", "warning")][:8])
print("http errors:", obs["http_errors"][:8], "failed:", [f for f in obs["failed_requests"] if "pico" not in f["url"]][:8])
