---
title: Secure by Default
---

_New in reflex-enterprise v0.9.1._

# Secure by Default

Once `rxe.AuthPlugin` is configured (see the [auth overview](/docs/enterprise/auth/overview/)),
**every** non-exempt page, event handler, base field, and computed var in your
app requires a logged-in user — unless you explicitly opt it out. You don't
mark things as protected; they start protected, and you open up exactly the
surfaces that should be public.

Every `rxe.*` wrapper takes the same `auth=` argument, whose value means:

| `auth=` value | Meaning |
| --- | --- |
| `True` | Require an authenticated user. **This is the secure default for every surface.** |
| `False` | Public — allow everyone (opt out of protection). |
| a callable check | An authorization check that runs **only after** authentication succeeds. Truthy result allows; a falsey result or a raised exception denies. |

The four wrappers are exported at top level: `rxe.page`, `rxe.event`,
`rxe.field`, and `rxe.var`. The rest of this page covers each surface, then the
shared enforcement semantics and how to read the current user.

```md alert warning
# Requires `rxe.App` and a configured provider
Secure-by-default only applies when your app uses `rxe.App()` (not `rx.App()`) and `rxe.AuthPlugin` is in `rxe.Config(plugins=[...])` with an OIDC identity provider configured via env vars. See the [overview](/docs/enterprise/auth/overview/).
```

## Pages

Protect a page with `@rxe.page`. For pages, `auth` is a **bool only** — callable
checks are not supported here.

```python
@rxe.page(
    route: str | None = None,
    *,
    auth: bool = True,
    **page_kwargs,
)
```

A protected page (`auth=True`, the default) injects
`PageGuardState.enforce_login` as the **first** `on_load` event. Anonymous
visitors are redirected to the login endpoint, and the page they were trying to
reach is preserved as a `redirect_to` query parameter so the post-login flow
returns them there.

```python
@rxe.page(route="/dashboard", title="Dashboard")  # auth=True is the default
def dashboard() -> rx.Component:
    """Protected page: anonymous visitors are redirected to /login."""
    ...
```

Set `auth=False` for a public page:

```python
@rxe.page(route="/", title="Home", auth=False)
def index() -> rx.Component:
    """Public landing page (opted out of secure-by-default)."""
    ...
```

Any extra `**page_kwargs` are forwarded verbatim to `rx.page` — `title`,
`image`, `description`, `meta`, `script_tags`, and `on_load`. When you also pass
`on_load`, the login guard is prepended to it (so it always runs before your own
on-load events).

### Every page is protected, not just `@rxe.page` ones

With the plugin on, `rxe.App()` defaults every page to login-required — pages
added via `app.add_page(...)` or plain `@rx.page` are guarded too. Opt out with
`auth=False`:

```python
app.add_page(index, route="/", auth=False)
```

Plain `@rx.page` takes no `auth` argument, so opt a decorated page out with
`@rxe.page(auth=False)`.

## Event handlers

Protect an event handler with `@rxe.event`. Here `auth` accepts a bool or a
callable check.

```python
@rxe.event(
    fn=None,
    *,
    auth: bool | Callable = True,
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
        """Greet the logged-in user, resolved from the backend userinfo."""
        user = await User.current() or {}
        return rx.toast(f"Hello {user.get('name') or user.get('sub')}!")

    @rxe.event(auth=False)
    def toggle_loading(self):
        """A public handler anyone may call."""
        self.loading = not self.loading
```

For finer-grained control, pass a check with the signature
`func(handler, payload, userinfo) -> bool`. It runs only after the caller is
authenticated; an anonymous caller is redirected to login first and never reaches
the check.

```python
def _is_admin(handler, payload, userinfo) -> bool:
    """Event authz check: allow only members of the ``admins`` group."""
    return "admins" in (userinfo.get("groups") or [])


class DemoState(rx.State):
    @rxe.event(auth=_is_admin)  # authz failure -> "Action not allowed" toast
    def admin_action(self):
        """An action only members of the ``admins`` group may run."""
        return rx.toast.success("Admin action executed.")
```

## Base fields

Base (state) fields are protected by default too. A plain `rx.field(...)` — or a
bare annotation — on a non-exempt state class is **already** protected: it is
dropped from the state delta until the user logs in. You only reach for
`rxe.field` when you want to opt a field out or attach a check.

```python
def field(
    default=...,
    *,
    auth: bool | Callable = True,
    default_factory=None,
    is_var=True,
)
```

```python
class DemoState(rx.State):
    # Base fields are protected by default: dropped from the delta until login.
    notes: rx.Field[str] = rx.field("These notes are only sent once you log in.")
    # Explicitly public field, always sent to the client.
    loading: rx.Field[bool] = rxe.field(False, auth=False)
```

A field check has the signature `func(field, userinfo) -> bool`:

```python
def _is_admin(field, userinfo) -> bool:
    return bool(userinfo) and "admin" in (userinfo.get("groups") or [])


class DemoState(rx.State):
    audit_log: rx.Field[list[str]] = rxe.field([], auth=_is_admin)
```

A protected field is dropped from the state delta until the user is resolved,
then re-delivered (see [How withholding works](#how-withholding-works)).

## Computed vars

Computed vars are protected by default and withheld from the delta until login.
Wrap them with `@rxe.var`.

```python
def var(
    fget=None,
    *,
    auth: bool | Callable = True,
    **var_kwargs,
)
```

Usable bare (`@rxe.var`) or called (`@rxe.var(auth=..., initial_value=...)`).
Extra `**var_kwargs` are forwarded verbatim to `rx.var`: `initial_value`,
`cache`, `deps`, `auto_deps`, `interval`, and `backend`.

```md alert info
# Always pair a protected var with `initial_value`
Because a protected var is withheld until the user is resolved, the client has no value to render in the meantime. Set `initial_value=` to a placeholder that is baked into the frontend bundle and shown until the real value is delivered after login.
```

```python
class DemoState(rx.State):
    @rxe.var(initial_value="🔒 (log in to reveal this protected computed var)")
    def protected_tip(self) -> str:
        """Protected by default: the placeholder shows until a user is resolved."""
        return "✅ This computed var is delivered only to logged-in users."

    @rxe.var(auth=False)
    def public_label(self) -> str:
        """A computed var opened up to anonymous visitors."""
        return "This text is public — anyone can read it."
```

A var check has the signature `func(var, userinfo) -> bool`, and (as with
fields) pairs well with `initial_value`:

```python
class DemoState(rx.State):
    @rxe.var(auth=_is_admin, initial_value=0)
    def pending_approvals(self) -> int: ...
```

## Authentication vs authorization

The two failure modes are deliberately different. Think of it as a decision tree
applied per surface against the resolved user:

| Situation | Outcome |
| --- | --- |
| `auth=False` | **Allow.** |
| Not logged in (no user resolved) | **Redirect to login** (authentication failure), before any check runs. |
| Logged in and `auth=True` | **Allow.** |
| Logged in and the check returns truthy | **Allow.** |
| Logged in and the check returns falsey or raises | **"Action not allowed" toast** (authorization failure) — never a login redirect. |

An **authentication** failure (not logged in) always redirects to the login
endpoint. An **authorization** failure (a check said no) shows the default
`"Action not allowed"` toast and never redirects — redirecting an
already-logged-in user to login would just loop.

Two properties follow from the ordering: a check **never runs for an anonymous
caller** (the redirect happens first, so `userinfo` is always present inside a
check), and a check that **raises fails closed** (the exception is treated as a
deny, not an allow).

## How withholding works

Protected base fields are dropped from the state delta, and protected computed
vars are skipped, for any caller who isn't authorized to see them.

The subtlety is timing. The `hydrate` event runs **before** the auth cookies are
known, so even for a user who is logged in, protected values are withheld at
first — the user simply hasn't been resolved yet that early. Once an event
resolves an authenticated user (the page guard on a protected page does this),
the protected names are re-delivered in that event's delta, filtered against the
now-resolved user.

This is exactly why protected computed vars should set `initial_value`: that
placeholder is baked into the frontend bundle and shown until the real value
arrives after login.

## Logout resets protected state

On logout, each non-exempt state's **protected** surface is reset so one user's
session data never leaks to the next user on the same client token:

- Protected base vars revert to their declared defaults.
- Protected cached computed vars are dropped.
- Backend vars are cleared.

**Public (`auth=False`) fields and vars are preserved** across logout — they are
not part of the authenticated session.

## Exempt states

Some state classes are never protected and never gated:

- State classes defined inside `reflex` or `reflex_enterprise`.
- Any `OIDCAuthState` subclass — i.e. the auth providers, even user-defined ones.

This is why a provider state's own vars are always delivered (they read straight
from the auth cookies, so they are simply empty until you log in), and why the
page guard — itself a framework state — can resolve the user without being gated.

## Reading the current user

Import the `User` facade to read the current user from either the frontend or
the backend:

```python
from reflex_enterprise.auth import User
```

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
| `User.State` | The active provider class (the first configured provider). Use it to reach provider events / `get_login_button`. |

```python
rx.avatar(src=User.picture, fallback="U", size="5")
rx.heading(User.name, size="6")
rx.text(User.email, color_scheme="gray")
```

**Backend** — call these inside an event handler. Both are async:

| Call | Returns |
| --- | --- |
| `await User.current()` | The current user's `OIDCUserInfo` dict for this event, or `None` when anonymous/unresolved. |
| `await User.current_provider()` | The provider **class** that actually resolved this event's user (vs `User.State`, which is always the first configured), or `None`. |

`OIDCUserInfo` is a plain dict at runtime, so read claims with `.get(...)`:

```python
class DemoState(rx.State):
    @rxe.event  # default auth=True
    async def protected_action(self):
        """Greet the logged-in user, resolved from the backend userinfo."""
        user = await User.current() or {}
        return rx.toast(f"Hello {user.get('name') or user.get('sub')}!")
```

```md alert warning
# One function, one auth value
The same function cannot back two surfaces with different `auth` values (e.g. one var `auth=True` and another `auth=False` sharing a single getter) — that raises `ValueError`. Reusing a function with the *same* auth is fine; otherwise define a separate function per surface.
```

## Related

- [Overview](/docs/enterprise/auth/overview/) — enable the plugin and read the current user.
- [Providers](/docs/enterprise/auth/providers/) — swap in a real identity provider.
- [Custom pages](/docs/enterprise/auth/custom-pages/) — replace the login / callback / logout screens.
- [Testing](/docs/enterprise/auth/testing/) — drive guarded surfaces in unit tests.
- [Reflex Enterprise overview](/docs/enterprise/overview/) — the rest of reflex-enterprise.
