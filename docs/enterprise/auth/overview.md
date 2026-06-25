---
title: Authentication Overview
---

_New in reflex-enterprise v0.9.1._

# Authentication Overview

`rxe.AuthPlugin` adds [OIDC](https://openid.net/developers/how-connect-works/)
(OpenID Connect) authentication to your Reflex app with a **secure-by-default**
model. Drop the plugin into `rxe.Config(plugins=[...])`, point it at an identity
provider with three environment variables, and every page, event handler, base
field, and computed var in your app requires a logged-in user — until you
explicitly opt a surface out.

The plugin runs the real OIDC Authorization Code + PKCE flow against your
identity provider (IdP) and auto-registers friendly `/login`, `/logout`,
`/callback`, and `/forbidden` routes, so you never reimplement the protocol.

```md alert warning
# Requirements
The auth plugin ships with `reflex-enterprise` (v0.9.1+). Your app **must** use `rxe.App()` (not `rx.App()`), and you must configure an OIDC identity provider via environment variables. Using a plain `rx.App()` with the plugin raises a `ConfigError` at startup.
```

## Quickstart

There are three steps: install the plugin, configure a provider, and use
`rxe.App()`.

**1. Add `rxe.AuthPlugin()` to `rxconfig.py`** and configure your OIDC provider
through the `OIDC_*` environment variables:

```python
import os

import reflex as rx
import reflex_enterprise as rxe

os.environ.setdefault("OIDC_ISSUER_URI", "https://your-idp.example.com")
os.environ.setdefault("OIDC_CLIENT_ID", "your-client-id")
os.environ.setdefault("OIDC_CLIENT_SECRET", "your-client-secret")  # optional with PKCE

config = rxe.Config(
    app_name="my_app",
    plugins=[
        rxe.AuthPlugin(),
    ],
)
```

With the `OIDC_*` variables set, the app imports and compiles even before the IdP
is reachable — the issuer is contacted only when a user logs in (OIDC discovery),
so placeholder values are enough for local builds and CI.

**2. Use `rxe.App()`** (not `rx.App()`) in your app module:

```python
import reflex_enterprise as rxe

app = rxe.App()
```

**3. Register the redirect URI with your IdP.** Add the plugin's
`auth_callback_endpoint` (`/callback` by default) as an allowed redirect URI in
your identity provider's client settings. Register the **full** URL (scheme +
host + path) for each environment — the most common setup error is
`redirect_uri_mismatch`; see
[deploying to production](/docs/enterprise/auth/deployment/) for the exact value
to register.

That's it. With the `OIDC_*` variables set you need **no provider code** — the
plugin defaults to a built-in `GenericOIDCAuthState` that reads those three
variables. See [providers](/docs/enterprise/auth/providers/) for named and
multi-provider setups.

## The four protected surfaces

Once the plugin is active, four kinds of surface are protected by default. Each
has its own opt-out and its own behavior when a caller is not allowed:

| Surface | Default | How it's withheld | Opt out / gate |
| --- | --- | --- | --- |
| Pages (`@rxe.page` / `@rx.page` / `app.add_page`) | login required | redirect to `/login` | `auth=False`, or `@rxe.page(auth=True)` to force login |
| Event handlers (`@rxe.event`) | login required | block + redirect/toast | `@rxe.event(auth=False)` or `auth=<check>` |
| Base fields (`rxe.field` / plain `rx.field`) | withheld until login | replaced with its declared default | `rxe.field(default, auth=False)` or `auth=<check>` |
| Computed vars (`@rxe.var`) | withheld until login | replaced with its `initial_value` (dropped if it has none) | `@rxe.var(auth=False)` or `auth=<check>` |

`auth=True` is the secure default on every surface, so a plain `rx.field(...)` or
a bare `@rxe.var` on one of your state classes is **already** protected. You
don't mark things protected — they start protected, and you open up the
surfaces that should be public.

```python
import reflex as rx
import reflex_enterprise as rxe


class DashboardState(rx.State):
    # Protected by default — withheld from the client until the user logs in.
    revenue: rx.Field[float] = rx.field(0.0)

    # Explicitly public — always sent to the client.
    theme: rx.Field[str] = rxe.field("light", auth=False)

    @rxe.event  # default auth=True: anonymous callers are redirected to /login
    async def refresh(self): ...

    @rxe.event(auth=False)  # public handler anyone may call
    def toggle_theme(self):
        self.theme = "dark" if self.theme == "light" else "light"
```

See [secure by default](/docs/enterprise/auth/secure-by-default/) for the full
enforcement model, the four `auth=` wrappers, and authorization check functions.

## Reading the current user

`reflex_enterprise.auth.User` is the app-facing handle on the current user (an
alias of `AuthUserState`). Its class-level Vars embed directly in components and
are populated after login by whichever provider authenticated the user:

```python
import reflex as rx
from reflex_enterprise.auth import User


def profile() -> rx.Component:
    return rx.hstack(
        rx.avatar(src=User.picture, fallback="U"),
        rx.vstack(
            rx.heading(User.name),
            rx.text(User.email, color_scheme="gray"),
        ),
    )
```

Inside an event handler, `await User.current()` returns the user's
`OIDCUserInfo` claims dict (or `None` when anonymous):

```python
import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.auth import User


class GreetState(rx.State):
    @rxe.event  # default auth=True
    async def greet(self):
        user = await User.current() or {}
        return rx.toast(f"Hello {user.get('name') or user.get('sub')}!")
```

The full `User` facade — frontend Vars, `current()`, and `current_provider()` —
is documented in
[secure by default](/docs/enterprise/auth/secure-by-default/#reading-the-current-user).

## Signing out

There is no logout-button helper. Sign the user out either by linking to the
`/logout` route — which dispatches the active provider's logout — or by binding
the provider's `redirect_to_logout` event directly:

```python
import reflex as rx
from reflex_enterprise.auth import GenericOIDCAuthState

# Either link to the logout route…
rx.link("Sign out", href="/logout")

# …or bind the provider's logout event.
rx.button("Sign out", on_click=GenericOIDCAuthState.redirect_to_logout)
```

A canonical header that links to `/login` when anonymous and to `/logout` once a
user is signed in, completing the `User.provider_name` pattern from
[secure by default](/docs/enterprise/auth/secure-by-default/#reading-the-current-user):

```python
import reflex as rx
from reflex_enterprise.auth import User


def header() -> rx.Component:
    return rx.cond(
        User.provider_name != "",
        rx.hstack(
            rx.text(f"Signed in as {User.name}"),
            rx.link("Sign out", href="/logout"),
        ),
        rx.link("Log in", href="/login"),
    )
```

## How a login flows end to end

1. An anonymous visitor hits a protected page (or calls a protected handler) and
   is redirected to `/login`, with the page they wanted preserved as a
   `redirect_to` query parameter.
2. `/login` renders a button per configured provider. The visitor clicks one and
   is sent to the IdP's authorization endpoint (Authorization Code + PKCE).
3. The IdP authenticates the user and redirects back to `/callback`, which
   validates the OAuth `state` (CSRF), exchanges the code for tokens, and stores
   them in secure cookies.
4. The user is redirected back to `redirect_to`. Protected fields, vars, pages,
   and handlers now resolve against the authenticated user.
5. `/logout` clears the session — tokens and the protected surface of every
   state — and chains the provider's logout. A CSRF guard blocks cross-site
   logout requests (see
   [secure by default](/docs/enterprise/auth/secure-by-default/#logout-is-protected-against-csrf)).

## Learn more

- [Secure by default](/docs/enterprise/auth/secure-by-default/) — the
  enforcement model, the four `auth=` wrappers, sync and async authorization
  checks, and the `User` facade.
- [Providers](/docs/enterprise/auth/providers/) — the built-in
  `GenericOIDCAuthState`, naming your own provider, OIDC environment variables,
  scopes and refresh tokens, and multi-provider setups.
- [Custom pages](/docs/enterprise/auth/custom-pages/) — replacing the rendered
  `/login`, `/callback`, `/logout`, and `/forbidden` components with your own
  builders.
- [Testing](/docs/enterprise/auth/testing/) — unit-testing authorization checks
  and exercising the full OIDC flow against a mock IdP.
- [Deploying to production](/docs/enterprise/auth/deployment/) — HTTPS/cookies,
  the exact redirect URI, reverse proxies, and a troubleshooting reference.
- [Enterprise overview](/docs/enterprise/overview/) — the rest of
  reflex-enterprise.
