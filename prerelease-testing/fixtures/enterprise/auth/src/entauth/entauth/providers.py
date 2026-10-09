"""Two user-defined OIDC providers for the AUTH_MULTI=1 variant (same mock IdP)."""

import reflex as rx
from reflex_enterprise.auth.oidc.state import OIDCAuthState


class AcmeAuthState(OIDCAuthState, rx.State):
    """First configured provider."""

    __provider__ = "acme"


class GlobexAuthState(OIDCAuthState, rx.State):
    """Second configured provider."""

    __provider__ = "globex"
