"""Connections and secrets a deployment depends on, and whether they are set.

One summary behind ``reflex workflows doctor``, ``GET /connections``, and the
console's Connections page. Each row is one thing whose absence is silent
in production -- a webhook secret that is unset, an approval key missing,
the API token that decides whether the HTTP surface exists -- with a
severity: ``problem`` when a declared feature cannot work, ``note`` when a
choice deserves a second look at deploy time.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any

from reflex_base.workflow import ScheduleTrigger, WebhookTrigger

from reflex.workflow.alerts import ALERT_WEBHOOK_ENV
from reflex.workflow.api import TOKEN_ENV
from reflex.workflow.approvals import SECRET_ENV

if TYPE_CHECKING:
    from reflex.workflow.definition import WorkflowDefinition


def describe_connections(
    definitions: tuple[WorkflowDefinition, ...],
) -> list[dict[str, Any]]:
    """Summarize every secret and connection the definitions rely on.

    Args:
        definitions: The compiled workflows.

    Returns:
        One row per dependency: ``kind``, ``name`` (an environment variable
        or a declared topic), ``present``, ``severity`` (``ok``, ``note``,
        ``problem``), ``used_by``, and a human ``message``.
    """
    rows: list[dict[str, Any]] = []
    seen_secrets: dict[str, list[str]] = {}
    for definition in definitions:
        for handler in definition.handlers.values():
            trigger = handler.trigger
            target = f"{definition.workflow_id}.{handler.name}"
            if isinstance(trigger, WebhookTrigger):
                _describe_webhook(rows, seen_secrets, trigger, target)
            elif isinstance(trigger, ScheduleTrigger):
                rows.append({
                    "kind": "schedule",
                    "name": trigger.cron,
                    "present": True,
                    "severity": "note",
                    "used_by": [target],
                    "message": f"{target} runs on '{trigger.cron}'; a process must be serving it.",
                })
        for channel in definition.channels.values():
            if channel.trigger is not None:
                _describe_webhook(
                    rows,
                    seen_secrets,
                    channel.trigger,
                    f"{definition.workflow_id}.{channel.name}",
                )
    for secret_env, users in seen_secrets.items():
        present = bool(os.environ.get(secret_env))
        rows.append({
            "kind": "secret",
            "name": secret_env,
            "present": present,
            "severity": "ok" if present else "problem",
            "used_by": users,
            "message": (
                f"{secret_env} is set."
                if present
                else f"{secret_env} is unset, so {', '.join(users)} will refuse "
                "every delivery."
            ),
        })
    approval_set = bool(os.environ.get(SECRET_ENV))
    rows.append({
        "kind": "secret",
        "name": SECRET_ENV,
        "present": approval_set,
        "severity": "ok" if approval_set else "note",
        "used_by": ["rx.approval_link()"],
        "message": (
            f"{SECRET_ENV} is set."
            if approval_set
            else f"{SECRET_ENV} is unset. Signals work without it; "
            "rx.approval_link() raises until it is set."
        ),
    })
    token_set = bool(os.environ.get(TOKEN_ENV)) or any(
        os.environ.get(f"{TOKEN_ENV}_{scope}")
        for scope in ("READ", "START", "SIGNAL", "OPERATE")
    )
    rows.append({
        "kind": "secret",
        "name": TOKEN_ENV,
        "present": token_set,
        "severity": "ok" if token_set else "note",
        "used_by": ["HTTP API"],
        "message": (
            "An API token is configured; the HTTP API is mounted."
            if token_set
            else f"{TOKEN_ENV} (or a scoped variant) is unset, so the HTTP API is "
            "not mounted. Runs start from Python only."
        ),
    })
    alert_url = os.environ.get(ALERT_WEBHOOK_ENV, "").strip()
    rows.append({
        "kind": "sink",
        "name": ALERT_WEBHOOK_ENV,
        "present": bool(alert_url),
        "severity": "ok" if alert_url else "note",
        "used_by": ["alerts"],
        "message": (
            "Alerts post to the configured webhook."
            if alert_url
            else f"{ALERT_WEBHOOK_ENV} is unset, so failed runs, runs needing "
            "attention, dropped schedule occurrences, and dead letters are "
            "visible only in the console and the store. Set it to a "
            "Slack-compatible incoming webhook URL to be paged."
        ),
    })
    return rows


def _describe_webhook(
    rows: list[dict[str, Any]],
    seen_secrets: dict[str, list[str]],
    trigger: WebhookTrigger,
    target: str,
) -> None:
    """Record what one webhook trigger depends on.

    Args:
        rows: The summary being built.
        seen_secrets: Verifier secret variables and who uses them.
        trigger: The webhook trigger.
        target: The root or channel it feeds, for messages.
    """
    if trigger.verify is None:
        rows.append({
            "kind": "webhook",
            "name": trigger.topic,
            "present": True,
            "severity": "note",
            "used_by": [target],
            "message": (
                f"{target} accepts unverified deliveries on topic "
                f"'{trigger.topic}' -- anyone who knows the URL can reach it. "
                f"Declared reason: {trigger.unverified_reason or 'none given'}."
            ),
        })
        return
    secret_env = getattr(trigger.verify, "secret_env", None)
    if secret_env:
        seen_secrets.setdefault(secret_env, []).append(target)


def problems(rows: list[dict[str, Any]]) -> list[str]:
    """The messages that mean a declared feature cannot work.

    Args:
        rows: A connection summary.

    Returns:
        Problem messages, in order.
    """
    return [row["message"] for row in rows if row["severity"] == "problem"]
