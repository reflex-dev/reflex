"""Server-side rendering (SSR) backend for Reflex apps.

This is the request-time half of SSR: the ``/_ssr_data`` endpoint that computes
the hydrated initial state for a route by reusing the regular event machinery.
It lives in the top-level ``reflex`` package because it depends on the state and
app machinery that is not part of ``reflex_base``.

The config gate (:func:`is_enabled`) and the compiler JS snippets live in
:mod:`reflex_base.ssr` so the compiler templates can use them without importing
``reflex``.  ``is_enabled`` is re-exported here for convenience.

Everything here is a no-op unless ``config.ssr_mode`` is not ``OFF``.
"""

from __future__ import annotations

import asyncio
import inspect
import traceback
from typing import TYPE_CHECKING, Any

from reflex_base import constants
from reflex_base.ssr import is_enabled as is_enabled

from reflex.utils import console

if TYPE_CHECKING:
    from starlette.requests import Request
    from starlette.responses import Response

    from reflex.app import App
    from reflex.event import Event
    from reflex.state import BaseState

# Sentinel token/session id used for the stateless SSR render.
SSR_TOKEN = "__ssr__"


def _build_router_data(
    app: App, path: str, headers: dict[str, str], client_ip: str
) -> dict[str, Any]:
    """Build the ``router_data`` dict for a stateless SSR render.

    Args:
        app: The app, used to resolve the concrete path to a route pattern.
        path: The concrete request path (e.g. ``/blog/hello-world``).
        headers: The forwarded request headers.
        client_ip: The client IP address.

    Returns:
        A ``router_data`` dict with the same shape ``process()`` produces.
    """
    from reflex.route import extract_route_params

    resolved_route = app.router(path) or "404"
    params = extract_route_params(path, resolved_route)
    return {
        constants.RouteVar.PATH: "/" + resolved_route.removeprefix("/"),
        constants.RouteVar.ORIGIN: path,
        constants.RouteVar.QUERY: dict(params),
        constants.RouteVar.CLIENT_TOKEN: SSR_TOKEN,
        constants.RouteVar.SESSION_ID: SSR_TOKEN,
        constants.RouteVar.HEADERS: {
            "origin": headers.get("origin", headers.get("host", "http://localhost")),
            **headers,
        },
        constants.RouteVar.CLIENT_IP: client_ip,
    }


async def _run_on_load_event(state: BaseState, event: Event, path: str) -> None:
    """Run a single resolved on_load event on the ephemeral SSR state.

    Resolves the handler's target substate from ``event.name`` and invokes it
    directly (rather than going through the session-managed event queue, which
    needs a real client token and state manager).  Handlers mutate the state in
    place; their return value is consumed but discarded since the whole tree is
    serialized later.

    Args:
        state: The ephemeral root state instance.
        event: The resolved on_load event (``event.name`` is the dotted handler).
        path: The URL path (for error logging).
    """
    try:
        # e.g. "reflex___state____state.blog_state.on_load" -> substate + method.
        *substate_path, method = event.name.split(".")
        substate = state.get_substate(substate_path)
        handler = substate.event_handlers[method]

        result = handler.fn(substate)
        if asyncio.iscoroutine(result):
            result = await result
        if inspect.isgenerator(result):
            for _ in result:
                pass
        elif inspect.isasyncgen(result):
            async for _ in result:
                pass
    except Exception:
        console.warn(f"SSR on_load handler failed for {path}: {traceback.format_exc()}")


async def _run_on_load_events(app: App, state: BaseState, path: str) -> None:
    """Run the route's on_load handlers on the ephemeral SSR state.

    Args:
        app: The app to get load events from.
        state: The ephemeral root state instance.
        path: The URL path (for error logging).
    """
    from reflex.event import Event

    load_events = app.get_load_events(path)
    if not load_events:
        return
    for event in Event.from_event_type(load_events, router_data=state.router_data):
        await _run_on_load_event(state, event, path)


def ssr_data(app: App):
    """Build the ``/_ssr_data`` endpoint handler.

    The handler creates an ephemeral state, applies route data, runs on_load
    handlers, and returns the serialized state tree for server-side rendering.

    Args:
        app: The app to get SSR data for.

    Returns:
        The SSR data request handler.
    """
    from starlette.responses import Response

    from reflex.state import RouterData, State
    from reflex.utils import format

    async def ssr_data_handler(request: Request) -> Response:
        """Handle an SSR data request.

        Args:
            request: The Starlette request object.

        Returns:
            Response with the serialized state as JSON.
        """
        body = await request.json()
        path = body.get("path", "/")
        headers = body.get("headers", {})

        if not app._state:
            return Response(
                content='{"state": null}',
                media_type="application/json",
            )

        # Ephemeral root state — no persistent session is created.  Use State
        # (root) rather than app._state which may be a subclass whose inherited
        # vars can't be set without a parent.
        state = State(_reflex_internal_init=True)  # pyright: ignore[reportCallIssue]

        router_data = _build_router_data(
            app,
            path,
            headers,
            request.client.host if request.client else "0.0.0.0",
        )
        # Assigning router_data recomputes dependent DynamicRouteVars.
        state.router_data = router_data
        state.router = RouterData.from_router_data(router_data)

        await _run_on_load_events(app, state, path)

        json_str = format.json_dumps({"state": state.dict()})
        return Response(
            content=json_str,
            media_type="application/json",
            headers={"Cache-Control": "no-cache"},
        )

    return ssr_data_handler
