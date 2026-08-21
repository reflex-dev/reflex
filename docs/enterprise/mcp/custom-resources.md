---
title: Custom MCP Resources
---

_New in reflex-enterprise v0.9.4._

# Custom MCP Resources

`queue_event` drives your event handlers — the *actions*. For the read side,
decorate a state method with `rxe.mcp.resource` to publish it as a **var-like,
read-only MCP resource**: a computed value that can take arguments and is tied
to the caller's session state.

```python
import reflex as rx
import reflex_enterprise as rxe


def admins_only(ctx) -> bool:
    return ctx.auth_user_state.userinfo.get("role") == "admin"


class DashboardState(rx.State):
    orders: list[dict] = []

    @rxe.mcp.resource
    def order_count(self) -> int:
        """How many orders the current user has."""
        return len(self.orders)

    @rxe.mcp.resource(auth=admins_only)
    def revenue(self, quarter: str) -> dict:
        """Revenue for a quarter (admins only)."""
        return {"quarter": quarter, "total": self._revenue_for(quarter)}
```

The method runs against the caller's live session state and its return value is
the resource content. It is registered as a top-level resource — **never** an
event handler — so it does not appear in `search_events` or `queue_event`.

## URIs

Each parameter becomes a URI-template variable (a required path segment), so
the resources above are addressed as:

```
state-resource://<state>/order_count
state-resource://<state>/revenue/{quarter}
```

`<state>` is the state's name as `search_events` reports it — the
module-prefixed name with the root `State` prefix stripped, and dots replaced by
slashes for nested substates. For a `DashboardState` defined in
`my_app/my_app.py` that is:

```
state-resource://my_app___my_app____dashboard_state/order_count
```

Resources are advertised in the server
[instructions](/docs/enterprise/mcp/#server-instructions) and through the
standard `resources/templates/list`, so a client discovers the exact URIs
without you writing them down.

## Options

| Option | Default | Purpose |
| --- | --- | --- |
| `auth` | the app's secure default | `True` (any authenticated user), `False` (public), or a `check(ctx) -> bool` callable. |
| `name` | `<state>.<method>` | Resource name advertised to clients. |
| `description` | the docstring summary | Resource description. |
| `mime_type` | `application/json` | MIME type of the returned content. |

`auth=` takes the same values as [`rxe.var`](/docs/enterprise/auth/secure-by-default/),
and its `ctx` carries `ctx.auth_user_state` (the user) plus
[`ctx.surface` / `ctx.token_scopes`](/docs/enterprise/mcp/authentication/#surface-aware-auth-checks).
It is enforced whenever an `AuthPlugin` provides identity. An anonymous session
has no user, so only `auth=False` resources are readable with one.

## Rules

- **Decorate a plain method.** `def name(self, ...)` — not an `rx.event`
  handler and not an `rx.var`. Anything else raises a `TypeError` at import
  time. The decorated method stays callable as `self.method(...)` from your own
  code.
- **Async is fine.** An `async def` resource method is awaited.
- **Annotate the parameters.** Their annotations become the resource's input
  schema (an unannotated parameter is treated as `str`).
- **Read-only by contract**, like a computed var. Drive state changes through
  `queue_event`.
- `rxe_request_context` is a reserved parameter name — the wrapper appends a
  parameter of that name to receive the MCP request context.

## Related

- [Auto MCP](/docs/enterprise/mcp/): the built-in `reflex://` resources for
  reading state and enumerating handlers.
- [Extending the server](/docs/enterprise/mcp/extending/): register arbitrary
  `FastMCP` tools, resources, and prompts.
- [Authentication](/docs/enterprise/mcp/authentication/): identity, scopes, and
  surface-aware checks.
