"""FINDING-002 follow-through: does the MCP endpoint answer once the prod server starts?

Prints the RFC 8414 metadata, the protected-resource metadata, the unauthenticated MCP
initialize response (status + WWW-Authenticate) and an OAuth dynamic client registration.
Usage: mcp_probe.py <base url, e.g. http://localhost:8380>
"""

import json
import sys

import httpx

B = sys.argv[1].rstrip("/")
c = httpx.Client(timeout=20, trust_env=False)


def show(name, r):
    ct = r.headers.get("content-type", "")
    body = r.text[:300] if "json" in ct else repr(r.text[:80])
    print(f"{name}: {r.status_code} ct={ct} body={body}")


r = c.get(B + "/.well-known/oauth-authorization-server")
show("as-metadata", r)
md = r.json() if "json" in r.headers.get("content-type", "") else {}
for path in ("/.well-known/oauth-protected-resource/_reflex/mcp", "/.well-known/oauth-protected-resource"):
    show("prm " + path, c.get(B + path))
init = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {"protocolVersion": "2025-06-18", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}},
}
hdr = {"accept": "application/json, text/event-stream", "content-type": "application/json"}
for path in ("/_reflex/mcp", "/_reflex/mcp/"):
    r = c.post(B + path, json=init, headers=hdr)
    print(f"POST {path}: {r.status_code} www-authenticate={r.headers.get('www-authenticate')!r} body={r.text[:200]!r}")
if md.get("registration_endpoint"):
    reg = c.post(
        md["registration_endpoint"],
        json={
            "client_name": "probe",
            "redirect_uris": ["http://localhost:8394/cb"],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "client_secret_post",
        },
    )
    print("register", reg.status_code, json.dumps({k: v for k, v in reg.json().items() if k in ("client_id_issued_at", "redirect_uris")}) if reg.status_code < 300 else reg.text[:200])

# Anonymous-session path (MCPPlugin without AuthPlugin): grant a token, then drive MCP.
g = c.post(B + "/_reflex/auth/token")
print("token grant", g.status_code, sorted(g.json()) if "json" in g.headers.get("content-type", "") else g.text[:120])
tok = g.json().get("access_token") if g.status_code == 200 else None
if tok:
    h = {**hdr, "authorization": "Bearer " + tok}
    r = c.post(B + "/_reflex/mcp/", json=init, headers=h)
    sid = r.headers.get("mcp-session-id")
    print("initialize", r.status_code, "session" if sid else "no-session", r.text[:160].replace("\n", " "))
    if r.status_code == 200 and r.text.startswith("{"):
        ins = json.loads(r.text)["result"].get("instructions") or ""
        print("instructions server_url/pages lines:", [ln for ln in ins.splitlines() if "served at" in ln or ln.lstrip().startswith("- `/") or "http" in ln][:6])
    if True:
        if sid:
            h["mcp-session-id"] = sid
        c.post(B + "/_reflex/mcp/", json={"jsonrpc": "2.0", "method": "notifications/initialized"}, headers=h)
        r = c.post(B + "/_reflex/mcp/", json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"}, headers=h)
        print("tools/list", r.status_code, r.text[:400].replace("\n", " "))
        r = c.post(B + "/_reflex/mcp/", json={"jsonrpc": "2.0", "id": 3, "method": "resources/list"}, headers=h)
        print("resources/list", r.status_code, r.text[:600].replace("\n", " "))
        tools = [t["name"] for t in json.loads(r0.text)["result"]["tools"]] if (r0 := c.post(B + "/_reflex/mcp/", json={"jsonrpc": "2.0", "id": 4, "method": "tools/list"}, headers=h)).status_code == 200 and r0.text.startswith("{") else []
        print("tool names", tools)
        for t in tools:
            if "bump" in t or "event" in t:
                r = c.post(B + "/_reflex/mcp/", json={"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": t, "arguments": {}}}, headers=h)
                print("tools/call", t, r.status_code, r.text[:400].replace("\n", " "))
                break
