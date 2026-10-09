"""MCP OAuth on Redis: partial consent -> scope denial, consent denial (app + IdP), invalid scope,
background event, parallel hammering, refresh rotation, revocation.

Usage: check_mcp_oauth_redis.py <backend_base> <frontend_base> <label>
"""

import asyncio
import json
import re
import sys
import time
from urllib.parse import parse_qs, urlencode, urlparse

import httpx
from playwright.sync_api import expect, sync_playwright

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from common import CHROMIUM, W, attach, login, save  # noqa: E402
from mcp_common import AGENT, call, mcp_session, pkce, read  # noqa: E402

BASE = sys.argv[1].rstrip("/")
FRONT = sys.argv[2].rstrip("/")
LABEL = sys.argv[3]
RESOURCE = BASE + "/_reflex/mcp"
MCP = BASE + "/_reflex/mcp/"
CALLBACK = "http://localhost:8638/mcp-return"  # never actually served; intercepted by route()
ev = {"browser": {}}


def authorize_url(md, client_id, scope, challenge, state="st-1"):
    return md["authorization_endpoint"] + "?" + urlencode({
        "client_id": client_id, "redirect_uri": CALLBACK, "response_type": "code",
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
        "resource": RESOURCE, "scope": scope})


def register(client, md, scope, name):
    r = client.post(md["registration_endpoint"], json={
        "client_name": name, "redirect_uris": [CALLBACK],
        "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"],
        "token_endpoint_auth_method": "client_secret_post", "scope": scope})
    return r


def browser_flow(pw_browser, url, *, user="alice", consent="approve", uncheck=None, idp_deny=False, ctx=None, tag=""):
    """Drive the consent flow; return the final callback URL params or the stuck page."""
    own = ctx is None
    ctx = ctx or pw_browser.new_context()
    ctx.route(CALLBACK + "**", lambda route: route.fulfill(status=200, content_type="text/html", body="<p>cb</p>"))
    page = ctx.new_page()
    sink = ev["browser"].setdefault(tag, {})
    attach(page, sink)
    page.set_default_timeout(45_000)
    page.goto(url)
    out = {}
    try:
        login_btn = page.get_by_role("button", name="Login with Generic")
        approve_btn = page.get_by_role("button", name="Approve", exact=True)
        login_btn.or_(approve_btn).first.wait_for(timeout=45_000)
        if login_btn.count():
            if idp_deny:
                page.get_by_role("button", name="Login with Generic").click()
                page.wait_for_url(re.compile("/oauth2/authorize"))
                deny = page.locator('button[name="action"][value="deny"]')
                out["idp_deny_button_count"] = deny.count()
                deny.first.click()
                page.wait_for_timeout(6000)
                out["final_url"] = page.url
                out["final_text"] = page.inner_text("body")[:500]
                page.screenshot(path=str(W / "screenshots" / f"{LABEL}-mcp-{tag}.png"))
                return out
            login(page, user)
        page.wait_for_url(re.compile("/agent-consent"), timeout=45_000)
        expect(page.get_by_role("button", name="Approve", exact=True)).to_be_enabled(timeout=45_000)
        boxes = page.get_by_role("checkbox")
        out["checkbox_states_initial"] = [boxes.nth(i).get_attribute("aria-checked") or boxes.nth(i).get_attribute("data-state") for i in range(boxes.count())]
        if uncheck is not None:
            boxes.nth(uncheck).click()
            page.wait_for_timeout(800)
            out["checkbox_states_after"] = [boxes.nth(i).get_attribute("data-state") for i in range(boxes.count())]
        page.screenshot(path=str(W / "screenshots" / f"{LABEL}-mcp-{tag}-consent.png"))
        page.get_by_role("button", name="Deny" if consent == "deny" else "Approve", exact=True).click()
        page.wait_for_url(lambda u: u.startswith(CALLBACK), timeout=45_000)
        out["callback_params"] = {k: v[0] for k, v in parse_qs(urlparse(page.url).query).items()}
    except Exception as exc:
        out["error"] = f"{type(exc).__name__}: {str(exc)[:300]}"
        out["stuck_url"] = page.url
        out["stuck_text"] = page.inner_text("body")[:500]
        page.screenshot(path=str(W / "screenshots" / f"{LABEL}-mcp-{tag}-stuck.png"))
    finally:
        if own:
            ctx.close()
    return out


async def mcp_checks(token):
    out = {}
    async with mcp_session(MCP, token) as s:
        names = (await call(s, "search_events", {"query": ""}))["value"]["results"]
        n = {e["name"].rsplit(".", 1)[-1]: e["name"] for e in names if "flow_state" not in e["name"]}
        n["reveal"] = next(e["name"] for e in names if e["name"].endswith("flow_state.reveal"))
        out["whoami"] = await call(s, "queue_event", {"event_name": n["whoami"]})
        out["scoped_write"] = await call(s, "queue_event", {"event_name": n["scoped_write"]})
        out["scoped_writes_var"] = await read(s, f"reflex://state/vars/{AGENT}/scoped_writes")
        out["scoped_view"] = await read(s, f"reflex://state/vars/{AGENT}/scoped_view")
        out["private_summary"] = await read(s, "state-resource://entauth___entauth____agent_state/private_summary")
        t = time.time()
        out["start_bg"] = await call(s, "queue_event", {"event_name": n["start_bg"], "payload": {"steps": 4}})
        out["start_bg_latency_s"] = round(time.time() - t, 2)
        out["pending"] = await call(s, "get_pending_updates")
        t = time.time()
        out["start_bg_long"] = await call(s, "queue_event", {"event_name": n["start_bg"], "payload": {"steps": 30}})
        out["start_bg_long_latency_s"] = round(time.time() - t, 2)
        out["start_bg_long"] = str(out["start_bg_long"])[:300]
        out["bg_progress"] = await read(s, f"reflex://state/vars/{AGENT}/bg_progress")
        out["flow_reveal"] = await call(s, "queue_event", {"event_name": next(v for k, v in n.items() if k == "reveal")})
        out["flow_secret"] = await read(s, "reflex://state/vars/reflex___state____state.entauth___entauth____flow_state/secret")
        out["admin_view"] = await read(s, "reflex://state/vars/reflex___state____state.entauth___entauth____flow_state/admin_view")
        out["async_admin_view"] = await read(s, "reflex://state/vars/reflex___state____state.entauth___entauth____flow_state/async_admin_view")
    async with mcp_session(MCP, token) as s1, mcp_session(MCP, token) as s2:
        bump = n["bump"]
        before = (await read(s1, f"reflex://state/vars/{AGENT}/count"))["value"]["value"]
        res = await asyncio.gather(*[call(s, "queue_event", {"event_name": bump, "payload": {"amount": 1}}) for _ in range(15) for s in (s1, s2)])
        out["hammer_errors"] = [str(r["value"])[:200] for r in res if r["is_error"]]
        after = (await read(s1, f"reflex://state/vars/{AGENT}/count"))["value"]["value"]
        out["hammer_delta"] = after - before
    return out


def main():
    with httpx.Client(timeout=30) as client:
        md = client.get(BASE + "/.well-known/oauth-authorization-server").json()
        ev["metadata_scopes"] = md.get("scopes_supported")
        prm = client.get(BASE + "/.well-known/oauth-protected-resource/_reflex/mcp")
        ev["prm"] = {"status": prm.status_code, "body": prm.json() if prm.status_code == 200 else prm.text[:200]}
        reg_a = register(client, md, "profile:read items:write", "Client A both scopes")
        ev["register_a"] = reg_a.status_code
        a = reg_a.json()
        reg_bad = register(client, md, "admin:all", "Client bad scope")
        ev["register_invalid_scope"] = {"status": reg_bad.status_code, "body": reg_bad.text[:300]}
        reg_b = register(client, md, "profile:read", "Client B profile only")
        b = reg_b.json()
        verifier, challenge = pkce()
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=CHROMIUM)
            # 1. partial consent: untick items:write (index 1)
            ctx = browser.new_context()
            r1 = browser_flow(browser, authorize_url(md, a["client_id"], "profile:read items:write", challenge), uncheck=1, ctx=ctx, tag="partial")
            ev["partial_consent"] = r1
            # 2. consent denial at the app consent page (same browser, already logged in)
            r2 = browser_flow(browser, authorize_url(md, a["client_id"], "profile:read", challenge, "st-2"), consent="deny", ctx=ctx, tag="deny")
            ev["consent_deny"] = r2
            # 3. client asks a scope it did not register
            r3 = browser_flow(browser, authorize_url(md, b["client_id"], "items:write", challenge, "st-3"), ctx=ctx, tag="unregistered-scope")
            ev["unregistered_scope"] = r3
            raw = client.get(authorize_url(md, b["client_id"], "items:write", challenge, "st-3b"), follow_redirects=False)
            ev["unregistered_scope_raw"] = {"status": raw.status_code, "location": raw.headers.get("location"), "body": raw.text[:300]}
            ctx.close()
            # 4. denial at the IdP (fresh browser, not logged in to the app)
            r4 = browser_flow(browser, authorize_url(md, a["client_id"], "profile:read", challenge, "st-4"), idp_deny=True, tag="idp-deny")
            ev["idp_deny"] = r4
            browser.close()
        code = (r1.get("callback_params") or {}).get("code")
        if not code:
            raise SystemExit("no code from partial consent: " + json.dumps(r1)[:500])
        tok = client.post(md["token_endpoint"], data={
            "grant_type": "authorization_code", "code": code, "redirect_uri": CALLBACK,
            "client_id": a["client_id"], "client_secret": a["client_secret"],
            "code_verifier": verifier, "resource": RESOURCE})
        ev["exchange"] = {"status": tok.status_code}
        tokens = tok.json()
        ev["granted_scope"] = tokens.get("scope")
        ev["mcp"] = asyncio.run(mcp_checks(tokens["access_token"]))
        ref = client.post(md["token_endpoint"], data={
            "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"],
            "client_id": a["client_id"], "client_secret": a["client_secret"], "resource": RESOURCE})
        ev["refresh"] = {"status": ref.status_code, "scope": ref.json().get("scope")}
        new = ref.json()
        rep = client.post(md["token_endpoint"], data={
            "grant_type": "refresh_token", "refresh_token": tokens["refresh_token"],
            "client_id": a["client_id"], "client_secret": a["client_secret"], "resource": RESOURCE})
        ev["refresh_replay"] = {"status": rep.status_code, "body": rep.text[:200]}
        # revocation
        rv = client.post(md.get("revocation_endpoint", BASE + "/revoke"), data={
            "token": new["access_token"], "client_id": a["client_id"], "client_secret": a["client_secret"]})
        ev["revoke"] = {"status": rv.status_code, "body": rv.text[:200]}
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-03-26", "capabilities": {}, "clientInfo": {"name": "t", "version": "1"}}}
        after = client.post(MCP, json=init, headers={"Authorization": "Bearer " + new["access_token"], "Accept": "application/json, text/event-stream"})
        ev["after_revoke_mcp"] = {"status": after.status_code, "body": after.text[:200]}
        old_access = client.post(MCP, json=init, headers={"Authorization": "Bearer " + tokens["access_token"], "Accept": "application/json, text/event-stream"})
        ev["old_access_after_refresh"] = {"status": old_access.status_code, "body": old_access.text[:200]}
    save(f"mcp-oauth-{LABEL}.json", ev)


main()
summary = {k: v for k, v in ev.items() if k != "browser"}
print(json.dumps(summary, default=str)[:15000])
print("BROWSER_ERRORS", json.dumps({k: {"page_errors": v.get("page_errors"), "http_errors": v.get("http_errors"), "console_err": [c for c in v.get("console", []) if c["type"] == "error"][:6]} for k, v in ev["browser"].items()})[:3000])
