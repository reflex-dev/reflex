---
title: OIDC Providers
---

_New in reflex-enterprise v0.9.1._

# OIDC Providers

An OIDC provider is the state class that runs the OpenID Connect Authorization
Code + PKCE flow against your identity provider (IdP). `rxe.AuthPlugin` ships a
built-in provider and resolves all of its configuration from environment
variables, so the common case needs no provider code at all. This page covers
the default provider, naming your own, the environment variables each one reads,
registering providers with the plugin, scopes and refresh tokens, running
several providers at once, customizing the user-info claims, and the advanced
hooks you can override.

See [secure-by-default](/docs/enterprise/auth/secure-by-default/) for how the
plugin protects pages, events, fields, and computed vars, and the
[overview](/docs/enterprise/auth/overview/) for the big picture.

## The default provider

`GenericOIDCAuthState` is the built-in provider. It reads three environment
variables:

```bash
OIDC_ISSUER_URI=https://your-issuer.example.com
OIDC_CLIENT_ID=your-client-id
OIDC_CLIENT_SECRET=your-client-secret
```

`AuthPlugin.auth_providers` defaults to `[GenericOIDCAuthState]`, so with the
`OIDC_*` variables set you do not need to write or register a custom provider:

```python
import reflex as rx
import reflex_enterprise as rxe

config = rxe.Config(
    app_name="my_app",
    plugins=[rxe.AuthPlugin()],  # uses GenericOIDCAuthState + OIDC_* env vars
)
```

`GenericOIDCAuthState` declares a nested `UserInfo` `TypedDict` describing the
standard claims it covers — `sub`, `name`, `email`, `picture`, and
`groups` — on top of the base `OIDCUserInfo`:

```python
class GenericOIDCAuthState(OIDCAuthState, rx.State):
    __provider__ = "generic"

    class UserInfo(OIDCUserInfo, total=False):
        groups: list[str]
        name: str
        email: str
        picture: str
```

## Naming a provider

To use provider-specific environment variables (and to register multiple
distinct IdPs), subclass `OIDCAuthState` and set `__provider__`:

```python
import reflex as rx
from reflex_enterprise.auth.oidc.state import OIDCAuthState


class OktaAuthState(OIDCAuthState, rx.State):
    __provider__ = "okta"
```

With `__provider__ = "okta"`, config resolution prefers the
`OKTA_CLIENT_ID` / `OKTA_CLIENT_SECRET` / `OKTA_ISSUER_URI` variables, falling
back to the shared `OIDC_*` keys:

```bash
OKTA_ISSUER_URI=https://your-org.okta.com
OKTA_CLIENT_ID=your-okta-client-id
OKTA_CLIENT_SECRET=your-okta-client-secret
```

Render a login button for the provider with its `get_login_button()`
classmethod (pass children to customize the clickable element):

```python
def login() -> rx.Component:
    return OktaAuthState.get_login_button()
```

## Environment variables

Each provider resolves every config key by trying the provider-specific
`{PROVIDER}_{KEY}` variable first, then falling back to the shared `OIDC_{KEY}`
variable. `{PROVIDER}` is the uppercased `__provider__` value.

| Key | Provider-specific | Shared fallback | Notes |
| --- | --- | --- | --- |
| Issuer | `{PROVIDER}_ISSUER_URI` | `OIDC_ISSUER_URI` | The IdP issuer URL. |
| Client ID | `{PROVIDER}_CLIENT_ID` | `OIDC_CLIENT_ID` | The OAuth client id. |
| Client Secret | `{PROVIDER}_CLIENT_SECRET` | `OIDC_CLIENT_SECRET` | Optional — PKCE works without it. |

The default `GenericOIDCAuthState` (`__provider__ = "generic"`) resolves
`GENERIC_*` then `OIDC_*`, so in practice you only set the `OIDC_*` keys for it.
Register the plugin's `auth_callback_endpoint` URI (default `/callback`) with
your IdP as the redirect URI.

## Registering providers with the plugin

`AuthPlugin(auth_providers=[...])` accepts either provider **classes** or
`"module.ClassName"` import-path **strings** (resolved lazily at compile time).
Order is preserved, and the two forms may be mixed. The default is
`[GenericOIDCAuthState]`.

```md alert warning
# Use import-path strings in `rxconfig.py`
Provider modules import `reflex_enterprise`, which loads `rxconfig` at import
time. Importing a provider class directly in `rxconfig.py` would re-enter the
config. Pass providers as `"module.ClassName"` strings there so the plugin can
resolve them lazily once the config exists.
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

Outside `rxconfig.py` (for example, in tests), you may pass the classes
themselves:

```python
from my_app.auth import OktaAuthState

rxe.AuthPlugin(auth_providers=[OktaAuthState])
```

## Scopes and refresh tokens

`extra_scopes` is forwarded to every configured provider and merged into the
scopes each one requests. The merge is deduped and preserves any existing scopes
(including `openid` and `offline_access`):

```python
rxe.AuthPlugin(
    auth_providers=["my_app.auth.OktaAuthState"],
    extra_scopes=["offline_access"],
)
```

- `extra_scopes=["offline_access"]` asks the IdP to issue a **refresh token**.
  Once a refresh token is granted, the framework refreshes the access token
  automatically and proactively as it nears expiry.
- `extra_scopes=["groups"]` requests group claims, useful for authorization
  checks against `userinfo.get("groups")`.

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
If two or more providers would both fall back to the shared `OIDC_*` config for
a required key (issuer or client id), distinct identity providers would silently
collapse onto one value. The plugin raises a `ConfigError` at wiring time naming
the offending providers. Set a provider-specific `{PROVIDER}_*` variable
(e.g. `OKTA_ISSUER_URI`, `AZURE_ISSUER_URI`) for each.
```

## Customizing claims

`OIDCUserInfo` is a `TypedDict` (`total=False`) with a single `sub` key; it is a
plain dict at runtime, so you read claims with `.get(...)`. To document the
extra claims a provider returns, declare a nested
`UserInfo(OIDCUserInfo, total=False)` on your provider — exactly as
`GenericOIDCAuthState.UserInfo` does:

```python
from reflex_enterprise.auth.oidc.state import OIDCAuthState
from reflex_enterprise.auth.oidc.types import OIDCUserInfo


class OktaAuthState(OIDCAuthState, rx.State):
    __provider__ = "okta"

    class UserInfo(OIDCUserInfo, total=False):
        name: str
        email: str
        groups: list[str]
```

## Advanced extension points

`OIDCAuthState` exposes a set of overridable async hooks for advanced cases.
Most apps never need to touch these — the defaults run the standard flow. Each
is a method you override on your provider subclass:

- `_validate_tokens(self) -> bool` — validate the current access and ID tokens;
  return whether they are valid.
- `_verify_jwt(self, token_json) -> Token` — verify the ID token JWT; override
  to customize verification.
- `_valid_issuers(self) -> list[str] | None` — return the acceptable `iss` claim
  values; override for cases like Azure multi-tenant.
- `_set_tokens(self, access_token, id_token=None, refresh_token=None, granted_scopes=None, **kwargs)`
  — persist the tokens after a successful exchange; override to handle extra
  data from the token response.
- `_validate_auth_callback_exchange(self, exchange) -> dict | None` — validate
  the token-exchange response from the callback.
- `_fetch_userinfo(self) -> OIDCUserInfo` — fetch the claims from the IdP's
  userinfo endpoint; override to fetch or reshape the claims differently.
- `_on_access_token_change(self, new_access_token, refresh=False)` — react when
  the access token is set or refreshed.
- `_on_refresh_access_token(self, new_access_token)` — react specifically when
  the access token is refreshed.

## Migrating from `register_auth_endpoints`

`OIDCAuthState.register_auth_endpoints(app)` is deprecated (since
reflex-enterprise v0.9.1, removed in 1.0). Register `rxe.AuthPlugin` in
`rxe.Config(plugins=[...])` instead — it wires the `/login`, `/logout`, and
`/callback` routes (and the secure-by-default protections) automatically.

## Related

- [Custom pages](/docs/enterprise/auth/custom-pages/) — replace the login /
  callback / logout page builders.
- [Testing](/docs/enterprise/auth/testing/) — exercise guarded surfaces against
  an injected user.
- [Secure by default](/docs/enterprise/auth/secure-by-default/) — how the plugin
  protects pages, event handlers, fields, and computed vars.
