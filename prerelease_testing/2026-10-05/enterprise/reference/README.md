<div align="center">

# Reflex Enterprise

**Advanced components, authentication, and agent APIs for [Reflex](https://reflex.dev) apps — in pure Python.**

[![PyPI](https://img.shields.io/pypi/v/reflex-enterprise)](https://pypi.org/project/reflex-enterprise/)
[![Python](https://img.shields.io/pypi/pyversions/reflex-enterprise)](https://pypi.org/project/reflex-enterprise/)

[**Documentation**](https://reflex.dev/docs/enterprise/overview/) ·
[**Components**](https://reflex.dev/docs/enterprise/components/) ·
[**Pricing**](https://reflex.dev/pricing/)

</div>

---

## What is it?

`reflex-enterprise` is the premium add-on package for the [Reflex](https://github.com/reflex-dev/reflex)
web framework. It adds components and plugins that the Reflex team builds and maintains:

- **Enterprise-grade components** — AG Grid data tables, Leaflet maps, drag-and-drop, node
  editors, and more, all wrapped for Python with typed props and event handlers.
- **Secure-by-default authentication** — OIDC login, plus page, event, and state-field
  protection that is on unless you opt out.
- **A first-class agent surface** — expose your app's own event handlers to AI agents over
  MCP or REST, with OAuth 2.1 and per-scope human consent.

It is a drop-in layer, not a different framework: swap `rx.App` for `rxe.App` and `rx.Config`
for `rxe.Config`, and the rest of your Reflex app is unchanged. Everything in `rx` keeps
working exactly as before.

## Installation

```bash
pip install reflex-enterprise
```

Optional extras:

```bash
pip install "reflex-enterprise[mcp]"      # MCPPlugin — expose the app to AI agents
pip install "reflex-enterprise[testing]"  # the reflex_app pytest fixture
```

Requires Python 3.10+ and `reflex >= 0.9.6` (installed automatically).

## Getting started

Two swaps, then run the app as usual with `reflex run`.

```python
# rxconfig.py
import reflex_enterprise as rxe

config = rxe.Config(
    app_name="my_app",
    # accepts every rx.Config option, plus the enterprise-only ones
)
```

```python
# my_app/my_app.py
import reflex_enterprise as rxe

app = rxe.App()
```

Enterprise components live in the `rxe` namespace next to everything you already use from `rx`.

## Free usage and licensing

`reflex-enterprise` is **free to use in development**, but it is not open source — it ships
under a [proprietary EULA](https://github.com/reflex-dev/reflex/blob/main/docs/enterprise/LICENSE)
and its use is tied to a Reflex account.

- **A Reflex login is required.** Run `reflex login`, or set `REFLEX_ACCESS_TOKEN`. An app
  started while logged out exits with an error.
- **Development is free.** `reflex run` works on the Free tier, with no time limit and no
  feature gating on components.
- **Shipping is free with the badge.** `reflex run --env prod` and `reflex export` work on the
  Free tier as long as the app shows the "Built with Reflex" badge (see below). (Deploying to
  [Reflex Cloud](https://reflex.dev/docs/hosting/deploy-quick-start/) is not gated by this
  check — it follows your cloud plan.)
- **The ["Built with Reflex" badge](https://reflex.dev/docs/enterprise/built-with-reflex/)**
  is displayed in production builds and exports. Hiding it (`show_built_with_reflex=False`) requires Pro
  or above on Reflex Cloud, and Enterprise when self-hosted.

See [reflex.dev/pricing](https://reflex.dev/pricing/) for what each tier includes.

## Features

### Authentication — [`AuthPlugin`](https://reflex.dev/docs/enterprise/auth/overview/)

Add OIDC login to an app by registering one plugin. Pages, event handlers, state fields, and
computed vars are then **protected by default** — a protected var is never serialized to an
anonymous visitor, and a protected handler never runs for one — so an unguarded surface has to
be an explicit choice rather than an oversight.

```python
# rxconfig.py
import reflex_enterprise as rxe

config = rxe.Config(app_name="my_app", plugins=[rxe.AuthPlugin()])
```

```python
import reflex as rx

import reflex_enterprise as rxe


class DashboardState(rx.State):
    revenue: int = 0  # protected: never sent to an anonymous visitor

    @rxe.var(auth=False)
    def headline(self) -> str:  # explicitly public
        return "Welcome!"

    @rxe.event(auth=lambda ctx: ctx.auth_user_state.email.endswith("@acme.com"))
    def close_the_books(self): ...


@rxe.page(route="/dashboard")      # login required
def dashboard() -> rx.Component: ...


@rxe.page(route="/", auth=False)   # public
def index() -> rx.Component: ...
```

`/login`, `/logout`, `/callback`, and `/forbidden` routes are generated for you (and are fully
customizable), an event blocked before login is replayed afterwards instead of being lost, and
an [audit hook](https://reflex.dev/docs/enterprise/auth/audit/) can observe every login and
access decision.

### AI agent access — [`MCPPlugin`](https://reflex.dev/docs/enterprise/mcp/overview)

Publish your app's existing event handlers as [Model Context Protocol](https://modelcontextprotocol.io)
tools, so an agent can drive the real app — no separate API to write or keep in sync.

```python
# rxconfig.py
import reflex_enterprise as rxe

config = rxe.Config(app_name="my_app", plugins=[rxe.AuthPlugin(), rxe.MCPPlugin()])
```

A streamable-HTTP MCP server is mounted at `/_reflex/mcp` with `search_events` and
`queue_event` tools plus a `reflex://` resource family for reading live session state. Add an
`AuthPlugin` and the app becomes a spec-compliant **OAuth 2.1 authorization + resource server**:
agents authenticate through your existing identity provider, the human approves individually
grantable app scopes on a consent page, and the app issues its own resource-bound tokens so
upstream IdP tokens never leave the server. Every auth check you already wrote applies to agent
traffic unchanged. Prefer REST? [`EventHandlerAPIPlugin`](https://reflex.dev/docs/enterprise/event-handler-api/)
exposes the same handlers as HTTP endpoints with a generated OpenAPI spec.

### Advanced components

| Component | Description | Docs |
| --- | --- | --- |
| **AG Grid** | Enterprise data grid — sorting, filtering, pivoting, grouping, master/detail, cell selection, server-side row model, and direct SQLModel table binding. | [Docs](https://reflex.dev/docs/enterprise/ag-grid/) |
| **AG Charts** | Financial and statistical visualizations, with charting driven straight from state. | [Docs](https://reflex.dev/docs/enterprise/ag-chart/) |
| **Map** | Interactive Leaflet maps: tile layers, markers, popups, vector shapes, controls, and a programmatic map API. | [Docs](https://reflex.dev/docs/enterprise/map/) |
| **Drag and Drop** | `react-dnd` draggables and drop targets, with hooks for advanced cases. | [Docs](https://reflex.dev/docs/enterprise/drag-and-drop/) |
| **React Flow** | Node-based editors, flowcharts, and diagrams with custom nodes and edges. | [Docs](https://reflex.dev/docs/enterprise/react-flow/) |
| **Mantine** | Extra inputs and UI primitives — autocomplete, multi-select, tags input, tree, timeline, date pickers, progress rings. | [Docs](https://reflex.dev/docs/enterprise/mantine/) |

```python
import reflex as rx

import reflex_enterprise as rxe


class State(rx.State):
    column_defs: list[dict] = [{"field": "name"}, {"field": "age"}]
    row_data: list[dict] = [{"name": "Ada", "age": 36}]

    @rx.event
    def handle_drop(self, item: dict):
        return rx.toast(f"dropped {item}")


rxe.ag_grid(
    id="grid",
    column_defs=State.column_defs,
    row_data=State.row_data,
    row_selection={"mode": "multiRow"},
)

rxe.map(
    rxe.map.tile_layer(url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"),
    rxe.map.marker(rxe.map.popup("You are here"), position=rxe.map.latlng(lat=51.505, lng=-0.09)),
    id="map",
    center=rxe.map.latlng(lat=51.505, lng=-0.09),
    zoom=13,
    height="50vh",
)

rxe.dnd.drop_target(
    rxe.dnd.draggable(rx.card("Drag me"), type="card"),
    accept=["card"],
    on_drop=State.handle_drop,
)
```

### Testing

The `reflex_app` pytest fixture boots your real app — frontend and backend — and hands the test
a live URL to drive with Playwright or any other browser tooling. It is registered through an
entry point, so there is no `conftest.py` wiring to do.

```python
from playwright.sync_api import Page, expect

from reflex_enterprise.testing import ReflexApp


def test_signup(reflex_app: ReflexApp, page: Page):
    page.goto(reflex_app.url)

    page.get_by_placeholder("Email").fill("dev@reflex.dev")
    page.get_by_role("button", name="Sign up").click()

    expect(page.get_by_text("Thanks, dev@reflex.dev!")).to_be_visible()
```

The app under test is discovered by walking up to the nearest `rxconfig.py`, started once per
session, and reused across tests.

## Links

- [Enterprise documentation](https://reflex.dev/docs/enterprise/overview/)
- [Reflex documentation](https://reflex.dev/docs/getting-started/introduction/)
- [Changelog](https://reflex.dev/docs/changelog/reflex-enterprise/)
- [Pricing and tiers](https://reflex.dev/pricing/)
- Questions or bugs? Reach us at [support@reflex.dev](mailto:support@reflex.dev)

## License

Proprietary — see the
[EULA](https://github.com/reflex-dev/reflex/blob/main/docs/enterprise/LICENSE).
Copyright © Pynecone, Inc.
