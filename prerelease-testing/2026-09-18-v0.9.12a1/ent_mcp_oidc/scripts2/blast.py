import traceback
import reflex as rx
print("reflex", rx.constants.Reflex.VERSION)
import reflex_enterprise as rxe
checks = [
 ("rxe.AuthPlugin()", lambda: rxe.AuthPlugin()),
 ("rxe.MCPPlugin()", lambda: rxe.MCPPlugin()),
 ("from reflex_enterprise.auth import AuthUserState", lambda: __import__("reflex_enterprise.auth", fromlist=["AuthUserState"]).AuthUserState),
 ("from reflex_enterprise.auth import GenericOIDCAuthState", lambda: __import__("reflex_enterprise.auth", fromlist=["GenericOIDCAuthState"]).GenericOIDCAuthState),
 ("import reflex_enterprise.auth.oidc", lambda: __import__("reflex_enterprise.auth.oidc")),
 ("rxe.App(plugins)", lambda: rxe.App()),
]
for name, fn in checks:
    try:
        r = fn(); print("OK  ", name, "->", repr(r)[:80])
    except Exception as e:
        print("FAIL", name, "->", type(e).__name__, str(e)[:200])
