---
title: Authentication Overview
---

_New in reflex-enterprise v0.9.1._

# Authentication Overview

`rxe.AuthPlugin` adds OIDC (OpenID Connect) authentication to your Reflex app
with a **secure-by-default** model. Once the plugin is in
`rxe.Config(plugins=[...])`, four surfaces require a logged-in user unless you
explicitly opt out: **pages** (anonymous visitors are redirected to login),
**event handlers** (anonymous callers are blocked and redirected), **base state
fields** (dropped from the state delta until login), and **computed vars**
(withheld until login). The plugin runs the real OIDC Authorization Code + PKCE
flow against your identity provider and auto-registers friendly `/login`,
`/logout`, and `/callback` routes.

```md alert warning
# Requirements
Requires `reflex-enterprise` with the auth plugin (v0.9.1+). Your app must use `rxe.App()` (not `rx.App()`), and you must configure an OIDC identity provider via environment variables.
```

## Quickstart

Add `rxe.AuthPlugin()` to the `plugins` list of `rxe.Config` in `rxconfig.py`,
and configure your OIDC provider through the `OIDC_*` environment variables:

```python
import os

import reflex as rx
import reflex_enterprise as rxe

os.environ.setdefault("OIDC_ISSUER_URI", "https://your-idp.example.com")
os.environ.setdefault("OIDC_CLIENT_ID", "your-client-id")
os.environ.setdefault("OIDC_CLIENT_SECRET", "your-client-secret")

config = rxe.Config(
    app_name="my_app",
    plugins=[
        rxe.AuthPlugin(),
    ],
)
```

Your app must use `rxe.App()` (not `rx.App()`):

```python
import reflex_enterprise as rxe

app = rxe.App()
```

With the `OIDC_*` variables set you need **no custom provider** — the plugin
defaults `auth_providers` to `[GenericOIDCAuthState]`, which reads
`OIDC_ISSUER_URI`, `OIDC_CLIENT_ID`, and `OIDC_CLIENT_SECRET`. Register the
plugin's `auth_callback_endpoint` (`/callback` by default) as the redirect URI
with your IdP. See [providers](/docs/enterprise/auth/providers/) for named and
multi-provider setups.

## The four protected surfaces

Each surface is protected by default and has its own way to opt out or gate:

| Surface | Default | Opt out / gate |
| --- | --- | --- |
| Pages (`@rxe.page` / `app.add_page` / `@rx.page`) | login required | `@rxe.page(auth=False)` or `app.add_page(..., auth=False)` |
| Event handlers (`@rxe.event`) | login required | `@rxe.event(auth=False)` or `@rxe.event(auth=<check>)` |
| Base fields (`rxe.field` / plain `rx.field`) | withheld until login | `rxe.field(default, auth=False)` |
| Computed vars (`@rxe.var`) | withheld until login | `@rxe.var(auth=False)` |

`auth=True` is the secure default on every surface, so a plain `rx.field(...)`
or a bare `@rxe.var` on a non-exempt state is already protected. Pass
`auth=False` to opt a surface out and make it public. Event handlers and
fields/vars also accept a **callable** authorization check that runs only after
authentication succeeds; pages take `auth` as a bool only. See
[secure-by-default](/docs/enterprise/auth/secure-by-default/) for the full
enforcement model and check-function signatures.

## Reading the current user

`reflex_enterprise.auth.User` is the app-facing handle on the current user. Its
class-level Vars — `User.name`, `User.email`, `User.sub`, `User.picture` — embed
directly in components (`rx.text(User.name)`, `rx.avatar(src=User.picture)`).
Inside an event handler, `await User.current()` returns the user's `OIDCUserInfo`
dict (or `None` when anonymous):

```python
import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.auth import User


class DemoState(rx.State):
    @rxe.event  # default auth=True
    async def protected_action(self):
        user = await User.current() or {}
        return rx.toast(f"Hello {user.get('name') or user.get('sub')}!")
```

See [secure-by-default](/docs/enterprise/auth/secure-by-default/) for the full
`User` facade and how protected values are delivered after login.

## Learn more

- [Secure by default](/docs/enterprise/auth/secure-by-default/) — the
  enforcement model, the four `auth=` wrappers, check functions, and the `User`
  facade.
- [Providers](/docs/enterprise/auth/providers/) — `GenericOIDCAuthState`, named
  and multi-provider setups, and OIDC environment variables.
- [Custom pages](/docs/enterprise/auth/custom-pages/) — replacing the rendered
  `/login`, `/callback`, and `/logout` components with your own builders.
- [Testing](/docs/enterprise/auth/testing/) — exercising guarded surfaces with
  `auth_as`.
- [Enterprise overview](/docs/enterprise/overview/) — the rest of
  reflex-enterprise.
