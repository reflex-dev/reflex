---
title: OIDC Providers
---

_New in reflex-enterprise v0.9.1._

# OIDC Providers

An OIDC provider is the state class that runs the OpenID Connect Authorization
Code + PKCE flow against your identity provider (IdP). `rxe.AuthPlugin` ships a
built-in provider and resolves all of its configuration from environment
variables, so the common case needs no provider code at all.

This page covers the default provider, naming your own, the environment
variables each one reads, registering providers with the plugin, scopes and
refresh tokens, running several providers at once, the claims they return, and
the advanced hooks you can override.

See [secure by default](/docs/enterprise/auth/secure-by-default/) for how the
plugin protects pages, events, fields, and computed vars, and the
[overview](/docs/enterprise/auth/overview/) for the big picture.

## The default provider

`GenericOIDCAuthState` is the built-in provider. It reads three environment
variables:

```bash
OIDC_ISSUER_URI=https://your-issuer.example.com
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret   # optional — PKCE works without it
```

`AuthPlugin.auth_providers` defaults to `[GenericOIDCAuthState]`, so with the
`OIDC_*` variables set you don't write or register a provider:

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

Render a login button for the provider with its `get_login_button()` classmethod
(pass children to customize the clickable element):

```python
def login() -> rx.Component:
    return (
        OktaAuthState.get_login_button()
    )  # or .get_login_button(rx.button("Sign in with Okta"))
```

`display_name()` returns a pretty label for the provider — by default the
`__provider__` value title-cased (`"okta"` → `"Okta"`). Override it to control
the login-button label:

```python
class OktaAuthState(OIDCAuthState, rx.State):
    __provider__ = "okta"

    @classmethod
    def display_name(cls) -> str:
        return "Okta SSO"
```

## Running inside an iframe

When the app detects it is embedded in an iframe, login and logout automatically
switch from a top-level redirect to a popup window with a `postMessage` token
hand-off — so a Reflex auth app embeds inside another product with no extra
configuration. The popup opens from the user's click (to avoid pop-up blockers)
and posts tokens back to the app's own origin.

This auto-switch only works through the provider's `get_login_button()` — it
mounts the message listener that receives the tokens posted from the popup. A
hand-rolled button that merely calls `redirect_to_login` still takes the popup
branch but has nowhere to receive the tokens, so the session never completes.
If you wrap `get_login_button()` (see
[custom pages](/docs/enterprise/auth/custom-pages/)), keep the returned element
in the tree so the listener stays mounted.

Advanced override knobs live on your provider subclass: `_use_popup_flow(self)
-> bool` decides whether the popup flow is used (override to force or disable
it; the default returns whether the app is iframed).

## Environment variables

Each provider resolves every config key by trying the provider-specific
`{PROVIDER}_{KEY}` variable first, then falling back to the shared `OIDC_{KEY}`.
`{PROVIDER}` is the uppercased `__provider__`.

| Key | Provider-specific | Shared fallback | Notes |
| --- | --- | --- | --- |
| Issuer | `{PROVIDER}_ISSUER_URI` | `OIDC_ISSUER_URI` | The IdP issuer URL (its `.well-known/openid-configuration` is discovered from here). |
| Client ID | `{PROVIDER}_CLIENT_ID` | `OIDC_CLIENT_ID` | The OAuth client id. |
| Client Secret | `{PROVIDER}_CLIENT_SECRET` | `OIDC_CLIENT_SECRET` | Optional — PKCE works without it. |

The default `GenericOIDCAuthState` (`__provider__ = "generic"`) resolves
`GENERIC_*` then `OIDC_*`, so in practice you only set the `OIDC_*` keys for it.

## Registering providers with the plugin

`AuthPlugin(auth_providers=[...])` accepts either provider **classes** or
`"module.ClassName"` import-path **strings** (resolved lazily at compile time).
Order is preserved, and the two forms may be mixed. The default is
`[GenericOIDCAuthState]`.

```md alert warning
# Use import-path strings in `rxconfig.py`
Provider modules import `reflex_enterprise`, which loads `rxconfig` at import time. Importing a provider class directly in `rxconfig.py` would re-enter the config. Pass providers as `"module.ClassName"` strings there so the plugin resolves them lazily once the config exists.
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
  Once granted, the framework refreshes the access token automatically and
  proactively as it nears expiry, coordinated across browser tabs. The refresh
  request only asks for the scopes the IdP originally **granted**, so a scope the
  IdP consumed without granting (e.g. `offline_access` itself) won't cause the
  refresh to fail with `invalid_scope`.
- Without `offline_access` there is no refresh token, so the session ends when
  the access token expires and the user is returned to `/login`.
- If a refresh fails (the refresh token was revoked or expired), the session is
  reset and the user is logged out.
- `extra_scopes=["groups"]` requests group claims, useful for authorization
  checks against `ctx.auth_user_state.userinfo.get("groups")`.

Independent of token expiry, every auth cookie has a fixed 7-day lifetime (no
configuration knob) — this is the effective maximum session length. See the
[deployment guide](/docs/enterprise/auth/deployment/) for the HTTPS and cookie
requirements.

### Per-provider scopes

`extra_scopes` is applied uniformly to every configured provider and only
**adds** to the defaults. To give a single provider a distinct set — e.g. a
resource/API scope that only one IdP should receive — set the
`_requested_scopes` class attribute on that subclass. Unlike `extra_scopes`,
this **replaces** the default `"openid email profile"` rather than merging into
it:

```python
import reflex as rx
from reflex_enterprise.auth import OIDCAuthState


class DatabricksAuthState(OIDCAuthState, rx.State):
    __provider__ = "databricks"
    _requested_scopes: str = "all-apis offline_access openid email profile"
```

### Reading granted scopes

Every provider exposes a `granted_scopes` Var — the space-delimited scopes the
IdP actually granted (which may differ from what was requested). Use it to gate
optional-scope features at runtime, e.g. only show refresh-dependent UI when
`offline_access` was granted:

```python
rx.cond(
    DatabricksAuthState.granted_scopes.contains("offline_access"),
    rx.text("Long-lived session enabled"),
    rx.text("Session ends at token expiry"),
)
```

## Multiple providers

With two or more providers, `/login` shows a palette — one button per provider —
and the visitor clicks to choose; there is no automatic redirect to a single
IdP. The callback resolves the **initiating** provider (via the OAuth `state`
parameter), and logout resolves the **active** provider (the one currently
holding tokens).

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
If two or more providers would both fall back to the shared `OIDC_*` config for a required key (issuer or client id), distinct identity providers would silently collapse onto one value. The plugin raises a `ConfigError` at startup naming the offending providers. Set a provider-specific `{PROVIDER}_*` variable (e.g. `OKTA_ISSUER_URI`, `AZURE_ISSUER_URI`) for each.
```

Reading the user is provider-agnostic: `User.name` / `.email` / `.sub` /
`.picture` bind to `AuthUserState`, which is populated by whichever provider
completes login, so they render correctly no matter which button the visitor
clicked. To branch on the provider, read `User.provider_name` in a component or
`await User.current_provider()` in an event handler:

```python
rx.cond(User.provider_name == "okta", rx.text("via Okta"), rx.text("via Azure"))
```

## The claims a provider returns

`OIDCUserInfo` is a `TypedDict` (`total=False`) declaring only `sub` — per the
OIDC spec it is the one claim always returned. Profile claims like `name`,
`email`, and `picture` appear only when their scope is granted. It is a plain
dict at runtime, so you read claims with `.get(...)`.

To document the extra claims a provider returns, declare a nested
`UserInfo(OIDCUserInfo, total=False)` on your provider — exactly as the built-in
`GenericOIDCAuthState` does:

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

`OIDCAuthState` exposes a set of overridable async hooks for advanced cases. Most
apps never need these — the defaults run the standard flow. Override the ones you
need on your provider subclass:

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
`id_token_hint` and `post_logout_redirect_uri`. If the IdP advertises **no**
`end_session_endpoint`, logout only clears the local tokens and redirects to the
app index — the IdP session is **not** terminated, so a later login may silently
re-authenticate.
```

## Using the access token to call an API

Inside an `@rx.event` (or computed var) on **your** `OIDCAuthState` subclass,
`await self._access_token` to get the current OAuth access token, then send it as
a bearer token to a downstream service or the IdP. Despite the leading
underscore, `_access_token` is the accessor — it is a server-only awaitable Var,
never exposed to the browser, and is kept fresh by the framework's background
refresh, so the value you read is normally current:

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

To react when the token is (re)issued — e.g. to invalidate a cached downstream
client — override `_on_access_token_change` or `_on_refresh_access_token` on the
subclass (see the hook table above).

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
provider still reads its own `__provider__`-namespaced cookies, so the shared
code always operates on the right provider's tokens.

## Persisting extra token-exchange data

`_set_tokens_payload_from_exchange` builds the payload (`access_token`, plus any
of `id_token`, `refresh_token`, and `granted_scopes` the exchange returned) from
the IdP's token-exchange response, and that payload is the entire set of kwargs
`_set_tokens` receives on both the callback and refresh paths. To persist a custom field from the
exchange, override **both** hooks — `_set_tokens_payload_from_exchange` to carry
the field through, and `_set_tokens` to accept and store it:

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

The popup/iframe login path sets tokens directly and does **not** route through
`_set_tokens_payload_from_exchange`, so always give the extra `_set_tokens`
keyword a default (as `org_id=""` above) to keep that path working.

## Migrating from `register_auth_endpoints`

`OIDCAuthState.register_auth_endpoints(app)` is deprecated (since
reflex-enterprise v0.9.1, removed in 1.0). Register `rxe.AuthPlugin` in
`rxe.Config(plugins=[...])` instead — it wires the `/login`, `/logout`,
`/callback`, and `/forbidden` routes (and the secure-by-default protections)
automatically.

## Related

- [Secure by default](/docs/enterprise/auth/secure-by-default/) — how the plugin protects every surface, and authorization checks against claims.
- [Custom pages](/docs/enterprise/auth/custom-pages/) — replace the login / callback / logout / forbidden page builders.
- [Testing](/docs/enterprise/auth/testing/) — exercise guarded surfaces and the full OIDC flow.
