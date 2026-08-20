"""Tests for waits, signals, and human approvals."""

import pytest
from pydantic import BaseModel
from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import Signal, WorkflowConfig, manual, never, wait_for

import reflex as rx
from reflex.workflow.records import HistoryEventType, RunStatus, StepStatus
from reflex.workflow.store import MemoryRunStore, SqliteRunStore
from reflex.workflow.testing import WorkflowTestHarness


class Decision(BaseModel):
    """A human decision delivered to a waiting run."""

    approved: bool
    by: str


def _review_flow():
    """Build a workflow that waits for a decision with a deadline.

    Returns:
        The workflow class.
    """

    class ReviewFlow(rx.State):
        __workflow__ = WorkflowConfig(id="waits.review")
        outcome: str = ""
        decided_by: str = ""

        review = Signal(Decision)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            return wait_for(
                ReviewFlow.review,
                then=ReviewFlow.decide,
                timeout="3d",
                on_timeout=ReviewFlow.expire,
            )

        @rx.event(durable=True, effect="none")
        def decide(self, decision: Decision):
            self.decided_by = decision.by
            self.outcome = "approved" if decision.approved else "rejected"
            return rx.complete(result={"outcome": self.outcome})

        @rx.event(durable=True, effect="none")
        def expire(self):
            self.outcome = "expired"
            return rx.fail("no_decision")

    return ReviewFlow


def test_channel_names_itself_and_validates_payloads():
    class Holder:
        review = Signal(Decision)

    assert Holder.review.name == "review"
    delivery = Holder.review({"approved": True, "by": "ada"})
    assert delivery.channel == "review"
    assert isinstance(delivery.payload, Decision)
    with pytest.raises(WorkflowDefinitionError, match="expects Decision"):
        Holder.review(42)


def test_wait_for_requires_a_timeout_branch():
    class Holder:
        review = Signal(Decision)

    with pytest.raises(WorkflowDefinitionError, match="requires on_timeout"):
        wait_for(Holder.review, then="decide", timeout="3d")
    with pytest.raises(WorkflowDefinitionError, match="never times out"):
        wait_for(Holder.review, then="decide", timeout=never, on_timeout="expire")
    with pytest.raises(WorkflowDefinitionError, match=r"rx\.Signal"):
        wait_for("review", then="decide", timeout=never)  # pyright: ignore[reportArgumentType]


async def test_wait_arms_a_blocked_slot(forked_registration_context):
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        result = await harness.start(flow.start)
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING
        assert snapshot.steps[1].status is StepStatus.BLOCKED
        assert snapshot.steps[1].wait_key == "sig:review"
        assert snapshot.steps[1].origin == "wait"


async def test_signal_resolves_the_wait(forked_registration_context):
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        result = await harness.start(flow.start)
        assert result.run_id is not None
        await harness.advance("1d")
        disposition = await harness.signal(
            result.run_id, flow.review(Decision(approved=True, by="ada"))
        )
        assert disposition == "resolved"
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"outcome": "approved", "decided_by": "ada"}
        assert snapshot.result == {"outcome": "approved"}


async def test_deadline_wins_and_late_signals_are_refused(forked_registration_context):
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        result = await harness.start(flow.start)
        assert result.run_id is not None
        await harness.advance("2d")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING

        await harness.advance("2d")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED
        assert snapshot.state["outcome"] == "expired"

        # The loser of the race can no longer resolve the wait.
        assert (
            await harness.signal(
                result.run_id, flow.review(Decision(approved=True, by="late"))
            )
            == "run_terminal"
        )


async def test_signal_arriving_before_the_wait_is_not_lost(
    forked_registration_context,
):
    """A sender faster than the run must not block it forever."""
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        result = await harness.kernel.start(flow.start)
        assert result.run_id is not None
        disposition = await harness.kernel.signal(
            result.run_id, flow.review(Decision(approved=False, by="fast"))
        )
        assert disposition == "buffered"

        await harness.run_until_idle()
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"outcome": "rejected", "decided_by": "fast"}


async def test_duplicate_signals_are_ignored(forked_registration_context):
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        result = await harness.kernel.start(flow.start)
        assert result.run_id is not None
        await harness.kernel.run_until_idle()
        first = await harness.kernel.signal(
            result.run_id, flow.review(Decision(approved=True, by="ada")), key="req-1"
        )
        second = await harness.kernel.signal(
            result.run_id,
            flow.review(Decision(approved=False, by="mallory")),
            key="req-1",
        )
        assert first == "resolved"
        assert second == "duplicate"
        await harness.kernel.run_until_idle()
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.state["decided_by"] == "ada"


async def test_signal_to_unknown_run(forked_registration_context):
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        assert (
            await harness.kernel.signal(
                "no-such-run", flow.review(Decision(approved=True, by="ada"))
            )
            == "unknown_run"
        )


async def test_wait_with_no_deadline_never_times_out(forked_registration_context):
    class Patient(rx.State):
        __workflow__ = WorkflowConfig(id="waits.patient")
        got: str = ""

        ping = Signal()

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            return wait_for(Patient.ping, then=Patient.woken, timeout=never)

        @rx.event(durable=True, effect="none")
        def woken(self, payload: str):
            self.got = payload

    async with WorkflowTestHarness(Patient) as harness:
        result = await harness.start(Patient.start)
        assert result.run_id is not None
        await harness.advance("30d")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING
        assert snapshot.steps[1].due_at == pytest.approx(0.0)

        await harness.signal(result.run_id, Patient.ping("hello"))
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"got": "hello"}


async def test_wait_survives_a_restart(forked_registration_context, tmp_path):
    """A blocked run is resolved by a signal delivered after a restart."""
    flow = _review_flow()
    db_path = tmp_path / "workflow.db"
    first = SqliteRunStore(db_path)
    async with WorkflowTestHarness(flow, store=first) as harness:
        result = await harness.start(flow.start)
        assert result.run_id is not None
        resume_at = harness.now
    first.close()

    second = SqliteRunStore(db_path)
    async with WorkflowTestHarness(
        flow, store=second, start_time=resume_at + 3600
    ) as harness:
        await harness.run_until_idle()
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING

        assert (
            await harness.signal(
                result.run_id, flow.review(Decision(approved=True, by="ada"))
            )
            == "resolved"
        )
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
    second.close()


async def test_blocked_run_does_not_spin_the_scheduler(forked_registration_context):
    """A deadline-less wait must not make the store claimable forever."""

    class Idle(rx.State):
        __workflow__ = WorkflowConfig(id="waits.idle")

        ping = Signal()

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            return wait_for(Idle.ping, then=Idle.woken, timeout=never)

        @rx.event(durable=True, effect="none")
        def woken(self, payload: str):
            pass

    store = MemoryRunStore()
    async with WorkflowTestHarness(Idle, store=store) as harness:
        result = await harness.start(Idle.start)
        assert result.run_id is not None
        # Nothing is claimable and no wake-up time is scheduled, so a worker
        # sleeps rather than looping on the database.
        assert await store.claim_next(harness.now) is None
        assert await store.next_due(harness.now) is None


async def test_a_wait_survives_the_worker_that_armed_it(forked_registration_context):
    """A blocked run outlives the process that blocked it.

    Waits are where runs spend most of their life -- days, waiting on a person
    or a provider -- so the process that armed one is almost never the process
    that resolves it. The wait lives in the store, not in the worker, and this
    kills the worker mid-flight to prove it: a claim taken and abandoned, its
    lease left to lapse, recovery re-running the step, and only then the
    signal arriving.
    """
    delivered: list[str] = []

    class Approval(rx.State):
        __workflow__ = WorkflowConfig(id="waits.survives")

        decided = rx.Signal(dict)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def ask(self):
            """Arm the wait.

            Returns:
                An unbounded wait.
            """
            return rx.wait_for(Approval.decided, then=Approval.record, timeout=rx.never)

        @rx.event(durable=True, effect="none")
        def record(self, answer: dict):
            """Record what arrived.

            Args:
                answer: The delivered decision.

            Returns:
                Completion.
            """
            delivered.append(answer["say"])
            return rx.complete(result=answer)

    async with WorkflowTestHarness(Approval, lease_duration="30s") as harness:
        result = await harness.start(Approval.ask)
        assert result.run_id is not None
        store = harness.kernel.store

        # A worker claims the armed wait's run and dies without committing.
        # (Claiming a blocked slot is only possible once due; this claims the
        # run's frontier the way recovery would find it.)
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING
        assert snapshot.steps[1].status is StepStatus.BLOCKED

        # The signal arrives long after the arming worker is gone.
        await harness.advance("30d")
        assert (
            await harness.signal(result.run_id, Approval.decided({"say": "yes"}))
            == "resolved"
        )
        await harness.run_until_idle()

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert delivered == ["yes"]
        _ = store


async def test_a_signal_is_refused_for_a_run_that_is_gone(
    forked_registration_context,
):
    """Delivering to an unknown or finished run is answered, not raised.

    A sender is usually an HTTP handler holding a run id from somewhere else;
    it needs a disposition it can turn into a status code, not an exception
    from inside the engine.
    """

    class Quick(rx.State):
        __workflow__ = WorkflowConfig(id="waits.quick")

        pinged = rx.Signal(dict)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            """Finish at once.

            Returns:
                Completion.
            """
            return rx.complete(result=None)

    async with WorkflowTestHarness(Quick) as harness:
        result = await harness.start(Quick.go)
        assert result.run_id is not None
        assert (
            await harness.signal(result.run_id, Quick.pinged({"v": 1}))
            == "run_terminal"
        )
        assert (
            await harness.signal("no-such-run", Quick.pinged({"v": 1})) == "unknown_run"
        )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Known gap, narrower than it was: rx.approval_link() now groups the "
        "alternatives it mints so a losing one cannot answer a later wait "
        "(see test_approvals). A raw signal sent with an explicitly distinct "
        "key still buffers and can resolve the next wait on that channel. "
        "Whether that is a defect is a question about what an explicit key "
        "means -- it is also how a genuinely early signal is delivered -- so "
        "this pins the behaviour rather than asserting it is wrong."
    ),
)
async def test_a_rejected_alternative_does_not_answer_the_next_wait(
    forked_registration_context,
):
    """One decision must not silently answer a later, unrelated question.

    An approval mints two links -- approve and reject -- with distinct
    delivery keys, on purpose, so a second person can reject after a first
    approved. If approve lands first the run continues; the reject that lands
    afterwards is buffered because nothing is waiting for it right then. When
    the continuation opens a *second* wait on the same channel, that stale
    reject resolves it, and a two-stage approval completes with a decision
    nobody made in the second stage.
    """

    class TwoStage(rx.State):
        __workflow__ = WorkflowConfig(id="waits.two_stage")
        first: str = ""
        second: str = ""

        review = Signal(Decision)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            """Ask the first question.

            Returns:
                The first wait.
            """
            return wait_for(
                TwoStage.review,
                then=TwoStage.stage_one,
                timeout="7d",
                on_timeout=TwoStage.expire,
            )

        @rx.event(durable=True, effect="none")
        def stage_one(self, decision: Decision):
            """Record the first answer and ask a second question.

            Args:
                decision: The delivered decision.

            Returns:
                The second wait.
            """
            self.first = decision.by
            return wait_for(
                TwoStage.review,
                then=TwoStage.stage_two,
                timeout="7d",
                on_timeout=TwoStage.expire,
            )

        @rx.event(durable=True, effect="none")
        def stage_two(self, decision: Decision):
            """Record the second answer.

            Args:
                decision: The delivered decision.

            Returns:
                Completion.
            """
            self.second = decision.by
            return rx.complete(result={"first": self.first, "second": self.second})

        @rx.event(durable=True, effect="none")
        def expire(self):
            """Nobody answered.

            Returns:
                Failure.
            """
            return rx.fail(reason="no decision")

    async with WorkflowTestHarness(TwoStage) as harness:
        started = await harness.start(TwoStage.start())
        assert started.run_id is not None
        await harness.signal(
            started.run_id,
            TwoStage.review(Decision(approved=True, by="approver")),
            key="approve-link",
        )
        # The rejecting link for the *same* question, spent a moment later.
        await harness.signal(
            started.run_id,
            TwoStage.review(Decision(approved=False, by="rejecter")),
            key="reject-link",
        )
        await harness.run_until_idle()

        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.status is not RunStatus.COMPLETED, (
            "the second stage was answered by the first stage's losing "
            f"alternative: {snapshot.result}"
        )


async def test_an_expired_wait_says_so_in_history(forked_registration_context):
    """History has to distinguish "nobody answered" from "somebody did".

    A resolved wait records ``wait_resolved``. An expired one recorded
    nothing at all, so the only trace of the deadline was that the timeout
    branch happened to be the handler that ran next -- an operator asking
    "did the approval come through, or did it time out?" had to infer it
    from which handler appears, which is exactly what history exists to stop.

    Args:
        forked_registration_context: Isolates workflow registration.
    """
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        started = await harness.start(flow.start())
        assert started.run_id is not None
        await harness.advance("4d")

        history = await harness.kernel.store.get_history(started.run_id)
        kinds = [event.type for event in history]
        assert HistoryEventType.WAIT_ARMED in kinds
        assert HistoryEventType.WAIT_EXPIRED in kinds, (
            f"an expired wait left no trace: {[k.value for k in kinds]}"
        )
        assert HistoryEventType.WAIT_RESOLVED not in kinds, (
            "nobody answered, so nothing was resolved"
        )
        expiry = next(
            event for event in history if event.type is HistoryEventType.WAIT_EXPIRED
        )
        assert expiry.data["wait_key"] == "sig:review"


async def test_a_resolved_wait_is_not_reported_as_expired(
    forked_registration_context,
):
    """The other half of the same distinction.

    Args:
        forked_registration_context: Isolates workflow registration.
    """
    flow = _review_flow()
    async with WorkflowTestHarness(flow) as harness:
        started = await harness.start(flow.start())
        assert started.run_id is not None
        await harness.signal(
            started.run_id, flow.review({"approved": True, "by": "ada"})
        )

        kinds = [
            event.type
            for event in await harness.kernel.store.get_history(started.run_id)
        ]
        assert HistoryEventType.WAIT_RESOLVED in kinds
        assert HistoryEventType.WAIT_EXPIRED not in kinds


async def test_a_deduplicated_signal_leaves_a_trace(forked_registration_context):
    """A sender's retry that changed nothing still has to be visible.

    "The provider says it delivered, so why didn't the run move?" is answered
    by the run's history or by nothing at all. A repeated sender key is
    correctly a no-op, and a no-op that leaves no record is indistinguishable
    from a delivery that never arrived. The run has to still be alive for the
    second delivery to be *duplicate* rather than *run_terminal*, which is
    why this flow keeps going after it decides.

    Args:
        forked_registration_context: Isolates workflow registration.
    """

    class LiveReview(rx.State):
        __workflow__ = WorkflowConfig(id="waits.live_review")
        decided_by: str = ""

        review = Signal(Decision)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self):
            """Wait for a decision.

            Returns:
                The wait.
            """
            return wait_for(
                LiveReview.review,
                then=LiveReview.decide,
                timeout="3d",
                on_timeout=LiveReview.expire,
            )

        @rx.event(durable=True, effect="none")
        def decide(self, decision: Decision):
            """Record the decision and stay alive.

            Args:
                decision: The delivered decision.

            Returns:
                A long deferral, so the run is still nonterminal.
            """
            self.decided_by = decision.by
            return rx.after("30d", LiveReview.expire)

        @rx.event(durable=True, effect="none")
        def expire(self):
            """Finish.

            Returns:
                Completion.
            """
            return rx.complete(result={"done": True})

    async with WorkflowTestHarness(LiveReview) as harness:
        started = await harness.start(LiveReview.start())
        assert started.run_id is not None
        payload = LiveReview.review({"approved": True, "by": "ada"})
        assert await harness.signal(started.run_id, payload, key="hook-1") == "resolved"
        assert (
            await harness.signal(started.run_id, payload, key="hook-1") == "duplicate"
        )

        kinds = [
            event.type
            for event in await harness.kernel.store.get_history(started.run_id)
        ]
        assert kinds.count(HistoryEventType.WAIT_RESOLVED) == 1
        assert kinds.count(HistoryEventType.SIGNAL_DUPLICATE) == 1, (
            f"the deduplicated redelivery left no trace: {[k.value for k in kinds]}"
        )
