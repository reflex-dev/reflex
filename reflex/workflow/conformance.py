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
    HistoryEventType,
    RunQuery,
    RunRecord,
    RunStatus,
    StepRecord,
    StepStatus,
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
    assert await store.recover_orphans(NOW + LEASE - 1, max_recoveries=10) == 0
    steps = await store.get_steps("run1")
    assert steps[0].status is StepStatus.CLAIMED
    assert steps[0].recoveries == 0


async def check_recovery_reclaims_an_expired_lease(store: RunStore) -> None:
    """A lapsed claim is recovered, and charged to the recovery budget."""
    await store.admit(make_run(), make_step(), _ADMITTED)
    claim = await store.claim_next(NOW, lease_duration=LEASE)
    assert claim is not None
    assert await store.recover_orphans(NOW + LEASE, max_recoveries=10) == 1
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


CONFORMANCE_CHECKS: tuple[Callable[[RunStore], Awaitable[None]], ...] = (
    check_admit_creates_a_run,
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
    check_an_early_delivery_is_buffered_then_consumed,
    check_early_deliveries_queue_in_order,
    check_children_are_created_with_their_join,
    check_join_arrivals_count_once,
    check_finalize_refuses_while_a_step_is_claimed,
    check_finalize_tombstones_open_slots,
    check_resume_only_reopens_a_suspended_run,
    check_list_runs_filters_and_orders,
    check_flow_control_queries,
)
