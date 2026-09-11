"""A minimal, self-contained OIDC provider for testing reflex-enterprise auth.

Implements discovery, JWKS, authorization code + PKCE, token, refresh, userinfo
and RP-initiated logout. Auto-approves every authorization request.

Usage: python fake_idp.py <port>
"""

import base64
import hashlib
import json
import secrets
import sys
import time
from urllib.parse import urlencode

from cryptography.hazmat.primitives.asymmetric import rsa
from joserfc import jwt
from joserfc.jwk import RSAKey
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9899
ISSUER = f"http://localhost:{PORT}"
CLIENT_ID = "test-client"
CLIENT_SECRET = "test-secret"

_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KEY = RSAKey.import_key(
    _priv.private_bytes(
        encoding=__import__("cryptography.hazmat.primitives.serialization", fromlist=["x"]).Encoding.PEM,
        format=__import__("cryptography.hazmat.primitives.serialization", fromlist=["x"]).PrivateFormat.PKCS8,
        encryption_algorithm=__import__("cryptography.hazmat.primitives.serialization", fromlist=["x"]).NoEncryption(),
    ).decode()
)
KID = "test-key-1"

CODES: dict[str, dict] = {}
TOKENS: dict[str, dict] = {}
REFRESH: dict[str, dict] = {}
LOG: list[str] = []


def b64u(raw: bytes) -> str:
    """Base64url-encode without padding."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def at_hash(access_token: str) -> str:
    """Compute the OIDC at_hash for an RS256 id_token."""
    return b64u(hashlib.sha256(access_token.encode()).digest()[:16])


def make_id_token(sub: str, nonce: str | None, access_token: str, extra: dict | None = None) -> str:
    """Mint a signed id_token."""
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "sub": sub,
        "aud": CLIENT_ID,
        "iat": now,
        "exp": now + 3600,
        "email": f"{sub}@example.test",
        "name": f"User {sub}",
        "preferred_username": sub,
        "at_hash": at_hash(access_token),
    }
    if nonce:
        claims["nonce"] = nonce
    if extra:
        claims.update(extra)
    return jwt.encode({"alg": "RS256", "kid": KID}, claims, KEY)


async def discovery(request: Request):
    """OIDC discovery document."""
    LOG.append("GET /.well-known/openid-configuration")
    return JSONResponse({
        "issuer": ISSUER,
        "authorization_endpoint": f"{ISSUER}/authorize",
        "token_endpoint": f"{ISSUER}/token",
        "userinfo_endpoint": f"{ISSUER}/userinfo",
        "jwks_uri": f"{ISSUER}/jwks",
        "end_session_endpoint": f"{ISSUER}/logout",
        "revocation_endpoint": f"{ISSUER}/revoke",
        "response_types_supported": ["code"],
        "subject_types_supported": ["public"],
        "id_token_signing_alg_values_supported": ["RS256"],
        "scopes_supported": ["openid", "profile", "email", "offline_access"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"],
        "code_challenge_methods_supported": ["S256"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "claims_supported": ["sub", "iss", "aud", "exp", "iat", "email", "name"],
    })


async def jwks(request: Request):
    """Public JWKS."""
    LOG.append("GET /jwks")
    pub = KEY.as_dict(private=False)
    pub["kid"] = KID
    pub["use"] = "sig"
    pub["alg"] = "RS256"
    return JSONResponse({"keys": [pub]})


async def authorize(request: Request):
    """Auto-approving authorization endpoint."""
    q = dict(request.query_params)
    LOG.append(f"GET /authorize {json.dumps(q)}")
    code = secrets.token_urlsafe(16)
    CODES[code] = {
        "nonce": q.get("nonce"),
        "code_challenge": q.get("code_challenge"),
        "code_challenge_method": q.get("code_challenge_method"),
        "redirect_uri": q.get("redirect_uri"),
        "scope": q.get("scope", ""),
        "sub": "alice",
    }
    params = {"code": code}
    if q.get("state"):
        params["state"] = q["state"]
    return RedirectResponse(f"{q['redirect_uri']}?{urlencode(params)}", status_code=302)


def _issue(sub: str, nonce: str | None, scope: str):
    """Mint an access/refresh/id token triple."""
    access = secrets.token_urlsafe(24)
    refresh = secrets.token_urlsafe(24)
    TOKENS[access] = {"sub": sub, "exp": time.time() + 3600}
    REFRESH[refresh] = {"sub": sub, "nonce": nonce, "scope": scope}
    body = {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": refresh,
        "id_token": make_id_token(sub, nonce, access),
        "scope": scope,
    }
    return body


async def token(request: Request):
    """Token endpoint: authorization_code and refresh_token grants."""
    form = dict(await request.form())
    LOG.append(f"POST /token grant={form.get('grant_type')} keys={sorted(form)}")
    gt = form.get("grant_type")
    if gt == "authorization_code":
        code = form.get("code")
        rec = CODES.pop(code, None)
        if rec is None:
            return JSONResponse({"error": "invalid_grant", "error_description": "unknown code"}, 400)
        verifier = form.get("code_verifier")
        if rec["code_challenge"]:
            if not verifier:
                LOG.append("PKCE FAIL: challenge issued but no verifier sent")
                return JSONResponse({"error": "invalid_grant", "error_description": "missing code_verifier"}, 400)
            calc = b64u(hashlib.sha256(verifier.encode()).digest())
            if calc != rec["code_challenge"]:
                LOG.append(f"PKCE FAIL: {calc} != {rec['code_challenge']}")
                return JSONResponse({"error": "invalid_grant", "error_description": "PKCE mismatch"}, 400)
            LOG.append("PKCE OK")
        return JSONResponse(_issue(rec["sub"], rec["nonce"], rec["scope"]))
    if gt == "refresh_token":
        rec = REFRESH.pop(form.get("refresh_token"), None)
        if rec is None:
            return JSONResponse({"error": "invalid_grant", "error_description": "unknown refresh token"}, 400)
        LOG.append("REFRESH OK")
        return JSONResponse(_issue(rec["sub"], rec["nonce"], rec["scope"]))
    return JSONResponse({"error": "unsupported_grant_type"}, 400)


async def userinfo(request: Request):
    """Userinfo endpoint."""
    auth = request.headers.get("authorization", "")
    tok = auth.removeprefix("Bearer ").strip()
    rec = TOKENS.get(tok)
    LOG.append(f"GET /userinfo valid={rec is not None}")
    if rec is None:
        return JSONResponse({"error": "invalid_token"}, 401)
    return JSONResponse({
        "sub": rec["sub"],
        "email": f"{rec['sub']}@example.test",
        "name": f"User {rec['sub']}",
        "preferred_username": rec["sub"],
    })


async def logout(request: Request):
    """RP-initiated logout."""
    q = dict(request.query_params)
    LOG.append(f"GET /logout {json.dumps(q)}")
    target = q.get("post_logout_redirect_uri") or f"{ISSUER}/loggedout"
    return RedirectResponse(target, status_code=302)


async def loggedout(request: Request):
    """Terminal logout page."""
    return JSONResponse({"logged_out": True})


async def log(request: Request):
    """Return the request log for assertions."""
    return JSONResponse({"log": LOG})


async def expire(request: Request):
    """Force-expire all issued access tokens (to exercise refresh)."""
    for v in TOKENS.values():
        v["exp"] = 0
    LOG.append("ADMIN expire-all")
    return JSONResponse({"expired": len(TOKENS)})


app = Starlette(routes=[
    Route("/.well-known/openid-configuration", discovery),
    Route("/jwks", jwks),
    Route("/authorize", authorize),
    Route("/token", token, methods=["POST"]),
    Route("/userinfo", userinfo),
    Route("/logout", logout),
    Route("/loggedout", loggedout),
    Route("/_log", log),
    Route("/_expire", expire, methods=["POST"]),
])

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
