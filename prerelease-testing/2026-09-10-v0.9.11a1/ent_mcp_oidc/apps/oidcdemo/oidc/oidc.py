import logging
from typing import ClassVar

import aiohttp
import reflex as rx

import reflex_enterprise as rxe
from reflex_enterprise.auth.cookie import HTTPCookie
from reflex_enterprise.auth.oidc.state import OIDCAuthState
from reflex_enterprise.auth.oidc.types import AsyncHTTPClientProtocol
from reflex_enterprise.utils import chain_event_out_of_band

logging.basicConfig(
    level=logging.INFO, format="%(levelname)-7s %(name)-10s: %(message)s"
)
logging.getLogger("httpx").setLevel(logging.DEBUG)
logging.getLogger("aiohttp").setLevel(logging.DEBUG)

_CACHED_HTTP_CLIENT: AsyncHTTPClientProtocol | None = None


class LogAtMixin(rx.State, mixin=True):
    # Uncomment to test with aiohttp instead of httpx
    @classmethod
    def _http_client(cls) -> AsyncHTTPClientProtocol:
        """Get the HTTP client instance for OIDC operations."""
        global _CACHED_HTTP_CLIENT
        if _CACHED_HTTP_CLIENT is None:
            _CACHED_HTTP_CLIENT = aiohttp.ClientSession()
        return _CACHED_HTTP_CLIENT

    @rx.event
    async def log_at(self):
        """Log the current authentication state."""
        access_token = await self._access_token
        self._logger.info(
            f"Userinfo: {await self.userinfo}, ID Token: {self._id_token}, Access Token: {access_token}"
        )

    @rx.var
    def last_access_token_hash(self) -> str | None:
        """A hash of the last access token for comparison to detect changes."""
        return self._last_access_token_hash


class OktaAuthState(LogAtMixin, OIDCAuthState, rx.State):
    """OIDC Auth State for Okta."""

    __provider__ = "okta"
    _logger: ClassVar[logging.Logger] = logging.getLogger(__provider__)
    _logger.setLevel(logging.DEBUG)


class DatabricksAuthState(LogAtMixin, OIDCAuthState, rx.State):
    """OIDC Auth State for Databricks."""

    __provider__ = "databricks"
    _requested_scopes: str = "all-apis offline_access openid email profile"
    _logger: ClassVar[logging.Logger] = logging.getLogger(__provider__)
    _logger.setLevel(logging.DEBUG)

    async def _on_access_token_change(self, new_access_token, refresh=False):
        self._logger.info(
            self._format_log_message(f"Access token change callback hit {refresh=}")
        )
        if refresh:
            await chain_event_out_of_band(self, rx.toast("Access token refreshed"))


class FooState(rx.State):
    @rx.event
    def do_nothing(self):
        pass


def user_info_card(auth_cls: type[OIDCAuthState]) -> rx.Component:
    return rx.card(
        rx.cond(
            auth_cls.userinfo.is_not_none(),
            rx.vstack(
                rx.heading(f"{auth_cls.display_name()} User Info", size="4"),
                rx.foreach(
                    auth_cls.userinfo,
                    lambda kv: rx.text(f"{kv[0]}: {kv[1]} "),
                ),
                rx.vstack(
                    rx.badge(
                        rx.moment(auth_cls.userinfo.to(dict)["iat"], unix=True),
                        color_scheme="green",
                    ),
                    rx.badge(
                        rx.moment(auth_cls.userinfo.to(dict)["exp"], unix=True),
                        color_scheme="red",
                    ),
                    rx.badge(auth_cls.last_access_token_hash, color_scheme="blue"),
                    rx.badge(auth_cls.latest_access_token_hash_ls, color_scheme="blue"),
                )
                if auth_cls is DatabricksAuthState
                else rx.fragment(),
                rx.button(
                    "Log AT",
                    on_click=auth_cls.log_at,
                ),
                rx.button("Logout", on_click=auth_cls.redirect_to_logout),
            ),
            auth_cls.get_login_button(),
        ),
    )


def index() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("OIDC Demo", size="9"),
            rx.hstack(
                user_info_card(OktaAuthState),
                user_info_card(DatabricksAuthState),
                spacing="2",
            ),
            rx.button(
                "Do Nothing",
                on_click=FooState.do_nothing,
            ),
            rx.button(
                "Cookie Sync",
                on_click=HTTPCookie.sync(),
            ),
        ),
    )


def iframe() -> rx.Component:
    return rx.container(
        rx.color_mode.button(position="top-right"),
        rx.vstack(
            rx.heading("Iframed Auth"),
            rx.el.iframe(
                src="/",
                width="100%",
                height="80vh",
                border=f"1px solid {rx.color('accent', 12)}",
            ),
        ),
    )


app = rxe.App()
app.add_page(index)
app.add_page(iframe, route="/iframe")

OktaAuthState.register_auth_endpoints()
DatabricksAuthState.register_auth_endpoints()
