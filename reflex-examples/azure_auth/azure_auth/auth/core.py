import msal
import reflex as rx
from typing import Dict, List, Optional

client_id: str = "0df2a88e-fddb-4cc2-b3e0-f475f162b373"
client_secret: str = ""
tenant_id: str = "f2c9cbbe-006b-46b8-9ad0-d877d8446d6d"
authority = f"https://login.microsoftonline.com/{tenant_id}"
login_redirect = "/"
cache = msal.TokenCache()

sso_app: msal.ClientApplication
if client_secret:
    sso_app = msal.ConfidentialClientApplication(
        client_id=client_id,
        client_credential=client_secret,
        authority=authority,
        token_cache=cache,
    )
else:
    sso_app = msal.PublicClientApplication(
        client_id=client_id,
        authority=authority,
        token_cache=cache,
    )


class State(rx.State):
    _access_token: str = ""
    _flow: dict
    _token: Dict[str, str] = {}

    def redirect_sso(self, scope: Optional[List] = None) -> rx.Component:
        if scope is None:
            scope = []
        self._flow = sso_app.initiate_auth_code_flow(
            scopes=scope, redirect_uri=f"{self.router.page.host}/callback"
        )
        return rx.redirect(self._flow["auth_uri"])

    def require_auth(self):
        if not self._token:
            return self.redirect_sso()

    @rx.var(cache=True)
    def check_auth(self) -> bool:
        return True if self._token else False

    @rx.var(cache=True)
    def token(self) -> Dict[str, str]:
        return self._token

    def logout(self):
        self._token = {}
        return rx.redirect(authority + "/oauth2/v2.0/logout")

    def callback(self):
        query_components = self.router.page.params

        auth_response = {
            "code": query_components.get("code"),
            "client_info": query_components.get("client_info"),
            "state": query_components.get("state"),
            "session_state": query_components.get("session_state"),
            "client-secret": client_secret,
        }
        try:
            result = sso_app.acquire_token_by_auth_code_flow(
                self._flow, auth_response, scopes=[]
            )
        except Exception:
            return rx.toast("error something went wrong")
        # this can be used for accessing graph
        self._access_token = result.get("access_token")
        self._token = result.get("id_token_claims")
        return rx.redirect(login_redirect)
