"""What starts each workflow, and where each schedule stands.

One summary behind ``reflex workflows triggers``, ``GET /triggers``, and the
console's Triggers page, so the three surfaces cannot disagree about which
URL a provider posts to, whether it is verified, or when a cron next fires.
"""

from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Any

from reflex_base.workflow import ScheduleTrigger, WebhookTrigger

from reflex.workflow.cron import CronSchedule
from reflex.workflow.ingress import WEBHOOK_ROUTE, collect_webhook_routes

_TOPIC_PARAM = re.compile(r"\{topic(?::[^}]*)?\}")
"""The route's topic parameter, with or without its Starlette converter."""

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from reflex.workflow.definition import WorkflowDefinition


def _verifier_ready(trigger: WebhookTrigger) -> bool | None:
    """Whether a webhook's verifier has the secret it needs, if knowable.

    Args:
        trigger: The webhook trigger.

    Returns:
        True/False when the verifier names an environment variable, None
        when it cannot be inspected.
    """
    if trigger.verify is None:
        return None
    secret_env = getattr(trigger.verify, "secret_env", None)
    if secret_env is None:
        return None
    return bool(os.environ.get(secret_env))


def describe_triggers(
    definitions: tuple[WorkflowDefinition, ...],
    now: float,
    cursors: Mapping[str, float] | None = None,
    paused: frozenset[str] = frozenset(),
) -> list[dict[str, Any]]:
    """Summarize every trigger across a set of definitions.

    Args:
        definitions: The compiled workflows.
        now: Current time in epoch seconds, for the next occurrence.
        cursors: Durable schedule cursors keyed ``"{workflow_id}:{handler_id}"``,
            when the caller has the store to read them from.
        paused: Schedule keys an operator has paused.

    Returns:
        One row per trigger: webhooks (roots and channels), schedules, manual
        roots.
    """
    rows: list[dict[str, Any]] = []
    for topic, route in sorted(collect_webhook_routes(definitions).items()):
        rows.append({
            "kind": "webhook",
            "workflow": route.definition.workflow_id,
            "target": (
                route.handler.name
                if route.handler is not None
                else f"channel {route.channel.name if route.channel else '?'}"
            ),
            "detail": topic,
            "path": _TOPIC_PARAM.sub(topic, WEBHOOK_ROUTE),
            "verified": route.trigger.verify is not None,
            "secret_present": _verifier_ready(route.trigger),
            "dedupe_by": route.trigger.dedupe_by,
            "correlate_by": route.trigger.correlate_by,
        })
    for definition in definitions:
        for handler in definition.handlers.values():
            trigger = handler.trigger
            if isinstance(trigger, ScheduleTrigger):
                key = f"{definition.workflow_id}:{handler.id}"
                cursor = (cursors or {}).get(key)
                rows.append({
                    "kind": "schedule",
                    "workflow": definition.workflow_id,
                    "target": handler.name,
                    "detail": trigger.cron,
                    "key": key,
                    "paused": key in paused,
                    "next_fire": CronSchedule(trigger.cron).next_after(now),
                    "cursor": cursor,
                    "lag": None if cursor is None else max(0.0, now - cursor),
                })
            elif trigger is not None and not isinstance(trigger, WebhookTrigger):
                rows.append({
                    "kind": "manual",
                    "workflow": definition.workflow_id,
                    "target": handler.name,
                    "detail": "started from code or the API",
                })
    return rows


async def schedule_cursors(
    definitions: tuple[WorkflowDefinition, ...],
    read_cursor: Callable[[str], Any],
) -> dict[str, float]:
    """Read every schedule's durable cursor.

    Args:
        definitions: The compiled workflows.
        read_cursor: ``store.read_schedule_cursor``.

    Returns:
        Cursor per schedule key, for the schedules that have one.
    """
    cursors: dict[str, float] = {}
    for definition in definitions:
        for handler in definition.handlers.values():
            if isinstance(handler.trigger, ScheduleTrigger):
                key = f"{definition.workflow_id}:{handler.id}"
                stored = await read_cursor(key)
                if stored is not None:
                    cursors[key] = stored
    return cursors
