"""Plugin to expose event handlers as HTTP API endpoints."""

from __future__ import annotations

import contextlib
import inspect
import json
from functools import partial
from typing import TYPE_CHECKING, Any, get_args, get_origin

from starlette.requests import Request
from starlette.responses import JSONResponse, Response, StreamingResponse
from starlette.routing import BaseRoute
from starlette.schemas import OpenAPIResponse, SchemaGenerator

from reflex._internal.registry import RegisteredEventHandler, RegistrationContext
from reflex_core import constants
from reflex_core.event import Event
from reflex_core.plugins.base import Plugin as PluginBase
from reflex_core.utils.format import get_event_handler_parts, json_dumps

if TYPE_CHECKING:
    from reflex.app import App


# Mapping from Python types to OpenAPI (JSON Schema) types.
_PYTHON_TYPE_TO_OPENAPI: dict[type, dict[str, str]] = {
    str: {"type": "string"},
    int: {"type": "integer"},
    float: {"type": "number"},
    bool: {"type": "boolean"},
    bytes: {"type": "string", "format": "byte"},
}


def _python_type_to_openapi_schema(annotation: Any) -> dict[str, Any]:
    """Convert a Python type annotation to an OpenAPI JSON Schema fragment.

    Args:
        annotation: The Python type annotation.

    Returns:
        An OpenAPI-compatible schema dict.
    """
    if annotation is inspect.Parameter.empty or annotation is Any:
        return {}

    # Direct type match.
    if annotation in _PYTHON_TYPE_TO_OPENAPI:
        return dict(_PYTHON_TYPE_TO_OPENAPI[annotation])

    origin = get_origin(annotation)
    args = get_args(annotation)

    # Handle list[X] annotations.
    if origin is list:
        schema: dict[str, Any] = {"type": "array"}
        if args:
            schema["items"] = _python_type_to_openapi_schema(args[0])
        return schema

    # Handle dict[K, V] annotations.
    if origin is dict:
        schema = {"type": "object"}
        if len(args) >= 2:
            schema["additionalProperties"] = _python_type_to_openapi_schema(args[1])
        return schema

    # Optional[X] / X | None  →  unwrap to X
    if origin is type(int | str):  # types.UnionType (3.10+)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return {**_python_type_to_openapi_schema(non_none[0]), "nullable": True}

    # typing.Union / typing.Optional
    try:
        import typing

        if origin is typing.Union:
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return {
                    **_python_type_to_openapi_schema(non_none[0]),
                    "nullable": True,
                }
    except Exception:
        pass

    # Fallback - no schema constraint.
    return {}


def _build_endpoint_docstring(
    registered_event_handler: RegisteredEventHandler,
    dynamic_route_args: dict[str, str] | None = None,
) -> str:
    """Build an OpenAPI YAML docstring for a Starlette endpoint from an event handler.

    Args:
        registered_event_handler: The registered event handler.
        dynamic_route_args: Dynamic route arguments collected from all pages.

    Returns:
        A YAML string suitable for use as an endpoint function docstring.
    """
    handler = registered_event_handler.handler
    fn = handler.fn
    if isinstance(fn, partial):
        fn = fn.func

    # --- Summary / description from the original docstring ---
    raw_doc = inspect.getdoc(fn) or ""
    lines = raw_doc.strip().splitlines()
    summary = lines[0] if lines else handler.fn.__name__
    description_lines = [
        line
        for line in lines[1:]
        if not line.strip().startswith(("Args:", "Returns:", "Raises:"))
    ]
    # Trim leading blank lines and trailing whitespace-only section headers.
    while description_lines and not description_lines[0].strip():
        description_lines.pop(0)
    while description_lines and not description_lines[-1].strip():
        description_lines.pop()
    description = "\n".join(description_lines).strip() if description_lines else None

    # --- Request body schema from function parameters ---
    params = iter(handler.get_parameters().items())
    if handler.state is not None:
        next(params, None)  # skip the bound `self` parameter
    properties: dict[str, Any] = {}
    required: list[str] = []

    for name, param in params:
        prop = _python_type_to_openapi_schema(param.annotation)
        if not prop:
            prop = {}
        properties[name] = prop
        if param.default is inspect.Parameter.empty:
            required.append(name)
        else:
            # Include the default value in the schema.
            try:
                json.dumps(param.default)  # ensure it's JSON-serialisable
                prop["default"] = param.default
            except (TypeError, ValueError):
                pass

    # --- Assemble the OpenAPI operation object as a dict ---
    operation: dict[str, Any] = {}
    operation["summary"] = summary
    if description:
        operation["description"] = description

    if properties:
        operation["requestBody"] = {
            "required": bool(required),
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": properties,
                        **({"required": required} if required else {}),
                    }
                }
            },
        }

    operation["responses"] = {
        200: {"$ref": "#/components/responses/StreamedDelta"},
        401: {"$ref": "#/components/responses/Unauthorized"},
    }

    # Reference shared dynamic route query parameters.
    if dynamic_route_args:
        operation["parameters"] = [
            {"$ref": f"#/components/parameters/route_{name}"}
            for name in dynamic_route_args
        ]

    return json.dumps(operation)


def _add_event_handler_route(
    app: App,
    registered_event_handler: RegisteredEventHandler,
    dynamic_route_args: dict[str, str] | None = None,
) -> BaseRoute | None:
    """Add an API route for a registered event handler.

    Args:
        app: The app to add the route to.
        registered_event_handler: The registered event handler to add the route for.
        dynamic_route_args: Dynamic route arguments collected from all pages.

    Returns:
        The added route, or None if the route was not added.
    """
    from reflex.state import State

    if not app._api:
        return None

    docstring = _build_endpoint_docstring(registered_event_handler, dynamic_route_args)

    async def event_handler_endpoint(request: Request) -> Response:
        token = request.headers.get("Authorization", "").removeprefix("Bearer ")
        if not token:
            return JSONResponse(
                {
                    "error": "Unauthorized: Provide a generated UUID as your Authorization: Bearer <token>."
                },
                status_code=401,
            )
        if request.headers.get("Content-Length", "0") != "0":
            rbody = await request.json()
        else:
            rbody = None

        # Build router_data from the incoming HTTP request.
        headers = dict(request.headers)
        client_ip = request.client.host if request.client else "0.0.0.0"
        headers["asgi-scope-client"] = client_ip
        client_ip = headers.get("x-forwarded-for", client_ip).partition(",")[0].strip()
        router_data = {
            constants.RouteVar.CLIENT_TOKEN: token,
            constants.RouteVar.HEADERS: headers,
            constants.RouteVar.CLIENT_IP: client_ip,
            constants.RouteVar.QUERY: dict(request.query_params),
            constants.RouteVar.PATH: str(request.url.path),
        }

        async def _stream_response():
            try:
                async with contextlib.aclosing(
                    app.event_processor.enqueue_stream_delta(
                        token,
                        *Event.from_event_type(
                            registered_event_handler.handler(**(rbody or {})),
                            router_data=router_data,
                        ),
                    )
                ) as delta_stream:
                    async for delta in delta_stream:
                        yield json_dumps(delta) + "\n"
            except Exception as e:
                yield json.dumps({
                    "error": f"Error processing event: {e!s}. Check server logs for more details."
                })
                return

        return StreamingResponse(_stream_response(), media_type="application/x-ndjson")

    # Attach the generated OpenAPI YAML as the endpoint's docstring
    # so that Starlette's SchemaGenerator picks it up.
    event_handler_endpoint.__doc__ = docstring

    if registered_event_handler.handler.state:
        state_name, handler_name = get_event_handler_parts(
            registered_event_handler.handler
        )
        state_name = state_name.removeprefix(State.get_full_name() + ".")
        path = f"/_reflex/event/{state_name}/{handler_name}"
        app._api.add_route(
            path=path,
            route=event_handler_endpoint,
            methods=["POST"],
        )
        return app._api.routes[-1]
    return None


class EventHandlerAPIPlugin(PluginBase):
    """Plugin that exposes registered event handlers as HTTP API endpoints with OpenAPI schema."""

    def post_compile(self, **context) -> None:
        """Add event handler API routes after compilation.

        Args:
            context: The post-compile context containing the app.
        """
        from reflex.route import get_route_args
        from reflex.state import (
            EventHandlerSetVar,
            FrontendEventExceptionState,
            OnLoadInternalState,
            State,
            UpdateVarsInternalState,
        )
        from reflex_core.config import get_config
        from reflex_core.environment import environment
        from reflex_core.event import EventHandler, EventSpec

        app: App = context["app"]
        if not app._api:
            return

        config = get_config()

        # Collect dynamic route args from all registered pages.
        all_dynamic_args: dict[str, str] = {}
        for route in app._unevaluated_pages:
            all_dynamic_args.update(get_route_args(route))

        # Build page route documentation with on_load references.
        base_url = (config.deploy_url or "").rstrip("/")
        page_lines: list[str] = []
        for route in app._unevaluated_pages:
            display_route = f"/{route}" if route else "/"
            full_url = f"{base_url}{display_route}" if base_url else display_route
            load_events = app._load_events.get(route, [])
            if not load_events:
                page_lines.append(f"- `{full_url}`")
                continue
            handler_names: list[str] = []
            for evt in load_events:
                handler = None
                if isinstance(evt, EventHandler):
                    handler = evt
                elif isinstance(evt, EventSpec):
                    handler = evt.handler
                if handler and handler.state:
                    s_name, h_name = get_event_handler_parts(handler)
                    s_name = s_name.removeprefix(State.get_full_name() + ".")
                    handler_names.append(f"`POST /_reflex/event/{s_name}/{h_name}`")
            if handler_names:
                page_lines.append(
                    f"- `{full_url}` — on_load triggers " + ", ".join(handler_names)
                )
            else:
                page_lines.append(f"- `{full_url}`")

        description = (
            "Auto-generated API for Reflex event handlers.\n\n"
            "## Authentication\n\n"
            "All endpoints require a Bearer token passed via the "
            "`Authorization` header. The token should be a random UUID "
            "that identifies the client session.\n\n"
            "```\nAuthorization: Bearer <random-uuid>\n```\n\n"
            "Generate a token with any UUID library, e.g. "
            '`python -c "import uuid; print(uuid.uuid4())"`.'
        )

        if page_lines:
            description += (
                "\n\n## Pages\n\n"
                "The following pages are defined in the app. Pages with "
                "`on_load` handlers automatically trigger the referenced "
                "endpoint when a user navigates to them.\n\n" + "\n".join(page_lines)
            )

        if all_dynamic_args:
            description += (
                "\n\n## Dynamic Route Variables\n\n"
                "The app defines dynamic route segments in its page URLs. "
                "These are exposed as optional query parameters on every "
                "endpoint so the state can access them via `self.router`.\n\n"
                + "\n".join(
                    f"- `{name}` (from page URL pattern)" for name in all_dynamic_args
                )
            )

        # Build shared components for $ref reuse across endpoints.
        components: dict[str, Any] = {
            "securitySchemes": {
                "BearerToken": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": "A random UUID that identifies the client session.",
                }
            },
            "responses": {
                "StreamedDelta": {
                    "description": "Streamed state deltas as newline-delimited JSON.",
                    "content": {
                        "application/x-ndjson": {
                            "schema": {"type": "object"},
                        }
                    },
                },
                "Unauthorized": {
                    "description": "Missing or invalid Bearer token.",
                },
            },
        }

        if all_dynamic_args:
            from reflex_core.constants.route import RouteArgType

            components["parameters"] = {}
            for arg_name, arg_type in all_dynamic_args.items():
                param_schema: dict[str, Any] = (
                    {"type": "array", "items": {"type": "string"}}
                    if arg_type == RouteArgType.LIST
                    else {"type": "string"}
                )
                components["parameters"][f"route_{arg_name}"] = {
                    "name": arg_name,
                    "in": "query",
                    "required": False,
                    "schema": param_schema,
                    "description": "Dynamic route variable from a page URL.",
                }

        base_schema: dict[str, Any] = {
            "openapi": "3.0.0",
            "info": {
                "title": f"{config.app_name} API",
                "description": description,
            },
            "components": components,
            "security": [{"BearerToken": []}],
        }

        if config.api_url:
            # In prod single-port mode, the API is served from the same origin
            # as the frontend, so use deploy_url. Otherwise use api_url.
            if environment.REFLEX_MOUNT_FRONTEND_COMPILED_APP.get():
                server_url = config.deploy_url
            else:
                server_url = config.api_url
            if server_url:
                base_schema["servers"] = [{"url": server_url}]

        schemas = SchemaGenerator(base_schema)
        routes = [
            route
            for reh in RegistrationContext.get().event_handlers.values()
            if reh.handler.state
            not in (
                FrontendEventExceptionState,
                OnLoadInternalState,
                UpdateVarsInternalState,
            )
            and not isinstance(reh.handler, EventHandlerSetVar)
            and (route := _add_event_handler_route(app, reh, all_dynamic_args or None))
            is not None
        ]

        def openapi_response(request: Request) -> Response:
            schema = schemas.get_schema(routes=routes)
            return OpenAPIResponse(schema)

        app._api.add_route(
            "/_reflex/events/openapi.yaml",
            openapi_response,
            methods=["GET"],
            include_in_schema=False,
        )


Plugin = EventHandlerAPIPlugin
