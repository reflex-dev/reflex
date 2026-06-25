---
title: Customizing the Auth Pages
---

_New in reflex-enterprise v0.9.1._

# Customizing the Auth Pages

`rxe.AuthPlugin` registers four friendly routes and owns their **wiring**. You
can replace the **rendered component** on each route, but the real OIDC flow
itself — the login button's redirect (via `get_login_button`), the callback's
`on_load` token exchange, and the logout's `on_load` dispatch — stays
plugin-owned, so you never reimplement it.

| Endpoint | Default route | Plugin-owned wiring | Builder |
| --- | --- | --- | --- |
| `login_endpoint` | `/login` | Renders the login palette / starts the OIDC redirect. | `login_page` |
| `auth_callback_endpoint` | `/callback` | CSRF (OAuth `state`) check + authorization-code token exchange, then redirect back. | `callback_page` |
| `logout_endpoint` | `/logout` | Dispatches the active provider's logout; a CSRF guard blocks cross-site logout (see [secure by default](/docs/enterprise/auth/secure-by-default/#logout-is-protected-against-csrf)). | `logout_page` |
| `forbidden_endpoint` | `/forbidden` | Shown when an authenticated user lacks permission to view a page. | `forbidden_page` |

The routes themselves are configurable through `login_endpoint`,
`logout_endpoint`, `auth_callback_endpoint`, and `forbidden_endpoint`. See the
[providers](/docs/enterprise/auth/providers/) page for configuring identity
providers, and the [overview](/docs/enterprise/auth/overview/) for how the plugin
fits together.

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
applies to the login, callback, logout, and forbidden builders.

## A custom login page

The login builder wraps each provider's `get_login_button(*children)` so the real
OIDC redirect wiring is unchanged — only the surrounding layout is yours. Loop
over `providers` and pass the clickable element you want as the button's
children. `provider.display_name()` returns a pretty name (the provider's
`__provider__` title-cased by default):

```python
import reflex as rx


def custom_login_page(providers, **context) -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("Sign in"),
            *[
                provider.get_login_button(
                    rx.button(f"Continue with {provider.display_name()}")
                )
                for provider in providers
            ],
            spacing="4",
        ),
        min_height="60vh",
    )
```

With two or more providers this naturally renders one button per provider — a
login palette where the visitor picks an identity provider.

Wrapping `provider.get_login_button()` also preserves the iframe/popup message
listener it mounts — see "Running inside an iframe" in
[providers](/docs/enterprise/auth/providers/).

## Custom callback and logout pages

The callback and logout routes only show an interstitial while their
plugin-owned `on_load` runs. Reuse `providers[0].get_authentication_loading_page()`,
which already shows the validating and redirecting states as the exchange (or
logout) proceeds — and an error view if it fails (see
[auth-failure UX and troubleshooting](#auth-failure-ux-and-troubleshooting)):

```python
import reflex as rx


def custom_callback_page(providers, **context) -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.text("Completing sign-in…"),
            providers[0].get_authentication_loading_page(),
        ),
        min_height="60vh",
    )


def custom_logout_page(providers, **context) -> rx.Component:
    return providers[0].get_authentication_loading_page()
```

Wrap that view in your own layout to brand the interstitial — for example a
centered card with a heading above the loading view.

## Auth-failure UX and troubleshooting

When a token exchange or validation fails, `get_authentication_loading_page()`
swaps its spinner for an error view: a user-facing message plus an **error ID**
(a per-flow UUID) the user can hand to support. The same failure is logged on the
backend at `ERROR` level, prefixed `<client_token> [txid=<id>]` — emitted even
when the app configures no logging — so the ID the user sees greps straight to
the matching server log.

```md alert info
# Operator note
When a user reports a failed login, search the backend logs for `[txid=...]` with the ID they were shown.
```

The page builders do **not** take an error override — `default_callback_page`
just calls `get_authentication_loading_page()`. There are two real ways to
customize the failure UI:

**1. Override the state classmethods.** Subclass your provider state and override
`get_error_component`, `get_authentication_error_component`, or
`get_logout_error_component`. The loading page picks up the override automatically:

```python
import reflex as rx
from reflex_enterprise.auth import GenericOIDCAuthState


class MyProviderState(GenericOIDCAuthState):
    @classmethod
    def get_error_component(cls, operation, suggestion, error_id) -> rx.Component:
        return rx.vstack(
            rx.heading("Something went wrong"),
            rx.text(suggestion),
            rx.text("Error ID: ", rx.badge(error_id)),
        )
```

**2. Hand-write a page reading the public vars.** `has_error`,
`user_error_message`, and `last_error_txid` are public Vars on the provider state,
so a custom callback or logout builder can branch on them directly:

```python
import reflex as rx


def custom_callback_page(providers, **context) -> rx.Component:
    provider = providers[0]
    return rx.center(
        rx.cond(
            provider.has_error,
            rx.vstack(
                rx.heading("Sign-in failed"),
                rx.text(provider.user_error_message),
                rx.text("Error ID: ", rx.badge(provider.last_error_txid)),
            ),
            provider.get_authentication_loading_page(),
        ),
        min_height="60vh",
    )
```

## A custom forbidden page

`/forbidden` is shown when an **authenticated** user tries to load a page they
aren't authorized to view — i.e. the global default `AuthPlugin(auth=...)` is a
callable check that the user fails on a page load. It's a normal page with no
plugin-owned `on_load`, so it's the most freely customizable:

```python
import reflex as rx


def custom_forbidden_page(**context) -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("403", size="8"),
            rx.text("You don't have access to that page."),
            rx.link("Back to home", href="/"),
            spacing="3",
            align="center",
        ),
        min_height="60vh",
    )
```

```md alert info
# When does the forbidden page appear?
Only on a **page** load that an authenticated user fails (a callable global default). Failed event-handler checks show an `"Action not allowed"` toast, and failed field/var checks simply withhold the value — neither navigates to `/forbidden`. See [authentication vs authorization](/docs/enterprise/auth/secure-by-default/#authentication-vs-authorization).
```

## Wiring them up

Pass the builders to the plugin in `rxconfig.py` as **import-path strings**
(`"module.function"`). The builder modules import `reflex_enterprise`, which loads
`rxconfig` at import time, so importing them in `rxconfig.py` would re-enter the
config; the plugin resolves the strings lazily at compile time instead:

```python
import reflex_enterprise as rxe

config = rxe.Config(
    app_name="my_app",
    plugins=[
        rxe.AuthPlugin(
            login_page="my_app.auth_pages.custom_login_page",
            callback_page="my_app.auth_pages.custom_callback_page",
            logout_page="my_app.auth_pages.custom_logout_page",
            forbidden_page="my_app.auth_pages.custom_forbidden_page",
        ),
    ],
)
```

```md alert info
# Strings in rxconfig, callables elsewhere
The import-path string is only required because of the rxconfig re-entry. Where the builder is already importable, you can pass the callable directly: `login_page=custom_login_page`.
```

## Defaults

Omit a builder and the plugin falls back to its defaults from
`reflex_enterprise.auth.pages`:

| Builder argument | Default | Renders |
| --- | --- | --- |
| `login_page` | `default_login_page` | One `provider.get_login_button()` per provider. |
| `callback_page` | `default_callback_page` | `providers[0].get_authentication_loading_page()`. |
| `logout_page` | `default_logout_page` | `providers[0].get_authentication_loading_page()`. |
| `forbidden_page` | `default_forbidden_page` | A 403 "you don't have permission" view. |

The defaults take the same keyword context, so a custom builder may call one to
wrap the default content in its own layout:

```python
import reflex as rx
from reflex_enterprise.auth import default_login_page


def custom_login_page(providers, **context) -> rx.Component:
    return rx.center(default_login_page(providers=providers, **context))
```

## Related

- [Providers](/docs/enterprise/auth/providers/) — configure the identity providers the login page renders buttons for.
- [Secure by default](/docs/enterprise/auth/secure-by-default/) — how the rest of the app is protected, and when `/forbidden` is shown.
- [Testing](/docs/enterprise/auth/testing/) — verify guarded surfaces.
