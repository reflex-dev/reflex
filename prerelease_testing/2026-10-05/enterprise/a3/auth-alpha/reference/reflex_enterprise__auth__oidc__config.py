"""Reusable config mixin for OIDC providers."""

import os
from typing import ClassVar

from reflex_enterprise.auth.oidc.types import AsyncHTTPClientProtocol
from reflex_enterprise.auth.oidc.utils import DEFAULT_HTTP_CLIENT, issuer_endpoint


class ConfigMixin:
    """Customizable per-provider configuration from env var helper."""

    __provider__: ClassVar[str] = "base"

    # When set (by AuthPlugin), the OAuth redirect URI path is this friendly
    # route instead of the provider-prefixed authorization-code callback.
    _auth_callback_route: ClassVar[str | None] = None

    @classmethod
    def _http_client(cls) -> AsyncHTTPClientProtocol:
        """Get the HTTP client instance for OIDC operations."""
        return DEFAULT_HTTP_CLIENT

    @classmethod
    def _env_keys(cls, key: str) -> tuple[str, str]:
        """Get the provider-specific and shared-fallback env var names for a key.

        Config resolution prefers the provider-specific ``{PROVIDER}_{KEY}`` var
        and falls back to the shared ``OIDC_{KEY}``. Exposed so callers that
        reason about where a value comes from (e.g. the auth plugin's
        multi-provider validation) share this single naming convention instead
        of re-deriving it.

        Args:
            key: The configuration key (e.g. ``"issuer_uri"``).

        Returns:
            The ``({PROVIDER}_{KEY}, OIDC_{KEY})`` env var names.
        """
        upper = key.upper()
        return f"{cls.__provider__.upper()}_{upper}", f"OIDC_{upper}"

    async def _get_config_value(
        self, key: str, default: str | None = None
    ) -> str | None:
        """Get a configuration value for the OIDC provider.

        Args:
            key: The configuration key to retrieve.
            default: The default value if the key is not found.

        Returns:
            The configuration value as a string, or the default if not found.
        """
        full_key, fallback_key = self._env_keys(key)
        return os.environ.get(full_key, os.environ.get(fallback_key, default))

    @classmethod
    def _with_provider_prefix(cls, url: str) -> str:
        """Prefix a URL path with the provider name for namespacing.

        Args:
            url: The URL path to prefix.

        Returns:
            The namespaced URL path.
        """
        prefix = f"/_reflex_oidc_{cls.__provider__}"
        if not url.startswith("/"):
            url = "/" + url
        return prefix + url

    # Informational helper methods that should be overwritten by subclasses as needed
    @classmethod
    def _authorization_code_endpoint(cls) -> str:
        """Get the authorization code endpoint path."""
        if cls._auth_callback_route is not None:
            return cls._auth_callback_route
        return cls._with_provider_prefix("/authorization-code/callback")

    @classmethod
    def _popup_login_endpoint(cls) -> str:
        """Get the popup login endpoint path."""
        return cls._with_provider_prefix("/popup-login")

    @classmethod
    def _popup_logout_endpoint(cls) -> str:
        """Get the popup logout endpoint path."""
        return cls._with_provider_prefix("/popup-logout")

    async def _client_id(self) -> str:
        """Get the OIDC client ID."""
        client_id = await self._get_config_value("client_id")
        if not client_id:
            raise RuntimeError("OIDC client ID not configured")
        return client_id

    async def _client_secret(self) -> str:
        """Get the OIDC client secret."""
        return await self._get_config_value("client_secret") or ""

    async def _issuer_uri(self) -> str:
        """Get the OIDC issuer URI."""
        issuer = await self._get_config_value("issuer_uri")
        if not issuer:
            raise RuntimeError("OIDC issuer URI not configured")
        return issuer

    async def _valid_issuers(self) -> list[str] | None:
        """Override to return a list of acceptable iss claim values.

        Default returns None, meaning verify_jwt uses the configured issuer
        (with/without trailing slash). Subclasses (e.g. Azure multi-tenant)
        can override to expand /common/, /organizations/, /consumers/ etc.

        Returns:
            A list of acceptable iss claim values, or None to use the default.
        """
        return None

    async def _issuer_endpoint(self, service: str) -> str:
        """Get an endpoint URL (authorization/token/userinfo/etc) from OIDC metadata.

        Args:
            service: The OIDC service endpoint to retrieve.

        Returns:
            The endpoint URL as a string.
        """
        return await issuer_endpoint(
            await self._issuer_uri(), service, client=self._http_client()
        )
