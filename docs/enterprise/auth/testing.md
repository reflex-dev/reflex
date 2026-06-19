---
title: Testing Guarded Code
---

_New in reflex-enterprise v0.9.1._

# Testing Guarded Code

When the [AuthPlugin](/docs/enterprise/auth/overview/) is enabled, every
non-exempt page, event handler, base field, and computed var is
[secure by default](/docs/enterprise/auth/secure-by-default/) — guarded
surfaces only resolve against a logged-in user. Unit-testing that logic would
normally require a live identity provider, a real OIDC round-trip, and browser
cookies.

`auth_as` removes that requirement. It injects a fake authenticated user into
the per-event context that the gate populates, so guarded handlers, fields, and
vars can be exercised with no network and no IdP. Because it sets the *same*
context the gate sets, your tests run the production read path rather than a
test-only shortcut.

```md alert info
# Tests are async
The current-user read path is async. Write the tests as `async def test_...`
and `await User.current()`. The examples below use the `pytest-asyncio` style.
```

## auth_as

Import it from `reflex_enterprise.auth` (it is also available at
`reflex_enterprise.auth.testing.auth_as`):

```python
from reflex_enterprise.auth import auth_as
```

`auth_as` is a context manager:

```python
@contextlib.contextmanager
def auth_as(
    userinfo: OIDCUserInfo | None,
    provider: type[OIDCAuthState] | None = None,
) -> Iterator[OIDCUserInfo | None]: ...
```

| Argument | Type | Default | Meaning |
| --- | --- | --- | --- |
| `userinfo` | `OIDCUserInfo \| None` | — | The claims to present as the current user. Pass `None` to simulate an anonymous request. |
| `provider` | `type[OIDCAuthState] \| None` | `None` | The provider class to present as having resolved the user — what `User.current_provider()` returns inside the block. |

Within the `with` block, the resolution path, the state-delta filtering, and
`User.current()` all see `userinfo` as the resolved current user. `auth_as(None)`
simulates an anonymous caller. On exit, the context is restored to its previous
value, so blocks can be nested and tests stay isolated.

The `userinfo` you pass is just a [`OIDCUserInfo`](/docs/enterprise/auth/providers/)
dict — read claims with `.get(...)`. A representative value:

```python
{
    "sub": "user-1",
    "name": "Ada Lovelace",
    "email": "ada@example.com",
    "picture": "https://example.com/ada.png",
    "groups": ["moderators"],
}
```

## Testing the current user

`User.current()` reads the per-event context that `auth_as` populates and
returns the injected claims verbatim, or `None` when anonymous:

```python
from reflex_enterprise.auth import User, auth_as


async def test_current_returns_injected_userinfo():
    userinfo = {
        "sub": "user-1",
        "name": "Ada Lovelace",
        "email": "ada@example.com",
        "groups": ["moderators"],
    }
    with auth_as(userinfo):
        assert await User.current() == userinfo


async def test_anonymous():
    with auth_as(None):
        assert await User.current() is None
```

Pass `provider=` when the code under test calls `User.current_provider()`; it
returns exactly the provider class you supply:

```python
from reflex_enterprise.auth.oidc.state import GenericOIDCAuthState


async def test_current_provider():
    userinfo = {"sub": "user-1", "groups": ["moderators"]}
    with auth_as(userinfo, provider=GenericOIDCAuthState):
        assert await User.current_provider() is GenericOIDCAuthState
```

## Testing an authorization check

An `auth=<callable>` [check](/docs/enterprise/auth/secure-by-default/) is an
ordinary function, so the most direct test calls it with a `userinfo` dict and
asserts the boolean result. An event check has the signature
`func(handler, payload, userinfo) -> bool` and only ever runs for an
authenticated caller, so you can pass `None` for the arguments it ignores:

```python
def _is_moderator(handler, payload, userinfo) -> bool:
    return "moderators" in (userinfo.get("groups") or [])


def test_is_moderator_allows_member():
    member = {"sub": "user-1", "groups": ["moderators"]}
    assert _is_moderator(None, None, member) is True


def test_is_moderator_denies_non_member():
    outsider = {"sub": "user-2", "groups": []}
    assert _is_moderator(None, None, outsider) is False
```

To exercise the guarded handler end-to-end instead, run it inside `auth_as` so
the check sees the injected user. A member resolves the real return value; a
non-member is denied:

```python
import reflex as rx
import reflex_enterprise as rxe
from reflex_enterprise.auth import User, auth_as


class DemoState(rx.State):
    @rxe.event(auth=_is_moderator)
    async def moderator_action(self):
        user = await User.current() or {}
        return rx.toast(f"Hello {user.get('name') or user.get('sub')}!")
```

```md alert success
# Member vs. non-member
Inside `with auth_as(member_userinfo):` the check returns truthy and the handler
runs. Inside `with auth_as(non_member_userinfo):` the check returns falsey and
the gate denies the call with the default "Action not allowed" toast — never a
login redirect.
```

```md alert warning
# A check never runs for an anonymous caller
`auth_as(None)` resolves to *anonymous*, which is an authentication failure — it
short-circuits to a login redirect before any check runs. To test the check
itself, always inject a `userinfo` (call the function directly, or wrap the
handler in `auth_as(userinfo)`).
```

## End-to-end testing against a mock IdP

`auth_as` injects a user and skips the network — the right tool for
unit-testing guarded logic. When you instead want to exercise the **full** OIDC
flow (the login redirect, the `/callback` token exchange, JWKS validation, and
the userinfo fetch), run your app against a local mock identity provider.

[`oidc-provider-mock`](https://pypi.org/project/oidc-provider-mock/) is a small
OIDC server that runs in-process — the same tool reflex-enterprise uses for its
own integration tests. Add it as a dev dependency:

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
        "AUTHLIB_INSECURE_TRANSPORT": "1",  # accept plain-http localhost
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
browser-automation harness of choice, logging in as one of the users you
defined. `oidc-provider-mock` also ships a CLI if you prefer to run the IdP as a
standalone server for manual local testing.

```md alert info
# `auth_as` first; the mock IdP when you're testing the wiring
Reach for `auth_as` in the common case — it's faster and needs no server. Use
`oidc-provider-mock` only when the OIDC wiring itself (redirect, callback, token
exchange, refresh) is what's under test, not just the guarded logic.
```

## Related

- [Auth Overview](/docs/enterprise/auth/overview/) — enable the plugin and read the current user.
- [Secure by Default](/docs/enterprise/auth/secure-by-default/) — the `auth=` wrappers and enforcement semantics the tests exercise.
- [Enterprise Overview](/docs/enterprise/overview/) — the full reflex-enterprise feature set.
