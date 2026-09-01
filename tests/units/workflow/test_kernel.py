"""Behavioral tests for the workflow kernel via the test harness."""

import asyncio
import contextlib

import pytest
from pydantic import BaseModel
from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import (
    Retry,
    Signal,
    TransientWorkflowError,
    WorkflowConfig,
    after,
    complete,
    fail,
    hmac_signature,
    manual,
    needs_attention,
    wait_for,
    webhook,
)

import reflex as rx
from reflex.workflow.definition import compile_workflow
from reflex.workflow.kernel import WorkflowKernel
from reflex.workflow.records import HistoryEventType, RunStatus, StepStatus
from reflex.workflow.store import MemoryRunStore, SqliteRunStore
from reflex.workflow.testing import WorkflowTestHarness


class _Clock:
    """A manually advanced epoch-seconds clock."""

    def __init__(self, now: float):
        """Start the clock.

        Args:
            now: The starting time in epoch seconds.
        """
        self.now = now

    def __call__(self) -> float:
        """Read the clock.

        Returns:
            The current time in epoch seconds.
        """
        return self.now


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
            durable=True,
            trigger=webhook(
                "stripe.payment_succeeded",
                verify=hmac_signature(secret_env="SECRET", header="X-Signature"),
            ),
            effect="none",
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
        # The production path is gated: a webhook-only root is not reachable
        # through the default (browser-facing) start.
        with pytest.raises(WorkflowRuntimeError, match="cannot be started here"):
            await harness.kernel.start(StartRules.on_webhook())
        # The harness itself is privileged: in a test, the author is the
        # provider, so any root can be started directly.
        result = await harness.start(StartRules.on_webhook())
        assert result.disposition == "started"
        with pytest.raises(WorkflowRuntimeError, match="cannot be started here"):
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


async def test_policy_changes_do_not_strand_in_flight_runs(
    forked_registration_context, tmp_path
):
    """Retuning a step's effect and timeout must not disturb a live run.

    Deploying new code is routine; only a step that can no longer be
    dispatched suspends. See tests/units/workflow/test_versioning.py for the
    incompatible cases.
    """

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
        async def begin(self):
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
        assert snapshot.status is RunStatus.COMPLETED
    second_store.close()


async def test_cancelling_a_task_inside_release_lease_sticks(
    forked_registration_context,
):
    """A cancellation landing during lease release must end the task.

    The release path cancels the renewer and awaits it; a CancelledError
    raised there can be the renewer's echo or the releasing task's own
    cancellation. Swallowing the latter leaves a task that consumed teardown's
    single cancel and keeps running -- the immortal task a hanging
    _cancel_all_tasks waits on forever.
    """

    class Flow(rx.State):
        __workflow__ = WorkflowConfig(id="lease.cancelrace")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            """Nothing."""

    kernel = WorkflowKernel([compile_workflow(Flow)], MemoryRunStore())
    result = await kernel.start(Flow.go)
    assert result.run_id is not None
    claim = await kernel.store.claim_next(kernel._clock())
    assert claim is not None

    lease = kernel._acquire_lease(claim)

    # A renewer that takes a moment to process its cancellation, so the
    # releasing task is reliably parked inside `await renewer` when its own
    # cancellation arrives.
    async def slow_to_die():
        """Take a beat to process cancellation, like a real renewal would.

        Raises:
            asyncio.CancelledError: Always, once cleanup finishes.
        """
        try:
            await asyncio.sleep(3600)
        except asyncio.CancelledError:
            await asyncio.sleep(0.2)
            raise

    assert lease.renewer is not None
    lease.renewer.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await lease.renewer
    lease.renewer = asyncio.ensure_future(slow_to_die())

    releasing = asyncio.ensure_future(kernel._release_lease(lease))
    await asyncio.sleep(0.05)  # parked inside `await renewer`
    releasing.cancel()  # teardown's one and only cancel
    with contextlib.suppress(asyncio.CancelledError, TimeoutError):
        await asyncio.wait_for(asyncio.shield(releasing), timeout=2)
    assert releasing.done(), "the release task outlived its cancellation"
    assert releasing.cancelled(), "the release task swallowed its own cancellation"


async def test_run_until_idle_drains_every_attempt_it_started(
    forked_registration_context,
):
    """One call processes the whole batch, not the first completion's worth.

    A round can start several attempts and return after the first finishes;
    a later round that finds nothing newly claimable must still wait for the
    attempts this pump started, or the caller gets a half-processed graph
    and the harness cancels the survivors on exit.
    """

    class Slow(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.slowbatch")

        @rx.event(durable=True, trigger=manual(), effect="none")
        async def start(self, n: int):
            """Take long enough to still be running next round.

            Args:
                n: Which of the batch this is.

            Returns:
                Completion.
            """
            await asyncio.sleep(0.05)
            return rx.complete(result=n)

    store = MemoryRunStore()
    definition = compile_workflow(Slow)
    kernel = WorkflowKernel([definition], store, max_concurrency=8)
    for n in range(8):
        await kernel.start(Slow.start(n))
    await kernel.run_until_idle()

    from reflex.workflow.records import RunQuery

    runs = await store.list_runs(RunQuery(limit=20))
    statuses = sorted(run.status.value for run in runs)
    assert statuses == ["COMPLETED"] * 8, (
        f"run_until_idle returned with live attempts: {statuses}"
    )


async def test_work_cannot_commit_after_its_deadline(forked_registration_context):
    """A run past its deadline has one outcome, and it is not COMPLETED.

    The handler starts before the deadline, outruns cooperative cancellation,
    and tries to commit after it. Without the fence the commit lands and the
    caller -- who may already have been told the run timed out -- sees a run
    that completed after its own deadline.
    """
    release = asyncio.Event()

    class Deadlined(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.deadline_fence", run_timeout="10s")

        @rx.event(durable=True, trigger=manual(), effect="none")
        async def start(self):
            """Block until the test has moved the clock past the deadline.

            Returns:
                Completion that must never land.
            """
            await release.wait()
            return rx.complete(result="beat the sweep")

    clock = _Clock(1_000_000.0)
    store = MemoryRunStore()
    definition = compile_workflow(Deadlined)
    kernel = WorkflowKernel([definition], store, clock=clock)
    started = await kernel.start(Deadlined.start())
    assert started.run_id is not None
    pump = asyncio.create_task(kernel.run_until_idle())
    await asyncio.sleep(0.05)

    # The deadline passes while the attempt is still running.
    clock.now += 60
    release.set()
    await asyncio.wait_for(pump, timeout=10)
    await kernel.run_until_idle()

    snapshot = await kernel.get_run(started.run_id)
    assert snapshot is not None
    assert snapshot.status is RunStatus.TIMED_OUT, (
        f"a past-deadline run completed anyway: {snapshot.status}"
    )
    assert snapshot.result != "beat the sweep"


async def test_a_delivery_to_a_past_deadline_run_is_refused(
    forked_registration_context,
):
    """The answer resolved must not describe a decision the sweep discards."""

    class Waits(rx.State):
        __workflow__ = WorkflowConfig(id="kernel.deadline_wait", run_timeout="10s")

        decided = Signal(dict)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            """Wait for a decision.

            Returns:
                The wait.
            """
            return wait_for(
                Waits.decided, then=Waits.done, timeout="1h", on_timeout=Waits.lapse
            )

        @rx.event(durable=True, effect="none")
        def done(self, decision: dict):
            """Record the decision.

            Args:
                decision: The delivered payload.

            Returns:
                Completion.
            """
            return rx.complete(result=decision)

        @rx.event(durable=True, effect="none")
        def lapse(self):
            """Nobody answered.

            Returns:
                Failure.
            """
            return rx.fail(reason="lapsed")

    clock = _Clock(1_000_000.0)
    store = MemoryRunStore()
    kernel = WorkflowKernel([compile_workflow(Waits)], store, clock=clock)
    started = await kernel.start(Waits.start())
    assert started.run_id is not None
    await kernel.run_until_idle()

    clock.now += 60  # past the run deadline, before the wait's own timeout
    disposition = await kernel.signal(started.run_id, Waits.decided({"ok": True}))
    assert disposition == "expired", (
        f"a doomed run's wait answered {disposition!r} instead of refusing"
    )
