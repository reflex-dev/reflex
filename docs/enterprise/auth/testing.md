---
title: Testing Guarded Code
---

_New in reflex-enterprise v0.9.1._

# Testing Guarded Code

When the [AuthPlugin](/docs/enterprise/auth/overview/) is enabled, every
non-exempt page, event handler, base field, and computed var is
[secure by default](/docs/enterprise/auth/secure-by-default/). The logic worth
testing is almost always your **authorization checks** — the `auth=<callable>`
functions that decide who may see a value or run a handler.

Because a check is an ordinary function that takes a context object and returns a
bool, you can test it directly with no network, no IdP, and no browser. This page
shows that, then covers exercising the **full** OIDC flow against a local mock
provider when the wiring itself is what you want to test.

```md alert info
# Run these under pytest
The snippets construct `AuthUserState()` directly, which Reflex permits only in a test environment (it keys off pytest being active) — so run them with `pytest`, not a bare script. Async-check tests use [`pytest-asyncio`](https://pypi.org/project/pytest-asyncio/) (`uv add --dev pytest-asyncio`); the `@pytest.mark.asyncio` marker shown below works whether or not your project sets `asyncio_mode = "auto"`.
```

## A check is just a function

An authorization check receives a single context object and returns a bool (or an
awaitable of one). It reads the user's claims off `ctx.auth_user_state.userinfo`:

```python
from reflex_enterprise.auth import VarAuthContext


def is_staff(ctx: VarAuthContext) -> bool:
    return "staff" in (ctx.auth_user_state.userinfo.get("groups") or [])
```

To test it, build a context around an `AuthUserState` carrying the claims you
want, and call the check. `AuthUserState` (exported as `User`) holds the claims
in `_userinfo`:

```python
from reflex_enterprise.auth import AuthUserState, VarAuthContext

from my_app.auth import is_staff


def _ctx(userinfo) -> VarAuthContext:
    """A VarAuthContext presenting ``userinfo`` as the current user."""
    user = AuthUserState()
    user._userinfo = userinfo
    return VarAuthContext(auth_user_state=user, field_or_var=None)


def test_is_staff_allows_member():
    assert is_staff(_ctx({"sub": "u1", "groups": ["staff"]})) is True


def test_is_staff_denies_non_member():
    assert is_staff(_ctx({"sub": "u2", "groups": ["guests"]})) is False
```

The context classes are all exported from `reflex_enterprise.auth`. Build the one
that matches the surface your check guards:

| Context | Construct as |
| --- | --- |
| `VarAuthContext` | `VarAuthContext(auth_user_state=user, field_or_var=None)` |
| `EventAuthContext` | `EventAuthContext(auth_user_state=user, event_handler=None, payload={})` |
| `PageAuthContext` | `PageAuthContext(auth_user_state=user)` |

A check typed with the `AuthContext` union works on any surface, so you can test
it through whichever context is simplest to build (usually `VarAuthContext`).

```md alert info
# A check never runs for an anonymous caller
The plugin resolves authentication *before* any check, so `ctx.auth_user_state`
is always a logged-in user inside a check. You don't need to test the
"anonymous" case at the check level — that's an authentication failure (a login
redirect), handled before the check runs.
```

## Async checks

An `async` check that only reads `ctx.auth_user_state.userinfo` is tested exactly
the same way — just `await` it:

```python
import pytest


@pytest.mark.asyncio
async def test_async_check():
    assert await my_async_check(_ctx({"sub": "u1", "groups": ["admins"]})) is True
```

An async check that reaches **other state** — `await ctx.auth_user_state.get_state(OtherState)`,
a database, or a remote authorization service — needs a live state tree, so it
isn't unit-testable through a hand-built context alone. Two good options:

1. **Factor the decision into a pure function** of the inputs and unit-test that.
   Keep the check a thin adapter:

   ```python
   def user_may_access(groups: list[str], admin_group: str) -> bool:
       """Pure policy — trivially unit-testable with plain values."""
       return admin_group in groups


   async def is_org_admin(ctx) -> bool:
       policy = await ctx.auth_user_state.get_state(PolicyState)
       return user_may_access(
           ctx.auth_user_state.userinfo.get("groups") or [],
           policy.admin_group,
       )
   ```

   Then `assert user_may_access(["admins"], "admins") is True` covers the logic
   with no framework objects at all.

2. **Exercise it end-to-end** against a mock IdP (below), which builds the real
   state tree.

## End-to-end against a mock IdP

To exercise the **full** OIDC flow — the login redirect, the `/callback` token
exchange, JWKS validation, the userinfo fetch, and async checks that touch real
state — run your app against a local mock identity provider.

[`oidc-provider-mock`](https://pypi.org/project/oidc-provider-mock/) is a small
OIDC server that runs in-process. Add it as a dev dependency:

```bash
uv add --dev oidc-provider-mock
```

Run it on a background thread and point the `OIDC_*` env vars at it before the
app starts. It accepts any client credentials by default (no registration) and
issues refresh tokens, so the fixture is short:

```python
import os

import pytest
from oidc_provider_mock import User, run_server_in_thread


@pytest.fixture(scope="session")
def mock_idp():
    """Run a local mock OIDC IdP and point the OIDC_* env vars at it."""
    env = {
        # Lets the mock IdP (authlib, server-side) serve OAuth over plain HTTP —
        # redundant for a localhost issuer, needed for a non-localhost HTTP host.
        "AUTHLIB_INSECURE_TRANSPORT": "1",
        "OIDC_CLIENT_ID": "test-client",
        "OIDC_CLIENT_SECRET": "test-secret",
    }
    # Save and restore so the test run doesn't leak OIDC_* into other tests.
    saved = {key: os.environ.get(key) for key in [*env, "OIDC_ISSUER_URI"]}
    os.environ.update(env)
    users = [
        User(sub="user-1", claims={"name": "Ada Lovelace", "groups": ["admins"]}),
    ]
    try:
        with run_server_in_thread(user_claims=users) as server:
            os.environ["OIDC_ISSUER_URI"] = f"http://localhost:{server.server_port}"
            yield server
    finally:
        for key, value in saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
```

Then drive the app's real `/login`, `/callback`, and `/logout` pages with your
browser-automation harness of choice, logging in as one of the users you defined.
`oidc-provider-mock` also ships a CLI if you prefer to run the IdP as a standalone
server for manual local testing.

```md alert info
# Test the check directly first; the mock IdP when you're testing the wiring
Calling the check with a hand-built context is faster and needs no server — reach for it in the common case. Use `oidc-provider-mock` only when the OIDC wiring itself (redirect, callback, token exchange, refresh) or an async check that touches live state is what's under test.
```

## Related

- [Secure by default](/docs/enterprise/auth/secure-by-default/) — the `auth=` wrappers, the context objects, and the enforcement semantics the tests exercise.
- [Overview](/docs/enterprise/auth/overview/) — enable the plugin and read the current user.
- [Providers](/docs/enterprise/auth/providers/) — the providers the mock IdP stands in for.
