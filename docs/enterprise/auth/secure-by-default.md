---
title: Secure by Default
---

_New in reflex-enterprise v0.9.1._

# Secure by Default

Once `rxe.AuthPlugin` is configured (see the
[overview](/docs/enterprise/auth/overview/)), **every** non-exempt page, event
handler, base field, and computed var in your app requires a logged-in user —
unless you explicitly opt it out. You don't mark things as protected; they start
protected, and you open up exactly the surfaces that should be public.

This page covers the four `auth=` wrappers, the shared meaning of the `auth=`
value (including authorization checks), the difference between authentication
and authorization failures, and how protected values are delivered.

```md alert warning
# Requires `rxe.App` and a configured provider
Secure-by-default only applies when your app uses `rxe.App()` (not `rx.App()`) and `rxe.AuthPlugin` is in `rxe.Config(plugins=[...])` with an OIDC provider configured. See the [overview](/docs/enterprise/auth/overview/).
```

## The `auth=` value

Every `rxe.*` wrapper — and the plugin-wide default — takes the same `auth=`
argument. Its value means:

| `auth=` value | Meaning |
| --- | --- |
| `True` | Require an authenticated user. **This is the secure default for every surface.** |
| `False` | Public — allow everyone (opt out of protection). |
| a callable check | An authorization check that runs **only after** authentication succeeds. A truthy result allows; a falsey result or a raised exception denies. |

The four wrappers are exported at top level: `rxe.page`, `rxe.event`,
`rxe.field`, and `rxe.var`. Pages take `auth` as a **bool only**; event handlers,
fields, and computed vars also accept a callable check.

### The global default

`AuthPlugin(auth=...)` sets the default applied to every surface that carries no
explicit `auth=` of its own. It accepts the same three values:

```python
rxe.AuthPlugin(auth=True)  # any authenticated user (the default)
rxe.AuthPlugin(auth=False)  # open by default — opt in to protection per surface
rxe.AuthPlugin(auth=my_org_check)  # org-wide authorization check, run after login
```

A plain `rx.field(...)`, a bare `@rxe.var`, a bare `@rxe.event`, and an
`@rxe.page()` with no `auth=` all **inherit** this global default. An explicit
per-surface `rxe.*(auth=...)` always overrides it. This means you can flip your
whole app's baseline — from "any logged-in user" to "members of the `admins`
group" — by changing one `AuthPlugin(auth=...)` value, without touching a single
field, var, event, or page.

### Gate the whole app behind a role

A callable global default runs on every untagged page load, so one check gates
the entire app — no per-surface tagging:

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

`extra_scopes=["groups"]` is required so the `groups` claim exists to check —
see [providers](/docs/enterprise/auth/providers/#the-claims-a-provider-returns).
Authenticated users who fail the check are sent to `/forbidden` (not back to
login); you can replace that screen with a [custom forbidden
page](/docs/enterprise/auth/custom-pages/#a-custom-forbidden-page).

## Pages

Protect a page with `@rxe.page`. For pages, `auth` is a **bool only** — callable
checks are not supported as a per-page argument (the global default may still be
a callable; see below).

```python
def page(
    route: str | None = None,
    *,
    auth: bool | None = None,
    **page_kwargs,
)
```

- `auth=None` (the default) — follow the configured global default
  (`AuthPlugin(auth=...)`).
- `auth=True` — always require an authenticated user, regardless of the global
  default.
- `auth=False` — public page (opt out).

A protected page injects a guard as the **first** `on_load` event. Anonymous
visitors are redirected to the login endpoint, and the page they were trying to
reach is preserved as a `redirect_to` query parameter so the post-login flow
returns them there.

- The post-login `redirect_to` target is validated against the app's origin —
  only same-origin absolute paths (e.g. `/dashboard`) or URLs sharing the app's
  scheme and host are honored. Any cross-origin, scheme-relative (`//evil.test`),
  or backslash target silently falls back to the index page, so the framework
  can't be turned into an open redirect and you don't need to add your own
  validation.

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

Any extra `**page_kwargs` are forwarded verbatim to `rx.page` — `title`,
`image`, `description`, `meta`, `script_tags`, and `on_load`. When you pass your
own `on_load`, the guard is prepended to it, so it always runs first.

### Reading the user on page load

Because the guard is prepended and runs first, by the time your own `on_load`
runs the visitor is already authenticated — so `await User.current()` (or
`ctx.auth_user_state.userinfo`) is non-`None`:

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

`User.current()` is event-only; an `on_load` handler is an event, so it resolves
the just-authenticated user. See [reading the current
user](#reading-the-current-user).

### Every page is protected, not just `@rxe.page` ones

With the plugin on, `rxe.App()` defaults **every** page to login-required —
including pages added via `app.add_page(...)` or a plain `@rx.page`. Opt out with
`auth=False`:

```python
app.add_page(index, route="/", auth=False)
```

Plain `@rx.page` takes no `auth` argument, so to opt a decorated page out use
`@rxe.page(auth=False)` instead.

### When the global default is a callable

A page can't take a callable `auth=` directly, but if `AuthPlugin(auth=...)` is a
callable, untagged pages (`@rxe.page()` / `@rx.page` / `app.add_page`) run it on
load. An authenticated visitor who **fails** the check is redirected to the
`forbidden_endpoint` (`/forbidden` by default) — not back to login, which would
loop. An explicit `@rxe.page(auth=True)` only requires login and does **not**
run the callable default.

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

Base (state) fields are protected by default too. A plain `rx.field(...)` — or a
bare annotation — on one of your state classes is **already** protected: it is
dropped from the state delta until the user is resolved. Reach for `rxe.field`
only to opt a field out or attach a check.

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
    # Protected by default — dropped from the delta until login.
    notes: rx.Field[str] = rx.field("These notes are only sent once you log in.")

    # Explicitly public — always sent to the client.
    loading: rx.Field[bool] = rxe.field(False, auth=False)
```

A withheld field is replaced in the delta with its **declared default** (the
value baked into the frontend bundle) until the user is resolved, so the client
never holds a stale authenticated value.

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
A protected var is withheld until the user is resolved, so the client has no value to render in the meantime. Set `initial_value=` to a placeholder baked into the frontend bundle and shown until the real value is delivered after login.
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

For finer-grained control than "any authenticated user," pass a **callable** as
`auth=`. A check is a function that receives a single **context object** and
returns a bool (or an awaitable of one):

```python
def check(ctx) -> bool: ...  # sync
async def check(ctx) -> bool: ...  # async
```

A check runs **only after** authentication succeeds — an anonymous caller is
redirected to login first and never reaches the check, so a resolved user is
always present inside the check.

### The context object

Each surface passes a different context, all carrying the current user as
`ctx.auth_user_state` (an `AuthUserState`). Import them from
`reflex_enterprise.auth`:

| Context | Surface | Extra attributes |
| --- | --- | --- |
| `EventAuthContext` | event handler | `event_handler` (the gated handler), `payload` (the event payload dict) |
| `VarAuthContext` | field / computed var | `field_or_var` (the `Var`, or `None`) |
| `PageAuthContext` | page (callable global default only) | — |

Read the user's claims off `ctx.auth_user_state.userinfo`, a plain dict:

```python
from reflex_enterprise.auth import EventAuthContext, VarAuthContext


def is_admin(ctx: EventAuthContext) -> bool:
    """Event check: allow only members of the ``admins`` group."""
    return "admins" in (ctx.auth_user_state.userinfo.get("groups") or [])


def is_staff(ctx: VarAuthContext) -> bool:
    """Field/var check: allow only staff."""
    return "staff" in (ctx.auth_user_state.userinfo.get("groups") or [])


class DemoState(rx.State):
    @rxe.event(auth=is_admin)  # authz failure -> "Action not allowed" toast
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
`ctx.auth_user_state.userinfo` is served from a server-side cache refreshed at most every 30 minutes (the access token is re-read at most about every 60 seconds), so a check on `groups` / roles can see IdP-side changes — like a group revocation — up to 30 minutes late within one token's life. The cache is invalidated whenever the access token changes, so short-lived-token setups using a refresh token (`extra_scopes=["offline_access"]`) pick up changes sooner. For immediate revocation, decide against an authoritative source inside an async check (`await ctx.auth_user_state.get_state(...)`, shown below) rather than cached claims.
```

### Async checks

A check may be `async` — return an awaitable and the framework awaits it. Whether
a check ran sync or async is decided by its **result**, not by inspecting the
function, so a sync check is run inline while an async one is awaited at the
right point (the per-event gate for handlers, the delta resolution for
fields/vars).

An async check can reach **any other state**, a database, or a remote
authorization service (e.g. OpenFGA / a ReBAC backend) via
`await ctx.auth_user_state.get_state(...)` — the round-trip a sync check can't
make:

```python
import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.auth import AuthContext


class PolicyState(rx.State):
    """A sibling state (or a stand-in for a DB / authz service)."""

    admin_group: rx.Field[str] = rxe.field("admins", auth=False)


async def is_org_admin(ctx: AuthContext) -> bool:
    """Async check combining the user's claims with a sibling state."""
    policy = await ctx.auth_user_state.get_state(PolicyState)
    return policy.admin_group in (ctx.auth_user_state.userinfo.get("groups") or [])


class DemoState(rx.State):
    @rxe.event(auth=is_org_admin)
    async def privileged_action(self):
        return rx.toast.success("Done.")

    @rxe.var(auth=is_org_admin, initial_value="🔒 admins only")
    async def admin_view(self) -> str:
        return "✅ admin-only value."
```

```md alert warning
# One function, one auth value
The same function cannot back two surfaces with different `auth` values (e.g. one var `auth=True` and another `auth=False` sharing a single getter) — that raises `ValueError`. Reusing a function with the *same* auth is fine; otherwise define a separate function per surface.
```

## Authentication vs authorization

The two failure modes are deliberately different. Applied per surface against the
resolved user:

| Situation | Outcome |
| --- | --- |
| `auth=False` | **Allow.** |
| Not logged in (no user resolved) | **Authentication failure** — handled before any check runs. |
| Logged in and `auth=True` | **Allow.** |
| Logged in and the check returns truthy | **Allow.** |
| Logged in and the check returns falsey or raises | **Authorization failure** — never a login redirect. |

What each failure does depends on the surface:

| Surface | Authentication failure (anonymous) | Authorization failure (check said no) |
| --- | --- | --- |
| Event handler | block + redirect to `/login` | block + `"Action not allowed"` toast |
| Page | redirect to `/login` (with `redirect_to`) | redirect to `/forbidden` |
| Field / computed var | withheld (placeholder / default shown) | withheld (placeholder / default shown) |

Two properties follow from the ordering: a check **never runs for an anonymous
caller** (authentication is resolved first, so `ctx.auth_user_state` is always a
real user inside a check), and a check that **raises fails closed** (the
exception is treated as a deny, not an allow).

## How withholding works

Protected base fields are dropped from the state delta, and protected computed
vars are withheld, for any caller who isn't authorized to see them. A sync check
is evaluated inline as the delta is built; an async check is deferred and awaited
during delta resolution.

The subtlety is timing. The `hydrate` event runs **before** the auth cookies are
known, so even for a logged-in user, protected values are withheld at first — the
user simply hasn't been resolved that early. Once an event resolves an
authenticated user (the page guard on a protected page does this), the protected
names are re-delivered in that event's delta, filtered against the now-resolved
user.

This is exactly why protected computed vars should set `initial_value`: that
placeholder is baked into the frontend bundle and shown until the real value
arrives after login.

## Logout resets protected state

On logout, each non-exempt state's **protected** surface is reset so one user's
session data never leaks to the next user on the same client token:

- Protected base vars revert to their declared defaults.
- Protected cached computed vars are dropped.
- Server-only backend vars are cleared.

**Public (`auth=False`) fields and vars are preserved** across logout — they are
not part of the authenticated session.

### Logout is protected against CSRF

The plugin auto-installs middleware that blocks cross-site GET navigations to
`/logout` — using the browser-set, JS-unspoofable `Sec-Fetch-Site` header — so an
attacker's `<iframe>` can't silently log the user out (it is redirected to the
frontend root before the SPA boots). It honors the configured `logout_endpoint`,
and there is nothing to opt into.

```md alert warning
# Only covers the backend-served frontend
This guards the logout route only where the backend serves the compiled frontend (the default fullstack deployment). In a split frontend/backend deployment the logout page is served elsewhere and is **not** protected — add your own cross-site guard there.
```

## Exempt states

Some state classes are never protected and never gated:

- State classes defined inside `reflex` or `reflex_enterprise`.
- Any `OIDCAuthState` subclass — i.e. the auth providers, even user-defined ones.

This is why a provider state's own vars are always delivered (they read straight
from the auth cookies, so they are simply empty until you log in), and why the
page guard — itself a framework state — can resolve the user without being gated.

## Reading the current user

Import the `User` facade to read the current user from either the frontend or the
backend:

```python
from reflex_enterprise.auth import User
```

`User` is an alias of `AuthUserState`; you can read claims off either name.

**Frontend Vars** — embed these class-level descriptors directly in components.
They bind to `AuthUserState`, populated after login by whichever provider
authenticated the user, so they are correct in single- and multi-provider setups
alike. Each is typed `str` (empty `""` until login):

| Attribute | Value |
| --- | --- |
| `User.name` | The user's name claim. |
| `User.email` | The user's email claim. |
| `User.sub` | The user's subject identifier. |
| `User.picture` | The user's picture URL. |
| `User.provider_name` | The `__provider__` of the provider that authenticated the user (`""` when anonymous). |

```python
rx.avatar(src=User.picture, fallback="U", size="5")
rx.heading(User.name, size="6")
rx.text(User.email, color_scheme="gray")
rx.cond(
    User.provider_name != "", rx.text("Signed in"), rx.link("Log in", href="/login")
)
```

### Reading other claims in a component

Only `name`, `email`, `sub`, `picture`, and `provider_name` are projected as
frontend Vars; the full `userinfo` dict is server-only and never serialized. To
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

For backend checks you don't need a substate — read the same claims via
`await User.current()` or `ctx.auth_user_state.userinfo.get(...)`. See
[the claims a provider
returns](/docs/enterprise/auth/providers/#the-claims-a-provider-returns).

**Backend** — call these inside an event handler. Both are async:

| Call | Returns |
| --- | --- |
| `await User.current()` | The current user's `OIDCUserInfo` claims dict for this event, or `None` when anonymous. |
| `await User.current_provider()` | The provider **class** that actually authenticated this event's user, or `None`. Correct in multi-provider setups. |

`OIDCUserInfo` is a plain dict at runtime, so read claims with `.get(...)`:

```python
class DemoState(rx.State):
    @rxe.event  # default auth=True
    async def whoami(self):
        user = await User.current() or {}
        return rx.toast(f"You are {user.get('name') or user.get('sub')}.")
```

## Related

- [Overview](/docs/enterprise/auth/overview/) — enable the plugin and the login flow.
- [Providers](/docs/enterprise/auth/providers/) — swap in a real identity provider.
- [Custom pages](/docs/enterprise/auth/custom-pages/) — replace the login / callback / logout / forbidden screens.
- [Testing](/docs/enterprise/auth/testing/) — unit-test checks and drive the full flow.
