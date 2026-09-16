---
title: Customizing the Auth Pages
---

_New in reflex-enterprise v0.9.1._

# Customizing the Auth Pages

`rxe.AuthPlugin` registers four auth routes and owns their protocol wiring. The
component rendered on each route is customizable; the OIDC redirect, callback
token exchange, and logout dispatch remain plugin-owned.

| Endpoint | Default route | Plugin-owned wiring | Builder |
| --- | --- | --- | --- |
| `login_endpoint` | `/login` | Renders the login palette and starts the OIDC redirect. | `login_page` |
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

Name the required entries and add `**context` to ignore the rest:

```python
import reflex as rx


def custom_login_page(providers, **context) -> rx.Component: ...
```

A builder may also accept only `**context`. The same contract
applies to the login, callback, logout, and forbidden builders.

## A custom login page

In most apps, send users to `/login`. Customize `login_page` when the default
login buttons need a different layout.

Call each provider's `get_login_button(*children)` and pass the clickable
element as children. This preserves the OIDC redirect wiring and the iframe
popup listener. `provider.display_name()` returns the provider label; by default
it is the title-cased `__provider__` value:

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

With two or more providers, render one `get_login_button()` per provider. See
[running inside an iframe](/docs/enterprise/auth/providers/#running-inside-an-iframe)
for the popup flow requirement.

## Custom callback and logout pages

The callback and logout routes only show an interstitial while their
plugin-owned `on_load` runs. Reuse `providers[0].get_authentication_loading_page()`,
which already shows the validating and redirecting states as the exchange (or
logout) proceeds, plus an error view if it fails (see
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

Wrap that view in an app-specific layout when the interstitial needs branding.

## Auth-failure UX and troubleshooting

When a token exchange or validation fails, `get_authentication_loading_page()`
swaps its spinner for an error view: a user-facing message plus an **error ID**
(a per-flow UUID) the user can hand to support. The same failure is logged on the
backend at `ERROR` level, prefixed `<client_token> [txid=<id>]`. The log entry
is emitted even when the app configures no logging. Use the displayed ID to find
the matching server log.

```md alert info
# Operator note
When a user reports a failed login, search the backend logs for `[txid=...]` with the ID they were shown.
```

The page builders do **not** take an error override. `default_callback_page`
calls `get_authentication_loading_page()`. There are two supported ways to
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
A custom callback or logout builder can branch on them directly:

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
are not authorized to view. This happens when the global default
`AuthPlugin(auth=...)` is a callable check that fails on a page load. The
forbidden page has no plugin-owned `on_load`.

```python
import reflex as rx


def custom_forbidden_page(**context) -> rx.Component:
    return rx.center(
        rx.vstack(
            rx.heading("403", size="8"),
            rx.text("Access denied."),
            rx.link("Back to home", href="/"),
            spacing="3",
            align="center",
        ),
        min_height="60vh",
    )
```

```md alert info
# When does the forbidden page appear?
Only on a **page** load that an authenticated user fails through a callable global default. Failed event-handler checks show an `"Action not allowed"` toast. Failed field and var checks withhold the value. Neither navigates to `/forbidden`. See [authentication vs authorization](/docs/enterprise/auth/secure-by-default/#authentication-vs-authorization).
```

## Wiring them up

Pass the builders to the plugin in `rxconfig.py` as **import-path strings**
(`"module.function"`). The builder modules import `reflex_enterprise`, which loads
`rxconfig` at import time. Importing them directly in `rxconfig.py` would
re-enter the config. Import-path strings are resolved lazily at compile time:

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
The import-path string is only required in `rxconfig.py`. Where the builder is already importable, pass the callable directly: `login_page=custom_login_page`.
```

## Defaults

Omit a builder and the plugin falls back to its defaults from
`reflex_enterprise.auth.pages`:

| Builder argument | Default | Renders |
| --- | --- | --- |
| `login_page` | `default_login_page` | One `provider.get_login_button()` per provider. |
| `callback_page` | `default_callback_page` | `providers[0].get_authentication_loading_page()`. |
| `logout_page` | `default_logout_page` | `providers[0].get_authentication_loading_page()`. |
| `forbidden_page` | `default_forbidden_page` | A 403 access denied view. |

The defaults take the same keyword context. A custom builder may call a default
builder and wrap the returned content:

```python
import reflex as rx
from reflex_enterprise.auth import default_login_page


def custom_login_page(providers, **context) -> rx.Component:
    return rx.center(default_login_page(providers=providers, **context))
```

## Related

- [Providers](/docs/enterprise/auth/providers/): identity provider
  configuration.
- [Secure by default](/docs/enterprise/auth/secure-by-default/): protected
  surfaces and `/forbidden` behavior.
- [Testing](/docs/enterprise/auth/testing/): guarded-surface tests.
