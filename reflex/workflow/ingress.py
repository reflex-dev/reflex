"""HTTP ingress for workflows started by a provider webhook.

The endpoint is public but never anonymously trusted: it preserves the raw
request body, verifies the provider's signature over those exact bytes, decodes
and validates the payload, then durably admits the run *before* acknowledging
the provider. A provider that redelivers the same event reaches the same run
through the trigger's deduplication key rather than starting a second one.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter, ValidationError
from reflex_base.utils import console
from starlette.requests import Request
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Mapping

    from reflex_base.workflow import WebhookTrigger

    from reflex.workflow.definition import HandlerDefinition, WorkflowDefinition
    from reflex.workflow.runtime import WorkflowRuntime

MAX_BODY_BYTES = 1_048_576

WEBHOOK_ROUTE = "/_workflow/webhook/{topic:path}"


class WebhookRoute:
    """One workflow root reachable over HTTP.

    Attributes:
        definition: The workflow definition owning the root.
        handler: The root handler started by this topic.
        trigger: The webhook trigger declaring the topic and its verification.
    """

    __slots__ = ("definition", "handler", "trigger")

    def __init__(
        self,
        definition: WorkflowDefinition,
        handler: HandlerDefinition,
        trigger: WebhookTrigger,
    ):
        """Initialize the route.

        Args:
            definition: The workflow definition owning the root.
            handler: The root handler started by this topic.
            trigger: The webhook trigger declaring the topic.
        """
        self.definition = definition
        self.handler = handler
        self.trigger = trigger


def collect_webhook_routes(
    definitions: tuple[WorkflowDefinition, ...],
) -> dict[str, WebhookRoute]:
    """Index every webhook-triggered root by its topic.

    Args:
        definitions: The registered workflow definitions.

    Returns:
        Routes keyed by topic.

    Raises:
        WorkflowDefinitionError: If two roots claim the same topic, which would
            make delivery ambiguous.
    """
    from reflex_base.utils.exceptions import WorkflowDefinitionError
    from reflex_base.workflow import WebhookTrigger

    routes: dict[str, WebhookRoute] = {}
    for definition in definitions:
        for handler_id in definition.roots:
            handler = definition.handlers[handler_id]
            trigger = handler.trigger
            if not isinstance(trigger, WebhookTrigger):
                continue
            existing = routes.get(trigger.topic)
            if existing is not None:
                msg = (
                    f"Webhook topic {trigger.topic!r} is claimed by both "
                    f"{existing.definition.workflow_id}.{existing.handler.id} and "
                    f"{definition.workflow_id}.{handler.id}; a topic must "
                    "identify exactly one root."
                )
                raise WorkflowDefinitionError(msg)
            routes[trigger.topic] = WebhookRoute(definition, handler, trigger)
    return routes


def _dedupe_key(trigger: WebhookTrigger, payload: Any) -> str | None:
    """Extract the deduplication key a provider redelivery would repeat.

    Args:
        trigger: The webhook trigger declaring the key field.
        payload: The decoded request payload.

    Returns:
        The key as a string, or None when the trigger declares none or the
        field is absent.
    """
    if trigger.dedupe_by is None or not isinstance(payload, dict):
        return None
    value = payload.get(trigger.dedupe_by)
    return None if value is None else str(value)


def _root_args(handler: HandlerDefinition, payload: Any) -> dict[str, Any]:
    """Map a decoded payload onto the root handler's parameters.

    Args:
        handler: The root handler definition.
        payload: The decoded request payload.

    Returns:
        The keyword arguments to start the root with.
    """
    if not handler.params:
        return {}
    if len(handler.params) == 1:
        return {handler.params[0]: payload}
    if isinstance(payload, dict):
        return {name: payload.get(name) for name in handler.params}
    return {}


def webhook_endpoint(
    runtime: WorkflowRuntime,
) -> Callable[[Request], Coroutine[Any, Any, JSONResponse]]:
    """Build the ASGI endpoint that accepts provider webhooks.

    Args:
        runtime: The workflow runtime that owns the registered definitions.

    Returns:
        The Starlette endpoint.
    """

    async def endpoint(request: Request) -> JSONResponse:
        topic = request.path_params.get("topic", "")
        routes = collect_webhook_routes(runtime.definitions)
        route = routes.get(topic)
        if route is None:
            return JSONResponse({"error": "unknown topic"}, status_code=404)

        body = await request.body()
        if len(body) > MAX_BODY_BYTES:
            return JSONResponse({"error": "payload too large"}, status_code=413)

        headers: Mapping[str, str] = request.headers
        if route.trigger.verify is not None:
            try:
                verified = route.trigger.verify(body, headers)
            except Exception:
                console.warn(f"Webhook verifier raised for topic {topic!r}.")
                verified = False
            if not verified:
                return JSONResponse({"error": "invalid signature"}, status_code=401)

        try:
            payload = json.loads(body) if body else {}
        except ValueError:
            return JSONResponse({"error": "payload is not JSON"}, status_code=400)

        if route.trigger.model is not None:
            try:
                TypeAdapter(route.trigger.model).validate_python(payload)
            except ValidationError:
                return JSONResponse(
                    {"error": "payload does not match the declared model"},
                    status_code=400,
                )

        spec = getattr(route.definition.state_cls, route.handler.name)
        args = _root_args(route.handler, payload)
        result = await runtime.kernel.start(
            spec(**args) if args else spec,
            request_key=_dedupe_key(route.trigger, payload),
            trigger_kind="webhook",
        )
        return JSONResponse(
            {"disposition": result.disposition, "run_id": result.run_id},
            status_code=202,
        )

    return endpoint
