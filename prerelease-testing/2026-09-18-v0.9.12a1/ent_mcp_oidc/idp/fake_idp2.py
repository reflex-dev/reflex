"""A multi-client OIDC provider for testing the reflex-enterprise OIDC demo.

Extends idp/fake_idp.py (same cluster) with:
  * multiple registered clients (the demo drives two providers at once),
  * ``aud`` taken from the authorizing client instead of a constant,
  * a configurable ``expires_in`` (env ``IDP_EXPIRES_IN``) so the
    proactive access-token refresh fires within a test run,
  * ``/_log`` (request log) and ``/_expire`` (invalidate access tokens).

Auto-approves every authorization request as user ``alice``.

Usage: python fake_idp2.py <port>
"""

import base64
import hashlib
import json
import os
import secrets
import sys
import time
from urllib.parse import urlencode

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from joserfc import jwt
from joserfc.jwk import RSAKey
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, RedirectResponse
from starlette.routing import Route

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 9670
ISSUER = f"http://localhost:{PORT}"
EXPIRES_IN = int(os.environ.get("IDP_EXPIRES_IN", "3600"))

# client_id -> client_secret
CLIENTS = {
    "okta-client": "okta-secret",
    "databricks-client": "databricks-secret",
    "test-client": "test-secret",
}

_priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
KEY = RSAKey.import_key(
    _priv.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
)
KID = "test-key-1"

CODES: dict[str, dict] = {}
TOKENS: dict[str, dict] = {}
REFRESH: dict[str, dict] = {}
LOG: list[str] = []


def note(msg: str) -> None:
    """Record and echo one request-log line."""
    LOG.append(f"{time.strftime('%H:%M:%S')} {msg}")
    print(LOG[-1], flush=True)


def b64u(raw: bytes) -> str:
    """Base64url-encode without padding."""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def at_hash(access_token: str) -> str:
    """Compute the OIDC at_hash for an RS256 id_token."""
    return b64u(hashlib.sha256(access_token.encode()).digest()[:16])


def make_id_token(sub: str, aud: str, nonce: str | None, access_token: str) -> str:
    """Mint a signed id_token for one client."""
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "sub": sub,
        "aud": aud,
        "iat": now,
        "exp": now + max(EXPIRES_IN, 300),
        "email": f"{sub}@example.test",
        "name": f"User {sub}",
        "preferred_username": sub,
        "at_hash": at_hash(access_token),
    }
    if nonce:
        claims["nonce"] = nonce
    return jwt.encode({"alg": "RS256", "kid": KID}, claims, KEY)


async def discovery(request: Request):
    """OIDC discovery document."""
    note("GET /.well-known/openid-configuration")
    return JSONResponse(
        {
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
            "scopes_supported": [
                "openid",
                "profile",
                "email",
                "offline_access",
                "all-apis",
            ],
            "token_endpoint_auth_methods_supported": [
                "client_secret_post",
                "client_secret_basic",
            ],
            "code_challenge_methods_supported": ["S256"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "claims_supported": ["sub", "iss", "aud", "exp", "iat", "email", "name"],
        }
    )


async def jwks(request: Request):
    """Public JWKS."""
    note("GET /jwks")
    pub = KEY.as_dict(private=False)
    pub["kid"] = KID
    pub["use"] = "sig"
    pub["alg"] = "RS256"
    return JSONResponse({"keys": [pub]})


async def authorize(request: Request):
    """Auto-approving authorization endpoint."""
    q = dict(request.query_params)
    note(f"GET /authorize {json.dumps(q)}")
    code = secrets.token_urlsafe(16)
    CODES[code] = {
        "nonce": q.get("nonce"),
        "code_challenge": q.get("code_challenge"),
        "code_challenge_method": q.get("code_challenge_method"),
        "redirect_uri": q.get("redirect_uri"),
        "scope": q.get("scope", ""),
        "client_id": q.get("client_id", ""),
        "sub": "alice",
    }
    params = {"code": code}
    if q.get("state"):
        params["state"] = q["state"]
    return RedirectResponse(f"{q['redirect_uri']}?{urlencode(params)}", status_code=302)


def _issue(sub: str, aud: str, nonce: str | None, scope: str):
    """Mint an access/refresh/id token triple."""
    access = secrets.token_urlsafe(24)
    refresh = secrets.token_urlsafe(24)
    TOKENS[access] = {"sub": sub, "exp": time.time() + EXPIRES_IN, "aud": aud}
    REFRESH[refresh] = {"sub": sub, "nonce": nonce, "scope": scope, "aud": aud}
    return {
        "access_token": access,
        "token_type": "Bearer",
        "expires_in": EXPIRES_IN,
        "refresh_token": refresh,
        "id_token": make_id_token(sub, aud, nonce, access),
        "scope": scope,
    }


def _client_from(form: dict, request: Request) -> str:
    """Resolve the authenticating client id from the token request."""
    if form.get("client_id"):
        return form["client_id"]
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("basic "):
        raw = base64.b64decode(auth.split(" ", 1)[1]).decode()
        return raw.split(":", 1)[0]
    return ""


async def token(request: Request):
    """Token endpoint: authorization_code and refresh_token grants."""
    form = dict(await request.form())
    client_id = _client_from(form, request)
    note(
        f"POST /token grant={form.get('grant_type')} client={client_id} "
        f"keys={sorted(form)}"
    )
    gt = form.get("grant_type")
    if gt == "authorization_code":
        rec = CODES.pop(form.get("code"), None)
        if rec is None:
            return JSONResponse(
                {"error": "invalid_grant", "error_description": "unknown code"}, 400
            )
        verifier = form.get("code_verifier")
        if rec["code_challenge"]:
            if not verifier:
                note("PKCE FAIL: challenge issued but no verifier sent")
                return JSONResponse(
                    {
                        "error": "invalid_grant",
                        "error_description": "missing code_verifier",
                    },
                    400,
                )
            calc = b64u(hashlib.sha256(verifier.encode()).digest())
            if calc != rec["code_challenge"]:
                note(f"PKCE FAIL: {calc} != {rec['code_challenge']}")
                return JSONResponse(
                    {"error": "invalid_grant", "error_description": "PKCE mismatch"},
                    400,
                )
            note(f"PKCE OK ({client_id})")
        aud = rec["client_id"] or client_id
        return JSONResponse(_issue(rec["sub"], aud, rec["nonce"], rec["scope"]))
    if gt == "refresh_token":
        rec = REFRESH.pop(form.get("refresh_token"), None)
        if rec is None:
            note("REFRESH FAIL: unknown refresh token")
            return JSONResponse(
                {
                    "error": "invalid_grant",
                    "error_description": "unknown refresh token",
                },
                400,
            )
        note(f"REFRESH OK ({rec['aud']}) scope={form.get('scope')!r}")
        return JSONResponse(
            _issue(rec["sub"], rec["aud"], rec["nonce"], form.get("scope") or rec["scope"])
        )
    return JSONResponse({"error": "unsupported_grant_type"}, 400)


async def userinfo(request: Request):
    """Userinfo endpoint."""
    tok = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    rec = TOKENS.get(tok)
    valid = rec is not None and rec["exp"] > time.time()
    note(f"GET /userinfo valid={valid}")
    if not valid:
        return JSONResponse({"error": "invalid_token"}, 401)
    return JSONResponse(
        {
            "sub": rec["sub"],
            "email": f"{rec['sub']}@example.test",
            "name": f"User {rec['sub']}",
            "preferred_username": rec["sub"],
            # The demo renders rx.moment(userinfo["iat"|"exp"], unix=True), so
            # serve them here as Databricks-style userinfo does.
            "iat": int(rec["exp"] - EXPIRES_IN),
            "exp": int(rec["exp"]),
        }
    )


async def revoke(request: Request):
    """Token revocation endpoint."""
    form = dict(await request.form())
    note(f"POST /revoke keys={sorted(form)}")
    TOKENS.pop(form.get("token", ""), None)
    REFRESH.pop(form.get("token", ""), None)
    return JSONResponse({})


async def logout(request: Request):
    """RP-initiated logout."""
    q = dict(request.query_params)
    note(f"GET /logout {json.dumps(q)}")
    target = q.get("post_logout_redirect_uri") or f"{ISSUER}/loggedout"
    return RedirectResponse(target, status_code=302)


async def loggedout(request: Request):
    """Terminal logout page."""
    return JSONResponse({"logged_out": True})


async def log(request: Request):
    """Return the request log for assertions."""
    return JSONResponse(
        {"log": LOG, "tokens": len(TOKENS), "refresh": len(REFRESH),
         "expires_in": EXPIRES_IN}
    )


async def expire(request: Request):
    """Force-expire every issued access token (to exercise refresh)."""
    for v in TOKENS.values():
        v["exp"] = 0
    note("ADMIN expire-all")
    return JSONResponse({"expired": len(TOKENS)})


app = Starlette(
    routes=[
        Route("/.well-known/openid-configuration", discovery),
        Route("/jwks", jwks),
        Route("/authorize", authorize),
        Route("/token", token, methods=["POST"]),
        Route("/userinfo", userinfo),
        Route("/revoke", revoke, methods=["POST"]),
        Route("/logout", logout),
        Route("/loggedout", loggedout),
        Route("/_log", log),
        Route("/_expire", expire, methods=["POST"]),
    ]
)

if __name__ == "__main__":
    import uvicorn

    print(f"fake IdP on {ISSUER} expires_in={EXPIRES_IN}", flush=True)
    uvicorn.run(app, host="127.0.0.1", port=PORT, log_level="warning")
