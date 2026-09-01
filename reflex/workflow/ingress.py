"""HTTP ingress for workflows started by a provider webhook.

The endpoint is public but never anonymously trusted: it preserves the raw
request body, verifies the provider's signature over those exact bytes, decodes
and validates the payload, then durably admits the run *before* acknowledging
the provider. A provider that redelivers the same event reaches the same run
through the trigger's deduplication key rather than starting a second one.
"""

from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Any

from starlette.requests import Request
from starlette.responses import JSONResponse

from reflex.workflow.validation import canonical_payload, missing_args, mistyped_args

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine, Mapping

    from reflex_base.workflow import Signal, WebhookTrigger

    from reflex.workflow.definition import HandlerDefinition, WorkflowDefinition
    from reflex.workflow.runtime import WorkflowRuntime

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 1_048_576

WEBHOOK_ROUTE = "/_workflow/webhook/{topic:path}"


class WebhookRoute:
    """One webhook topic reachable over HTTP: a root to start or a channel
    to deliver into.

    Attributes:
        definition: The workflow definition owning the target.
        handler: The root handler started by this topic, for a root route.
        trigger: The webhook trigger declaring the topic and its verification.
        channel: The signal channel this topic delivers into, for a channel
            route.
    """

    __slots__ = ("channel", "definition", "handler", "trigger")

    def __init__(
        self,
        definition: WorkflowDefinition,
        handler: HandlerDefinition | None,
        trigger: WebhookTrigger,
        channel: Signal | None = None,
    ):
        """Initialize the route.

        Args:
            definition: The workflow definition owning the target.
            handler: The root handler started by this topic, or None.
            trigger: The webhook trigger declaring the topic.
            channel: The signal channel this topic delivers into, or None.
        """
        self.definition = definition
        self.handler = handler
        self.trigger = trigger
        self.channel = channel


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

    def claim(topic: str, route: WebhookRoute, target: str) -> None:
        """Claim a topic, refusing a second claimant.

        Args:
            topic: The provider topic.
            route: The route claiming it.
            target: Human name of the claimant, for the error.

        Raises:
            WorkflowDefinitionError: If the topic is already claimed.
        """
        existing = routes.get(topic)
        if existing is not None:
            held_by = (
                f"{existing.definition.workflow_id}.{existing.handler.id}"
                if existing.handler is not None
                else f"{existing.definition.workflow_id}."
                f"{existing.channel.name if existing.channel else '?'}"
            )
            msg = (
                f"Webhook topic {topic!r} is claimed by both {held_by} and "
                f"{target}; a topic must identify exactly one target."
            )
            raise WorkflowDefinitionError(msg)
        routes[topic] = route

    for definition in definitions:
        for handler_id in definition.roots:
            handler = definition.handlers[handler_id]
            trigger = handler.trigger
            if not isinstance(trigger, WebhookTrigger):
                continue
            claim(
                trigger.topic,
                WebhookRoute(definition, handler, trigger),
                f"{definition.workflow_id}.{handler.id}",
            )
        for channel in definition.channels.values():
            if channel.trigger is None:
                continue
            claim(
                channel.trigger.topic,
                WebhookRoute(definition, None, channel.trigger, channel),
                f"{definition.workflow_id}.{channel.name}",
            )
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
    return _extract_identity(trigger.dedupe_by, payload, headers)


def _extract_identity(
    source: str, payload: Any, headers: Mapping[str, str]
) -> str | None:
    """Extract one identity value from a payload field or a header.

    Args:
        source: A payload field path, or ``"header:Name"``.
        payload: The decoded request payload.
        headers: The request headers.

    Returns:
        The identity, or None when the declared source is absent.
    """
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

    One parameter can mean two things: "hand me the event object" or "hand
    me this one field". The declared type decides -- if the whole payload
    satisfies the parameter's hint it is passed whole, and otherwise a dict
    payload carrying the parameter's name is unpacked to that field. Before
    types were consulted, ``def on_paid(self, id: str)`` received the entire
    event dict as ``id`` and nothing ever said so.

    Args:
        handler: The root handler definition.
        payload: The decoded request payload.

    Returns:
        The keyword arguments to start the root with; absent object fields
        are omitted rather than filled with None, so the boundary's
        missing-argument check can see them.
    """
    if not handler.params:
        return {}
    if len(handler.params) == 1:
        name = handler.params[0]
        if (
            mistyped_args(handler, {name: payload})
            and isinstance(payload, dict)
            and name in payload
            and not mistyped_args(handler, {name: payload[name]})
        ):
            return {name: payload[name]}
        return {name: payload}
    return {name: payload[name] for name in handler.params if name in payload}


async def _ingest_channel(
    runtime: WorkflowRuntime,
    route: WebhookRoute,
    payload: Any,
    headers: Mapping[str, str],
) -> JSONResponse:
    """Route a verified channel delivery into the durable channel inbox.

    Args:
        runtime: The workflow runtime.
        route: The channel route the topic resolved to.
        payload: The canonical payload.
        headers: The request headers, for header-sourced identities.

    Returns:
        The acknowledgement. Every durable outcome is a 202: once the row is
        committed the provider must stop retrying, whether the payload
        landed, parked, deduplicated, or died visibly for an operator.
    """
    assert route.channel is not None
    trigger = route.trigger
    dedupe = _extract_identity(trigger.dedupe_by or "", payload, headers)
    if dedupe is None:
        return JSONResponse(
            {
                "error": (
                    f"delivery carries no {trigger.dedupe_by!r}, which this "
                    "channel deduplicates by"
                )
            },
            status_code=400,
        )
    correlation = _extract_identity(trigger.correlate_by or "", payload, headers)
    if correlation is None:
        # Without the business key there is no run to route to and no key to
        # park under; accepting it would create a dead letter for a sender
        # error a 400 would have fixed.
        return JSONResponse(
            {
                "error": (
                    f"delivery carries no {trigger.correlate_by!r}, which this "
                    "channel correlates by"
                )
            },
            status_code=400,
        )
    disposition = await runtime.kernel.ingest_channel(
        route.definition.workflow_id,
        route.channel.name,
        str(correlation),
        str(dedupe),
        payload,
    )
    return JSONResponse({"disposition": disposition}, status_code=202)


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
                logger.warning(f"Webhook verifier raised for topic {topic!r}.")
                verified = False
            if not verified:
                return JSONResponse({"error": "invalid signature"}, status_code=401)

        content_type = headers.get("content-type", "")
        if "application/x-www-form-urlencoded" in content_type:
            # GitHub's form mode wraps the JSON document in a form field:
            # payload=<urlencoded JSON>. The signature is over the raw form
            # body and was already checked against exactly those bytes.
            from urllib.parse import parse_qs

            form = parse_qs(body.decode("utf-8", errors="replace"))
            wrapped = form.get("payload", [None])[0]
            if wrapped is None:
                return JSONResponse(
                    {"error": "form body has no 'payload' field"}, status_code=400
                )
            source = wrapped
        else:
            source = body
        try:
            payload = json.loads(source) if source else {}
        except ValueError:
            return JSONResponse({"error": "payload is not JSON"}, status_code=400)

        model = route.trigger.model or (
            route.channel.model if route.channel is not None else None
        )
        if model is not None:
            from pydantic import ValidationError

            try:
                # The canonical form -- coercions applied, defaults filled --
                # is what goes onward. Validating and then passing the raw
                # payload threw the validation away.
                payload = canonical_payload(model, payload)
            except ValidationError:
                return JSONResponse(
                    {"error": "payload does not match the declared model"},
                    status_code=400,
                )

        if route.channel is not None:
            return await _ingest_channel(runtime, route, payload, headers)

        assert route.handler is not None
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
        absent = missing_args(route.handler, args)
        wrong = mistyped_args(route.handler, args)
        if absent or wrong:
            # Refused before any run exists. Admitting would produce a run
            # that suspends on its first step for a reason the provider is
            # never told; a 400 naming the arguments is retryable after the
            # sender fixes their payload, and creates nothing until then.
            faults = [
                *(f"missing required argument {name!r}" for name in absent),
                *wrong,
            ]
            return JSONResponse(
                {"error": f"payload does not fit the handler: {'; '.join(faults)}"},
                status_code=400,
            )
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
