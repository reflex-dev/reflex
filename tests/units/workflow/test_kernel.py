"""Behavioral tests for the workflow kernel via the test harness."""

import asyncio

import pytest
from pydantic import BaseModel
from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import (
    Retry,
    TransientWorkflowError,
    WorkflowConfig,
    after,
    complete,
    fail,
    manual,
    needs_attention,
    webhook,
)

import reflex as rx
from reflex.workflow.records import HistoryEventType, RunStatus, StepStatus
from reflex.workflow.store import SqliteRunStore
from reflex.workflow.testing import WorkflowTestHarness


class Payment(BaseModel):
    """Typed payload for kernel tests."""

    id: str
    amount: int


async def test_chain_with_typed_payload(forked_registration_context):
    class ChainFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.chain")
        payment_id: str = ""
        amount: int = 0
        status: str = "pending"

        @rx.event(durable=True, trigger=manual(), effect="none")
        def receive(self, payment: Payment):
            self.payment_id = payment.id
            self.amount = payment.amount
            return ChainFlow.finish

        @rx.event(durable=True, effect="none")
        def finish(self):
            self.status = "done"

    async with WorkflowTestHarness(ChainFlow) as harness:
        result = await harness.start(ChainFlow.receive(Payment(id="pay_1", amount=42)))
        assert result.run_id is not None
        assert result.disposition == "started"
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {
            "payment_id": "pay_1",
            "amount": 42,
            "status": "done",
        }
        assert snapshot.state_version == 2
        assert [step.status for step in snapshot.steps] == [
            StepStatus.SUCCEEDED,
            StepStatus.SUCCEEDED,
        ]
        history = await harness.kernel.store.get_history(result.run_id)
        assert [event.type for event in history] == [
            HistoryEventType.RUN_ADMITTED,
            HistoryEventType.STEP_SCHEDULED,
            HistoryEventType.ATTEMPT_STARTED,
            HistoryEventType.ATTEMPT_SUCCEEDED,
            HistoryEventType.STEP_SCHEDULED,
            HistoryEventType.ATTEMPT_STARTED,
            HistoryEventType.ATTEMPT_SUCCEEDED,
            HistoryEventType.RUN_COMPLETED,
        ]


async def test_dedupe_by_request_key(forked_registration_context):
    class DedupeFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.dedupe")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

    async with WorkflowTestHarness(DedupeFlow) as harness:
        first = await harness.start(DedupeFlow.go(), request_key="sub-1")
        second = await harness.start(DedupeFlow.go(), request_key="sub-1")
        assert first.disposition == "started"
        assert second.disposition == "deduplicated"
        assert second.run_id == first.run_id


async def test_retry_backoff_and_discarded_patches(forked_registration_context):
    calls = []

    class RetryFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.retry")
        status: str = "pending"

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="idempotent_write",
            retry=Retry(max_attempts=3, initial_delay="5s", jitter="none"),
        )
        def flaky(self):
            calls.append(harnessed.now)
            self.status = "attempted"
            if len(calls) < 3:
                msg = "provider 503"
                raise TransientWorkflowError(msg)
            self.status = "ok"

    async with WorkflowTestHarness(RetryFlow) as harnessed:
        result = await harnessed.start(RetryFlow.flaky())
        assert result.run_id is not None
        snapshot = await harnessed.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.RETRYING
        # The failed attempt's state patch is discarded.
        assert snapshot.state == {"status": "pending"}
        await harnessed.advance("5s")
        await harnessed.advance("10s")
        snapshot = await harnessed.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"status": "ok"}
        assert snapshot.steps[0].attempts == 2
        # Exponential backoff: failures at t0, t0+5s, success at t0+15s.
        assert calls[1] - calls[0] == pytest.approx(5.0)
        assert calls[2] - calls[1] == pytest.approx(10.0)


async def test_retry_exhaustion_runs_failure_hook(forked_registration_context):
    class HookFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.hook")
        status: str = "pending"

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="read",
            retry=Retry(max_attempts=2, initial_delay="1s", jitter="none"),
            on_failure="report",
        )
        def flaky(self):
            msg = "still down"
            raise TransientWorkflowError(msg)

        @rx.event(durable=True, effect="none")
        def report(self):
            self.status = "reported"

    async with WorkflowTestHarness(HookFlow) as harness:
        result = await harness.start(HookFlow.flaky())
        assert result.run_id is not None
        await harness.advance("1s")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        # The failing step is final; the hook ran on a fresh slot afterwards.
        assert snapshot.steps[0].status is StepStatus.FAILED
        assert snapshot.steps[0].attempts == 2
        assert snapshot.steps[1].handler_id == "report"
        assert snapshot.steps[1].origin == "hook"
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"status": "reported"}


async def test_retry_exhaustion_without_hook_fails_run(forked_registration_context):
    class NoHookFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.nohook")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="read",
            retry=Retry(max_attempts=1),
        )
        def flaky(self):
            msg = "down"
            raise TransientWorkflowError(msg)

    async with WorkflowTestHarness(NoHookFlow) as harness:
        result = await harness.start(NoHookFlow.flaky())
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED
        assert snapshot.error is not None
        assert snapshot.error["type"] == "TransientWorkflowError"


async def test_do_not_retry_on_fails_fast(forked_registration_context):
    """A failure named in do_not_retry_on fails the run on the first attempt."""
    calls = []

    class DefectFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.defect")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="none",
            retry=Retry(max_attempts=3, do_not_retry_on=(ValueError,)),
        )
        def broken(self):
            calls.append(1)
            msg = "bug"
            raise ValueError(msg)

    async with WorkflowTestHarness(DefectFlow) as harness:
        result = await harness.start(DefectFlow.broken())
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED
        assert len(calls) == 1


async def test_ordinary_failures_retry_by_default(forked_registration_context):
    """A flaky dependency is survived without declaring a retry policy."""
    calls = []

    class FlakyFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.flaky_default")
        status: str = "pending"

        @rx.event(durable=True, trigger=manual(), effect="read")
        def fetch(self):
            calls.append(1)
            if len(calls) < 3:
                msg = "connection reset"
                raise ConnectionError(msg)
            self.status = "fetched"

    async with WorkflowTestHarness(FlakyFlow) as harness:
        result = await harness.start(FlakyFlow.fetch())
        assert result.run_id is not None
        await harness.advance("1s")
        await harness.advance("2s")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"status": "fetched"}
        assert len(calls) == 3


async def test_timeout_consumes_attempts_and_runs_timeout_hook(
    forked_registration_context,
):
    class TimeoutFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.timeout")
        status: str = "pending"

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="read",
            timeout="50ms",
            retry=Retry(max_attempts=2, initial_delay="1s", jitter="none"),
            on_timeout="expired",
        )
        async def slow(self):
            await asyncio.sleep(5)

        @rx.event(durable=True, effect="none")
        def expired(self):
            self.status = "expired"

    async with WorkflowTestHarness(TimeoutFlow) as harness:
        result = await harness.start(TimeoutFlow.slow())
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.RETRYING
        await harness.advance("1s")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.steps[0].status is StepStatus.TIMED_OUT
        assert snapshot.steps[0].attempts == 2
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"status": "expired"}


async def test_non_idempotent_failure_needs_attention(forked_registration_context):
    class UnsafeFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.unsafe")

        @rx.event(durable=True, trigger=manual(), effect="non_idempotent_write")
        def send_wire(self):
            msg = "socket dropped mid-request"
            raise ConnectionError(msg)

    async with WorkflowTestHarness(UnsafeFlow) as harness:
        result = await harness.start(UnsafeFlow.send_wire())
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.NEEDS_ATTENTION
        assert snapshot.steps[0].status is StepStatus.NEEDS_ATTENTION
        assert snapshot.error is not None
        assert "non-idempotent" in snapshot.error["reason"]
        # Suspension is not terminal and nothing further executes.
        await harness.advance("1h")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.NEEDS_ATTENTION


async def test_durable_delay(forked_registration_context):
    class DelayFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.delay")
        status: str = "pending"

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            self.status = "waiting"
            return after("2d", DelayFlow.follow_up)

        @rx.event(durable=True, effect="none")
        def follow_up(self):
            self.status = "done"

    async with WorkflowTestHarness(DelayFlow) as harness:
        result = await harness.start(DelayFlow.begin())
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING
        assert snapshot.state == {"status": "waiting"}
        await harness.advance("1d")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING
        await harness.advance("1d")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"status": "done"}


async def test_sequential_list_chain(forked_registration_context):
    order = []

    class ListFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.list")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            return [ListFlow.first, ListFlow.second]

        @rx.event(durable=True, effect="none")
        def first(self):
            order.append("first")

        @rx.event(durable=True, effect="none")
        def second(self):
            order.append("second")

    async with WorkflowTestHarness(ListFlow) as harness:
        result = await harness.start(ListFlow.begin())
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert order == ["first", "second"]


async def test_complete_tombstones_remaining_work(forked_registration_context):
    class CompleteFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.complete")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            return [CompleteFlow.decide, CompleteFlow.never_runs]

        @rx.event(durable=True, effect="none")
        def decide(self):
            return complete(result={"answer": 42})

        @rx.event(durable=True, effect="none")
        def never_runs(self):
            msg = "unreachable"
            raise AssertionError(msg)

    async with WorkflowTestHarness(CompleteFlow) as harness:
        result = await harness.start(CompleteFlow.begin())
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {"answer": 42}
        assert snapshot.steps[2].status is StepStatus.CANCELLED


async def test_fail_and_needs_attention_controls(forked_registration_context):
    class ControlFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.control")
        mode: str = ""

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self, mode: str):
            self.mode = mode
            if mode == "fail":
                return fail("bad_invoice", details={"code": 402})
            return needs_attention("manual_review")

    async with WorkflowTestHarness(ControlFlow) as harness:
        failed = await harness.start(ControlFlow.begin("fail"))
        assert failed.run_id is not None
        snapshot = await harness.get_run(failed.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED
        assert snapshot.error == {"reason": "bad_invoice", "details": {"code": 402}}
        # The handler itself succeeded and its state patch was committed.
        assert snapshot.state == {"mode": "fail"}
        assert snapshot.steps[0].status is StepStatus.SUCCEEDED

        suspended = await harness.start(ControlFlow.begin("review"))
        assert suspended.run_id is not None
        snapshot = await harness.get_run(suspended.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.NEEDS_ATTENTION
        assert snapshot.state == {"mode": "review"}


async def test_cancel_while_waiting(forked_registration_context):
    class CancelFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.cancel")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            return after("1d", CancelFlow.later)

        @rx.event(durable=True, effect="none")
        def later(self):
            pass

    async with WorkflowTestHarness(CancelFlow) as harness:
        result = await harness.start(CancelFlow.begin())
        assert result.run_id is not None
        assert await harness.cancel(result.run_id)
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.CANCELLED
        assert snapshot.steps[1].status is StepStatus.CANCELLED
        # Cancelling a terminal run reports False.
        assert not await harness.cancel(result.run_id)


async def test_cancel_in_flight_attempt(forked_registration_context):
    started = asyncio.Event()
    release = asyncio.Event()

    class InflightFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.inflight")

        @rx.event(durable=True, trigger=manual(), effect="none")
        async def hang(self):
            started.set()
            await release.wait()

    async with WorkflowTestHarness(InflightFlow) as harness:
        result = await harness.kernel.start(InflightFlow.hang())
        assert result.run_id is not None
        pump = asyncio.create_task(harness.run_until_idle())
        await asyncio.wait_for(started.wait(), timeout=2)
        await harness.cancel(result.run_id)
        await asyncio.wait_for(pump, timeout=2)
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.CANCELLED
        assert snapshot.steps[0].status is StepStatus.CANCELLED
        history = await harness.kernel.store.get_history(result.run_id)
        assert HistoryEventType.ATTEMPT_CANCELLED in [event.type for event in history]


async def test_max_steps_bounds_chains(forked_registration_context):
    class LoopFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.loop", max_steps=3)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            return LoopFlow.again

        @rx.event(durable=True, effect="none")
        def again(self):
            return LoopFlow.again

    async with WorkflowTestHarness(LoopFlow) as harness:
        result = await harness.start(LoopFlow.begin())
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED
        assert snapshot.error is not None
        assert snapshot.error["reason"] == "max_steps_exceeded"


async def test_run_timeout_deadline(forked_registration_context):
    class DeadlineFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.deadline", run_timeout="1h")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            return after("2h", DeadlineFlow.too_late)

        @rx.event(durable=True, effect="none")
        def too_late(self):
            pass

    async with WorkflowTestHarness(DeadlineFlow) as harness:
        result = await harness.start(DeadlineFlow.begin())
        assert result.run_id is not None
        await harness.advance("2h")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.TIMED_OUT
        assert snapshot.steps[1].status is StepStatus.CANCELLED


async def test_unserializable_state_fails_run(forked_registration_context):
    class BadStateFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.badstate")
        data: dict = {}

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            self.data = {"handle": object()}

    async with WorkflowTestHarness(BadStateFlow) as harness:
        result = await harness.start(BadStateFlow.begin())
        assert result.run_id is not None
        # Unserializable state is not transient, but nothing can tell the
        # difference at runtime, so it exhausts the default retries first.
        await harness.advance("1s")
        await harness.advance("2s")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED
        assert snapshot.error is not None
        assert snapshot.error["type"] == "WorkflowRuntimeError"


async def test_start_rejects_non_manual_roots(forked_registration_context):
    class StartRules(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.startrules")

        @rx.event(
            durable=True, trigger=webhook("stripe.payment_succeeded"), effect="none"
        )
        def on_webhook(self):
            pass

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

        @rx.event(durable=True, effect="none")
        def internal(self):
            pass

    async with WorkflowTestHarness(StartRules) as harness:
        with pytest.raises(WorkflowRuntimeError, match="manual"):
            await harness.start(StartRules.on_webhook())
        with pytest.raises(WorkflowRuntimeError, match="manual"):
            await harness.start(StartRules.internal())
        with pytest.raises(WorkflowRuntimeError, match="workflow"):
            await harness.start(object())


async def test_start_rejects_unregistered_class(forked_registration_context):
    class Registered(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.registered")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

    class Unregistered(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.unregistered")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            pass

    async with WorkflowTestHarness(Registered) as harness:
        with pytest.raises(WorkflowRuntimeError, match="add_workflow"):
            await harness.start(Unregistered.go())


async def test_sqlite_recovery_resumes_retry_schedule(
    forked_registration_context, tmp_path
):
    calls = []

    class DurableFlow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.durable")
        status: str = "pending"

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="idempotent_write",
            retry=Retry(max_attempts=3, initial_delay="5s", jitter="none"),
        )
        def sync(self):
            calls.append(1)
            if len(calls) < 2:
                msg = "down"
                raise TransientWorkflowError(msg)
            self.status = "done"

    db_path = tmp_path / "workflow.db"
    first_store = SqliteRunStore(db_path)
    async with WorkflowTestHarness(DurableFlow, store=first_store) as harness:
        result = await harness.start(DurableFlow.sync())
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.RETRYING
        resume_at = harness.now
    first_store.close()

    # A new process opens the same database and resumes the pending retry.
    second_store = SqliteRunStore(db_path)
    async with WorkflowTestHarness(
        DurableFlow, store=second_store, start_time=resume_at + 5
    ) as harness:
        await harness.run_until_idle()
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"status": "done"}
        assert snapshot.steps[0].attempts == 1
    second_store.close()


async def test_definition_digest_mismatch_suspends_run(
    forked_registration_context, tmp_path
):
    class PinnedV1(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.pinned")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            return after("1h", PinnedV1.finish)

        @rx.event(durable=True, effect="none")
        def finish(self):
            pass

    class PinnedV2(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.pinned")

        @rx.event(durable=True, trigger=manual(), effect="read", timeout="5s")
        def begin(self):
            return after("1h", PinnedV2.finish)

        @rx.event(durable=True, effect="read")
        def finish(self):
            pass

    db_path = tmp_path / "workflow.db"
    first_store = SqliteRunStore(db_path)
    async with WorkflowTestHarness(PinnedV1, store=first_store) as harness:
        result = await harness.start(PinnedV1.begin())
        assert result.run_id is not None
        resume_at = harness.now
    first_store.close()

    second_store = SqliteRunStore(db_path)
    async with WorkflowTestHarness(
        PinnedV2, store=second_store, start_time=resume_at + 3600
    ) as harness:
        await harness.run_until_idle()
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.NEEDS_ATTENTION
        assert snapshot.error == {"reason": "definition_digest_mismatch"}
    second_store.close()
