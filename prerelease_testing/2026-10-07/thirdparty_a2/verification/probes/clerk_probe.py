"""Exercise reflex-clerk 1.0.3's real class-level State config code on three reflex versions.

Run with the venv python that has reflex + reflex-clerk (thirdparty_a2-a2 / thirdparty-alpha / thirdparty-stable).
"""
import os, sys, warnings
warnings.simplefilter("ignore")
os.environ.pop("CLERK_SECRET_KEY", None)
import reflex as rx
from importlib.metadata import version
exp = os.environ["EXPECT_VENV"]
assert f"/envs/{exp}/" in rx.__file__, rx.__file__
print("reflex", version("reflex"), "reflex-clerk", version("reflex-clerk"), "venv", exp)

from reflex_clerk.lib.clerk_provider import ClerkState, ClerkProvider


def inst(cls):
    try:
        return cls(_reflex_internal_init=True)
    except TypeError:
        return cls()


def t(label, fn):
    try:
        r = fn()
        print(f"  {label:<70} -> {r!r}"[:230])
    except Exception as e:  # noqa: BLE001
        print(f"  {label:<70} -> EXC {type(e).__name__}: {str(e)[:100]}")


print("1) class-level READ of declared backend vars (reflex-clerk does `if cls._secret_key is None`)")
t("type(ClerkState._secret_key).__name__", lambda: type(ClerkState._secret_key).__name__)
t("ClerkState._secret_key is None", lambda: ClerkState._secret_key is None)
t("ClerkState.secret_key  (classmethod-property w/o env)", lambda: type(ClerkState.secret_key).__name__)

print("2) class-level ASSIGNMENT done by ClerkProvider.create / set_fetch_user_on_auth")
t("ClerkState.set_fetch_user_on_auth(False)", lambda: ClerkState.set_fetch_user_on_auth(False))
t("fresh instance._fetch_user (expect False if class assignment took effect)", lambda: inst(ClerkState)._fetch_user)
t("ClerkState._secret_key = 'sk_test_abc' (what ClerkProvider.create does)", lambda: setattr(ClerkState, "_secret_key", "sk_test_abc"))
t("fresh instance._secret_key", lambda: inst(ClerkState)._secret_key)
t("ClerkState._jwt_public_keys = [{'kid':'x'}]", lambda: setattr(ClerkState, "_jwt_public_keys", [{"kid": "x"}]))
t("fresh instance._jwt_public_keys", lambda: inst(ClerkState)._jwt_public_keys)
t("ClerkState._secret_key = None   (reset to unset)", lambda: setattr(ClerkState, "_secret_key", None))
t("ClerkState._secret_key = 12345  (wrong type)", lambda: setattr(ClerkState, "_secret_key", 12345))

print("3) ClerkProvider.create(secret_key=..., publishable_key=...)")
t("ClerkProvider.create(secret_key='sk_test_abc', publishable_key='pk_test_x')", lambda: type(ClerkProvider.create(secret_key="sk_test_abc", publishable_key="pk_test_x")).__name__)
t("after: fresh instance._secret_key", lambda: inst(ClerkState)._secret_key)
t("env var path: CLERK_SECRET_KEY=sk_env -> ClerkState.secret_key", lambda: (os.environ.__setitem__("CLERK_SECRET_KEY", "sk_env"), type(ClerkState.secret_key).__name__ + ":" + str(ClerkState.secret_key)[:50])[1])
