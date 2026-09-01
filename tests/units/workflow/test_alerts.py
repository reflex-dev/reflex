"""The alert sink: page-worthy transitions become webhook posts, off the kernel's path.

Driven by real runs through the harness where the condition is a run's
outcome, by the observer protocol directly where it is a mapping, and by a
real ASGI receiver behind httpx for the HTTP poster itself.
"""

import asyncio
import json

import httpx
import pytest
from reflex_base.workflow import Retry, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.alerts import (
    ALERT_KINDS,
    ALERT_KINDS_ENV,
    ALERT_WEBHOOK_ENV,
    AlertObserver,
)
from reflex.workflow.health import describe_connections
from reflex.workflow.kernel import CompositeObserver, MetricsObserver, WorkflowObserver
from reflex.workflow.records import HistoryEventType, RunStatus
from reflex.workflow.runtime import WorkflowRuntime
from reflex.workflow.store import MemoryRunStore
from reflex.workflow.testing import WorkflowTestHarness

HOOK = "http://alerts.test/hook"


class Charge(rx.State):
    """A step that fails for good, and one that hands the run to a person."""

    __workflow__ = WorkflowConfig(id="alerts.charge")

    @rx.event(
        durable=True, trigger=manual(), effect="none", retry=Retry(max_attempts=1)
    )
    def doomed(self):
        """Fail permanently.

        Raises:
            ValueError: Always.
        """
        msg = "card declined"
        raise ValueError(msg)

    @rx.event(durable=True, trigger=manual(), effect="none")
    def review(self):
        """Ask for a person.

        Returns:
            The attention request.
        """
        return rx.needs_attention("manual review")


class Orders(rx.State):
    """One step, one channel a late delivery can miss."""

    __workflow__ = WorkflowConfig(id="alerts.orders")
    shipped = rx.Signal()

    @rx.event(durable=True, trigger=manual(), effect="none")
    def place(self):
        """Complete at once."""


def _capture():
    """Build a capturing sender.

    Returns:
        The list alerts land in, and the sender.
    """
    sent: list[dict] = []

    async def send(payload: dict) -> None:  # noqa: RUF029
        sent.append(payload)

    return sent, send


async def test_a_failed_run_pages_once(forked_registration_context):
    """The run's failure is the alert; nothing else about it is.

    Args:
        forked_registration_context: Isolates workflow registration.
    """
    sent, send = _capture()
    observer = AlertObserver(HOOK, send=send)
    async with WorkflowTestHarness(Charge, observer=observer) as harness:
        run_id = (await harness.start(Charge.doomed())).run_id
        assert run_id is not None
        assert await observer.flush()

    assert [alert["kind"] for alert in sent] == ["run_failed"]
    alert = sent[0]
    assert alert["workflow_id"] == "alerts.charge"
    assert alert["run_id"] == run_id
    assert alert["text"].startswith(f"alerts.charge run {run_id[:8]} failed")
    assert "card declined" in alert["text"]
    assert alert["error"]["type"] == "ValueError"
    assert observer.sent == 1


async def test_a_run_needing_attention_pages_with_its_reason(
    forked_registration_context,
):
    """The reason the author gave is what the operator reads.

    Args:
        forked_registration_context: Isolates workflow registration.
    """
    sent, send = _capture()
    observer = AlertObserver(HOOK, send=send)
    async with WorkflowTestHarness(Charge, observer=observer) as harness:
        await harness.start(Charge.review())
        assert await observer.flush()

    assert [alert["kind"] for alert in sent] == ["run_needs_attention"]
    assert sent[0]["text"].endswith("needs attention: manual review")
    assert sent[0]["reason"] == "manual review"


async def test_a_delivery_to_a_finished_run_pages_as_a_dead_letter(
    forked_registration_context,
):
    """A dead letter has no run history to appear in; the alert is its only trace.

    Args:
        forked_registration_context: Isolates workflow registration.
    """
    sent, send = _capture()
    observer = AlertObserver(HOOK, send=send)
    metrics = MetricsObserver()
    async with WorkflowTestHarness(
        Orders, observer=CompositeObserver(observer, metrics)
    ) as harness:
        run_id = (await harness.start(Orders.place(), request_key="ord-1")).run_id
        assert run_id is not None
        snapshot = await harness.get_run(run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        disposition = await harness.kernel.ingest_channel(
            "alerts.orders", "shipped", "ord-1", "evt-1", {"carrier": "ups"}
        )
        assert disposition == "dead_letter"
        assert await observer.flush()

    assert [alert["kind"] for alert in sent] == ["dead_letter"]
    alert = sent[0]
    assert alert["workflow_id"] == "alerts.orders"
    assert alert["channel"] == "shipped"
    assert alert["count"] == 1
    assert alert["reason"] == "undeliverable"
    assert alert["text"] == (
        "1 delivery for alerts.orders.shipped became dead letters (undeliverable)"
    )
    assert metrics.totals["deliveries_dead_lettered"] == 1
    assert metrics.by_workflow["alerts.orders"]["deliveries_dead_lettered"] == 1


def test_every_run_outcome_maps_to_its_kind_and_nothing_else_alerts():
    """Completed and cancelled runs are not pages."""
    sent, send = _capture()
    observer = AlertObserver(HOOK, send=send)
    for event_type in HistoryEventType:
        observer.on_event(event_type, "run-1", "wf", {"reason": "because"})
    kinds = [alert["kind"] for alert in observer._queue]  # pyright: ignore[reportPrivateUsage]
    assert kinds == ["run_failed", "run_timed_out", "run_needs_attention"]
    assert not sent


def test_kinds_narrow_what_is_sent_and_unknown_kinds_are_refused():
    """A typo in the filter must not silently disable paging."""
    _, send = _capture()
    observer = AlertObserver(HOOK, kinds=["dead_letter"], send=send)
    observer.on_event(HistoryEventType.RUN_FAILED, "run-1", "wf", {})
    observer.on_schedule_skip("nightly", 3)
    observer.on_dead_letter(None, None, 2, "unclaimed")
    queued = list(observer._queue)  # pyright: ignore[reportPrivateUsage]
    assert [alert["kind"] for alert in queued] == ["dead_letter"]
    assert queued[0]["text"] == (
        "2 deliveries went unclaimed past the TTL and became dead letters"
    )

    with pytest.raises(ValueError, match="run_fialed"):
        AlertObserver(HOOK, kinds=["run_fialed"])


async def test_a_flaky_sink_is_retried_and_a_dead_one_is_given_up_on():
    """Retries hide a blip; a dead sink costs the alert, not the process."""
    calls = 0

    async def flaky(payload: dict) -> None:  # noqa: RUF029
        nonlocal calls
        calls += 1
        if calls < 3:
            msg = "503"
            raise ConnectionError(msg)

    observer = AlertObserver(HOOK, send=flaky, retry_delays=(0, 0))
    observer.on_schedule_skip("nightly", 1)
    assert await observer.flush()
    assert (calls, observer.sent, observer.failed) == (3, 1, 0)

    async def dead(payload: dict) -> None:  # noqa: RUF029
        msg = "refused"
        raise ConnectionError(msg)

    observer = AlertObserver(HOOK, send=dead, retry_delays=(0,))
    observer.on_schedule_skip("nightly", 1)
    observer.on_schedule_skip("weekly", 1)
    assert await observer.flush()
    assert (observer.sent, observer.failed) == (0, 2)
    await observer.aclose()


async def test_a_stuck_sink_drops_the_oldest_alerts_and_never_blocks():
    """The queue is bounded, and enqueueing is synchronous and instant."""

    async def stuck(payload: dict) -> None:
        await asyncio.Event().wait()

    observer = AlertObserver(HOOK, send=stuck, max_queued=3)
    for key in ("a", "b", "c", "d", "e"):
        observer.on_schedule_skip(key, 1)
    assert observer.dropped == 2
    assert [alert["schedule_key"] for alert in observer._queue] == ["c", "d", "e"]  # pyright: ignore[reportPrivateUsage]
    assert not await observer.flush(within=0.05)
    await observer.aclose(within=0.05)
    assert observer.dropped == 2


async def test_the_http_poster_posts_json_a_slack_hook_accepts():
    """The real transport, against a real ASGI receiver: body shape and retry on 5xx."""
    received: list[dict] = []

    async def receiver(scope, receive, send):
        body = b""
        while True:
            message = await receive()
            body += message.get("body", b"")
            if not message.get("more_body"):
                break
        received.append(json.loads(body))
        status = 500 if len(received) == 1 else 200
        await send({"type": "http.response.start", "status": status, "headers": []})
        await send({"type": "http.response.body", "body": b"{}"})

    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=receiver))
    observer = AlertObserver(HOOK, client=client, retry_delays=(0,), clock=lambda: 1.5)
    observer.on_schedule_skip("nightly", 2)
    assert await observer.flush()
    await observer.aclose()

    assert len(received) == 2
    assert received[-1] == {
        "kind": "schedule_skipped",
        "at": 1.5,
        "text": "schedule nightly dropped 2 occurrences",
        "schedule_key": "nightly",
        "count": 2,
    }
    assert observer.sent == 1


def test_the_environment_configures_the_sink(monkeypatch):
    """No URL means no sink; a URL means every kind unless narrowed.

    Args:
        monkeypatch: Environment control.
    """
    monkeypatch.delenv(ALERT_WEBHOOK_ENV, raising=False)
    assert AlertObserver.from_env() is None

    monkeypatch.setenv(ALERT_WEBHOOK_ENV, f" {HOOK} ")
    observer = AlertObserver.from_env()
    assert observer is not None
    assert (observer.url, observer.kinds) == (HOOK, ALERT_KINDS)

    monkeypatch.setenv(ALERT_KINDS_ENV, "run_failed, dead_letter,")
    observer = AlertObserver.from_env()
    assert observer is not None
    assert observer.kinds == {"run_failed", "dead_letter"}


async def test_every_runtime_installs_the_configured_sink_and_closes_it(monkeypatch):
    """Worker, service, and app all get alerts from the environment alone.

    Args:
        monkeypatch: Environment control.
    """
    monkeypatch.delenv(ALERT_WEBHOOK_ENV, raising=False)
    runtime = WorkflowRuntime(MemoryRunStore())
    assert runtime.alerts is None
    assert runtime._observer is runtime.metrics  # pyright: ignore[reportPrivateUsage]

    monkeypatch.setenv(ALERT_WEBHOOK_ENV, HOOK)
    runtime = WorkflowRuntime(MemoryRunStore())
    assert isinstance(runtime.alerts, AlertObserver)
    installed = runtime._observer  # pyright: ignore[reportPrivateUsage]
    assert isinstance(installed, CompositeObserver)
    assert installed.observers == (runtime.metrics, runtime.alerts)

    closed = False

    async def sender(payload: dict) -> None:  # noqa: RUF029
        nonlocal closed
        closed = True

    runtime.alerts._send = sender  # pyright: ignore[reportPrivateUsage]
    await runtime.startup(start_worker=False)
    runtime.alerts.on_schedule_skip("nightly", 1)
    await runtime.shutdown()
    assert closed


def test_dead_letters_fan_out_and_the_base_observer_ignores_them():
    """Composite fans out; a custom observer that predates the hook keeps working."""
    seen: list[tuple] = []

    class Spy(WorkflowObserver):
        def on_dead_letter(self, workflow_id, channel, count, reason) -> None:
            seen.append((workflow_id, channel, count, reason))

    metrics = MetricsObserver()
    CompositeObserver(metrics, Spy()).on_dead_letter(
        "orders", "shipped", 2, "undeliverable"
    )
    CompositeObserver(metrics).on_dead_letter(None, None, 3, "unclaimed")
    assert seen == [("orders", "shipped", 2, "undeliverable")]
    assert metrics.totals["deliveries_dead_lettered"] == 5
    assert metrics.by_workflow["orders"]["deliveries_dead_lettered"] == 2
    assert (
        WorkflowObserver().on_dead_letter("orders", "shipped", 1, "unclaimed") is None
    )


def test_doctor_reports_whether_a_sink_is_configured(monkeypatch):
    """An unconfigured sink is a note at deploy time, never a problem.

    Args:
        monkeypatch: Environment control.
    """
    monkeypatch.delenv(ALERT_WEBHOOK_ENV, raising=False)
    (row,) = [row for row in describe_connections(()) if row["kind"] == "sink"]
    assert (row["name"], row["present"], row["severity"]) == (
        ALERT_WEBHOOK_ENV,
        False,
        "note",
    )
    assert "dead letters" in row["message"]

    monkeypatch.setenv(ALERT_WEBHOOK_ENV, HOOK)
    (row,) = [row for row in describe_connections(()) if row["kind"] == "sink"]
    assert (row["present"], row["severity"]) == (True, "ok")


async def test_the_harness_never_installs_a_sink(
    monkeypatch, forked_registration_context
):
    """A test that fails a run on purpose must not page the on-call.

    Args:
        monkeypatch: Environment control.
        forked_registration_context: Isolates workflow registration.
    """
    monkeypatch.setenv(ALERT_WEBHOOK_ENV, HOOK)
    async with WorkflowTestHarness(Charge) as harness:
        assert harness._runtime.alerts is None  # pyright: ignore[reportPrivateUsage]
        await harness.start(Charge.doomed())
