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


def _identity_value(
    trigger: WebhookTrigger, payload: Any, headers: Mapping[str, str]
) -> str | None:
    """Extract the provider's delivery identity for one request.

    ``dedupe_by`` names a payload field, or a header when written as
    ``"header:Name"`` -- GitHub's canonical identity, for example, is the
    ``X-GitHub-Delivery`` header and appears nowhere in the body.

    Args:
        trigger: The webhook trigger declaring the identity source.
        payload: The decoded request payload.
        headers: The request headers.

    Returns:
        The identity, or None when the declared source is absent.
    """
    assert trigger.dedupe_by is not None
    source = trigger.dedupe_by
    if source.startswith("header:"):
        name = source[len("header:") :]
        value = headers.get(name.lower()) or headers.get(name)
        return None if value is None else str(value)
    if not isinstance(payload, dict):
        return None
    value = payload.get(source)
    return None if value is None else str(value)


def _dedupe_key(
    handler: HandlerDefinition,
    trigger: WebhookTrigger,
    payload: Any,
    headers: Mapping[str, str],
) -> str | None:
    """Extract the deduplication key a provider redelivery would repeat.

    The key is namespaced by the handler it starts. A provider numbers its
    events per object, not per topic, so ``invoice_failed`` and
    ``invoice_paid`` for one invoice arrive carrying the same id: unqualified,
    the second is deduplicated against the first and the payment is silently
    dropped. Two deliveries are the same event only if they would start the
    same handler.

    Args:
        handler: The root handler this delivery starts.
        trigger: The webhook trigger declaring the key source.
        payload: The decoded request payload.
        headers: The request headers.

    Returns:
        The key as a string, or None when the trigger declares none or the
        source is absent.
    """
    if trigger.dedupe_by is None:
        return None
    value = _identity_value(trigger, payload, headers)
    return None if value is None else f"webhook:{handler.id}:{value}"


def _legacy_dedupe_keys(trigger: WebhookTrigger, payload: Any) -> tuple[str, ...]:
    """Spellings this delivery's key had in earlier releases.

    Keys used to be the provider's raw value, unqualified by the handler. A
    run admitted under one must still be found after the upgrade, or the
    provider's next redelivery of an event already handled starts it again.

    Args:
        trigger: The webhook trigger declaring the key field.
        payload: The decoded request payload.

    Returns:
        The older keys to match, newest spelling first.
    """
    if (
        trigger.dedupe_by is None
        or trigger.dedupe_by.startswith("header:")
        or not isinstance(payload, dict)
    ):
        # Header identities are new; no release ever wrote them unqualified.
        return ()
    value = payload.get(trigger.dedupe_by)
    return () if value is None else (str(value),)


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
    return {name: payload.get(name) for name in handler.params}


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
        if len(route.handler.params) > 1 and not isinstance(payload, dict):
            # Several named parameters can only be filled from an object.
            # Admitting the run anyway would drop the payload silently and
            # produce a run that fails on its first step for a reason the
            # provider is never told, so the boundary refuses it instead.
            return JSONResponse(
                {"error": "payload must be a JSON object"}, status_code=400
            )
        request_key = _dedupe_key(route.handler, route.trigger, payload, headers)
        if route.trigger.dedupe_by is not None and request_key is None:
            # A configured identity that cannot be extracted must not
            # silently disable deduplication: every redelivery of this event
            # would then execute again. The provider is told what is missing
            # so its operator sees a config problem, not a duplicate charge.
            return JSONResponse(
                {
                    "error": (
                        f"delivery carries no {route.trigger.dedupe_by!r}, "
                        "which this webhook deduplicates by"
                    )
                },
                status_code=400,
            )
        args = _root_args(route.handler, payload)
        result = await runtime.kernel.start(
            spec(**args) if args else spec,
            request_key=request_key,
            superseded_keys=_legacy_dedupe_keys(route.trigger, payload),
            trigger_kind="webhook",
        )
        return JSONResponse(
            {"disposition": result.disposition, "run_id": result.run_id},
            status_code=202,
        )

    return endpoint
