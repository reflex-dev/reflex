"""ISSUE 2 probe: where does the MCP OAuth authorization endpoint send the browser in dev (frontend 3393 / backend 8393)?

Registers a client, GETs the authorization endpoint without following redirects, prints the Location and what it serves.
Usage: mcp_consent_probe.py [backend=http://localhost:8393]
"""
import base64, hashlib, json, os, sys
from urllib.parse import urlencode
import httpx

B = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8393"
c = httpx.Client(timeout=20, trust_env=False)
md = c.get(B + "/.well-known/oauth-authorization-server").json()
print("issuer", md["issuer"], "authorization_endpoint", md["authorization_endpoint"])
reg = c.post(md["registration_endpoint"], json={"client_name": "probe", "redirect_uris": ["http://localhost:8398/mcp-return"],
      "grant_types": ["authorization_code", "refresh_token"], "response_types": ["code"], "token_endpoint_auth_method": "client_secret_post", "scope": "profile:read"})
print("register", reg.status_code)
cid = reg.json()["client_id"]
v = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
ch = base64.urlsafe_b64encode(hashlib.sha256(v.encode()).digest()).rstrip(b"=").decode()
q = urlencode({"client_id": cid, "redirect_uri": "http://localhost:8398/mcp-return", "response_type": "code", "code_challenge": ch,
               "code_challenge_method": "S256", "state": "s", "resource": B + "/_reflex/mcp", "scope": "profile:read"})
r = c.get(md["authorization_endpoint"] + "?" + q)
loc = r.headers.get("location", "")
print("authorize ->", r.status_code, "Location:", loc[:160])
t = c.get(loc)
print("consent URL ->", t.status_code, t.headers.get("content-type"), repr(t.text[:80]))
