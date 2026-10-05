import traceback, sys
import reflex as rx
print("reflex", rx.constants.Reflex.VERSION)
try:
    from reflex_enterprise.auth import OktaAuthState  # noqa
    print("OktaAuthState OK")
except Exception as e:
    print("OktaAuthState FAIL:", type(e).__name__, str(e)[:160])
for n in ["DatabricksAuthState", "GoogleAuthState", "GenericOIDCAuthState", "OIDCAuthState"]:
    try:
        m = __import__("reflex_enterprise.auth", fromlist=[n]); getattr(m, n); print(n, "OK")
    except Exception as e:
        print(n, "FAIL:", type(e).__name__, str(e)[:120])
