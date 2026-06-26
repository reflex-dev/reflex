---
title: Secure by Default
---

_New in reflex-enterprise v0.9.1._

# Secure by Default

Once `rxe.AuthPlugin` is configured (see the
[overview](/docs/enterprise/auth/overview/)), **every** non-exempt page, event
handler, base field, and computed var in your app requires a logged-in user
unless you explicitly opt it out.

```md alert warning
# Requires `rxe.App` and a configured provider
Secure-by-default only applies when your app uses `rxe.App()` (not `rx.App()`) and `rxe.AuthPlugin` is in `rxe.Config(plugins=[...])` with an OIDC provider configured. See the [overview](/docs/enterprise/auth/overview/).
```

## The `auth=` value

`auth=` accepts three kinds of value:

| `auth=` value | Meaning |
| --- | --- |
| `True` | Require an authenticated user. This is the default for every surface. |
| `False` | Public. Allow everyone. |
| a callable check | An authorization check that runs **only after** authentication succeeds. A truthy result allows; a falsey result or a raised exception denies. |

The four wrappers are exported at top level: `rxe.page`, `rxe.event`,
`rxe.field`, and `rxe.var`. `rxe.event`, `rxe.field`, and `rxe.var` accept all
three values. `rxe.page` takes a **bool only**.

### The global default

`AuthPlugin(auth=...)` sets the default applied to every surface that carries no
explicit `auth=` of its own. It accepts the same three values:

```python
rxe.AuthPlugin(auth=True)  # any authenticated user (the default)
rxe.AuthPlugin(auth=False)  # open by default
rxe.AuthPlugin(auth=my_org_check)  # org-wide authorization check after login
```

A plain `rx.field(...)`, a bare `@rxe.var`, a bare `@rxe.event`, and an
`@rxe.page()` with no `auth=` all **inherit** this global default. An explicit
per-surface `rxe.*(auth=...)` always overrides it. Changing
`AuthPlugin(auth=...)` changes the app baseline without editing each field, var,
event, or page.

### Gate the whole app behind a role

A callable global default runs on every untagged page load:

```python
# my_app/auth.py
from reflex_enterprise.auth import AuthContext


def is_member_of(ctx: AuthContext) -> bool:
    """Allow only members of the ``admins`` group."""
    return "admins" in (ctx.auth_user_state.userinfo.get("groups") or [])
```

```python
# rxconfig.py
import reflex_enterprise as rxe

from my_app.auth import is_member_of

config = rxe.Config(
    app_name="my_app",
    plugins=[
        rxe.AuthPlugin(
            auth=is_member_of,
            extra_scopes=["groups"],
        )
    ],
)
```

Request `extra_scopes=["groups"]` when checks need the `groups` claim. See
[providers](/docs/enterprise/auth/providers/#the-claims-a-provider-returns).
Authenticated users who fail the check are sent to `/forbidden`, not back to
login. Replace that screen with a [custom forbidden
page](/docs/enterprise/auth/custom-pages/#a-custom-forbidden-page).

## Pages

Protect a page with `@rxe.page`. For pages, `auth` is a **bool only**. Callable
checks are not supported as a per-page argument, although the global default may
still be callable.

```python
def page(
    route: str | None = None,
    *,
    auth: bool | None = None,
    **page_kwargs,
)
```

- `auth=None` (the default): follow the configured global default
  (`AuthPlugin(auth=...)`).
- `auth=True`: always require an authenticated user, regardless of the global
  default.
- `auth=False`: public page.

A protected page injects a guard as the **first** `on_load` event. Anonymous
visitors are redirected to the login endpoint, and the requested page is
preserved as a `redirect_to` query parameter. The post-login flow returns them
there.

- The post-login `redirect_to` target is validated against the app's origin.
  Only same-origin absolute paths (e.g. `/dashboard`) or URLs sharing the app's
  scheme and host are honored. Any cross-origin, scheme-relative (`//evil.test`),
  or backslash target falls back to the index page.

```python
@rxe.page(
    route="/dashboard", title="Dashboard"
)  # auth=None: follows the global default
def dashboard() -> rx.Component:
    """Protected: anonymous visitors are redirected to /login."""
    ...


@rxe.page(route="/", title="Home", auth=False)
def index() -> rx.Component:
    """Public landing page (opted out of secure-by-default)."""
    ...
```

Any extra `**page_kwargs` are forwarded to `rx.page`: `title`, `image`,
`description`, `meta`, `script_tags`, and `on_load`. When `on_load` is provided,
the guard is prepended.

### Reading the user on page load

Because the guard is prepended, a page's `on_load` runs after authentication.
`await User.current()` (or `ctx.auth_user_state.userinfo`) is non-`None` there:

```python
@rxe.page(route="/dashboard", title="Dashboard", on_load=DashboardState.load)
def dashboard() -> rx.Component: ...


class DashboardState(rx.State):
    greeting: str = ""

    @rxe.event
    async def load(self):
        user = await User.current() or {}
        self.greeting = f"Welcome, {user.get('name') or user.get('sub')}"
```

`User.current()` is event-only; an `on_load` handler is an event and resolves
the authenticated user from the guard. See [reading the current
user](#reading-the-current-user).

### Pages Added Without `@rxe.page`

With the plugin active, `rxe.App()` defaults **every** page to login-required,
including pages added via `app.add_page(...)` or a plain `@rx.page`. Opt out with
`auth=False`:

```python
app.add_page(index, route="/", auth=False)
```

Because plain `@rx.page` takes no `auth` argument, use
`@rxe.page(auth=False)` to opt a decorated page out.

### When the global default is a callable

A page cannot take a callable `auth=` directly. If `AuthPlugin(auth=...)` is
callable, untagged pages (`@rxe.page()` / `@rx.page` / `app.add_page`) run it on
load. An authenticated visitor who **fails** the check is redirected to the
`forbidden_endpoint` (`/forbidden` by default). An explicit
`@rxe.page(auth=True)` only requires login and does **not** run the callable
default.

## Event handlers

Protect an event handler with `@rxe.event`. Here `auth` accepts a bool or a
callable check.

```python
def event(
    fn=None,
    *,
    auth: bool | EventAuthCheck = ...,
    **event_kwargs,
)
```

Works bare (`@rxe.event`) or called (`@rxe.event(auth=...)`), and can wrap a raw
function or an already-converted `EventHandler`. Extra `**event_kwargs` are
forwarded to `rx.event`: `background`, `stop_propagation`, `prevent_default`,
`throttle`, `debounce`, and `temporal`.

```python
class DemoState(rx.State):
    @rxe.event  # default auth=True: anonymous callers are redirected to /login
    async def protected_action(self):
        user = await User.current() or {}
        return rx.toast(f"Hello {user.get('name') or user.get('sub')}!")

    @rxe.event(auth=False)
    def public_action(self):
        """Anyone may call this."""
        ...
```

A failed authorization check on an event handler shows the
`"Action not allowed"` toast (see
[authentication vs authorization](#authentication-vs-authorization)).

## Base fields

Base (state) fields are protected by default. A plain `rx.field(...)`, or a bare
annotation, on one of your state classes is protected and dropped from the state
delta until the user is resolved. Use `rxe.field` to opt a field out or attach a
check.

```python
def field(
    default=...,
    *,
    auth: bool | FieldVarAuthCheck = ...,
    default_factory=None,
    is_var=True,
)
```

```python
class DemoState(rx.State):
    # Protected by default; dropped from the delta until login.
    notes: rx.Field[str] = rx.field("These notes are only sent once you log in.")

    # Public; always sent to the client.
    loading: rx.Field[bool] = rxe.field(False, auth=False)
```

A withheld field is replaced in the delta with its **declared default** (the
value baked into the frontend bundle) until the user is resolved.

## Computed vars

Computed vars are protected by default and withheld until login. Wrap them with
`@rxe.var`.

```python
def var(
    fget=None,
    *,
    auth: bool | FieldVarAuthCheck = ...,
    **var_kwargs,
)
```

Usable bare (`@rxe.var`) or called (`@rxe.var(auth=..., initial_value=...)`).
Extra `**var_kwargs` are forwarded verbatim to `rx.var`: `initial_value`,
`cache`, `deps`, `auto_deps`, `interval`, and `backend`.

```md alert info
# Always pair a protected var with `initial_value`
A protected var is withheld until the user is resolved. Set `initial_value=` to a placeholder baked into the frontend bundle and shown until the real value is delivered after login.
```

```python
class DemoState(rx.State):
    @rxe.var(initial_value="🔒 log in to reveal this")
    def protected_tip(self) -> str:
        """Protected by default; the placeholder shows until a user is resolved."""
        return "✅ Delivered only to logged-in users."

    @rxe.var(auth=False)
    def public_label(self) -> str:
        """Opened up to anonymous visitors."""
        return "Anyone can read this."
```

## Authorization checks

For finer-grained control than "any authenticated user," attach a **callable**
`auth=` check to the specific events, vars, or fields that need it. A check is a
function that receives a single **context object** and returns a bool (or an
awaitable of one):

```python
def check(ctx) -> bool: ...  # sync
async def check(ctx) -> bool: ...  # async
```

A check runs **only after** authentication succeeds. Anonymous callers are
redirected to login before the check runs, and a resolved user is always present
inside the check.

### The context object

Each surface passes a different context, all carrying the current user as
`ctx.auth_user_state` (an `AuthUserState`). Import them from
`reflex_enterprise.auth`:

| Context | Surface | Extra attributes |
| --- | --- | --- |
| `EventAuthContext` | event handler | `event_handler` (the gated handler), `payload` (the event payload dict) |
| `VarAuthContext` | field / computed var | `field_or_var` (the `Var`, or `None`) |
| `PageAuthContext` | page (callable global default only) | None |

Read the user's claims from `ctx.auth_user_state.userinfo`, a plain dict:

```python
from reflex_enterprise.auth import EventAuthContext, VarAuthContext


def is_admin(ctx: EventAuthContext) -> bool:
    """Event check: allow only members of the ``admins`` group."""
    return "admins" in (ctx.auth_user_state.userinfo.get("groups") or [])


def is_staff(ctx: VarAuthContext) -> bool:
    """Field/var check: allow only staff."""
    return "staff" in (ctx.auth_user_state.userinfo.get("groups") or [])


class DemoState(rx.State):
    @rxe.event(auth=is_admin)  # authorization failure -> "Action not allowed" toast
    def admin_action(self):
        return rx.toast.success("Admin action executed.")

    # Withheld unless the staff check passes; the placeholder shows otherwise.
    audit_log: rx.Field[list[str]] = rxe.field([], auth=is_staff)

    @rxe.var(auth=is_staff, initial_value="🔒 staff only")
    def staff_view(self) -> str:
        return "✅ staff-only computed var."
```

### One check for any surface

Annotate `ctx` with the `AuthContext` union to make one function usable on **any**
surface; annotate it with a single context type to restrict it (and get exact
autocomplete). `isinstance(ctx, EventAuthContext)` narrows the union inside the
body:

```python
from reflex_enterprise.auth import AuthContext, EventAuthContext


def is_admin(ctx: AuthContext) -> bool:
    """Usable as an event, field, var, or global-default check."""
    return "admins" in (ctx.auth_user_state.userinfo.get("groups") or [])
```

```md alert warning
# Cached claims can lag the IdP by up to 30 minutes
`ctx.auth_user_state.userinfo` is served from a server-side cache refreshed at most every 30 minutes. The access token is re-read at most about every 60 seconds. Checks that depend on `groups` or roles may see IdP-side changes, such as group revocation, up to 30 minutes late within one token's life. The cache is invalidated whenever the access token changes, so short-lived-token setups using a refresh token (`extra_scopes=["offline_access"]`) pick up changes sooner. If revocation must take effect immediately, check your database or authorization service in an async check instead of relying on cached claims.
```

### Async checks

Most checks can be sync. Read OIDC claims from
`ctx.auth_user_state.userinfo`:

```python
import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthContext


def is_org_admin(ctx: AuthContext) -> bool:
    return "admins" in (ctx.auth_user_state.userinfo.get("groups") or [])


class DemoState(rx.State):
    @rxe.event(auth=is_org_admin)
    async def privileged_action(self):
        return rx.toast.success("Done.")

    @rxe.var(auth=is_org_admin, initial_value="🔒 admins only")
    def admin_view(self) -> str:
        return "✅ admin-only value."
```

Request `extra_scopes=["groups"]` during OAuth login when checks depend on the
`groups` claim.

A check may also be async. The framework awaits it at the right point: the
per-event gate for handlers, or delta resolution for fields and vars. Use an
async check when it calls async APIs, for example:

- Querying a database.
- Calling a remote authorization service, such as OpenFGA or another
  ReBAC backend.
- Accessing another Reflex state with `await ctx.auth_user_state.get_state(...)`
  when the policy input is stored in state.

```md alert warning
# One function, one auth value
The same function cannot back two surfaces with different `auth` values, such as one var with `auth=True` and another with `auth=False` sharing a single getter. That raises `ValueError`. Reusing a function with the same auth value is supported; otherwise define a separate function per surface.
```

## Authentication vs authorization

The two failure modes are deliberately different. Applied per surface against the
resolved user:

| Situation | Outcome |
| --- | --- |
| `auth=False` | **Allow.** |
| Not logged in (no user resolved) | **Authentication failure**. Handled before any check runs. |
| Logged in and `auth=True` | **Allow.** |
| Logged in and the check returns truthy | **Allow.** |
| Logged in and the check returns falsey or raises | **Authorization failure.** Never a login redirect. |

What each failure does depends on the surface:

| Surface | Authentication failure (anonymous) | Authorization failure (check said no) |
| --- | --- | --- |
| Event handler | block + redirect to `/login` | block + `"Action not allowed"` toast |
| Page | redirect to `/login` (with `redirect_to`) | redirect to `/forbidden` |
| Field / computed var | withheld (placeholder / default shown) | withheld (placeholder / default shown) |

Two properties follow from the ordering: a check **never runs for an anonymous
caller**, and a check that **raises fails closed**. Exceptions are treated as
deny results.

## How withholding works

Protected base fields are dropped from the state delta, and protected computed
vars are withheld, for any caller who isn't authorized to see them. A sync check
is evaluated inline as the delta is built; an async check is deferred and awaited
during delta resolution.

The `hydrate` event runs **before** the auth cookies are known. Even for a
logged-in user, protected values are withheld at first because the user has not
been resolved yet. Once an event resolves an authenticated user (for example,
the page guard on a protected page), the protected names are re-delivered in
that event's delta, filtered against the resolved user.

Set `initial_value` on protected computed vars. The placeholder is baked into
the frontend bundle and shown until the real value arrives after login.

## Logout resets protected state

On logout, each non-exempt state's **protected** surface is reset. This prevents
one user's session data from leaking to the next user on the same client token:

- Protected base vars revert to their declared defaults.
- Protected cached computed vars are dropped.
- Server-only backend vars are cleared.

**Public (`auth=False`) fields and vars are preserved** across logout. They are
not part of the authenticated session.

### Logout is protected against CSRF

The plugin installs middleware for the configured `logout_endpoint`. Cross-site
GET navigations to `/logout` are blocked when the browser sends
`Sec-Fetch-Site: cross-site`; those requests are redirected to the frontend root.
Same-origin logout requests continue normally. No configuration is required.

```md alert warning
# Only covers the backend-served frontend
This guard applies only when the backend serves the compiled frontend, which is the default fullstack deployment. In a split frontend/backend deployment, the logout page is served elsewhere and is **not** protected. Add a cross-site guard there.
```

## Exempt states

Some state classes are never protected and never gated:

- State classes defined inside `reflex` or `reflex_enterprise`.
- Any `OIDCAuthState` subclass, including user-defined auth providers.

These exemptions let provider states read auth cookies before login and let the
page guard resolve the current user without being gated.

## Reading the current user

Import the `User` facade to read the current user from either the frontend or the
backend:

```python
from reflex_enterprise.auth import User
```

`User` is an alias of `reflex_enterprise.auth.AuthUserState` and may be used
interchangeably.

**Frontend Vars**: embed these class-level descriptors directly in components.
They bind to `AuthUserState`, populated after login by the provider that
authenticated the user. Each is typed `str` and is empty (`""`) until login:

| Attribute | Value |
| --- | --- |
| `User.name` | The user's name claim. |
| `User.email` | The user's email claim. |
| `User.sub` | The user's subject identifier. |
| `User.picture` | The user's picture URL. |

```python
rx.avatar(src=User.picture, fallback="U", size="5")
rx.heading(User.name, size="6")
rx.text(User.email, color_scheme="gray")
rx.cond(User.sub != "", rx.text("Signed in"), rx.link("Log in", href="/login"))
```

### Reading other claims in a component

The common OIDC claims `name`, `email`, `sub`, and `picture` are projected as
frontend Vars. The full `userinfo` dict is server-only and never serialized. To
render any other claim (`groups`, roles, a custom field) in a component, opt it
onto the frontend by declaring a computed var on an `AuthUserState` substate:

```python
import reflex as rx
from reflex_enterprise.auth import AuthUserState


class UserExtras(AuthUserState):
    @rx.var
    def groups(self) -> list[str]:
        return self.userinfo.get("groups") or []


# in a component:
rx.cond(UserExtras.groups.contains("admins"), rx.badge("Admin"), rx.fragment())
```

For backend checks, read the same claims via `await User.current()` or
`ctx.auth_user_state.userinfo.get(...)`. See
[the claims a provider
returns](/docs/enterprise/auth/providers/#the-claims-a-provider-returns).

**Backend**: call these inside an event handler. Both are async:

| Call | Returns |
| --- | --- |
| `await User.current()` | The current user's `OIDCUserInfo` claims dict for this event, or `None` when anonymous. |
| `await User.current_provider()` | The provider **class** that actually authenticated this event's user, or `None`. Correct in multi-provider setups. |

Inside an authorization check, `ctx.auth_user_state.provider` returns the same
provider class.

`OIDCUserInfo` is a plain dict at runtime. Read claims with `.get(...)`:

```python
class DemoState(rx.State):
    @rxe.event  # default auth=True
    async def whoami(self):
        user = await User.current() or {}
        return rx.toast(f"You are {user.get('name') or user.get('sub')}.")
```

## Related

- [Overview](/docs/enterprise/auth/overview/): plugin setup and the login flow.
- [Providers](/docs/enterprise/auth/providers/): provider configuration.
- [Custom pages](/docs/enterprise/auth/custom-pages/): custom login, callback,
  logout, and forbidden pages.
- [Testing](/docs/enterprise/auth/testing/): unit tests and mock-IdP flow tests.
