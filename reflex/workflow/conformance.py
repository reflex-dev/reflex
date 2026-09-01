"""An executable specification for ``RunStore`` implementations.

``RunStore`` is a public extension point: a deployment can back workflows with
Postgres, a hosted kernel, or anything else. The protocol's method signatures
say nothing about the invariants that make durable execution correct, so those
invariants live here as runnable checks rather than prose.

Every check takes a fresh, empty store and asserts one property. Run the whole
suite against an implementation before trusting it::

    import pytest
    from reflex.workflow.conformance import CONFORMANCE_CHECKS

    @pytest.mark.parametrize("check", CONFORMANCE_CHECKS, ids=lambda c: c.__name__)
    async def test_my_store_conforms(check):
        await check(MyRunStore())
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from reflex.workflow.records import (
    TERMINAL_RUN_STATUSES,
    HistoryEventType,
    ParkedStatus,
    RunQuery,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
    WorkerRecord,
)
from reflex.workflow.store import StaleClaimError, StepCompletion

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from reflex.workflow.store import RunStore

NOW = 1_000_000.0

LEASE = 30.0

_ADMITTED = ((HistoryEventType.RUN_ADMITTED, {}),)


def make_run(run_id: str = "run1", **overrides: Any) -> RunRecord:
    """Build a run record for a conformance check.

    Args:
        run_id: The run identity.
        overrides: Fields to override on the record.

    Returns:
        The run record.
    """
    fields: dict[str, Any] = {
        "run_id": run_id,
        "workflow_id": "conformance.flow",
        "definition_digest": "digest",
        "status": RunStatus.PENDING,
        "state": {"n": 0},
        "state_version": 0,
        "next_ordinal": 1,
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return RunRecord(**fields)


def make_step(run_id: str = "run1", ordinal: int = 0, **overrides: Any) -> StepRecord:
    """Build a step record for a conformance check.

    Args:
        run_id: The owning run.
        ordinal: The mailbox position.
        overrides: Fields to override on the record.

    Returns:
        The step record.
    """
    fields: dict[str, Any] = {
        "run_id": run_id,
        "ordinal": ordinal,
        "handler_id": "go",
        "status": StepStatus.READY,
        "args": {},
        "origin": "root",
        "created_at": NOW,
        "updated_at": NOW,
    }
    fields.update(overrides)
    return StepRecord(**fields)


async def check_admit_creates_a_run(store: RunStore) -> None:
    """A run and its root slot are readable straight after admission."""
    created, run_id = await store.admit(make_run(), make_step(), _ADMITTED)
    assert created
    assert run_id == "run1"
    run = await store.get_run("run1")
    assert run is not None
    assert run.state == {"n": 0}
    steps = await store.get_steps("run1")
    assert [step.ordinal for step in steps] == [0]
    history = await store.get_history("run1")
    assert [event.seq for event in history] == [1]


async def check_admit_deduplicates_on_request_key(store: RunStore) -> None:
    """One request key admits one run, however many times it is submitted."""
    await store.admit(make_run(request_key="key"), make_step(), _ADMITTED)
    created, run_id = await store.admit(
        make_run("run2", request_key="key"), make_step("run2"), _ADMITTED
    )
    assert not created
    assert run_id == "run1"
    assert await store.get_run("run2") is None


async def check_only_the_frontier_is_claimable(store: RunStore) -> None:
    """A later slot never overtakes an unresolved earlier one."""
    await store.admit(make_run(next_ordinal=2), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.RUNNING,
            state={"n": 1},
            new_steps=(
                make_step(ordinal=1, due_at=NOW + 60, origin="delay"),
                make_step(ordinal=2, origin="chain"),
            ),
            next_ordinal=3,
        ),
        NOW,
    )
    assert await store.claim_next(NOW, lease_duration=LEASE) is None
    later = await store.claim_next(NOW + 61, lease_duration=LEASE)
    assert later is not None
    assert later.step.ordinal == 1


async def check_commit_is_atomic(store: RunStore) -> None:
    """State, successors, and history all become visible together."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.RUNNING,
            state={"n": 7},
            new_steps=(make_step(ordinal=1, handler_id="second"),),
            next_ordinal=2,
            events=((HistoryEventType.STEP_SCHEDULED, {"ordinal": 1}),),
        ),
        NOW,
    )
    run = await store.get_run("run1")
    assert run is not None
    assert run.state == {"n": 7}
    assert run.state_version == 1
    assert run.next_ordinal == 2
    steps = await store.get_steps("run1")
    assert len(steps) == 2
    assert any(
        event.type is HistoryEventType.STEP_SCHEDULED
        for event in await store.get_history("run1")
    )


async def check_a_fenced_claim_cannot_commit(store: RunStore) -> None:
    """Two claims of one step cannot both commit."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    first = await store.claim_next(NOW, lease_duration=LEASE)
    assert first is not None
    await store.commit(
        first,
        StepCompletion(
            step_status=StepStatus.RETRY_WAIT,
            run_status=RunStatus.RETRYING,
            state=None,
            consume_attempt=True,
            due_at=NOW,
        ),
        NOW,
    )
    second = await store.claim_next(NOW, lease_duration=LEASE)
    assert second is not None
    assert second.step.epoch > first.step.epoch
    with pytest.raises(StaleClaimError):
        await store.commit(
            first,
            StepCompletion(
                step_status=StepStatus.SUCCEEDED,
                run_status=RunStatus.COMPLETED,
                state={"n": 99},
            ),
            NOW,
        )
    run = await store.get_run("run1")
    assert run is not None
    assert run.state == {"n": 0}


async def check_a_failed_attempt_discards_its_state(store: RunStore) -> None:
    """A commit that carries no state must not advance the state version."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.RETRY_WAIT,
            run_status=RunStatus.RETRYING,
            state=None,
            consume_attempt=True,
            due_at=NOW + 5,
        ),
        NOW,
    )
    run = await store.get_run("run1")
    assert run is not None
    assert run.state_version == 0
    steps = await store.get_steps("run1")
    assert steps[0].attempts == 1


async def check_claim_carries_a_renewable_lease(store: RunStore) -> None:
    """A claim's lease can be extended without transitioning the step."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    assert claim.step.lease_expires_at == pytest.approx(NOW + LEASE)
    assert await store.renew_lease(claim, NOW + 10, lease_duration=LEASE)
    steps = await store.get_steps("run1")
    assert steps[0].lease_expires_at == pytest.approx(NOW + 10 + LEASE)
    assert steps[0].epoch == claim.step.epoch
    assert steps[0].status is StepStatus.CLAIMED


async def check_recovery_spares_a_live_lease(store: RunStore) -> None:
    """A claim being executed by a peer is never reclaimed."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    assert (await store.recover_orphans(NOW + LEASE - 1, max_recoveries=10))[0] == 0
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.CLAIMED
    assert steps[0].recoveries == 0


async def check_recovery_reclaims_an_expired_lease(store: RunStore) -> None:
    """A lapsed claim is recovered, and charged to the recovery budget."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    assert (await store.recover_orphans(NOW + LEASE, max_recoveries=10))[0] == 1
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.RECOVERY_WAIT
    assert steps[0].recoveries == 1
    assert steps[0].attempts == 0
    assert not await store.renew_lease(claim, NOW + LEASE, lease_duration=LEASE)


async def check_next_due_only_promises_claimable_work(store: RunStore) -> None:
    """Whatever time next_due reports, something really is claimable then."""
    await store.admit(make_run(), make_step(due_at=NOW + 120), _ADMITTED)
    assert await store.claim_next(NOW, lease_duration=LEASE) is None
    due = await store.next_due(NOW)
    assert due is not None
    assert due == pytest.approx(NOW + 120)
    assert await store.claim_next(due, lease_duration=LEASE) is not None


async def check_a_wait_without_a_deadline_is_never_due(store: RunStore) -> None:
    """A blocked slot with no deadline must not busy-wake the scheduler."""
    await store.admit(
        make_run(),
        make_step(status=StepStatus.BLOCKED, wait_key="sig:ping", due_at=0.0),
        _ADMITTED,
    )
    assert await store.claim_next(NOW, lease_duration=LEASE) is None
    assert await store.next_due(NOW) is None
    assert await store.claim_next(NOW + 86400, lease_duration=LEASE) is None


async def check_a_wait_deadline_makes_the_slot_claimable(store: RunStore) -> None:
    """Claiming a blocked slot at its deadline is the timeout branch."""
    await store.admit(
        make_run(),
        make_step(status=StepStatus.BLOCKED, wait_key="sig:ping", due_at=NOW + 60),
        _ADMITTED,
    )
    assert await store.claim_next(NOW, lease_duration=LEASE) is None
    assert await store.next_due(NOW) == pytest.approx(NOW + 60)
    claim = await store.claim_next(NOW + 60, lease_duration=LEASE)
    assert claim is not None
    assert claim.step.ordinal == 0


async def check_delivery_resolves_a_matching_wait(store: RunStore) -> None:
    """A delivery flips the blocked slot and hands over its payload."""
    await store.admit(
        make_run(),
        make_step(status=StepStatus.BLOCKED, wait_key="sig:ping", due_at=0.0),
        _ADMITTED,
    )
    assert (
        await store.deliver("run1", "sig:ping", "d1", {"value": 1}, NOW) == "resolved"
    )
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.READY
    assert steps[0].args["__payload__"] == {"value": 1}


async def check_delivery_never_touches_run_state(store: RunStore) -> None:
    """A delivery must not be able to fence a live attempt."""
    await store.admit(
        make_run(),
        make_step(status=StepStatus.BLOCKED, wait_key="sig:ping", due_at=0.0),
        _ADMITTED,
    )
    before = await store.get_run("run1")
    assert before is not None
    await store.deliver("run1", "sig:ping", "d1", {"value": 1}, NOW)
    after = await store.get_run("run1")
    assert after is not None
    assert after.state_version == before.state_version
    assert after.state == before.state


async def check_duplicate_deliveries_are_ignored(store: RunStore) -> None:
    """The same delivery key resolves a wait at most once."""
    await store.admit(
        make_run(),
        make_step(status=StepStatus.BLOCKED, wait_key="sig:ping", due_at=0.0),
        _ADMITTED,
    )
    assert await store.deliver("run1", "sig:ping", "d1", {"v": 1}, NOW) == "resolved"
    assert await store.deliver("run1", "sig:ping", "d1", {"v": 2}, NOW) == "duplicate"
    steps = await store.get_steps("run1")
    assert steps[0].args["__payload__"] == {"v": 1}


async def check_an_early_delivery_is_buffered_then_consumed(store: RunStore) -> None:
    """A signal that beats its wait is applied when the wait is armed."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    assert await store.deliver("run1", "sig:ping", "d1", {"v": 1}, NOW) == "buffered"
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.WAITING,
            state={"n": 1},
            new_steps=(
                make_step(
                    ordinal=1,
                    status=StepStatus.BLOCKED,
                    wait_key="sig:ping",
                    due_at=0.0,
                    origin="wait",
                ),
            ),
            next_ordinal=2,
        ),
        NOW,
    )
    steps = await store.get_steps("run1")
    assert steps[1].status is StepStatus.READY
    assert steps[1].args["__payload__"] == {"v": 1}


async def check_join_arrivals_count_once(store: RunStore) -> None:
    """A join is satisfied by distinct arrivals, never by a redelivery."""
    await store.admit(
        make_run(),
        make_step(
            status=StepStatus.BLOCKED,
            wait_key="join:0",
            join_expected=2,
            origin="join",
            due_at=0.0,
        ),
        _ADMITTED,
    )
    assert await store.record_arrival("run1", 0, {"a": 1}, "c1", NOW) == "counted"
    assert await store.record_arrival("run1", 0, {"a": 1}, "c1", NOW) == "duplicate"
    steps = await store.get_steps("run1")
    assert steps[0].join_arrived == 1
    assert steps[0].status is StepStatus.BLOCKED
    assert await store.record_arrival("run1", 0, {"b": 2}, "c2", NOW) == "resolved"
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.READY
    assert steps[0].join_arrived == 2
    assert len(steps[0].args["__results__"]) == 2


async def check_finalize_refuses_while_a_step_is_claimed(store: RunStore) -> None:
    """A run cannot be terminated out from under a running attempt."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    assert await store.request_cancel("run1", NOW)
    assert await store.control_pending(NOW) == ()
    assert not await store.finalize_run(
        "run1",
        status=RunStatus.CANCELLED,
        error=None,
        event=HistoryEventType.RUN_CANCELLED,
        now=NOW,
    )


async def check_finalize_tombstones_open_slots(store: RunStore) -> None:
    """Terminating a run closes every slot it will never run."""
    await store.admit(make_run(next_ordinal=2), make_step(), _ADMITTED)
    assert await store.request_cancel("run1", NOW)
    assert await store.finalize_run(
        "run1",
        status=RunStatus.CANCELLED,
        error=None,
        event=HistoryEventType.RUN_CANCELLED,
        now=NOW,
    )
    steps = await store.get_steps("run1")
    assert all(step.status is StepStatus.CANCELLED for step in steps)
    assert not await store.request_cancel("run1", NOW)


async def check_resume_only_reopens_a_suspended_run(store: RunStore) -> None:
    """Resuming applies to suspension, not to healthy or finished runs."""
    await store.admit(
        make_run(status=RunStatus.NEEDS_ATTENTION),
        make_step(status=StepStatus.NEEDS_ATTENTION, attempts=3),
        _ADMITTED,
    )
    assert await store.resume_run("run1", NOW)
    run = await store.get_run("run1")
    assert run is not None
    assert run.status is RunStatus.PENDING
    assert run.error is None
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.READY
    assert steps[0].attempts == 0
    assert not await store.resume_run("run1", NOW)
    assert not await store.resume_run("missing", NOW)


async def check_list_runs_filters_and_orders(store: RunStore) -> None:
    """Listing is newest first and honors every filter."""
    await store.admit(
        make_run("a", labels={"customer": "acme"}, created_at=NOW),
        make_step("a"),
        _ADMITTED,
    )
    await store.admit(
        make_run(
            "b",
            labels={"customer": "globex"},
            status=RunStatus.COMPLETED,
            created_at=NOW + 1,
        ),
        make_step("b"),
        _ADMITTED,
    )
    listed = await store.list_runs(RunQuery())
    assert [run.run_id for run in listed] == ["b", "a"]
    assert [
        run.run_id
        for run in await store.list_runs(RunQuery(labels={"customer": "acme"}))
    ] == ["a"]
    assert [
        run.run_id
        for run in await store.list_runs(RunQuery(statuses=(RunStatus.COMPLETED,)))
    ] == ["b"]
    assert await store.list_runs(RunQuery(workflow_id="other.flow", limit=10)) == ()


async def check_runs_are_findable_by_definition_digest(store: RunStore) -> None:
    """Runs can be narrowed to the compiled definition that admitted them.

    "Is anything still running the release I am replacing" has to be one
    query. Answering it by listing everything and filtering client-side
    breaks the moment a deployment has more runs than a page.
    """
    await store.admit(
        make_run("old", definition_digest="d-old"), make_step("old"), _ADMITTED
    )
    await store.admit(
        make_run("new1", definition_digest="d-new"), make_step("new1"), _ADMITTED
    )
    await store.admit(
        make_run("new2", definition_digest="d-new"), make_step("new2"), _ADMITTED
    )
    assert await store.count_runs(RunQuery(definition_digest="d-old")) == 1
    assert await store.count_runs(RunQuery(definition_digest="d-new")) == 2
    assert await store.count_runs(RunQuery(definition_digest="d-gone")) == 0
    listed = await store.list_runs(RunQuery(definition_digest="d-new"))
    assert {run.run_id for run in listed} == {"new1", "new2"}
    assert (
        await store.count_runs(
            RunQuery(definition_digest="d-new", statuses=(RunStatus.PENDING,))
        )
        == 2
    ), "the digest filter composes with the others rather than replacing them"


async def check_count_runs_matches_the_listing(store: RunStore) -> None:
    """A count answers for the same set a listing would return.

    An operator view reports totals next to a page of runs. If the two read
    the filters differently, the page and the number above it describe
    different things, and the number is the one nobody can check.
    """
    await store.admit(
        make_run("a", labels={"customer": "acme"}, created_at=NOW),
        make_step("a"),
        _ADMITTED,
    )
    await store.admit(
        make_run(
            "b",
            labels={"customer": "globex"},
            status=RunStatus.COMPLETED,
            created_at=NOW + 1,
        ),
        make_step("b"),
        _ADMITTED,
    )
    assert await store.count_runs(RunQuery()) == 2
    assert await store.count_runs(RunQuery(statuses=(RunStatus.COMPLETED,))) == 1
    assert await store.count_runs(RunQuery(labels={"customer": "acme"})) == 1
    assert await store.count_runs(RunQuery(workflow_id="other.flow")) == 0
    # Paging bounds a listing; it must not bound an aggregate.
    assert await store.count_runs(RunQuery(limit=1)) == 2
    assert await store.count_runs(RunQuery(created_before=(NOW + 1, "b"))) == 2, (
        "a cursor pages a listing and says nothing about how many exist"
    )


async def check_flow_control_queries(store: RunStore) -> None:
    """Start policies can see what is active and what started recently."""
    await store.admit(
        make_run("a", flow_key="k1", created_at=NOW), make_step("a"), _ADMITTED
    )
    await store.admit(
        make_run("b", flow_key="k1", status=RunStatus.COMPLETED, created_at=NOW + 1),
        make_step("b"),
        _ADMITTED,
    )
    await store.admit(
        make_run("c", flow_key="k2", created_at=NOW + 2), make_step("c"), _ADMITTED
    )
    assert await store.count_active("conformance.flow", "k1") == 1
    first = await store.first_active("conformance.flow", "k1")
    assert first is not None
    assert first.run_id == "a"
    assert await store.first_active("conformance.flow", "missing") is None
    assert await store.count_started_since("conformance.flow", "k1", NOW - 1) == 2
    assert await store.count_started_since("conformance.flow", "k1", NOW) == 1
    assert await store.defer_root("a", NOW + 30, NOW)
    steps = await store.get_steps("a")
    assert steps[0].due_at == pytest.approx(NOW + 30)


async def check_nth_recent_start_orders_by_scheduled_time(store: RunStore) -> None:
    """Throttling can find the nth most recent scheduled start under a key."""
    for index, offset in enumerate((0.0, 5.0, 20.0)):
        await store.admit(
            make_run(f"s{index}", flow_key="k1", created_at=NOW + offset),
            make_step(f"s{index}"),
            _ADMITTED,
        )
    await store.admit(
        make_run("other", flow_key="k2", created_at=NOW + 99),
        make_step("other"),
        _ADMITTED,
    )
    assert await store.nth_recent_start("conformance.flow", "k1", 1) == pytest.approx(
        NOW + 20
    )
    assert await store.nth_recent_start("conformance.flow", "k1", 3) == pytest.approx(
        NOW
    )
    assert await store.nth_recent_start("conformance.flow", "k1", 4) is None
    assert await store.nth_recent_start("conformance.flow", "missing", 1) is None

    # A deferred run is scheduled by its due time, not by when it was admitted.
    assert await store.defer_root("s0", NOW + 50, NOW)
    assert await store.nth_recent_start("conformance.flow", "k1", 1) == pytest.approx(
        NOW + 50
    )


async def check_early_deliveries_queue_in_order(store: RunStore) -> None:
    """Several signals arriving before a wait are kept, not overwritten."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    assert await store.deliver("run1", "sig:ping", "d1", {"v": 1}, NOW) == "buffered"
    assert await store.deliver("run1", "sig:ping", "d2", {"v": 2}, NOW) == "buffered"
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.WAITING,
            state={"n": 1},
            new_steps=(
                make_step(
                    ordinal=1,
                    status=StepStatus.BLOCKED,
                    wait_key="sig:ping",
                    due_at=0.0,
                    origin="wait",
                ),
            ),
            next_ordinal=2,
        ),
        NOW,
    )
    steps = await store.get_steps("run1")
    # The first signal to arrive is the one that resolves the wait.
    assert steps[1].args["__payload__"] == {"v": 1}


async def check_children_are_created_with_their_join(store: RunStore) -> None:
    """A fan-out commit creates the join slot and its children together."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    child = make_run("child1", parent_run_id="run1", parent_ordinal=1)
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.WAITING,
            state={"n": 1},
            new_steps=(
                make_step(
                    ordinal=1,
                    status=StepStatus.BLOCKED,
                    wait_key="join:1",
                    join_expected=1,
                    origin="join",
                    due_at=0.0,
                ),
            ),
            next_ordinal=2,
            children=((child, make_step("child1")),),
        ),
        NOW,
    )
    created = await store.get_run("child1")
    assert created is not None
    assert created.parent_run_id == "run1"
    assert created.parent_ordinal == 1
    assert len(await store.get_steps("child1")) == 1


async def check_list_children_finds_a_joins_branches(store: RunStore) -> None:
    """The children of one join slot are addressable without a full scan."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.WAITING,
            state={},
            new_steps=(
                make_step(
                    ordinal=1,
                    status=StepStatus.BLOCKED,
                    wait_key="join:1",
                    join_expected=2,
                    origin="join",
                    due_at=0.0,
                ),
            ),
            next_ordinal=2,
            children=(
                (
                    make_run("childA", parent_run_id="run1", parent_ordinal=1),
                    make_step("childA"),
                ),
                (
                    make_run("childB", parent_run_id="run1", parent_ordinal=1),
                    make_step("childB"),
                ),
            ),
        ),
        NOW,
    )
    children = await store.list_children("run1", 1)
    assert {child.run_id for child in children} == {"childA", "childB"}
    assert await store.list_children("run1", 2) == ()
    assert await store.list_children("nobody", 1) == ()


async def check_claims_respect_queue_boundaries(store: RunStore) -> None:
    """A worker claims only from queues it serves, and skips whole runs."""
    await store.admit(make_run(), make_step(queue="video"), _ADMITTED)
    assert await store.claim_next(NOW, lease_duration=LEASE, queues=("emails",)) is None
    assert await store.next_due(NOW, queues=("emails",)) is None
    claim = await store.claim_next(NOW, lease_duration=LEASE, queues=("video",))
    assert claim is not None
    assert claim.step.queue == "video"
    await store.release_claim(claim, status=StepStatus.READY, events=(), now=NOW)
    # None serves everything, and the queue survives the round trip.
    fallback = await store.claim_next(NOW, lease_duration=LEASE)
    assert fallback is not None
    assert fallback.step.queue == "video"


async def check_substeps_record_once_and_fence_stale_writers(
    store: RunStore,
) -> None:
    """The substep journal memoizes by key and refuses fenced writers."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    epoch = claim.step.epoch

    assert await store.record_substep("run1", 0, epoch, "charge", {"n": 1}, NOW)
    assert await store.get_substeps("run1", 0) == {"charge": {"n": 1}}

    # First write wins: a racing duplicate reports success without replacing.
    assert await store.record_substep("run1", 0, epoch, "charge", {"n": 2}, NOW)
    assert await store.get_substeps("run1", 0) == {"charge": {"n": 1}}

    # A stale epoch is a zombie attempt; its write must be refused.
    assert not await store.record_substep("run1", 0, epoch - 1, "late", {}, NOW)
    # An unclaimed or unknown step accepts nothing either.
    assert not await store.record_substep("run1", 7, epoch, "wild", {}, NOW)
    assert not await store.record_substep("ghost", 0, epoch, "wild", {}, NOW)
    assert await store.get_substeps("run1", 0) == {"charge": {"n": 1}}

    # Several keys come back in recording order.
    assert await store.record_substep("run1", 0, epoch, "label", {"n": 3}, NOW + 1)
    assert list(await store.get_substeps("run1", 0)) == ["charge", "label"]


async def check_recovery_respects_a_live_lease(store: RunStore) -> None:
    """Recovery reclaims lapsed leases only: a slow worker is never raced."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=30.0)
    assert claim is not None
    recovered, failed = await store.recover_orphans(NOW + 5, 10)
    assert recovered == 0, "a live lease was reclaimed"
    assert failed == ()
    recovered, _ = await store.recover_orphans(NOW + 31, 10)
    assert recovered == 1, "a lapsed lease was not reclaimed"


async def check_a_terminal_run_refuses_further_control(store: RunStore) -> None:
    """Finalizing waits for the run to drain, and ends it for good."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    # A claimed step means an attempt may still be running: refuse.
    assert not await store.finalize_run(
        "run1",
        status=RunStatus.CANCELLED,
        error=None,
        event=HistoryEventType.RUN_CANCELLED,
        now=NOW + 1,
    )
    await store.release_claim(claim, status=StepStatus.READY, events=(), now=NOW + 1)
    assert await store.finalize_run(
        "run1",
        status=RunStatus.CANCELLED,
        error=None,
        event=HistoryEventType.RUN_CANCELLED,
        now=NOW + 2,
    )
    # Terminal is terminal: no further control lands.
    assert not await store.request_cancel("run1", NOW + 3)
    assert not await store.resume_run("run1", NOW + 3)
    assert not await store.finalize_run(
        "run1",
        status=RunStatus.COMPLETED,
        error=None,
        event=HistoryEventType.RUN_COMPLETED,
        now=NOW + 4,
    )


async def check_finalize_delivers_a_childs_arrival(store: RunStore) -> None:
    """Ending a child by cancellation or timeout tells its parent, atomically.

    The commit path is not the only way a child ends. If cancellation and
    run-timeout delivered their arrival afterwards, a crash in that window
    would strand the join exactly as it would have on commit.
    """
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    child = make_run("child1", parent_run_id="run1", parent_ordinal=1)
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.WAITING,
            state={},
            new_steps=(
                make_step(
                    ordinal=1,
                    status=StepStatus.BLOCKED,
                    wait_key="join:1",
                    join_expected=1,
                    origin="join",
                    due_at=0.0,
                ),
            ),
            next_ordinal=2,
            children=((child, make_step("child1")),),
        ),
        NOW,
    )

    assert await store.finalize_run(
        "child1",
        status=RunStatus.CANCELLED,
        error=None,
        event=HistoryEventType.RUN_CANCELLED,
        now=NOW + 1,
        parent_arrival=(
            "run1",
            1,
            {"run_id": "child1", "status": "CANCELLED", "result": None, "error": None},
            "child1",
        ),
    )
    steps = await store.get_steps("run1")
    assert steps[1].join_arrived == 1
    assert steps[1].status is StepStatus.READY


async def check_the_crash_matrix_holds_at_every_boundary(store: RunStore) -> None:
    """Walk CONTRACT.md section 8: kill at each boundary, check the outcome.

    A worker dies without cleanup at an arbitrary instant. What the store
    holds afterwards is the only evidence, and the contract names exactly one
    permitted outcome per boundary. This walks them in order rather than
    trusting that each is covered somewhere.
    """
    # Killed before admission commits: nothing exists, and the retry admits.
    assert await store.get_run("run1") is None
    await store.admit(make_run(), make_step(), _ADMITTED)

    # Killed after claim, before the handler ran: the lease lapses and
    # recovery re-offers the step. It costs a recovery, not an attempt.
    claim = await store.claim_next(NOW, lease_duration=1.0)
    assert claim is not None
    recovered, failed = await store.recover_orphans(NOW + 2, 10)
    assert (recovered, failed) == (1, ())
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.RECOVERY_WAIT
    assert steps[0].attempts == 0, "a crash consumed a business attempt"
    assert steps[0].recoveries == 1

    # Killed mid-handler after a substep recorded: the record survives, so a
    # re-execution replays it instead of repeating the work.
    claim = await store.claim_next(NOW + 3, lease_duration=1.0)
    assert claim is not None
    assert await store.record_substep(
        "run1", 0, claim.step.epoch, "charged", {"id": "ch_1"}, NOW + 3
    )
    await store.recover_orphans(NOW + 5, 10)
    assert await store.get_substeps("run1", 0) == {"charged": {"id": "ch_1"}}

    # Killed during a recovery sweep: sweeping again is idempotent, not a
    # second recovery of the same step.
    before = (await store.get_steps("run1"))[0].recoveries
    assert await store.recover_orphans(NOW + 6, 10) == (0, ())
    assert (await store.get_steps("run1"))[0].recoveries == before

    # Killed after a commit: everything the transition promised is durable,
    # including a child's arrival at its parent's join.
    claim = await store.claim_next(NOW + 7, lease_duration=LEASE)
    assert claim is not None
    child = make_run("child1", parent_run_id="run1", parent_ordinal=1)
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.WAITING,
            state={"n": 1},
            new_steps=(
                make_step(
                    ordinal=1,
                    status=StepStatus.BLOCKED,
                    wait_key="join:1",
                    join_expected=1,
                    origin="join",
                    due_at=0.0,
                ),
            ),
            next_ordinal=2,
            children=((child, make_step("child1")),),
        ),
        NOW + 7,
    )
    run = await store.get_run("run1")
    assert run is not None
    assert run.state == {"n": 1}
    assert await store.get_run("child1") is not None

    # The child dies for good: its arrival lands with its terminal
    # transition, so the join is never left waiting on a finished child.
    child_claim = await store.claim_next(NOW + 8, lease_duration=LEASE)
    assert child_claim is not None
    assert child_claim.run.run_id == "child1"
    await store.commit(
        child_claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.COMPLETED,
            state={},
            parent_arrival=(
                "run1",
                1,
                {"run_id": "child1", "status": "COMPLETED", "result": None},
                "child1",
            ),
        ),
        NOW + 9,
    )
    steps = await store.get_steps("run1")
    assert steps[1].join_arrived == 1
    assert steps[1].status is StepStatus.READY


async def check_flow_gate_enforces_every_policy(store: RunStore) -> None:
    """The whole policy decision is one atomic store transaction.

    Deciding outside the store is a check-then-act race two processes both
    win, which is how every advertised start policy was violated 50 out of 50
    times across two OS processes. These pin the store-side semantics; the
    cross-instance atomicity itself is pinned by tests that open two stores
    on one database.
    """
    from reflex.workflow.store import FlowGate

    skip = FlowGate(singleton_skip=True)
    first = await store.admit_flow(
        make_run("a", flow_key="k1"), make_step("a"), _ADMITTED, skip, NOW
    )
    assert (first.disposition, first.run_id) == ("started", "a")
    # A second start under the key is refused and told which run holds it.
    second = await store.admit_flow(
        make_run("b", flow_key="k1", created_at=NOW + 1),
        make_step("b"),
        _ADMITTED,
        skip,
        NOW + 1,
    )
    assert (second.disposition, second.run_id) == ("skipped", "a")
    assert await store.get_run("b") is None
    # A different key is unaffected.
    other = await store.admit_flow(
        make_run("c", flow_key="k2", created_at=NOW + 2),
        make_step("c"),
        _ADMITTED,
        skip,
        NOW + 2,
    )
    assert other.disposition == "started"
    # Once the holder is terminal the key is free again.
    assert await store.finalize_run(
        "a",
        status=RunStatus.COMPLETED,
        error=None,
        event=HistoryEventType.RUN_COMPLETED,
        now=NOW + 3,
    )
    third = await store.admit_flow(
        make_run("d", flow_key="k1", created_at=NOW + 4),
        make_step("d"),
        _ADMITTED,
        skip,
        NOW + 4,
    )
    assert third.disposition == "started"


async def check_flow_gate_rate_throttle_and_debounce(store: RunStore) -> None:
    """Rate limits refuse, throttles delay, debounces coalesce latest-wins."""
    from reflex.workflow.store import FlowGate

    rate = FlowGate(rate_limit=(1, 60.0))
    first = await store.admit_flow(
        make_run("r1", flow_key="rk"), make_step("r1"), _ADMITTED, rate, NOW
    )
    assert first.disposition == "started"
    refused = await store.admit_flow(
        make_run("r2", flow_key="rk", created_at=NOW + 1),
        make_step("r2"),
        _ADMITTED,
        rate,
        NOW + 1,
    )
    assert refused.disposition == "rejected"
    assert refused.retry_after is not None
    assert abs(refused.retry_after - 60.0) < 1e-9
    assert await store.get_run("r2") is None

    throttle = FlowGate(throttle=(1, 60.0))
    held = await store.admit_flow(
        make_run("t1", flow_key="tk", created_at=NOW + 1),
        make_step("t1", due_at=NOW + 1),
        _ADMITTED,
        throttle,
        NOW + 1,
    )
    assert held.disposition == "started"
    spaced = await store.admit_flow(
        make_run("t2", flow_key="tk", created_at=NOW + 2),
        make_step("t2", due_at=NOW + 2),
        _ADMITTED,
        throttle,
        NOW + 2,
    )
    assert spaced.disposition == "started"
    steps = await store.get_steps("t2")
    assert abs(steps[0].due_at - (NOW + 1 + 60.0)) < 1e-9, (
        "the second start sits one window after the first, not at its own time"
    )

    debounce = FlowGate(debounce=30.0)
    pending = await store.admit_flow(
        make_run("d1", flow_key="dk", created_at=NOW + 2),
        make_step("d1", args={"revision": 1}, due_at=NOW + 2),
        _ADMITTED,
        debounce,
        NOW + 2,
    )
    assert pending.disposition == "started"
    coalesced = await store.admit_flow(
        make_run("d2", flow_key="dk", created_at=NOW + 3),
        make_step("d2", args={"revision": 2}, due_at=NOW + 3),
        _ADMITTED,
        debounce,
        NOW + 3,
    )
    assert (coalesced.disposition, coalesced.run_id) == ("coalesced", "d1")
    assert await store.get_run("d2") is None
    steps = await store.get_steps("d1")
    assert abs(steps[0].due_at - (NOW + 3 + 30.0)) < 1e-9, "the quiet period extends"
    assert steps[0].args == {"revision": 2}, (
        "a debounced burst starts with its last payload, not its first"
    )


async def check_flow_gate_singleton_cancel_replaces(store: RunStore) -> None:
    """Cancel-mode admits the replacement and cancels the incumbent atomically."""
    from reflex.workflow.store import FlowGate

    cancel = FlowGate(singleton_cancel=True)
    first = await store.admit_flow(
        make_run("old", flow_key="ck"), make_step("old"), _ADMITTED, cancel, NOW
    )
    assert first.disposition == "started"
    replaced = await store.admit_flow(
        make_run("new", flow_key="ck", created_at=NOW + 1),
        make_step("new"),
        _ADMITTED,
        cancel,
        NOW + 1,
    )
    assert replaced.disposition == "started"
    assert replaced.cancelled == ("old",)
    old = await store.get_run("old")
    assert old is not None
    assert old.cancel_requested, (
        "the incumbent's cancellation intent rides the admitting transaction"
    )


async def check_purge_deletes_only_stale_terminal_runs(store: RunStore) -> None:
    """Retention removes finished history and never touches live work."""
    await store.admit(
        make_run("done", status=RunStatus.COMPLETED, request_key="evt-done"),
        make_step("done", status=StepStatus.SUCCEEDED),
        _ADMITTED,
    )
    await store.admit(
        make_run(
            "fresh",
            status=RunStatus.COMPLETED,
            created_at=NOW + 500,
            updated_at=NOW + 500,
        ),
        make_step("fresh", status=StepStatus.SUCCEEDED),
        _ADMITTED,
    )
    await store.admit(make_run("live", created_at=NOW), make_step("live"), _ADMITTED)

    deleted = await store.purge_runs(NOW + 100)
    assert deleted == 1
    assert await store.get_run("done") is None
    assert await store.get_steps("done") == ()
    assert await store.get_history("done") == ()
    fresh = await store.get_run("fresh")
    assert fresh is not None, "a terminal run inside the window stays"
    live = await store.get_run("live")
    assert live is not None, "an open run is never retention's business"
    # The purged run's dedupe key is forgotten with it: a redelivery after
    # the retention window is a fresh admission, by design.
    replay = await store.admit(
        make_run("done2", request_key="evt-done", created_at=NOW + 600),
        make_step("done2"),
        _ADMITTED,
    )
    assert replay == (True, "done2")


async def check_flow_gate_dedupes_before_policy(store: RunStore) -> None:
    """A redelivered event is its prior run, not a new start to be policed."""
    from reflex.workflow.store import FlowGate

    gate = FlowGate(rate_limit=(1, 60.0))
    first = await store.admit_flow(
        make_run("g1", flow_key="gk", request_key="evt-1"),
        make_step("g1"),
        _ADMITTED,
        gate,
        NOW,
    )
    assert first.disposition == "started"
    redelivered = await store.admit_flow(
        make_run("g2", flow_key="gk", request_key="evt-1", created_at=NOW + 1),
        make_step("g2"),
        _ADMITTED,
        gate,
        NOW + 1,
    )
    assert (redelivered.disposition, redelivered.run_id) == ("deduplicated", "g1"), (
        "hitting the rate limit must not turn a redelivery into a rejection"
    )


async def check_skip_unsticks_a_stopped_run(store: RunStore) -> None:
    """Skipping marks the blocking step terminal and lets the run continue."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    # A pending run has nothing to skip.
    assert not await store.skip_step("run1", NOW)

    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.NEEDS_ATTENTION,
            run_status=RunStatus.NEEDS_ATTENTION,
            state={},
            run_error={"reason": "uncertain"},
        ),
        NOW,
    )

    assert await store.skip_step("run1", NOW + 1)
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.SKIPPED
    run = await store.get_run("run1")
    assert run is not None
    # Nothing was left to run, so the run is finished rather than pending.
    assert run.status is RunStatus.COMPLETED
    assert run.error is None
    # And it is no longer a stopped run, so skipping again does nothing.
    assert not await store.skip_step("run1", NOW + 2)
    assert not await store.skip_step("missing", NOW)


async def check_retry_reopens_only_failed_runs(store: RunStore) -> None:
    """An operator retry applies to a failed run and nothing else."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    # A pending run is not a failure to retry.
    assert not await store.retry_run("run1", NOW)

    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.FAILED,
            run_status=RunStatus.FAILED,
            state={},
            run_error={"reason": "boom"},
        ),
        NOW,
    )
    assert await store.retry_run("run1", NOW + 1)
    run = await store.get_run("run1")
    assert run is not None
    assert run.status is RunStatus.PENDING
    assert run.error is None
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.READY
    assert steps[0].attempts == 0
    # Now re-opened, it is no longer a failed run.
    assert not await store.retry_run("run1", NOW + 2)
    assert not await store.retry_run("missing", NOW)


async def check_force_finalize_records_a_result(store: RunStore) -> None:
    """An operator ending a run may record what it should be treated as."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    assert await store.finalize_run(
        "run1",
        status=RunStatus.COMPLETED,
        error=None,
        event=HistoryEventType.RUN_COMPLETED,
        now=NOW,
        result={"by": "operator"},
    )
    run = await store.get_run("run1")
    assert run is not None
    assert run.status is RunStatus.COMPLETED
    assert run.result == {"by": "operator"}
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.CANCELLED


async def check_schedule_cursors_persist(store: RunStore) -> None:
    """A schedule's catch-up position survives the process that wrote it."""
    assert await store.read_schedule_cursor("wf:tick") is None
    await store.write_schedule_cursor("wf:tick", NOW)
    assert await store.read_schedule_cursor("wf:tick") == pytest.approx(NOW)
    # Advancing overwrites rather than accumulating.
    await store.write_schedule_cursor("wf:tick", NOW + 60)
    assert await store.read_schedule_cursor("wf:tick") == pytest.approx(NOW + 60)
    # An out-of-order write from a second worker never rewinds it.
    await store.write_schedule_cursor("wf:tick", NOW)
    assert await store.read_schedule_cursor("wf:tick") == pytest.approx(NOW + 60)
    # Schedules are independent of one another.
    assert await store.read_schedule_cursor("wf:other") is None


async def check_reads_do_not_alias_stored_state(store: RunStore) -> None:
    """Mutating a returned record must not change what the store holds."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    run = await store.get_run("run1")
    assert run is not None
    run.state["n"] = 999
    steps = await store.get_steps("run1")
    steps[0].args["injected"] = True

    again = await store.get_run("run1")
    assert again is not None
    assert again.state == {"n": 0}
    fresh = await store.get_steps("run1")
    assert fresh[0].args == {}


async def check_pagination_skips_nothing_on_tied_timestamps(store: RunStore) -> None:
    """Runs sharing a created_at must all be reachable by paging.

    A fan-out stamps every child with the same time, so a cursor on time alone
    silently hides runs from the operator surface.
    """
    for index in range(4):
        await store.admit(
            make_run(f"run{index}", created_at=NOW), make_step(f"run{index}"), _ADMITTED
        )
    seen: list[str] = []
    cursor = None
    while True:
        page = await store.list_runs(RunQuery(limit=2, created_before=cursor))
        if not page:
            break
        seen.extend(run.run_id for run in page)
        cursor = (page[-1].created_at, page[-1].run_id)
    assert sorted(seen) == ["run0", "run1", "run2", "run3"]


async def check_label_filter_handles_awkward_keys(store: RunStore) -> None:
    """A label key is data, never part of a query expression."""
    await store.admit(
        make_run("a", labels={"team.name": "core", 'quoted"key': "yes"}),
        make_step("a"),
        _ADMITTED,
    )
    await store.admit(
        make_run("b", labels={"team.name": "other"}), make_step("b"), _ADMITTED
    )
    dotted = await store.list_runs(RunQuery(labels={"team.name": "core"}))
    assert [run.run_id for run in dotted] == ["a"]
    quoted = await store.list_runs(RunQuery(labels={'quoted"key': "yes"}))
    assert [run.run_id for run in quoted] == ["a"]


async def check_finalizing_a_parent_closes_its_branches(store: RunStore) -> None:
    """Closing a run marks its branches for cancellation in the same write.

    Best-effort follow-up from the worker that finalized is not enough: an
    operator cancels a rollout to stop the regional deploys, and a worker that
    dies mid-follow-up would leave them deploying.
    """
    await store.admit(make_run(next_ordinal=2), make_step(), _ADMITTED)
    for run_id, close in (("kid1", "cancel"), ("kid2", "abandon")):
        await store.admit(
            make_run(
                run_id, parent_run_id="run1", parent_ordinal=1, parent_close=close
            ),
            make_step(run_id),
            _ADMITTED,
        )
    assert await store.request_cancel("run1", NOW)
    assert await store.finalize_run(
        "run1",
        status=RunStatus.CANCELLED,
        error=None,
        event=HistoryEventType.RUN_CANCELLED,
        now=NOW,
    )
    closed = await store.get_run("kid1")
    spared = await store.get_run("kid2")
    assert closed is not None
    assert spared is not None
    assert closed.cancel_requested
    assert closed.status is RunStatus.CANCELLING
    assert not spared.cancel_requested, "abandon must survive its parent"
    assert spared.status is RunStatus.PENDING


async def check_closing_a_branch_never_revives_a_finished_one(
    store: RunStore,
) -> None:
    """A branch that already finished is left exactly as it finished."""
    await store.admit(make_run(next_ordinal=2), make_step(), _ADMITTED)
    await store.admit(
        make_run("kid1", parent_run_id="run1", parent_ordinal=1),
        make_step("kid1"),
        _ADMITTED,
    )
    assert await store.request_cancel("kid1", NOW)
    assert await store.finalize_run(
        "kid1",
        status=RunStatus.COMPLETED,
        error=None,
        event=HistoryEventType.RUN_COMPLETED,
        now=NOW,
    )
    assert await store.request_cancel("run1", NOW)
    assert await store.finalize_run(
        "run1",
        status=RunStatus.FAILED,
        error={"message": "boom"},
        event=HistoryEventType.RUN_FAILED,
        now=NOW,
    )
    child = await store.get_run("kid1")
    assert child is not None
    assert child.status is RunStatus.COMPLETED


async def check_a_duplicate_delivery_is_recorded_in_history(store: RunStore) -> None:
    """A no-op delivery still has to be visible to whoever sent it.

    A repeated sender key is correctly ignored, and an ignored delivery that
    leaves no record is indistinguishable from one that never arrived --
    which is the question the history exists to answer.
    """
    await store.admit(
        make_run(),
        make_step(status=StepStatus.BLOCKED, wait_key="sig:ping", due_at=0.0),
        _ADMITTED,
    )
    assert await store.deliver("run1", "sig:ping", "d1", {"v": 1}, NOW) == "resolved"
    assert await store.deliver("run1", "sig:ping", "d1", {"v": 1}, NOW) == "duplicate"
    kinds = [event.type for event in await store.get_history("run1")]
    assert kinds.count(HistoryEventType.SIGNAL_DUPLICATE) == 1, kinds


async def check_a_delivery_to_a_past_deadline_run_is_refused(store: RunStore) -> None:
    """A run that can never execute the continuation must not say "resolved".

    Claims exclude past-deadline runs and the sweep is about to finalize this
    one TIMED_OUT, so answering "resolved" tells the sender their decision
    landed when it is about to be discarded -- and the sender is often a
    person clicking approve.
    """
    await store.admit(
        make_run(deadline=NOW - 1),
        make_step(status=StepStatus.BLOCKED, wait_key="sig:ping", due_at=0.0),
        _ADMITTED,
    )
    assert await store.deliver("run1", "sig:ping", "d1", {"v": 1}, NOW) == "expired"


async def check_an_arrival_to_a_past_deadline_parent_is_refused(
    store: RunStore,
) -> None:
    """A join that can never run must not be resolved by a late branch.

    The parent is about to finalize TIMED_OUT and its join slot will be
    tombstoned, so counting the arrival records a continuation that cannot
    happen -- and the stores disagreed about it, which is worse than either
    answer: the same fan-out resolved on one store and refused on another.
    """
    await store.admit(
        make_run(next_ordinal=2, deadline=NOW - 1),
        make_step(status=StepStatus.BLOCKED, wait_key="join:0", due_at=0.0),
        _ADMITTED,
    )
    assert await store.record_arrival(
        "run1", 0, {"status": "completed"}, "kid1", NOW
    ) == ("expired")


async def check_recovery_exhaustion_closes_the_whole_run(store: RunStore) -> None:
    """Exhausting the recovery budget must end the run the way failure does.

    The budget path marked the one exhausted step FAILED and stamped the run
    FAILED -- and stopped. Preallocated successor slots stayed open, so the
    dead run still surfaced wake times and confused retry; child runs kept
    working for a parent that no longer existed. A budget exhaustion is a
    failure, and failure closes the run completely: open slots tombstoned,
    branches told to stop.
    """
    await store.admit(
        make_run("par0", next_ordinal=1),
        make_step(
            "par0",
            status=StepStatus.BLOCKED,
            wait_key="join:0",
            join_expected=1,
            origin="join",
            due_at=0.0,
        ),
        _ADMITTED,
    )
    await store.admit(
        make_run(parent_run_id="par0", parent_ordinal=0), make_step(), _ADMITTED
    )
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    assert claim.run.run_id == "run1", "par0 has no claimable slot"
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.PENDING,
            state={"n": 1},
            new_steps=(
                make_step(ordinal=1, due_at=NOW),
                make_step(ordinal=2, due_at=NOW + 3600),
            ),
            next_ordinal=3,
            events=((HistoryEventType.ATTEMPT_SUCCEEDED, {}),),
            children=(
                (
                    make_run("kid", parent_run_id="run1", parent_ordinal=2),
                    make_step("kid", due_at=NOW + 7200),
                ),
            ),
        ),
        NOW,
    )
    claim = await store.claim_next(NOW, lease_duration=0.0)
    assert claim is not None
    assert claim.run.run_id == "run1"

    _, failed = await store.recover_orphans(NOW + 1, max_recoveries=0)
    assert "run1" in failed

    run = await store.get_run("run1")
    assert run is not None
    assert run.status is RunStatus.FAILED
    steps = await store.get_steps("run1")
    assert steps[1].status is StepStatus.FAILED
    assert steps[2].status is StepStatus.CANCELLED, (
        f"the preallocated slot must be tombstoned CANCELLED -- the exact "
        f"status retry restores -- not left {steps[2].status}"
    )
    kid = await store.get_run("kid")
    assert kid is not None
    assert kid.cancel_requested, "the child kept working for a dead parent"
    par_steps = await store.get_steps("par0")
    assert par_steps[0].join_arrived == 1, "the parent never heard the child exhausted"
    assert par_steps[0].args["__results__"][0]["status"] == RunStatus.FAILED.value
    # No leftover-claim sweep here: with every slot's status pinned exactly
    # above, a frontier-based claim has nothing left to find, and a loop
    # that cannot iterate reads as coverage it does not provide.


async def check_skipping_the_last_step_completes_like_a_completion(
    store: RunStore,
) -> None:
    """A skip that finishes the run must finish it everywhere it matters.

    Skipping the only open slot stamped the run COMPLETED and stopped there:
    no arrival reached the parent's join, which stayed BLOCKED 0/1 forever,
    and the skipped run's own children kept running. "Completed by an
    operator's decision" and "completed" must be the same terminal
    transition.
    """
    await store.admit(
        make_run("par", next_ordinal=1),
        make_step(
            "par",
            status=StepStatus.BLOCKED,
            wait_key="join:0",
            join_expected=1,
            origin="join",
            due_at=0.0,
        ),
        _ADMITTED,
    )
    await store.admit(
        make_run(
            "kid",
            parent_run_id="par",
            parent_ordinal=0,
            status=RunStatus.FAILED,
            error={"reason": "boom"},
        ),
        make_step("kid", status=StepStatus.FAILED, error={"reason": "boom"}),
        _ADMITTED,
    )
    await store.admit(make_run("gk", parent_run_id="kid"), make_step("gk"), _ADMITTED)

    assert await store.skip_step("kid", NOW)

    kid = await store.get_run("kid")
    assert kid is not None
    assert kid.status is RunStatus.COMPLETED
    par_steps = await store.get_steps("par")
    assert par_steps[0].join_arrived == 1, "the parent never heard the child finished"
    assert par_steps[0].status is StepStatus.READY
    assert par_steps[0].args["__results__"][0]["status"] == RunStatus.COMPLETED.value
    gk = await store.get_run("gk")
    assert gk is not None
    assert gk.cancel_requested, "the grandchild kept working under a closed branch"


async def check_a_cascade_flag_survives_the_childs_own_exhaustion(
    store: RunStore,
) -> None:
    """One crashed worker takes out a parent and its child in the same pass.

    The parent exhausts first and its cascade durably requests the child's
    cancellation; the child's own exhaustion then fails the child. Rebuilding
    the child's record from a pre-pass snapshot reverted the flag the cascade
    had just set, and a later retry could revive a branch whose parent is
    dead with nothing ever re-requesting its cancellation. The failure may
    keep the child FAILED, but the request must survive it.

    Run ids are chosen so every store processes the parent first ("a-" sorts
    and inserts before "z-"), which is the ordering that exercises the
    cascade-then-exhaust path.
    """
    await store.admit(make_run("a-par"), make_step("a-par"), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=0.0)
    assert claim is not None
    assert claim.run.run_id == "a-par"
    await store.admit(
        make_run("z-kid", parent_run_id="a-par"), make_step("z-kid"), _ADMITTED
    )
    claim = await store.claim_next(NOW, lease_duration=0.0)
    assert claim is not None
    assert claim.run.run_id == "z-kid"

    _, failed = await store.recover_orphans(NOW + 1, max_recoveries=0)
    assert "a-par" in failed

    kid = await store.get_run("z-kid")
    assert kid is not None
    assert kid.status in TERMINAL_RUN_STATUSES
    assert kid.cancel_requested, (
        "the parent's cascade requested cancellation and the child's own "
        "exhaustion erased the request"
    )


async def check_a_second_close_does_not_repeat_the_cancel_request(
    store: RunStore,
) -> None:
    """History records the decision to stop a branch once, not per close.

    A failed run whose children were already told to stop can reach a second
    terminal transition -- an operator skipping its failed step completes it.
    The second close used to append another cancel-requested event to every
    still-CANCELLING child, so history read as if the decision were made
    twice. The flag is durable and monotonic; a marked child has nothing
    left to write.
    """
    await store.admit(
        make_run("x", status=RunStatus.FAILED, error={"reason": "boom"}),
        make_step("x", status=StepStatus.FAILED, error={"reason": "boom"}),
        _ADMITTED,
    )
    await store.admit(make_run("kid", parent_run_id="x"), make_step("kid"), _ADMITTED)
    assert await store.request_cancel("kid", NOW)
    assert await store.skip_step("x", NOW + 1)

    kid = await store.get_run("kid")
    assert kid is not None
    assert kid.cancel_requested
    events = [
        event
        for event in await store.get_history("kid")
        if event.type is HistoryEventType.RUN_CANCEL_REQUESTED
    ]
    assert len(events) == 1, f"the stop decision was recorded {len(events)} times"


async def check_retry_after_exhaustion_restores_waits_as_waits(
    store: RunStore,
) -> None:
    """A restored join must wait again, not run with missing inputs.

    Exhaustion tombstones every open slot, including a BLOCKED join holding
    partial arrivals and a delayed slot holding a future due time. Retry
    restores the chain -- and restoring a join as READY would run its
    handler immediately with a partial result set, while rewriting a delayed
    slot's due time to "now" would erase the delay. What was waiting comes
    back waiting, with its arrival count and its deadline intact.
    """
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    await store.commit(
        claim,
        StepCompletion(
            step_status=StepStatus.SUCCEEDED,
            run_status=RunStatus.PENDING,
            state={"n": 1},
            new_steps=(
                make_step(ordinal=1, due_at=NOW),
                make_step(
                    ordinal=2,
                    status=StepStatus.BLOCKED,
                    wait_key="join:2",
                    join_expected=2,
                    join_arrived=1,
                    origin="join",
                    due_at=NOW + 9000,
                ),
                make_step(ordinal=3, due_at=NOW + 3600),
            ),
            next_ordinal=4,
            events=((HistoryEventType.ATTEMPT_SUCCEEDED, {}),),
        ),
        NOW,
    )
    claim = await store.claim_next(NOW, lease_duration=0.0)
    assert claim is not None
    assert claim.step.ordinal == 1

    _, failed = await store.recover_orphans(NOW + 1, max_recoveries=0)
    assert "run1" in failed
    steps = await store.get_steps("run1")
    assert steps[2].status is StepStatus.CANCELLED
    assert steps[3].status is StepStatus.CANCELLED

    assert await store.retry_run("run1", NOW + 10)
    steps = await store.get_steps("run1")
    assert steps[2].status is StepStatus.BLOCKED, (
        f"the join came back {steps[2].status}, and READY would run it with "
        "one of two results"
    )
    assert steps[2].join_arrived == 1, "the arrival already counted was lost"
    assert steps[2].due_at == pytest.approx(NOW + 9000), (
        "the join's timeout deadline was rewritten"
    )
    assert steps[3].status is StepStatus.READY
    assert steps[3].due_at == pytest.approx(NOW + 3600), (
        "the delayed slot's due time was rewritten; its delay is erased"
    )


async def check_none_is_a_legal_payload_everywhere(store: RunStore) -> None:
    """None is the JSON value null, not an absent column.

    A signal with no payload -- an "approved" ping -- and a journaled
    substep whose call returned nothing are both everyday shapes, and one
    store refusing what the others accept is a divergence someone only
    finds after migrating.
    """
    await store.admit(
        make_run(),
        make_step(status=StepStatus.BLOCKED, wait_key="sig:ping", due_at=0.0),
        _ADMITTED,
    )
    assert await store.deliver("run1", "sig:ping", "d1", None, NOW) == "resolved"
    steps = await store.get_steps("run1")
    assert steps[0].args["__payload__"] is None

    await store.admit(make_run("sub1"), make_step("sub1"), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    while claim is not None and claim.run.run_id != "sub1":
        # run1's resolved continuation is claimable too, and stores order
        # their frontiers differently.
        claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    assert await store.record_substep("sub1", 0, claim.step.epoch, "notify", None, NOW)
    assert await store.get_substeps("sub1", 0) == {"notify": None}


async def check_a_delivery_before_its_run_lands_exactly_once(
    store: RunStore,
) -> None:
    """The Phase 2 acceptance flow, minus the crash: park, redeliver, admit.

    A shipment event arrives before the order workflow exists, the provider
    sends it three times, and the run starts later. Exactly one signal must
    reach the run -- the channel-inbox row keyed by the provider's event id
    is what collapses redelivery and crash-after-ack replays into one fact.
    """
    first = await store.ingest_channel_delivery(
        "conformance.flow", "shipped", "order_1", "evt_1", {"parcel": "P1"}, NOW
    )
    assert first == "parked", "no run exists yet; the delivery must wait"
    for _ in range(2):
        again = await store.ingest_channel_delivery(
            "conformance.flow", "shipped", "order_1", "evt_1", {"parcel": "P1"}, NOW
        )
        assert again == "duplicate", "a redelivery is the same event"

    await store.admit(
        make_run(request_key="order_1"),
        make_step(status=StepStatus.BLOCKED, wait_key="sig:shipped", due_at=0.0),
        _ADMITTED,
    )
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.READY, "the parked payload resolved it"
    assert steps[0].args["__payload__"] == {"parcel": "P1"}

    late = await store.ingest_channel_delivery(
        "conformance.flow", "shipped", "order_1", "evt_1", {"parcel": "P1"}, NOW + 1
    )
    assert late == "duplicate", "the event id survives delivery"
    rows = await store.list_parked(workflow_id="conformance.flow")
    assert len(rows) == 1
    assert rows[0].status is ParkedStatus.DELIVERED
    assert rows[0].run_id == "run1"


async def check_a_delivery_to_a_live_run_lands_immediately(store: RunStore) -> None:
    """With the run already waiting, ingest is an ordinary delivery.

    The channel-inbox row is still written -- it is the event-id dedupe for
    every later redelivery -- but the payload goes straight through.
    """
    await store.admit(
        make_run(request_key="order_2"),
        make_step(status=StepStatus.BLOCKED, wait_key="sig:shipped", due_at=0.0),
        _ADMITTED,
    )
    landed = await store.ingest_channel_delivery(
        "conformance.flow", "shipped", "order_2", "evt_2", {"n": 2}, NOW
    )
    assert landed == "resolved"
    again = await store.ingest_channel_delivery(
        "conformance.flow", "shipped", "order_2", "evt_2", {"n": 2}, NOW
    )
    assert again == "duplicate"
    steps = await store.get_steps("run1")
    assert steps[0].args["__payload__"] == {"n": 2}


async def check_a_dead_letter_is_visible_and_replayable(store: RunStore) -> None:
    """A delivery nothing can take becomes an operator's problem, loudly.

    The run is terminal, so the payload can never land -- but silence would
    read as delivered. The row dies visibly, and after the operator revives
    the run, replay routes the same row with the same idempotency.
    """
    await store.admit(
        make_run(request_key="order_3", status=RunStatus.FAILED),
        make_step(status=StepStatus.FAILED, error={"reason": "boom"}),
        _ADMITTED,
    )
    dead = await store.ingest_channel_delivery(
        "conformance.flow", "shipped", "order_3", "evt_3", {"n": 3}, NOW
    )
    assert dead == "dead_letter"
    rows = await store.list_parked(status=ParkedStatus.DEAD)
    assert len(rows) == 1
    assert rows[0].reason == "run_terminal"

    assert await store.retry_run("run1", NOW + 1)
    replayed = await store.replay_parked(rows[0].parked_id, NOW + 2)
    assert replayed == "buffered", "the revived run has no wait open yet"
    rows = await store.list_parked(workflow_id="conformance.flow")
    assert rows[0].status is ParkedStatus.DELIVERED
    assert await store.replay_parked(rows[0].parked_id, NOW + 3) == "duplicate", (
        "replaying a delivered row must never signal twice"
    )
    assert await store.replay_parked("missing", NOW) == "unknown_key"


async def check_unclaimed_deliveries_become_dead_letters(store: RunStore) -> None:
    """A parked delivery whose run never arrives surfaces, not lingers."""
    await store.ingest_channel_delivery(
        "conformance.flow", "shipped", "order_4", "evt_4", {"n": 4}, NOW
    )
    assert await store.sweep_parked(NOW + 100, ttl=3600) == 0, "not yet unclaimed"
    assert await store.sweep_parked(NOW + 4000, ttl=3600) == 1
    rows = await store.list_parked(status=ParkedStatus.DEAD)
    assert len(rows) == 1
    assert rows[0].reason == "unclaimed"
    assert await store.sweep_parked(NOW + 5000, ttl=3600) == 0, "dead rows stay dead"


async def check_policy_admission_also_flushes_parked_mail(store: RunStore) -> None:
    """A run admitted through a start policy still receives its early mail.

    Policy admission is a second door into existence; a delivery parked
    before the run must not depend on which door the run came through.
    """
    from reflex.workflow.store import FlowGate

    parked = await store.ingest_channel_delivery(
        "conformance.flow", "shipped", "order_5", "evt_5", {"n": 5}, NOW
    )
    assert parked == "parked"
    admission = await store.admit_flow(
        make_run(request_key="order_5", flow_key="order_5"),
        make_step(status=StepStatus.BLOCKED, wait_key="sig:shipped", due_at=0.0),
        _ADMITTED,
        FlowGate(),
        NOW,
    )
    assert admission.disposition == "started"
    steps = await store.get_steps(admission.run_id or "run1")
    assert steps[0].status is StepStatus.READY
    assert steps[0].args["__payload__"] == {"n": 5}
    rows = await store.list_parked(workflow_id="conformance.flow")
    assert rows[0].status is ParkedStatus.DELIVERED


async def check_a_pinned_run_drains_only_on_its_release(store: RunStore) -> None:
    """Release routing: a run never mixes two releases' code.

    A v2 worker must not claim a run v1 admitted -- the run drains on the
    release whose code recorded its payloads. An unpinned run (admitted
    before releases were declared) is claimable by anyone, and a worker with
    no declared release (dev, tests) claims anything: pinning constrains
    only when both sides declare.
    """
    await store.admit(make_run(release_id="v1"), make_step(due_at=0.0), _ADMITTED)
    assert await store.claim_next(NOW, release="v2") is None, (
        "a v2 worker claimed a v1-pinned run"
    )
    claim = await store.claim_next(NOW, release="v1")
    assert claim is not None
    assert claim.run.release_id == "v1"
    await store.release_claim(claim, status=StepStatus.READY, events=(), now=NOW)

    claim = await store.claim_next(NOW, release=None)
    assert claim is not None, "an undeclared worker serves every release"
    await store.release_claim(claim, status=StepStatus.READY, events=(), now=NOW)

    await store.admit(make_run("free1"), make_step("free1", due_at=0.0), _ADMITTED)
    claim = await store.claim_next(NOW, release="v2")
    assert claim is not None
    assert claim.run.run_id == "free1", "an unpinned run is anyone's to run"


async def check_worker_registry_roundtrip(store: RunStore) -> None:
    """The fleet surface: register, heartbeat, list, deregister."""
    await store.register_worker(
        WorkerRecord(
            worker_id="w1",
            release_id="v1",
            queues=("default",),
            capacity=8,
            started_at=NOW,
            heartbeat_at=NOW,
        )
    )
    await store.register_worker(
        WorkerRecord(
            worker_id="w2",
            release_id=None,
            queues=(),
            capacity=4,
            started_at=NOW + 1,
            heartbeat_at=NOW + 1,
        )
    )
    workers = await store.list_workers()
    assert [worker.worker_id for worker in workers] == ["w2", "w1"]
    assert workers[1].queues == ("default",)

    await store.heartbeat_worker("w1", NOW + 60)
    workers = await store.list_workers()
    beat = next(worker for worker in workers if worker.worker_id == "w1")
    assert beat.heartbeat_at == pytest.approx(NOW + 60)

    await store.deregister_worker("w2")
    workers = await store.list_workers()
    assert [worker.worker_id for worker in workers] == ["w1"]


async def check_release_counts_answer_the_retirement_question(
    store: RunStore,
) -> None:
    """Count what still runs the release being replaced; zero means retire."""
    await store.admit(make_run(release_id="v1"), make_step(due_at=0.0), _ADMITTED)
    await store.admit(
        make_run("done1", release_id="v1", status=RunStatus.COMPLETED),
        make_step("done1", status=StepStatus.SUCCEEDED),
        _ADMITTED,
    )
    active = [status for status in RunStatus if status not in TERMINAL_RUN_STATUSES]
    assert (
        await store.count_runs(RunQuery(release_id="v1", statuses=tuple(active))) == 1
    )
    assert (
        await store.count_runs(RunQuery(release_id="v2", statuses=tuple(active))) == 0
    ), "nothing pins to a release that admitted nothing"


async def check_operator_actions_carry_attribution(store: RunStore) -> None:
    """Every operator mutation records who asked and why, in the run's story.

    An audit that lives outside the history would drift from it; attribution
    rides the same events, in the same transactions, so "who did this" is
    answered by the record that already answers "what happened".
    """
    who = {"actor": "alex", "reason": "customer asked"}

    await store.admit(make_run(), make_step(due_at=0.0), _ADMITTED)
    assert await store.request_cancel("run1", NOW, who)
    events = await store.get_history("run1")
    cancel_event = next(
        event for event in events if event.type is HistoryEventType.RUN_CANCEL_REQUESTED
    )
    assert cancel_event.data["actor"] == "alex"
    assert cancel_event.data["reason"] == "customer asked"

    await store.admit(
        make_run("fail1", status=RunStatus.FAILED, error={"reason": "boom"}),
        make_step("fail1", status=StepStatus.FAILED, error={"reason": "boom"}),
        _ADMITTED,
    )
    assert await store.retry_run("fail1", NOW, who)
    events = await store.get_history("fail1")
    resumed = next(
        event for event in events if event.type is HistoryEventType.RUN_RESUMED
    )
    assert resumed.data["actor"] == "alex"

    await store.admit(
        make_run("skip1", status=RunStatus.FAILED, error={"reason": "boom"}),
        make_step("skip1", status=StepStatus.FAILED, error={"reason": "boom"}),
        _ADMITTED,
    )
    assert await store.skip_step("skip1", NOW, who)
    events = await store.get_history("skip1")
    skipped = next(
        event for event in events if event.type is HistoryEventType.STEP_SKIPPED
    )
    assert skipped.data["reason"] == "customer asked"

    await store.admit(
        make_run("sus1", status=RunStatus.NEEDS_ATTENTION),
        make_step("sus1", status=StepStatus.NEEDS_ATTENTION),
        _ADMITTED,
    )
    assert await store.resume_run("sus1", NOW, who)
    events = await store.get_history("sus1")
    reopened = next(
        event for event in events if event.type is HistoryEventType.RUN_RESUMED
    )
    assert reopened.data["actor"] == "alex"

    await store.admit(make_run("fin1"), make_step("fin1", due_at=0.0), _ADMITTED)
    assert await store.finalize_run(
        "fin1",
        status=RunStatus.FAILED,
        error={"reason": "manual"},
        event=HistoryEventType.RUN_FAILED,
        now=NOW,
        attribution=who,
    )
    events = await store.get_history("fin1")
    failed = next(
        event for event in events if event.type is HistoryEventType.RUN_FAILED
    )
    assert failed.data["actor"] == "alex"
    assert failed.data["reason"] == "customer asked"


async def check_run_less_operator_actions_are_audited(store: RunStore) -> None:
    """Replay and purge have no run to carry history, so they carry an audit.

    Run-level actions ride the run's own history (attribution check above);
    these two would otherwise be the only operator mutations nobody could
    account for. The entry is written in the operation's own transaction
    and only when there is an actor to name: unattributed automation leaves
    no entry, so the log is operator decisions, not noise.
    """
    who = {"actor": "alex", "reason": "vendor fixed"}
    await store.ingest_channel_delivery(
        "conformance.flow", "shipped", "order_9", "evt_9", {"n": 9}, NOW
    )
    rows = await store.list_parked(status=ParkedStatus.PENDING)
    parked_id = rows[0].parked_id

    assert await store.replay_parked(parked_id, NOW + 1) == "parked"
    assert await store.list_audit() == (), "no actor, no entry"

    assert await store.replay_parked(parked_id, NOW + 2, who) == "parked"
    await store.admit(
        make_run("old1", status=RunStatus.COMPLETED),
        make_step("old1", status=StepStatus.SUCCEEDED),
        _ADMITTED,
    )
    assert await store.purge_runs(NOW + 10, attribution=who) == 1

    entries = await store.list_audit()
    assert [entry.action for entry in entries] == ["purge_runs", "replay_parked"], (
        "newest first"
    )
    purge, replay = entries
    assert replay.actor == "alex"
    assert replay.reason == "vendor fixed"
    assert replay.target == parked_id
    assert replay.detail == {"disposition": "parked"}
    assert purge.target == "*"
    assert purge.detail["deleted"] == 1
    assert await store.list_audit(action="purge_runs") == (purge,)


CONFORMANCE_CHECKS: tuple[Callable[[RunStore], Awaitable[None]], ...] = (
    check_admit_creates_a_run,
    check_reads_do_not_alias_stored_state,
    check_admit_deduplicates_on_request_key,
    check_only_the_frontier_is_claimable,
    check_commit_is_atomic,
    check_a_fenced_claim_cannot_commit,
    check_a_failed_attempt_discards_its_state,
    check_claim_carries_a_renewable_lease,
    check_recovery_spares_a_live_lease,
    check_recovery_reclaims_an_expired_lease,
    check_next_due_only_promises_claimable_work,
    check_a_wait_without_a_deadline_is_never_due,
    check_a_wait_deadline_makes_the_slot_claimable,
    check_delivery_resolves_a_matching_wait,
    check_delivery_never_touches_run_state,
    check_duplicate_deliveries_are_ignored,
    check_a_delivery_before_its_run_lands_exactly_once,
    check_a_delivery_to_a_live_run_lands_immediately,
    check_a_dead_letter_is_visible_and_replayable,
    check_unclaimed_deliveries_become_dead_letters,
    check_policy_admission_also_flushes_parked_mail,
    check_a_pinned_run_drains_only_on_its_release,
    check_worker_registry_roundtrip,
    check_release_counts_answer_the_retirement_question,
    check_operator_actions_carry_attribution,
    check_run_less_operator_actions_are_audited,
    check_a_delivery_to_a_past_deadline_run_is_refused,
    check_a_duplicate_delivery_is_recorded_in_history,
    check_an_early_delivery_is_buffered_then_consumed,
    check_early_deliveries_queue_in_order,
    check_children_are_created_with_their_join,
    check_list_children_finds_a_joins_branches,
    check_claims_respect_queue_boundaries,
    check_substeps_record_once_and_fence_stale_writers,
    check_none_is_a_legal_payload_everywhere,
    check_recovery_respects_a_live_lease,
    check_a_terminal_run_refuses_further_control,
    check_finalize_delivers_a_childs_arrival,
    check_the_crash_matrix_holds_at_every_boundary,
    check_flow_gate_enforces_every_policy,
    check_flow_gate_rate_throttle_and_debounce,
    check_flow_gate_singleton_cancel_replaces,
    check_flow_gate_dedupes_before_policy,
    check_purge_deletes_only_stale_terminal_runs,
    check_skip_unsticks_a_stopped_run,
    check_retry_reopens_only_failed_runs,
    check_force_finalize_records_a_result,
    check_schedule_cursors_persist,
    check_join_arrivals_count_once,
    check_an_arrival_to_a_past_deadline_parent_is_refused,
    check_finalize_refuses_while_a_step_is_claimed,
    check_recovery_exhaustion_closes_the_whole_run,
    check_a_cascade_flag_survives_the_childs_own_exhaustion,
    check_skipping_the_last_step_completes_like_a_completion,
    check_a_second_close_does_not_repeat_the_cancel_request,
    check_retry_after_exhaustion_restores_waits_as_waits,
    check_finalize_tombstones_open_slots,
    check_finalizing_a_parent_closes_its_branches,
    check_closing_a_branch_never_revives_a_finished_one,
    check_resume_only_reopens_a_suspended_run,
    check_list_runs_filters_and_orders,
    check_count_runs_matches_the_listing,
    check_runs_are_findable_by_definition_digest,
    check_pagination_skips_nothing_on_tied_timestamps,
    check_label_filter_handles_awkward_keys,
    check_flow_control_queries,
    check_nth_recent_start_orders_by_scheduled_time,
)
