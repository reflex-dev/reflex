"""One trigger summary behind the CLI, the service, and the console."""

import datetime as dt

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
from reflex.workflow.definition import compile_workflow, discover_workflows
from reflex.workflow.triggers import describe_triggers, schedule_cursors

NOW = dt.datetime(2026, 3, 1, 12, 0, tzinfo=dt.timezone.utc).timestamp()


@pytest.fixture(autouse=True)
def harness_store():
    """Opt out of the shared store parameter; nothing here touches a store.

    Returns:
        The store kind this module nominally uses.
    """
    return "memory"


def _billing(monkeypatch):
    """Build a workflow with every trigger kind.

    Args:
        monkeypatch: Used to install the webhook secret.

    Returns:
        The compiled definition.
    """
    monkeypatch.setenv("TRIG_SECRET", "s3cret")
    monkeypatch.delenv("TRIG_MISSING", raising=False)

    class Billing(rx.State):
        __workflow__ = WorkflowConfig(id="triggers.billing")

        shipped = Signal(
            trigger=webhook(
                "carrier_shipped",
                dedupe_by="event_id",
                correlate_by="invoice_id",
                verify=hmac_signature(secret_env="TRIG_MISSING", header="X-Sig"),
            )
        )

        @rx.event(
            durable=True,
            effect="none",
            trigger=webhook(
                "invoice_paid",
                dedupe_by="id",
                verify=hmac_signature(secret_env="TRIG_SECRET", header="X-Sig"),
            ),
        )
        def on_paid(self, id: str):
            """Start from a provider event.

            Args:
                id: The invoice.
            """

        @rx.event(durable=True, effect="none", trigger=schedule("0 3 * * *"))
        def nightly(self):
            """Run nightly."""

        @rx.event(durable=True, effect="none", trigger=manual())
        def begin(self):
            """Start by hand."""

    return compile_workflow(Billing)


def test_every_trigger_kind_is_described(monkeypatch, forked_registration_context):
    """Webhook roots, channel webhooks, schedules, and manual roots all appear.

    Args:
        monkeypatch: Used to install the webhook secret.
        forked_registration_context: Isolated state registry.
    """
    definition = _billing(monkeypatch)
    rows = describe_triggers(
        (definition,), NOW, {"triggers.billing:nightly": NOW - 7200}
    )
    by_detail = {row["detail"]: row for row in rows}

    paid = by_detail["invoice_paid"]
    assert paid["kind"] == "webhook"
    assert paid["target"] == "on_paid"
    assert paid["path"] == "/_workflow/webhook/invoice_paid"
    assert paid["verified"] is True
    assert paid["secret_present"] is True

    shipped = by_detail["carrier_shipped"]
    assert shipped["target"] == "channel shipped"
    assert shipped["correlate_by"] == "invoice_id"
    assert shipped["secret_present"] is False, "the verifier's secret is not set"

    nightly = by_detail["0 3 * * *"]
    assert nightly["kind"] == "schedule"
    assert (
        nightly["next_fire"]
        == dt.datetime(2026, 3, 2, 3, 0, tzinfo=dt.timezone.utc).timestamp()
    )
    assert nightly["lag"] == pytest.approx(7200.0)

    manual_row = next(row for row in rows if row["kind"] == "manual")
    assert manual_row["target"] == "begin"


async def test_schedule_cursors_are_read_per_schedule(
    monkeypatch, forked_registration_context
):
    """Cursors are looked up by the kernel's key and absent ones are omitted.

    Args:
        monkeypatch: Used to install the webhook secret.
        forked_registration_context: Isolated state registry.
    """
    definition = _billing(monkeypatch)
    asked: list[str] = []

    async def read_cursor(key: str) -> float | None:  # noqa: RUF029
        """Answer only the nightly schedule.

        Args:
            key: The schedule key.

        Returns:
            A cursor for the nightly key.
        """
        asked.append(key)
        return NOW - 60 if key.endswith(":nightly") else None

    cursors = await schedule_cursors((definition,), read_cursor)
    assert asked == ["triggers.billing:nightly"]
    assert cursors == {"triggers.billing:nightly": NOW - 60}


def test_discover_workflows_finds_declaring_classes_only(forked_registration_context):
    """Inherited __workflow__ declarations are not re-registered.

    Args:
        forked_registration_context: Isolated state registry.
    """
    import types

    class Base(rx.State):
        __workflow__ = WorkflowConfig(id="triggers.base")

        @rx.event(durable=True, effect="none", trigger=manual())
        def begin(self):
            """Start."""

    class Child(Base):
        pass

    module = types.ModuleType("fake")
    module.Base = Base  # pyright: ignore[reportAttributeAccessIssue]
    module.Child = Child  # pyright: ignore[reportAttributeAccessIssue]
    module.other = 42  # pyright: ignore[reportAttributeAccessIssue]
    assert discover_workflows(module) == [Base]
