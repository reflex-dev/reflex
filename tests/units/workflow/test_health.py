"""Connections and secrets: one summary behind doctor, the service, the console."""

import pytest
from reflex_base.workflow import (
    Signal,
    WorkflowConfig,
    hmac_signature,
    manual,
    schedule,
    webhook,
)

import reflex as rx
from reflex.workflow.approvals import SECRET_ENV
from reflex.workflow.definition import compile_workflow
from reflex.workflow.health import describe_connections, problems


@pytest.fixture(autouse=True)
def harness_store():
    """Opt out of the shared store parameter; nothing here touches a store.

    Returns:
        The store kind this module nominally uses.
    """
    return "memory"


def _deployment(monkeypatch):
    """Build a workflow whose secrets are half configured.

    Args:
        monkeypatch: Used to shape the environment.

    Returns:
        The compiled definition.
    """
    monkeypatch.setenv("HEALTH_SET", "present")
    monkeypatch.delenv("HEALTH_MISSING", raising=False)
    monkeypatch.delenv(SECRET_ENV, raising=False)
    for var in (
        "REFLEX_WORKFLOW_API_TOKEN",
        "REFLEX_WORKFLOW_API_TOKEN_READ",
        "REFLEX_WORKFLOW_API_TOKEN_START",
        "REFLEX_WORKFLOW_API_TOKEN_SIGNAL",
        "REFLEX_WORKFLOW_API_TOKEN_OPERATE",
    ):
        monkeypatch.delenv(var, raising=False)

    class Deploy(rx.State):
        __workflow__ = WorkflowConfig(id="health.deploy")

        arrived = Signal(
            trigger=webhook(
                "arrived",
                dedupe_by="id",
                correlate_by="order",
                verify=hmac_signature(secret_env="HEALTH_MISSING", header="X-Sig"),
            )
        )

        @rx.event(
            durable=True,
            effect="none",
            trigger=webhook(
                "paid",
                dedupe_by="id",
                verify=hmac_signature(secret_env="HEALTH_SET", header="X-Sig"),
            ),
        )
        def on_paid(self, id: str):
            """Verified root.

            Args:
                id: The event.
            """

        @rx.event(
            durable=True,
            effect="none",
            trigger=webhook(
                "ping",
                allow_unverified=True,
                unverified_reason="public status pings",
            ),
        )
        def on_ping(self, event: dict):
            """Unverified root.

            Args:
                event: The payload.
            """

        @rx.event(durable=True, effect="none", trigger=schedule("*/5 * * * *"))
        def tick(self):
            """A schedule."""

        @rx.event(durable=True, effect="none", trigger=manual())
        def begin(self):
            """Manual root."""

    return compile_workflow(Deploy)


def test_secrets_are_reported_present_or_missing_with_their_users(
    monkeypatch, forked_registration_context
):
    """Each verifier secret is one row, naming who depends on it.

    Args:
        monkeypatch: Used to shape the environment.
        forked_registration_context: Isolated state registry.
    """
    rows = describe_connections((_deployment(monkeypatch),))
    by_name = {row["name"]: row for row in rows}

    assert by_name["HEALTH_SET"]["present"] is True
    assert by_name["HEALTH_SET"]["severity"] == "ok"
    assert by_name["HEALTH_SET"]["used_by"] == ["health.deploy.on_paid"]

    missing = by_name["HEALTH_MISSING"]
    assert missing["present"] is False
    assert missing["severity"] == "problem"
    assert missing["used_by"] == ["health.deploy.arrived"], "the channel webhook"
    assert "refuse every delivery" in missing["message"]

    assert by_name["ping"]["severity"] == "note"
    assert "public status pings" in by_name["ping"]["message"]
    assert by_name["*/5 * * * *"]["kind"] == "schedule"
    assert by_name[SECRET_ENV]["severity"] == "note"
    assert by_name["REFLEX_WORKFLOW_API_TOKEN"]["severity"] == "note"
    assert problems(rows) == [missing["message"]]


def test_a_scoped_token_counts_as_the_api_being_configured(
    monkeypatch, forked_registration_context
):
    """Any scope variable mounts the API; the summary must not call it absent.

    Args:
        monkeypatch: Used to shape the environment.
        forked_registration_context: Isolated state registry.
    """
    definition = _deployment(monkeypatch)
    monkeypatch.setenv("REFLEX_WORKFLOW_API_TOKEN_READ", "tok")
    token_row = next(
        row
        for row in describe_connections((definition,))
        if row["name"] == "REFLEX_WORKFLOW_API_TOKEN"
    )
    assert token_row["present"] is True
    assert token_row["severity"] == "ok"
