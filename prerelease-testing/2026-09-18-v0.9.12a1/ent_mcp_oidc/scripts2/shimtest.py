import traceback
import reflex as rx
print("reflex", rx.constants.Reflex.VERSION)
import oidc_meta_shim
print("shim applied:", oidc_meta_shim.APPLIED)
from reflex_enterprise.auth import GenericOIDCAuthState, AuthUserState
print("GenericOIDCAuthState:", GenericOIDCAuthState)
# now subclass it as a real app would
try:
    class MyAuth(GenericOIDCAuthState, rx.State):
        __provider__ = "generic"
    print("subclass OK:", MyAuth, "cookies:", [f for f in MyAuth.__fields__ if "token" in f or "scope" in f])
except Exception:
    traceback.print_exc()
try:
    import reflex_enterprise as rxe
    app = rxe.App()
    print("App OK")
except Exception:
    traceback.print_exc()
