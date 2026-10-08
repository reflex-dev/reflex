"""reflex-clerk 1.0.3 keeps "static class variables" as underscore State attributes.

Usage: <venv>/bin/python clerk_probe.py <expected-venv-name>
"""
import os
import sys
import warnings

warnings.simplefilter("ignore")
os.environ.pop("CLERK_SECRET_KEY", None)
import reflex as rx

assert f"/scratchpad/envs/{sys.argv[1]}/" in rx.__file__, rx.__file__
import reflex_clerk as clerk
from reflex_clerk.lib.clerk_provider import ClerkState


def show(label, fn):
    try:
        v = fn()
        print(f"{label}: {type(v).__name__} {v!r}"[:300])
    except Exception as e:  # noqa: BLE001
        print(f"{label}: EXC {type(e).__name__}: {e}"[:300])


show("ClerkState._jwt_public_keys (class)", lambda: ClerkState._jwt_public_keys)
show("ClerkState._secret_key (class, before provider)", lambda: ClerkState._secret_key)
show("ClerkState.secret_key (class property, no key configured)", lambda: ClerkState.secret_key)
show("clerk_provider() WITHOUT secret key (should raise ValueError)", lambda: clerk.clerk_provider(rx.text("x"), publishable_key="pk_test_x"))
show("clerk_provider(secret_key=...)", lambda: type(clerk.clerk_provider(rx.text("x"), publishable_key="pk_test_x", secret_key="sk_test_123")).__name__)
show("ClerkState.secret_key after provider", lambda: ClerkState.secret_key)
show("ClerkState.jwt_public_keys (class property)", lambda: ClerkState.jwt_public_keys)

root = rx.State(_reflex_internal_init=True)
inst = root.get_substate(ClerkState.get_full_name().split(".")[1:])
import io, contextlib
buf = io.StringIO()
with contextlib.redirect_stdout(buf):
    show("set_clerk_session('not-a-jwt') on instance", lambda: ClerkState.set_clerk_session.fn(inst, "not-a-jwt"))
print(buf.getvalue().strip())
show("instance.is_signed_in / auth_error", lambda: (inst.is_signed_in, inst.auth_error))
