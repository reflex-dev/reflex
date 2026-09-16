---
title: Testing Guarded Code
---

_New in reflex-enterprise v0.9.1._

# Testing Guarded Code

When the [AuthPlugin](/docs/enterprise/auth/overview/) is enabled, every
non-exempt page, event handler, base field, and computed var is
[secure by default](/docs/enterprise/auth/secure-by-default/). The logic worth
testing is usually the `auth=<callable>` authorization checks that decide who
may see a value or run a handler.

Because a check is an ordinary function that takes a context object and returns a
bool, you can test it directly with no network, IdP, or browser. Use a local
mock provider when the OIDC wiring itself is under test.

```md alert info
# Run these under pytest
The snippets construct `AuthUserState()` directly, which Reflex permits only in a pytest environment. Run them with `pytest`, not as standalone scripts. Async-check tests use [`pytest-asyncio`](https://pypi.org/project/pytest-asyncio/) (`uv add --dev pytest-asyncio`); the `@pytest.mark.asyncio` marker shown below works whether or not your project sets `asyncio_mode = "auto"` in `pyproject.toml`.
```

## A check is a function

An authorization check receives a single context object and returns a bool (or an
awaitable of one). It reads the user's claims from
`ctx.auth_user_state.userinfo`:

```python
from reflex_enterprise.auth import VarAuthContext


def is_staff(ctx: VarAuthContext) -> bool:
    return "staff" in (ctx.auth_user_state.userinfo.get("groups") or [])
```

To test it, build a context around an `AuthUserState` carrying the claims for
that case, and call the check. Set the claims on the private `_userinfo` attribute;
the check reads them back through the public `userinfo` property:

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

The context classes are exported from `reflex_enterprise.auth`. Build the one
that matches the guarded surface:

| Context | Construct as |
| --- | --- |
| `VarAuthContext` | `VarAuthContext(auth_user_state=user, field_or_var=None)` |
| `EventAuthContext` | `EventAuthContext(auth_user_state=user, event_handler=None, payload={})` |
| `PageAuthContext` | `PageAuthContext(auth_user_state=user)` |

A check typed with the `AuthContext` union works on any surface. Test it through
the simplest matching context, usually `VarAuthContext`.

```md alert info
# A check never runs for an anonymous caller
The plugin resolves authentication before any check. `ctx.auth_user_state` is always a logged-in user inside a check. Test anonymous behavior at the protected surface level, not in the check function.
```

## Async checks

Async checks are tested the same way. Pass the claims into the test context and
await the check:

```python
import pytest


@pytest.mark.asyncio
async def test_async_check():
    assert await my_async_check(_ctx({"sub": "u1", "groups": ["admins"]})) is True
```

Use the mock IdP flow below when the OIDC wiring itself or live Reflex state is
under test.

## End-to-end against a mock IdP

To exercise the OIDC flow, including the login redirect, `/callback` token
exchange, JWKS validation, userinfo fetch, and async checks that touch real
state, run the app against a local mock identity provider.

[`oidc-provider-mock`](https://pypi.org/project/oidc-provider-mock/) is a small
OIDC server that runs in-process. Add it as a dev dependency:

```bash
uv add --dev oidc-provider-mock
```

Run it on a background thread and point the `OIDC_*` env vars at it before the
app starts. It accepts any client credentials by default and issues refresh
tokens:

```python
import os

import pytest
from oidc_provider_mock import User, run_server_in_thread


@pytest.fixture(scope="session")
def mock_idp():
    """Run a local mock OIDC IdP and point the OIDC_* env vars at it."""
    env = {
        # Lets the mock IdP (authlib, server-side) serve OAuth over plain HTTP.
        # Redundant for a localhost issuer, needed for a non-localhost HTTP host.
        "AUTHLIB_INSECURE_TRANSPORT": "1",
        "OIDC_CLIENT_ID": "test-client",
        "OIDC_CLIENT_SECRET": "test-secret",
    }
    # Save and restore to avoid leaking OIDC_* into other tests.
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

The login flow is browser-driven: redirects, cookies, and websocket state.
Exercise it with `AppHarness` (from `reflex.testing`) and a browser driver such
as Playwright. With the `mock_idp` fixture above active, drive the auth-specific
steps and assert that a protected value is delivered:

```python
import re

from playwright.sync_api import Page, expect


def test_login_delivers_protected_value(auth_app, page: Page):
    base = auth_app.frontend_url.rstrip("/")
    # A protected page bounces an anonymous visitor to /login.
    page.goto(f"{base}/dashboard")
    page.wait_for_url(re.compile(r"/login"))
    # Click the app's login button (labelled "Login with {display_name()}").
    # This starts the OIDC redirect to the IdP's authorize page.
    page.get_by_role("button", name="Login with Generic").click()
    # Authorize on the IdP. oidc-provider-mock authorizes with one passwordless
    # click per predefined user; a real IdP shows its own login/consent form here.
    page.locator('button[name="sub"][value="user-1"]').click()
    # Control returns to the app; the callback exchanges tokens and the
    # protected value is now delivered.
    page.wait_for_url(lambda url: url.startswith(base) and "callback" not in url)
    expect(page.get_by_text("Ada Lovelace")).to_be_visible()
```

The `auth_app` fixture starts your app under `AppHarness` with `mock_idp` active;
`page` is the standard Playwright fixture. `oidc-provider-mock` also ships a CLI
for standalone manual testing.

```md alert info
# Test the check directly first; the mock IdP when you're testing the wiring
Calling the check with a hand-built context is faster and needs no server. Use `oidc-provider-mock` when the OIDC wiring itself (redirect, callback, token exchange, refresh) or an async check that touches live state is under test.
```

## Related

- [Secure by default](/docs/enterprise/auth/secure-by-default/): `auth=`,
  context objects, and enforcement semantics.
- [Overview](/docs/enterprise/auth/overview/): plugin setup and current-user
  access.
- [Providers](/docs/enterprise/auth/providers/): provider configuration.
