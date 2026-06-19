---
title: Customizing the Auth Pages
---

_New in reflex-enterprise v0.9.1._

# Customizing the Auth Pages

`rxe.AuthPlugin` registers three friendly routes and owns their **wiring**:

| Endpoint | Default route | Plugin-owned wiring |
| --- | --- | --- |
| `login_endpoint` | `/login` | Renders the login palette / starts the OIDC redirect. |
| `auth_callback_endpoint` | `/callback` | CSRF (OAuth `state`) check + authorization-code token exchange, then redirect back. |
| `logout_endpoint` | `/logout` | Dispatches the active provider's logout. |

You can replace only the **rendered component** on each route via the
`login_page`, `callback_page`, and `logout_page` builders — the `on_load`
wiring (login redirect, callback token exchange, logout dispatch) stays
plugin-owned, so the real OIDC flow is never something you reimplement.

The routes themselves are configurable through `login_endpoint`,
`logout_endpoint`, and `auth_callback_endpoint` (defaults `/login`, `/logout`,
`/callback`). See the [providers](/docs/enterprise/auth/providers/) page for
configuring identity providers, and the
[overview](/docs/enterprise/auth/overview/) for how the plugin fits together.

```md alert warning
# Register the callback URI with your IdP
If you change `auth_callback_endpoint`, register that exact URI as the OAuth redirect URI with your identity provider, or the token exchange will be rejected.
```

## The page builder contract

A page builder is a callable that receives the build context as **keyword
arguments**:

| Keyword | Type | Meaning |
| --- | --- | --- |
| `providers` | `Sequence[type[OIDCAuthState]]` | The resolved provider state classes. |
| `plugin` | `AuthPlugin` | The plugin instance. |

Name the entries you need and add `**context` to ignore the rest:

```python
import reflex as rx


def custom_login_page(providers, **context) -> rx.Component: ...
```

A builder may also take all of it with `**context` only. The same contract
applies to the login, callback, and logout builders.

## A custom login page

The login builder wraps each provider's `get_login_button(*children)` so the
real OIDC redirect wiring is unchanged — only the surrounding layout is yours.
Loop over `providers` and pass the clickable element you want as the button's
children. `provider.display_name()` returns a pretty name (it defaults to the
provider's `__provider__` title-cased):

```python
import reflex as rx


def custom_login_page(providers, **context) -> rx.Component:
    return rx.center(
        rx.vstack(
            *[
                provider.get_login_button(
                    rx.button(f"Continue with {provider.display_name()}")
                )
                for provider in providers
            ],
        ),
    )
```

With two or more providers this naturally renders one button per provider — a
login palette where the visitor picks an identity provider.

## Custom callback and logout pages

The callback and logout routes only show an interstitial while their
plugin-owned `on_load` runs. Reuse `providers[0].get_authentication_loading_page()`,
which already shows the validating and redirecting states as the exchange (or
logout) proceeds — and an error view if it fails:

```python
import reflex as rx


def custom_callback_page(providers, **context) -> rx.Component:
    return providers[0].get_authentication_loading_page()


def custom_logout_page(providers, **context) -> rx.Component:
    return providers[0].get_authentication_loading_page()
```

Wrap that view in your own layout to brand the interstitial — for example a
centered card with a heading above the loading view.

## Wiring them up

Pass the builders to the plugin in `rxconfig.py` as **import-path strings**
(`"module.function"`). The builder modules import `reflex_enterprise`, which
loads `rxconfig` at import time, so importing them in `rxconfig.py` would
re-enter the config; the plugin resolves the strings lazily at compile time
instead:

```python
import reflex as rx

import reflex_enterprise as rxe

config = rxe.Config(
    app_name="my_app",
    plugins=[
        rxe.AuthPlugin(
            login_page="my_app.auth_pages.custom_login_page",
            callback_page="my_app.auth_pages.custom_callback_page",
            logout_page="my_app.auth_pages.custom_logout_page",
        ),
    ],
)
```

```md alert info
# Strings in rxconfig, callables elsewhere
The import-path string is only required because of the rxconfig re-entry. If you build the `AuthPlugin` somewhere the builder is already importable, you can pass the callable directly: `login_page=custom_login_page`.
```

## Defaults

Omit a builder and the plugin falls back to its defaults from
`reflex_enterprise.auth.pages`:

| Builder argument | Default | Renders |
| --- | --- | --- |
| `login_page` | `default_login_page` | One `provider.get_login_button()` per provider. |
| `callback_page` | `default_callback_page` | `providers[0].get_authentication_loading_page()`. |
| `logout_page` | `default_logout_page` | `providers[0].get_authentication_loading_page()`. |

The defaults take the same `providers` / `plugin` keyword context, so a custom
builder may call one to wrap the default content in its own layout:

```python
import reflex as rx

from reflex_enterprise.auth.pages import default_login_page


def custom_login_page(providers, **context) -> rx.Component:
    return rx.center(default_login_page(providers=providers, **context))
```

## Related

- [Providers](/docs/enterprise/auth/providers/) — configure the identity
  providers the login page renders buttons for.
- [Testing](/docs/enterprise/auth/testing/) — verify guarded surfaces.
- [Secure by default](/docs/enterprise/auth/secure-by-default/) — how the rest
  of the app is protected.
