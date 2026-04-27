---
title: Event Handler API
---

_New in reflex-enterprise v0.7.1._

# Event Handler API Plugin

`rxe.EventHandlerAPIPlugin` exposes every registered event handler on your
Reflex state as an HTTP `POST` endpoint and auto-generates an OpenAPI 3
specification for them. This turns any Reflex app into a machine-driveable
API without writing a single route by hand — great for LLM agents, CLI
scripts, end-to-end tests, or external integrations that need to drive the
same logic the frontend uses.

```md alert info
# Requires `reflex >= 0.9.0` and `reflex-enterprise`. The plugin only works with `rxe.App`.
```

## Endpoints

When the plugin is enabled, the following routes are added to the backend:

| Path | Purpose |
| --- | --- |
| `POST /_reflex/event/<state_full_name>/<handler_name>` | One endpoint per `@rx.event` handler on every state class. Streams state deltas as newline-delimited JSON. |
| `POST /_reflex/retrieve_state` | Returns the full root state `.dict()` for the session token without re-hydrating client storage. |
| `GET /_reflex/events/openapi.yaml` | Auto-generated OpenAPI 3 specification describing every endpoint above. |
| `GET,HEAD /.well-known/api-catalog` | RFC 9727 API catalog pointing at the OpenAPI spec (RFC 9264 Linkset). |

Handler argument names and type annotations are introspected to build each
`requestBody` schema, and the docstring's first line becomes the endpoint
`summary`. Handlers registered as page `on_load` triggers are listed in the
`description` field of the spec so API consumers can tell which endpoint is
invoked when a given page is "visited".

## Configuration

Add the plugin to the `plugins` list of `rxe.Config` in `rxconfig.py`:

```python
import reflex as rx
import reflex_enterprise as rxe

config = rxe.Config(
    app_name="my_app",
    plugins=[
        rxe.EventHandlerAPIPlugin(
            # All three arguments are optional.
            api_version="1.0.0",
            contact={"name": "Ops", "email": "ops@example.com"},
            license_info={
                "name": "Apache 2.0",
                "url": "https://opensource.org/licenses/Apache-2.0",
            },
        )
    ],
)
```

Your app must use `rxe.App()` (not `rx.App()`):

```python
import reflex_enterprise as rxe

app = rxe.App()
```

```md alert warning
# The backend serves the API on the Reflex backend port (default `http://localhost:8000` in dev, or the `deploy_url` in production). If you're running production with `--single-port`, the API is instead reachable on the frontend port (default `http://localhost:3000`).
```

## Authentication

Every endpoint requires a Bearer token in the `Authorization` header. The
token is a random UUID that identifies a **client session**:

```
Authorization: Bearer <random-uuid>
```

All calls using the same token share state — the token plays the same role
as the per-tab session cookie the browser uses. Generate one with any UUID
library:

```bash
TOKEN=$(python -c 'import uuid; print(uuid.uuid4())')
```

Reuse `$TOKEN` across calls if you want subsequent requests to see the
effects of earlier ones (e.g. create a ticket, then list tickets). Pick a
new UUID to get a fresh, independent session.

## Discovering the API

The plugin publishes the OpenAPI spec at a well-known location per RFC 9727.
Any compliant client can discover it from the catalog:

```bash
curl http://localhost:8000/.well-known/api-catalog
```

Response (RFC 9264 Linkset):

```json
{
  "linkset": [
    {
      "anchor": "http://localhost:8000/",
      "service-desc": [
        {
          "href": "http://localhost:8000/_reflex/events/openapi.yaml",
          "type": "application/vnd.oai.openapi"
        }
      ]
    }
  ]
}
```

Fetch the spec directly:

```bash
curl http://localhost:8000/_reflex/events/openapi.yaml
```

Browse it with any OpenAPI viewer (Swagger UI, Redoc, Scalar, the JetBrains
HTTP client, etc.) pointed at that URL.

## Response shape

Event handler endpoints return the state deltas produced by the handler as
**newline-delimited JSON** (`application/x-ndjson`). Each line is one
delta; the stream ends when the handler finishes:

```
{"state.TicketState": {"tickets": [...], "total_count": 3}}
{"state.TicketState": {"open_count": 2}}
```

For one-shot clients that just want the final state, simply consume the
stream to completion and then (optionally) fetch the full state:

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
     http://localhost:8000/_reflex/retrieve_state
```

```md alert info
# Unlike the built-in `hydrate` event, `/_reflex/retrieve_state` does **not** reset client-storage vars (`rx.Cookie`, `rx.LocalStorage`, `rx.SessionStorage`). Use it whenever you want to read state without modifying it.
```

## The tickets demo app

The `reflex-enterprise` repository includes a ready-to-run IT-ticketing demo
under `demos/tickets/` that exercises every feature of the plugin. Its
`rxconfig.py` is the minimal reference setup:

```python
import reflex as rx
import reflex_enterprise as rxe

config = rxe.Config(
    app_name="tickets",
    async_db_url="sqlite+aiosqlite:///tickets.db",
    db_url="sqlite:///tickets.db",
    plugins=[
        rxe.EventHandlerAPIPlugin(
            contact={"name": "Reflex Maintainers", "email": "info@reflex.dev"},
            license_info={
                "name": "Apache 2.0",
                "url": "https://opensource.org/licenses/Apache-2.0",
            },
        )
    ],
    disable_plugins=[rx.plugins.SitemapPlugin],
)
```

The state class exposes typical CRUD handlers — `create_ticket`,
`update_ticket`, `set_status`, `delete_ticket`, `seed`, `clear_all`, plus
list/filter/sort/pagination helpers and a `load_tickets` on-load handler.
Here's a trimmed excerpt:

```python
class TicketState(rx.State):
    tickets: list[TicketRecord] = []
    total_count: int = 0
    open_count: int = 0

    @rx.event
    async def create_ticket(
        self,
        title: str,
        description: str = "",
        priority: str = "medium",
        assignee: str = "",
    ) -> None:
        """Create a new IT support ticket.

        Args:
            title: Short summary of the issue.
            description: Optional long-form description.
            priority: One of "low", "medium", "high".
            assignee: Username of the person handling the ticket.
        """
        await self._create_ticket_record(
            title=title,
            description=description,
            priority=priority,
            assignee=assignee,
        )
        await self._reload_from_db()

    @rx.event
    async def set_status(self, ticket_id: str, status: str) -> None:
        """Set the status of a ticket.

        Args:
            ticket_id: The id of the ticket.
            status: One of "open", "in_progress", "closed".
        """
        ...
```

Because the state's full name is `tickets___tickets____ticket_state`, the
generated handler routes live at:

```
POST /_reflex/event/tickets___tickets____ticket_state/<handler_name>
```

The state full name is built from the Python module path (dot separators
become `___`) followed by the class name — inspect the generated
`openapi.yaml` if you are unsure of the exact path for a given handler.

### curl examples

Assume a dev server running on `http://localhost:8000` and a token in
`$TOKEN`:

```bash
TOKEN=$(python -c 'import uuid; print(uuid.uuid4())')
BASE=http://localhost:8000
TICKET_STATE=$BASE/_reflex/event/tickets___tickets____ticket_state
```

**Discover the API.**

```bash
curl $BASE/.well-known/api-catalog
curl $BASE/_reflex/events/openapi.yaml
```

**Retrieve the full state dict.**

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
     $BASE/_reflex/retrieve_state
```

**Seed some sample tickets.**

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
     $TICKET_STATE/seed
```

**Load the first page of tickets into the session.** This mirrors the
`on_load` handler the frontend runs when a browser hits `/`:

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
     $TICKET_STATE/load_tickets
```

**Create a ticket.** `title` is required; `description`, `priority`, and
`assignee` are optional (the server applies the same defaults as in the
Python signature):

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"title":"VPN is down","priority":"high","assignee":"alice"}' \
     $TICKET_STATE/create_ticket
```

**Change a ticket's status.**

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"ticket_id":"<uuid>","status":"in_progress"}' \
     $TICKET_STATE/set_status
```

**Partial update.** `update_ticket` treats empty strings as "leave
unchanged":

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"ticket_id":"<uuid>","assignee":"bob","priority":"low"}' \
     $TICKET_STATE/update_ticket
```

**Delete a ticket.**

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" \
     -d '{"ticket_id":"<uuid>"}' \
     $TICKET_STATE/delete_ticket
```

**Clear the board.**

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
     $TICKET_STATE/clear_all
```

### Example OpenAPI excerpt

The generated spec groups handlers under an OpenAPI `tag` matching the
state class name. Here's the entry for `create_ticket`:

```yaml
/_reflex/event/tickets___tickets____ticket_state/create_ticket:
  post:
    summary: Create a new IT support ticket.
    description: |
      title: Short summary of the issue.
      description: Optional long-form description.
      priority: One of "low", "medium", "high".
      assignee: Username of the person handling the ticket.
    operationId: TicketState_create_ticket
    tags: [TicketState]
    requestBody:
      required: true
      content:
        application/json:
          schema:
            type: object
            required: [title]
            properties:
              title:       {type: string}
              description: {type: string, default: ""}
              priority:    {type: string, default: medium}
              assignee:    {type: string, default: ""}
    responses:
      "200": {$ref: "#/components/responses/StreamedDelta"}
      "401": {$ref: "#/components/responses/Unauthorized"}
```

## Driving the app from an LLM

Because the OpenAPI spec is self-describing (summaries, parameter types,
defaults, on-load references), most LLM agents with HTTP tool access can
drive a Reflex app end-to-end without any extra glue code. Give them the
spec URL and a natural-language task:

> Use the API exposed at `http://localhost:8000/_reflex/events/openapi.yaml` to drive the application.
>
> Create a new ticket assigned to Masen for investigating RegistrationContext issues in reflex CI.

A well-equipped agent will:

1. `GET /_reflex/events/openapi.yaml` and parse the operations.
2. Generate a session token (`uuid4`) to use as the Bearer credential.
3. Call `POST /_reflex/event/.../create_ticket` with a body like
   `{"title": "Investigate RegistrationContext issues in Reflex CI", "assignee": "Masen", "priority": "medium"}`.
4. Optionally call `/_reflex/retrieve_state` to confirm the ticket landed.

Other prompts that work well with the tickets demo:

> Using the Reflex API at `http://localhost:8000`, seed the database, then close every ticket currently assigned to `bob`.

> Via `http://localhost:8000/_reflex/events/openapi.yaml`, page through every ticket and summarize which assignees have the largest open backlog.

> Using the Reflex API at `http://localhost:8000`, create three high-priority tickets for the following issues, then show me the resulting state: <list of issues>

```md alert info
# For agents that can't follow `api-catalog` automatically, point them directly at `/_reflex/events/openapi.yaml`. A single URL is enough context for most tool-using models to take it from there.
```

## Dynamic route variables

If any of your pages use dynamic route segments (e.g. `/tickets/[ticket_id]`),
the plugin surfaces those as **optional query parameters** on every
endpoint so the state can read them via `self.router`:

```
POST /_reflex/event/.../load_ticket_detail?ticket_id=<uuid>
```

They appear under `components.parameters.route_<name>` in the OpenAPI spec
and are referenced from every operation's `parameters` list.

## Security considerations

- **The Bearer token is just a session id, not an auth credential.** Anyone
  who can reach the backend and generate UUIDs can drive the app. Put the
  API behind your normal auth layer (reverse-proxy, OIDC, VPN, etc.) before
  exposing it outside trusted networks.
- **Every event handler on every state is exposed by default.** If you have
  privileged handlers, either split them onto a state class you don't want
  to expose, or run the plugin only in environments where API access is
  appropriate.
- **Handlers that return `rx.redirect(...)` work over the API**, but the
  redirect is emitted as a state delta rather than an HTTP 3xx — the client
  sees the URL change, not a browser redirect. This is usually what you
  want for programmatic clients.