---
title: Extending the MCP Server
---

_New in reflex-enterprise v0.9.4._

# Extending the MCP Server

Beyond the built-in tools and `reflex://` resources, you can register your own
tools, resources, and prompts on the underlying
[`FastMCP`](https://modelcontextprotocol.io) server. There are two ways in, and
both hand you the same instance.

## At build time — `configure=`

Pass `MCPPlugin(configure=...)` a callable (or a `"module.function"` import
path). It is invoked as `configure(server)` once the built-in tools and
resources are registered and **before the server is mounted**, so whatever you
add is serving from the first request:

```python
import reflex_enterprise as rxe


def customize(server):
    @server.tool()
    def ping() -> str:
        """Health check."""
        return "pong"

    @server.resource("config://version")
    def version() -> str:
        """The deployed app version."""
        return "1.0.0"


config = rxe.Config(
    app_name="my_app",
    plugins=[rxe.MCPPlugin(configure=customize)],
)
```

A tool or resource that declares a `Context`-typed parameter has it injected by
FastMCP, giving you the active request and session — the same mechanism the
built-in tools use to resolve the caller's session from their bearer token.

## At runtime — `get_mcp_server()`

To register from application code instead, grab the active server with
`rxe.get_mcp_server()`. The server is built when the app is **compiled**, so
this has to run after that — a
[lifespan task](/docs/utility-methods/lifespan-tasks/) is the natural home,
since it starts once the backend comes up:

```python
from contextlib import asynccontextmanager

import reflex_enterprise as rxe


@asynccontextmanager
async def register_mcp_tools(app):
    """Add app-defined tools to the MCP server at startup."""
    server = rxe.get_mcp_server()

    @server.tool()
    def ping() -> str:
        """Health check."""
        return "pong"

    yield


app = rxe.App()
app.register_lifespan_task(register_mcp_tools)
```

```md alert warning
# `get_mcp_server()` raises a `RuntimeError` until the app has compiled.
That rules out calling it at module scope, including as a bare `@rxe.get_mcp_server().tool()` decorator — at import time there is no server yet. Register from a lifespan task as above, or use `configure=` for setup-time customization. The same applies to the equivalent `plugin.get_mcp_server()` instance method.
```

If you register tools after the transport is already serving, connected clients
pick them up on their next `tools/list`.

## Related

- [Auto MCP](/docs/enterprise/mcp/): the built-in tools and resources your
  additions sit alongside.
- [Custom MCP resources](/docs/enterprise/mcp/custom-resources/): the simpler
  path when all you want is a read-only view of session state.
