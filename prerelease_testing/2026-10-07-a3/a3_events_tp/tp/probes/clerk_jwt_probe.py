"""reflex-clerk end-to-end at the Python level: can a state validate a real RS256 session JWT?

Mirrors what the package does when a user signs in: clerk_provider(secret_key=...) configures the class-level
statics (cls._secret_key = ..., set_fetch_user_on_auth(False) -> cls._fetch_user = False), the JWKS comes from
a stub ClerkAPIClient assigned at class level (no network), and ClerkState.set_clerk_session(token) runs on a state instance.

Usage: <venv>/bin/python clerk_jwt_probe.py <expected-venv-name>
"""
import json
import os
import sys
import time
import traceback
import warnings

warnings.simplefilter("ignore")
os.environ.pop("CLERK_SECRET_KEY", None)
from authlib.jose import JsonWebKey, jwt
from cryptography.hazmat.primitives.asymmetric import rsa

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
priv = JsonWebKey.import_key(key, {"kty": "RSA", "kid": "ins_test"})
pub_jwk = priv.as_dict(is_private=False)
pub_jwk["kid"] = "ins_test"
pub_jwk["alg"] = "RS256"
pub_jwk["use"] = "sig"

class _Jwks:
    def dict(self):
        return {"keys": [pub_jwk]}


class _StubClient(__import__("reflex_clerk.clerk_client.clerk_client", fromlist=["ClerkAPIClient"]).ClerkAPIClient):
    def __init__(self):  # no network, no real key
        pass

    def get_jwks(self):
        return _Jwks()

    def get_user(self, user_id):
        return None


token = jwt.encode({"alg": "RS256", "kid": "ins_test"}, {"sub": "user_123", "exp": int(time.time()) + 600}, priv).decode()

import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
import reflex_clerk as clerk
from reflex_clerk.lib.clerk_provider import ClerkState

clerk.clerk_provider(rx.text("x"), publishable_key="pk_test_x", secret_key="sk_test_123")
ClerkState.set_fetch_user_on_auth(False)
ClerkState._clerk_api_client = _StubClient()  # class-level static, as the package itself does
try:
    keys = ClerkState.jwt_public_keys  # the package evaluates this property before validating sessions
    print("ClerkState.jwt_public_keys ->", type(keys).__name__, repr(keys)[:90])
except BaseException as e:  # noqa: BLE001
    print("ClerkState.jwt_public_keys -> EXC %s: %s" % (type(e).__name__, str(e)[:160]))
root = rx.State(_reflex_internal_init=True)
inst = root.get_substate(ClerkState.get_full_name().split(".")[1:])
print("class-level _secret_key / _fetch_user:", repr(ClerkState._secret_key)[:70], "|", repr(ClerkState._fetch_user)[:70])
print("instance   _secret_key / _fetch_user:", repr(inst._secret_key)[:70], "|", repr(inst._fetch_user)[:70])
try:
    ClerkState.set_clerk_session.fn(inst, token)
    err = None
except BaseException as e:  # noqa: BLE001
    err = "%s: %s" % (type(e).__name__, str(e)[:160])
print("RESULT set_clerk_session(valid RS256 JWT): is_signed_in=%r user_id=%r auth_error=%r exc=%s" % (inst.is_signed_in, inst.user_id, inst.auth_error, err))
