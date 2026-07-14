---
title: OIDC Providers
---

_New in reflex-enterprise v0.9.1._

# OIDC Providers

An OIDC provider is the state class that runs the OpenID Connect Authorization
Code + PKCE flow against your identity provider (IdP). `rxe.AuthPlugin` ships a
built-in provider that resolves its configuration from environment variables.

See [secure by default](/docs/enterprise/auth/secure-by-default/) for how the
plugin protects pages, events, fields, and computed vars, and the
[overview](/docs/enterprise/auth/overview/) for setup.

## The default provider

`GenericOIDCAuthState` is the built-in provider. It reads three environment
variables:

```bash
OIDC_ISSUER_URI=https://your-issuer.example.com
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret   # optional; PKCE works without it
```

`AuthPlugin.auth_providers` defaults to `[GenericOIDCAuthState]`. With the
`OIDC_*` variables set, no provider class is required:

```python
import reflex as rx
import reflex_enterprise as rxe

config = rxe.Config(
    app_name="my_app",
    plugins=[rxe.AuthPlugin()],  # uses GenericOIDCAuthState + OIDC_* env vars
)
```

Register the plugin's `auth_callback_endpoint` (default `/callback`) as the
redirect URI with your IdP.

## Naming a provider

To use provider-specific environment variables (and to register multiple distinct
IdPs), subclass `OIDCAuthState` and set `__provider__`. The subclass must also
inherit `rx.State`:

```python
import reflex as rx
from reflex_enterprise.auth import OIDCAuthState


class OktaAuthState(OIDCAuthState, rx.State):
    __provider__ = "okta"
```

With `__provider__ = "okta"`, config resolution prefers the
`OKTA_ISSUER_URI` / `OKTA_CLIENT_ID` / `OKTA_CLIENT_SECRET` variables, falling
back to the shared `OIDC_*` keys:

```bash
OKTA_ISSUER_URI=https://your-org.okta.com
OKTA_CLIENT_ID=your-okta-client-id
OKTA_CLIENT_SECRET=your-okta-client-secret
```

After the provider is registered, the default `/login` page shows a login button
for it. `display_name()` controls the button label. By default, it returns the
title-cased `__provider__` value (`"okta"` -> `"Okta"`):

```python
class OktaAuthState(OIDCAuthState, rx.State):
    __provider__ = "okta"

    @classmethod
    def display_name(cls) -> str:
        return "Okta SSO"
```

## Running inside an iframe

Embedded apps use a popup login/logout flow instead of top-level redirects. The
popup is opened from the user's click and posts tokens back to the app's own
origin with `postMessage`.

When customizing `/login`, call `provider.get_login_button(*children)` for each
provider. This mounts the message listener used by the popup flow. Calling
`redirect_to_login` directly does not mount that listener.

In most apps, link users to `/login` and customize the login page when the
default layout is not enough. See
[custom pages](/docs/enterprise/auth/custom-pages/#a-custom-login-page).

Override `_use_popup_flow(self) -> bool` on the provider subclass to force or
disable the popup flow. The default returns whether the app is embedded.

## Environment variables

Each provider resolves every config key by trying the provider-specific
`{PROVIDER}_{KEY}` variable first, then falling back to the shared `OIDC_{KEY}`.
`{PROVIDER}` is the uppercased `__provider__`.

| Key | Provider-specific | Shared fallback | Notes |
| --- | --- | --- | --- |
| Issuer | `{PROVIDER}_ISSUER_URI` | `OIDC_ISSUER_URI` | The IdP issuer URL (its `.well-known/openid-configuration` is discovered from here). |
| Client ID | `{PROVIDER}_CLIENT_ID` | `OIDC_CLIENT_ID` | The OAuth client id. |
| Client Secret | `{PROVIDER}_CLIENT_SECRET` | `OIDC_CLIENT_SECRET` | Optional; PKCE works without it. |

The default `GenericOIDCAuthState` (`__provider__ = "generic"`) resolves
`GENERIC_*` then `OIDC_*`. For the default provider, set only the `OIDC_*` keys.

## Registering providers with the plugin

`AuthPlugin(auth_providers=[...])` accepts provider **classes** or
`"module.ClassName"` import-path **strings**. Strings are resolved lazily at
compile time. Order is preserved, and the two forms may be mixed. The default is
`[GenericOIDCAuthState]`.

```md alert warning
# Use import-path strings in `rxconfig.py`
Provider modules import `reflex_enterprise`, which loads `rxconfig` at import time. Importing a provider class directly in `rxconfig.py` would re-enter the config. Pass providers as `"module.ClassName"` strings there. The plugin resolves them lazily once the config exists.
```

In `rxconfig.py`, pass strings:

```python
import reflex_enterprise as rxe

config = rxe.Config(
    app_name="my_app",
    plugins=[
        rxe.AuthPlugin(
            auth_providers=["my_app.auth.OktaAuthState"],
        ),
    ],
)
```

Outside `rxconfig.py` (for example, in tests) you may pass the classes
themselves:

```python
from my_app.auth import OktaAuthState

rxe.AuthPlugin(auth_providers=[OktaAuthState])
```

## Scopes and refresh tokens

`extra_scopes` is forwarded to every configured provider and merged into the
scopes each one requests. The merge is deduped and preserves the existing scopes
(`openid email profile` by default):

```python
rxe.AuthPlugin(
    auth_providers=["my_app.auth.OktaAuthState"],
    extra_scopes=["offline_access"],
)
```

- `extra_scopes=["offline_access"]` asks the IdP to issue a **refresh token**.
  Once granted, the framework refreshes the access token as it nears expiry,
  coordinated across browser tabs. Refresh
  requests include only scopes the IdP originally **granted**; scopes consumed
  but not granted by the IdP, such as `offline_access`, do not trigger
  `invalid_scope` during refresh.
- Without `offline_access` there is no refresh token. The session ends when the
  access token expires, and the user is returned to `/login`.
- If a refresh fails (the refresh token was revoked or expired), the session is
  reset and the user is logged out.
- `extra_scopes=["groups"]` requests group claims, useful for authorization
  checks against `ctx.auth_user_state.userinfo.get("groups")`.

Independent of token expiry, every auth cookie has a fixed 7-day lifetime. This
is the effective maximum session length. See the
[deployment guide](/docs/enterprise/auth/deployment/) for the HTTPS and cookie
requirements.

### Per-provider scopes

`extra_scopes` is applied uniformly to every configured provider and only
**adds** to the defaults. To give a single provider a distinct set, set the
`_requested_scopes` class attribute on that subclass. Unlike `extra_scopes`,
this **replaces** the default `"openid email profile"` rather than merging into
it.

```python
import reflex as rx
from reflex_enterprise.auth import OIDCAuthState


class DatabricksAuthState(OIDCAuthState, rx.State):
    __provider__ = "databricks"
    _requested_scopes: str = "all-apis offline_access openid email profile"
```

### Reading granted scopes

Every provider exposes a `granted_scopes` Var holding the space-delimited scopes
the IdP actually granted. `await User.current_provider()` resolves whichever
provider authenticated the current user, so derive a computed var on your own
state that reads the active provider's scopes — then `rx.cond` gates on it,
regardless of which provider the user logged in with:

```python
import reflex as rx
from reflex_enterprise.auth import User


class DemoState(rx.State):
    @rx.var(initial_value=False, auto_deps=False, deps=[])
    async def has_offline_access(self) -> bool:
        """Whether the active provider was granted `offline_access`."""
        provider = await User.current_provider()
        if provider is None:
            return False
        scopes = (await self.get_state(provider)).granted_scopes.split()
        return "offline_access" in scopes
```

```python
rx.cond(
    DemoState.has_offline_access,
    rx.text("Long-lived session enabled"),
    rx.text("Session ends at token expiry"),
)
```

Granted scopes are fixed once the user logs in, so the var carries no reactive
dependencies (`auto_deps=False, deps=[]`): it resolves on login and stays stable
for the session.

## Multiple providers

`/login` shows one login button per provider, including when there is only one —
it never redirects to an IdP automatically. The callback resolves the
**initiating** provider from the OAuth `state` parameter; logout resolves the
**active** provider currently holding tokens.

```python
rxe.AuthPlugin(
    auth_providers=[
        "my_app.auth.OktaAuthState",
        "my_app.auth.AzureAuthState",
    ],
)
```

```md alert warning
# Give each provider its own config when running more than one
If two or more providers fall back to the shared `OIDC_*` config for a required key (issuer or client id), they would resolve to the same IdP value. The plugin raises a `ConfigError` at startup naming the affected providers. Set provider-specific `{PROVIDER}_*` variables, such as `OKTA_ISSUER_URI` and `AZURE_ISSUER_URI`, for each.
```

Reading the user is provider-agnostic: `User.name` / `.email` / `.sub` /
`.picture` bind to `AuthUserState`, which is populated by whichever provider
completes login. To branch on the provider in backend code, use
`await User.current_provider()`:

```python
import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.auth import User


class DemoState(rx.State):
    @rxe.event
    async def show_provider(self):
        provider = await User.current_provider()
        return rx.toast(provider.__provider__ if provider else "anonymous")
```

## The claims a provider returns

`OIDCUserInfo` is a `TypedDict` (`total=False`) declaring only `sub`. The OIDC
spec requires that claim. Profile claims such as `name`, `email`, and `picture`
appear only when their scope is granted. At runtime, `OIDCUserInfo` is a plain
dict; read claims with `.get(...)`.

To document the extra claims a provider returns, declare a nested
`UserInfo(OIDCUserInfo, total=False)` on your provider:

```python
from reflex_enterprise.auth import OIDCAuthState, OIDCUserInfo


class OktaAuthState(OIDCAuthState, rx.State):
    __provider__ = "okta"

    class UserInfo(OIDCUserInfo, total=False):
        name: str
        email: str
        picture: str
        groups: list[str]
```

The common claims are projected as read-only Vars on `User`
(`User.name`, `.email`, `.sub`, `.picture`); any other claim is read from the
dict via `await User.current()` or `ctx.auth_user_state.userinfo.get(...)`.

## Advanced extension points

`OIDCAuthState` exposes overridable async hooks for provider-specific behavior.
Override only the hooks required by your provider subclass:

| Hook | Purpose |
| --- | --- |
| `_validate_tokens(self) -> bool` | Validate the current access and ID tokens; return whether they're valid. |
| `_verify_jwt(self, token_json) -> Token` | Verify the ID token JWT; override to customize verification. |
| `_valid_issuers(self) -> list[str] \| None` | Acceptable `iss` claim values; override for e.g. Azure multi-tenant. |
| `_set_tokens(self, access_token, id_token=None, refresh_token=None, granted_scopes=None, **kwargs)` | Persist tokens after exchange; override to handle extra response data. |
| `_set_tokens_payload_from_exchange(self, exchange) -> dict` | Build the kwargs passed to `_set_tokens`; override to forward an extra field from the token-exchange response. |
| `_validate_auth_callback_exchange(self, exchange) -> dict \| None` | Validate the token-exchange response from the callback. |
| `_fetch_userinfo(self) -> OIDCUserInfo` | Fetch claims from the IdP's userinfo endpoint; override to fetch or reshape claims. |
| `_redirect_to_login_payload(self) -> dict` | Build the authorization-request query params (scope, state, PKCE challenge); override for non-standard login params. |
| `_redirect_to_logout_payload(self) -> dict[str, str]` | Build the IdP end-session params (`state`, `id_token_hint`, `post_logout_redirect_uri`); override for a custom `post_logout_redirect_uri` or non-standard end-session. |
| `_on_access_token_change(self, new_access_token, refresh=False)` | React when the access token is set or refreshed. |
| `_on_refresh_access_token(self, new_access_token)` | React specifically when the access token is refreshed. |

```md alert info
# Logout behavior
Logout chains the provider's discovered `end_session_endpoint` with an
`id_token_hint` and `post_logout_redirect_uri`. If the IdP advertises no
`end_session_endpoint`, logout clears local tokens and redirects to the app
index. The IdP session remains active and a later login may reuse it.
```

## Using the access token to call an API

Inside an `@rx.event` (or computed var) on **your** `OIDCAuthState` subclass,
`await self._access_token` to get the current OAuth access token, then send it as
a bearer token to a downstream service or the IdP. The leading underscore does
not indicate direct field access here: `_access_token` is a server-only
awaitable Var, never exposed to the browser, and kept fresh by background
refresh.

```python
import httpx
import reflex as rx
from reflex_enterprise.auth import OIDCAuthState


class OktaAuthState(OIDCAuthState, rx.State):
    __provider__ = "okta"

    @rx.event
    async def fetch_profile(self):
        access_token = await self._access_token
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://api.example.com/me",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            resp.raise_for_status()
```

To react when the token is issued or refreshed, override
`_on_access_token_change` or `_on_refresh_access_token` on the subclass.

## Sharing behavior across providers

To put the same fields, vars, event handlers, or hook overrides on more than one
provider without duplication, define an `rx.State` mixin with `mixin=True` and
list it **before** `OIDCAuthState` in each provider's bases:

```python
import reflex as rx
from reflex_enterprise.auth import OIDCAuthState


class SharedAuthBehavior(rx.State, mixin=True):
    async def _on_access_token_change(
        self, new_access_token, refresh=False
    ): ...  # runs for every provider that mixes this in


class OktaAuthState(SharedAuthBehavior, OIDCAuthState, rx.State):
    __provider__ = "okta"


class AzureAuthState(SharedAuthBehavior, OIDCAuthState, rx.State):
    __provider__ = "azure"
```

Base order matters: the mixin must come before `OIDCAuthState`/`rx.State`. Each
provider reads its own `__provider__`-namespaced cookies. The shared code
operates on that provider's tokens.

## Persisting extra token-exchange data

`_set_tokens_payload_from_exchange` builds the payload (`access_token`, plus any
of `id_token`, `refresh_token`, and `granted_scopes` the exchange returned) from
the IdP's token-exchange response, and that payload is the entire set of kwargs
`_set_tokens` receives on both the callback and refresh paths.

To persist a custom field from the exchange, override **both** hooks:
`_set_tokens_payload_from_exchange` carries the field through, and `_set_tokens`
accepts and stores it.

```python
import reflex as rx
from reflex_enterprise.auth import OIDCAuthState


class OrgAuthState(OIDCAuthState, rx.State):
    __provider__ = "myorg"
    _org_id: str = ""

    async def _set_tokens_payload_from_exchange(self, exchange):
        payload = await super()._set_tokens_payload_from_exchange(exchange)
        if "org_id" in exchange:
            payload["org_id"] = exchange["org_id"]
        return payload

    async def _set_tokens(
        self,
        access_token,
        id_token=None,
        refresh_token=None,
        granted_scopes=None,
        org_id="",
        **kwargs,
    ):
        await super()._set_tokens(
            access_token, id_token, refresh_token, granted_scopes, **kwargs
        )
        self._org_id = org_id
```

Under the popup/iframe flow, the popup and opener are separate clients. The popup
runs the callback and captures the field in its own state, then posts the tokens
to the opener, which applies them through `on_iframe_auth_success`, not
`_set_tokens_payload_from_exchange`. Only the posted tokens cross over, so a
custom field stored on the popup's `self` does not automatically reach the opener.

Give the extra `_set_tokens` keyword a default (as `org_id=""` above) so the
opener's call works.

## Migrating from `register_auth_endpoints`

`OIDCAuthState.register_auth_endpoints(app)` is deprecated (since
reflex-enterprise v0.9.1, removed in 1.0). Register `rxe.AuthPlugin` in
`rxe.Config(plugins=[...])` instead. The plugin registers `/login`, `/logout`,
`/callback`, and `/forbidden`, and applies the secure-by-default protections.

## Related

- [Secure by default](/docs/enterprise/auth/secure-by-default/): protected
  surfaces and authorization checks.
- [Custom pages](/docs/enterprise/auth/custom-pages/): custom login, callback,
  logout, and forbidden page builders.
- [Testing](/docs/enterprise/auth/testing/): guarded surfaces and mock-IdP
  tests.
