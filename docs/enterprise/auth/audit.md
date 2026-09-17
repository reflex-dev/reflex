---
title: Auditing Auth Actions
---

_New in reflex-enterprise v0.9.3._

# Auditing Auth Actions

`rxe.AuthPlugin(audit=...)` registers a single observe-only hook that is called
for every auth lifecycle action (login, logout, token refresh, session expiry)
and every access decision the plugin makes on your behalf (the per-event gate
and the page guard). Use it to feed a SIEM, an audit table, or a structured
log — anywhere "who did what, and was it allowed" needs to be recorded.

```python
# rxconfig.py
import reflex_enterprise as rxe

config = rxe.Config(
    app_name="my_app",
    plugins=[
        rxe.AuthPlugin(
            audit="my_app.audit.audit_auth",
        ),
    ],
)
```

```python
# my_app/audit.py
import logging

audit_logger = logging.getLogger("my_app.audit")


async def audit_auth(action, outcome, context) -> None:
    claims = context.userinfo or {}
    audit_logger.info(
        "%s %s provider=%s route=%s reason=%s user=%s",
        action.value,
        outcome.value,
        context.provider,
        context.route,
        context.reason,
        claims.get("sub"),
    )
```

Like `auth_providers` and the page builders, `audit=` accepts either the
callable itself or a `"module.function"` import-path string. Use the string
form in `rxconfig.py` — app modules cannot be imported while the config is
still being assigned. The path is resolved at compile time, so a typo fails
startup with a clear error rather than surfacing at the first audited event.

## The hook contract

The hook is called as `audit(action, outcome, context)`:

- **Sync or async** — both are accepted; an awaitable result is awaited.
- **Observe-only** — the return value is ignored. The hook can never veto or
  alter a decision; authorization semantics stay in the `auth=` checks.
- **Fail-open** — a raising hook is logged at `ERROR` (with traceback) and the
  auth flow proceeds unaffected.
- **Awaited inline** — events for a session arrive in causal order, but the
  hook runs on the hot path. Keep it fast; heavy sinks (HTTP, database) should
  enqueue internally and flush out-of-band, projecting the context down to the
  plain fields they need first.

`AuditAction` and `AuditOutcome` are str-valued enums, so `action.value` and
`outcome.value` drop into any log or JSON record as plain strings. The context
does not serialize as-is: `state`, `auth_user_state`, and `event_handler` are
live framework objects and `payload` is arbitrary event input, so handing the
whole `AuditContext` to a standard JSON encoder raises `TypeError`. Build the
record from the plain fields the sink needs (`handler_name`, `provider`,
`route`, `reason`, ...). Always read `.value` when formatting: on Python 3.11+
`f"{action}"` renders `AuditAction.LOGIN_COMPLETED` while 3.10 renders the
bare value.

## Actions and outcomes

Lifecycle actions record the user interacting with the plugin:

| Action | Emitted when | Outcomes |
| --- | --- | --- |
| `login_started` | The authorization redirect to the IdP is issued. | `success` / `failure` |
| `login_completed` | The callback token exchange finishes (or fails). | `success` / `failure` |
| `logout` | The session is cleared — user logout, popup sync, or stale-identity cleanup. | `success` / `failure` |
| `token_refresh` | An access-token refresh exchange completes (or is rejected). | `success` / `failure` |
| `session_expired` | A session dies without a logout: invalid tokens, rejected userinfo, or cookies that expired out-of-band. | `success` |

Access decisions record every allow/deny the plugin makes, phrased as what the
user experienced:

| Action | Surface | Outcomes |
| --- | --- | --- |
| `event_handler` | The per-event gate on protected event handlers. | `allowed` / `redirected_to_login` / `denied_toast` |
| `page_load` | The page guard on protected pages. | `allowed` / `redirected_to_login` / `redirected_to_forbidden` |

Public surfaces are not audited: an explicit `auth=False` handler, a public
page under an `auth=False` default, and framework events like `hydrate` emit
nothing — auditing "everything is public and allowed" would flood the sink.
Field and computed-var withholding (delta filtering and redelivery) is also
not audited; those derive from the same identity the gate and guard decisions
already recorded.

On failures, `context.reason` carries a machine-readable cause — for example
`"csrf_state_mismatch"`, `"token_exchange_failed"`, `"refresh_failed"`,
`"tokens_invalid"`, or `"stale_cookies"` — and `context.error_txid` matches
the error transaction id in the provider's backend logs and error UI.

## The context

`AuditContext` is frozen and keyword-only; new optional fields may be added
over time, but the 3-argument hook signature never changes.

| Field | Meaning |
| --- | --- |
| `state` | The state instance the audited flow ran on — always present, and the door into app state via `await context.state.get_state(...)`. |
| `auth_user_state` | The live per-token `AuthUserState` handle, or `None` if it could not be loaded. |
| `userinfo` | A claims snapshot at emission time. Emissions adjacent to a session reset (logout, expiry) capture it *before* the reset, so the event still records who logged out. |
| `provider` | The involved provider's name, when known. |
| `route` | The current page URL with query and fragment stripped (the query can carry OAuth `code`/invite tokens), when available. |
| `session_id` | The router session id, when available. |
| `handler_name` | The gated handler's function name (`event_handler` action only). |
| `event_handler` | The gated `EventHandler` object (`event_handler` action only). |
| `payload` | The gated event's payload, verbatim (`event_handler` action only). |
| `reason` | Machine-readable cause, e.g. `"refresh_failed"`. |
| `error_txid` | Correlates with the provider's backend error logs. |
| `timestamp` | `time.time()` at emission. |

```md alert warning
# Redaction is the hook's responsibility
`payload` carries the gated event's arguments verbatim (form input, possibly
secrets) and `userinfo` carries the full IdP claims (PII). Project to the
fields your sink needs — log `sub`, not the whole claims dict.
```

## Writing audit events into app state

`context.state` works exactly like `self` in an event handler: reach any
state via `get_state`. This trail state is deliberately public (`auth=False`)
so denial events recorded while anonymous still render after the redirect:

```python
import reflex as rx
import reflex_enterprise as rxe


class AuditTrailState(rx.State):
    entries: rx.Field[list[dict[str, str]]] = rxe.field([], auth=False)


async def audit_auth(action, outcome, context) -> None:
    trail = await context.state.get_state(AuditTrailState)
    trail.entries = [
        *trail.entries[-29:],
        {"action": action.value, "outcome": outcome.value},
    ]
```

Entries ride along with the next state delta, so a decision made while a
redirect is in flight (a gate-blocked event, for example) shows up once the
visitor lands back on a page.

## Volume

`event_handler`/`allowed` is the highest-frequency emission: it fires once per
protected handler per event, so a busy app records a lot of "allowed". Hooks
that only care about denials or lifecycle events should filter on
action/outcome first, before doing any I/O.

## Popup flows

Popup login/logout emits for both windows' sessions: the popup window's own
session records the provider round-trip (`login_started`, `login_completed`),
and the opener's session records the token handoff — `login_completed` with
reason `"popup_tokens_synced"`, `logout` with reason `"popup_logout_synced"`.
Hooks counting unique logins should key on one side of the pair; identity
(`userinfo`) is most complete on the opener's events.

See the [overview](/docs/enterprise/auth/overview/) for how the plugin fits
together, and [secure by default](/docs/enterprise/auth/secure-by-default/)
for the `auth=` checks whose decisions these events record.
