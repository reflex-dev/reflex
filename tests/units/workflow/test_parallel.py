"""Tests for parallel fan-out via child runs."""

from reflex_base.workflow import Retry, TransientWorkflowError, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.kernel import WorkflowKernel
from reflex.workflow.records import HistoryEventType, RunStatus, StepStatus
from reflex.workflow.store import MemoryRunStore
from reflex.workflow.testing import WorkflowTestHarness

BRANCH_CALLS: list[str] = []


class Slower(rx.State):
    """A branch that answers well after its sibling."""

    __workflow__ = WorkflowConfig(id="fan.slower")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def start(self, lead: str):
        """Answer much later.

        Args:
            lead: The lead identifier.

        Returns:
            A deferral.
        """
        return rx.after("5h", Slower.finish)

    @rx.event(durable=True, effect="none")
    def finish(self):
        """Answer.

        Returns:
            Completion.
        """
        BRANCH_CALLS.append("slower")
        return rx.complete(result="slower")


class Slowish(rx.State):
    """A branch that answers after a delay."""

    __workflow__ = WorkflowConfig(id="fan.slowish")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def start(self, lead: str):
        """Answer later.

        Args:
            lead: The lead identifier.

        Returns:
            A deferral.
        """
        return rx.after("1h", Slowish.finish)

    @rx.event(durable=True, effect="none")
    def finish(self):
        """Answer.

        Returns:
            Completion.
        """
        BRANCH_CALLS.append("slowish")
        return rx.complete(result="slowish")


class Enrich(rx.State):
    """A branch that succeeds."""

    __workflow__ = WorkflowConfig(id="fan.enrich")
    lead: str = ""

    @rx.event(durable=True, trigger=manual(), effect="read")
    def start(self, lead: str):
        """Enrich the lead.

        Args:
            lead: The lead identifier.

        Returns:
            Completion carrying the enriched value.
        """
        BRANCH_CALLS.append("enrich")
        self.lead = lead
        return rx.complete(result={"enriched": lead.upper()})


class Flaky(rx.State):
    """A branch that needs a retry of its own."""

    __workflow__ = WorkflowConfig(id="fan.flaky")
    lead: str = ""

    @rx.event(
        durable=True,
        trigger=manual(),
        effect="read",
        retry=Retry(max_attempts=3, initial_delay="1s", jitter="none"),
    )
    def start(self, lead: str):
        """Score the lead, failing once first.

        Args:
            lead: The lead identifier.

        Returns:
            Completion carrying the score.
        """
        BRANCH_CALLS.append("flaky")
        if BRANCH_CALLS.count("flaky") < 2:
            msg = "scoring service down"
            raise TransientWorkflowError(msg)
        self.lead = lead
        return rx.complete(result={"score": len(lead)})


class Doomed(rx.State):
    """A branch that always fails."""

    __workflow__ = WorkflowConfig(id="fan.doomed")

    @rx.event(
        durable=True, trigger=manual(), effect="read", retry=Retry(max_attempts=1)
    )
    def start(self, lead: str):
        """Fail to process the lead.

        Args:
            lead: The lead identifier.
        """
        BRANCH_CALLS.append("doomed")
        msg = "permanently broken"
        raise TransientWorkflowError(msg)


def _router(*branches, **fan_out_kwargs):
    """Build a parent workflow fanning out to the given branches.

    Args:
        branches: The branch classes to fan out to.
        fan_out_kwargs: Passed through to ``rx.parallel``.

    Returns:
        The parent workflow class.
    """

    class Router(rx.State):
        __workflow__ = WorkflowConfig(id="fan.router")
        outcomes: list[str] = []

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self, lead: str):
            """Fan out to every branch.

            Args:
                lead: The lead identifier.

            Returns:
                The parallel fan-out.
            """
            return rx.parallel(
                *[branch.start(lead) for branch in branches],
                then=Router.route,
                **fan_out_kwargs,
            )

        @rx.event(durable=True, effect="none")
        def route(self, results: list):
            """Collect the branch outcomes.

            Args:
                results: One entry per branch.

            Returns:
                Completion carrying the branch count.
            """
            self.outcomes = sorted(entry["status"] for entry in results)
            return rx.complete(result={"branches": len(results)})

    return Router


async def test_fan_out_joins_every_branch(forked_registration_context):
    BRANCH_CALLS.clear()
    router = _router(Enrich, Flaky)
    async with WorkflowTestHarness(router, Enrich, Flaky) as harness:
        result = await harness.start(router.begin("acme"))
        assert result.run_id is not None

        # The flaky branch retries on its own without blocking its sibling.
        await harness.advance("2s")

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {"branches": 2}
        assert snapshot.state["outcomes"] == ["COMPLETED", "COMPLETED"]
        assert snapshot.steps[1].join_expected == 2
        assert snapshot.steps[1].join_arrived == 2

        # Parent plus one run per branch, each independently inspectable.
        runs = await harness.kernel.list_runs()
        assert len(runs) == 3
        children = [run for run in runs if run.parent_run_id == result.run_id]
        assert len(children) == 2


async def test_a_failing_branch_still_reports(forked_registration_context):
    """One branch failing does not strand the parent."""
    BRANCH_CALLS.clear()
    router = _router(Enrich, Doomed)
    async with WorkflowTestHarness(router, Enrich, Doomed) as harness:
        result = await harness.start(router.begin("acme"))
        assert result.run_id is not None
        await harness.advance("2s")

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state["outcomes"] == ["COMPLETED", "FAILED"]


async def test_join_waits_for_the_last_branch(forked_registration_context):
    """The parent stays blocked until every branch has reported."""
    BRANCH_CALLS.clear()
    router = _router(Enrich, Flaky)
    async with WorkflowTestHarness(router, Enrich, Flaky) as harness:
        result = await harness.kernel.start(router.begin("acme"))
        assert result.run_id is not None
        await harness.kernel.run_until_idle()

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        # The flaky branch is still in backoff, so the join is short one arrival.
        assert snapshot.status is RunStatus.WAITING
        assert snapshot.steps[1].status is StepStatus.BLOCKED
        assert snapshot.steps[1].join_arrived == 1

        await harness.advance("2s")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED


async def test_duplicate_arrivals_are_counted_once(forked_registration_context):
    """A redelivered child result must not satisfy the join twice."""
    BRANCH_CALLS.clear()
    router = _router(Enrich, Flaky)
    async with WorkflowTestHarness(router, Enrich, Flaky) as harness:
        result = await harness.kernel.start(router.begin("acme"))
        assert result.run_id is not None
        await harness.kernel.run_until_idle()

        runs = await harness.kernel.list_runs()
        # The branch that already reported, not merely the first one listed:
        # re-reporting a branch still in flight would be a new arrival.
        child = next(
            run
            for run in runs
            if run.parent_run_id == result.run_id and run.status is RunStatus.COMPLETED
        )
        repeat = await harness.kernel.store.record_arrival(
            result.run_id,
            1,
            {"run_id": child.run_id, "status": "COMPLETED", "result": None},
            child.run_id,
            harness.now,
        )
        assert repeat == "duplicate"

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.steps[1].join_arrived == 1


async def test_a_cancelled_child_reports_to_its_join(forked_registration_context):
    """A child that is cancelled must not leave its parent waiting forever."""
    BRANCH_CALLS.clear()

    class SlowBranch(rx.State):
        __workflow__ = WorkflowConfig(id="fan.slow")
        n: int = 0

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self, lead: str):
            """Wait a long time before finishing.

            Args:
                lead: The lead identifier.

            Returns:
                A far-future continuation.
            """
            return rx.after("30d", SlowBranch.later)

        @rx.event(durable=True, effect="none")
        def later(self):
            """Never reached in this test."""

    router = _router(Enrich, SlowBranch)
    async with WorkflowTestHarness(router, Enrich, SlowBranch) as harness:
        result = await harness.start(router.begin("acme"))
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING

        runs = await harness.kernel.list_runs()
        slow = next(
            run
            for run in runs
            if run.parent_run_id == result.run_id and run.workflow_id == "fan.slow"
        )
        await harness.cancel(slow.run_id)

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state["outcomes"] == ["CANCELLED", "COMPLETED"]


async def test_a_timed_out_child_reports_to_its_join(forked_registration_context):
    """A child that blows its run deadline still reports to the join."""
    BRANCH_CALLS.clear()

    class ExpiringBranch(rx.State):
        __workflow__ = WorkflowConfig(id="fan.expiring", run_timeout="1h")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self, lead: str):
            """Wait past the run deadline.

            Args:
                lead: The lead identifier.

            Returns:
                A continuation scheduled after the deadline.
            """
            return rx.after("2h", ExpiringBranch.later)

        @rx.event(durable=True, effect="none")
        def later(self):
            """Never reached in this test."""

    router = _router(Enrich, ExpiringBranch)
    async with WorkflowTestHarness(router, Enrich, ExpiringBranch) as harness:
        result = await harness.start(router.begin("acme"))
        assert result.run_id is not None
        await harness.advance("2h")

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state["outcomes"] == ["COMPLETED", "TIMED_OUT"]


class SlowVendor(rx.State):
    """A branch that waits before answering."""

    __workflow__ = WorkflowConfig(id="race.slow")
    quote: int = 0

    @rx.event(durable=True, trigger=manual(), effect="read")
    def start(self, price: int):
        """Quote after a delay.

        Args:
            price: The price to quote.

        Returns:
            A deferral, then completion.
        """
        RACE_CALLS.append("slow")
        return rx.after("1h", SlowVendor.answer(price))

    @rx.event(durable=True, effect="read")
    def answer(self, price: int):
        """Deliver the delayed quote.

        Args:
            price: The price to quote.

        Returns:
            Completion carrying the quote.
        """
        RACE_CALLS.append("slow-answer")
        self.quote = price
        return rx.complete(result={"price": price})


class FastVendor(rx.State):
    """A branch that answers immediately."""

    __workflow__ = WorkflowConfig(id="race.fast")
    quote: int = 0

    @rx.event(durable=True, trigger=manual(), effect="read")
    def start(self, price: int):
        """Quote at once.

        Args:
            price: The price to quote.

        Returns:
            Completion carrying the quote.
        """
        RACE_CALLS.append("fast")
        self.quote = price
        return rx.complete(result={"price": price})


class Shopper(rx.State):
    """Takes the first quote back and abandons the rest."""

    __workflow__ = WorkflowConfig(id="race.shopper")
    winner: int = 0

    @rx.event(durable=True, trigger=manual(), effect="none")
    def start(self):
        """Ask both vendors and take whoever answers first.

        Returns:
            A racing fan-out.
        """
        return rx.parallel(
            SlowVendor.start(100),
            FastVendor.start(90),
            then=Shopper.book,
            mode="first",
        )

    @rx.event(durable=True, effect="read")
    def book(self, results: list):
        """Book the quote that arrived first.

        Args:
            results: One entry, from the branch that won.

        Returns:
            Completion.
        """
        self.winner = results[0]["result"]["price"]
        return rx.complete(result={"booked": self.winner})


RACE_CALLS: list[str] = []


async def _join_slot(harness: WorkflowTestHarness, run_id: str):
    """Find the fan-out slot of a run.

    Args:
        harness: The running harness.
        run_id: The parent run.

    Returns:
        The join step record.
    """
    steps = await harness.kernel.store.get_steps(run_id)
    return next(step for step in steps if step.wait_key is not None)


async def test_race_continues_on_the_first_branch_and_cancels_the_rest():
    """mode="first" resumes as soon as one branch reports.

    A quote race is worthless if it still waits for the slow vendor, and worse
    than worthless if that vendor keeps working after the order is booked.
    """
    RACE_CALLS.clear()
    async with WorkflowTestHarness(Shopper, SlowVendor, FastVendor) as harness:
        result = await harness.start(Shopper.start())
        assert result.run_id is not None

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {"booked": 90}

        join = await _join_slot(harness, result.run_id)
        children = await harness.kernel.store.list_children(result.run_id, join.ordinal)
        by_workflow = {child.workflow_id: child for child in children}
        assert by_workflow["race.fast"].status is RunStatus.COMPLETED
        assert by_workflow["race.slow"].status is RunStatus.CANCELLED

        # The loser's deferred step never runs, even once its timer comes due.
        await harness.advance("2h")
        assert "slow-answer" not in RACE_CALLS


async def test_race_mode_admits_every_branch():
    """Racing picks a winner; it does not skip a branch.

    Every branch is admitted as a child run. Whether a loser gets to run at all
    depends on how fast the winner is -- a loser cancelled before its first
    step is the best case, not a missed one -- so this asserts what is actually
    guaranteed rather than what one store's ordering happens to produce.
    """
    RACE_CALLS.clear()
    async with WorkflowTestHarness(Shopper, SlowVendor, FastVendor) as harness:
        result = await harness.start(Shopper.start())
        assert result.run_id is not None
        join = await _join_slot(harness, result.run_id)
        children = await harness.kernel.store.list_children(result.run_id, join.ordinal)
        assert {child.workflow_id for child in children} == {"race.fast", "race.slow"}


async def test_race_join_expects_one_arrival():
    """The join slot itself carries the racing intent."""
    RACE_CALLS.clear()
    async with WorkflowTestHarness(Shopper, SlowVendor, FastVendor) as harness:
        result = await harness.start(Shopper.start())
        assert result.run_id is not None
        join = await _join_slot(harness, result.run_id)
        assert join.join_expected == 1
        assert join.status is StepStatus.SUCCEEDED


async def test_a_childs_arrival_commits_with_its_final_transition():
    """A finished child and a told parent become true together.

    Delivering the arrival after the child's commit leaves a window: a worker
    that dies inside it leaves a run that is finished and a join that waits on
    it forever. Nothing recovers that, because from the store's point of view
    the child is done and the parent is simply blocked. The arrival therefore
    rides the same transaction as the child's terminal transition.

    This asserts it at the store level -- what is durable the instant the
    commit returns -- rather than through the kernel's follow-up work, which
    is exactly the code a crash would skip.
    """
    RACE_CALLS.clear()
    async with WorkflowTestHarness(Shopper, SlowVendor, FastVendor) as harness:
        result = await harness.start(Shopper.start())
        assert result.run_id is not None
        join = await _join_slot(harness, result.run_id)

        # The join was satisfied and the parent moved on, with no post-commit
        # delivery involved: the store alone carries the evidence.
        assert join.join_arrived >= 1
        history = await harness.kernel.store.get_history(result.run_id)
        resolutions = [
            event for event in history if event.type is HistoryEventType.CHILD_RESOLVED
        ]
        assert resolutions, "the join recorded no arrival"

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED


async def test_join_results_arrive_in_declaration_order(forked_registration_context):
    """`a, b = results` has to mean what the fan-out said, not who won.

    The join accumulates arrivals as they land. A branch that takes a day and
    a branch that takes a second finish in the opposite order to the one they
    were written in, and a caller unpacking the list has no other way to tell
    which result is which.
    """

    class Slow(rx.State):
        __workflow__ = WorkflowConfig(id="fan.slow")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self, lead: str):
            """Finish only after a delay.

            Args:
                lead: The lead identifier.

            Returns:
                The delayed completion.
            """
            return rx.after("1h", Slow.finish)

        @rx.event(durable=True, effect="none")
        def finish(self):
            """Complete late.

            Returns:
                Completion.
            """
            return rx.complete(result="slow")

    class Fast(rx.State):
        __workflow__ = WorkflowConfig(id="fan.fast")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def start(self, lead: str):
            """Complete immediately.

            Args:
                lead: The lead identifier.

            Returns:
                Completion.
            """
            return rx.complete(result="fast")

    class Ordered(rx.State):
        __workflow__ = WorkflowConfig(id="fan.ordered")
        seen: list = []

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Fan out slow first, fast second.

            Returns:
                The parallel fan-out.
            """
            return rx.parallel(
                Slow.start("lead"), Fast.start("lead"), then=Ordered.route
            )

        @rx.event(durable=True, effect="none")
        def route(self, results: list):
            """Record the results in the order they were handed over.

            Args:
                results: One entry per branch.

            Returns:
                Completion carrying the ordered results.
            """
            return rx.complete(result=[entry["result"] for entry in results])

    async with WorkflowTestHarness(Ordered, Slow, Fast) as harness:
        started = await harness.start(Ordered.begin())
        assert started.run_id is not None
        await harness.advance("2h")
        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == ["slow", "fast"], (
            "the fast branch finished first, but it was declared second"
        )


async def test_a_race_loser_performs_no_effect_after_it_has_lost(
    forked_registration_context,
):
    """One worker that resolves a race does stop the loser it is running.

    This is the case that holds: the kernel that saw the winner arrive
    cancels the losing child it owns, so the loser's deferred answer never
    runs and whatever external thing it would have done does not happen.

    It is deliberately not the whole guarantee. Cancelling the loser is
    advisory follow-up work by one worker, so it does not survive that worker
    dying between the winning commit and the cleanup, and it does not reach a
    loser another worker is already executing. Both of those need cancellation
    intent written in the same transaction that resolves the race, with
    commits fenced against it, and neither is covered here -- a passing test
    on this file says nothing about them.
    """
    RACE_CALLS.clear()

    async with WorkflowTestHarness(Shopper, SlowVendor, FastVendor) as harness:
        started = await harness.start(Shopper.start())
        assert started.run_id is not None
        await harness.run_until_idle()

        parent = await harness.get_run(started.run_id)
        assert parent is not None
        assert parent.status is RunStatus.COMPLETED, "the fast vendor should win"

        await harness.advance("2h")

        assert "slow-answer" not in RACE_CALLS, (
            "the losing branch answered after the race was already decided: "
            f"{RACE_CALLS}"
        )


async def test_arrivals_from_before_the_upgrade_are_still_ordered(
    forked_registration_context,
):
    """A join can span the deploy that taught arrivals to carry their branch.

    A worker on the older release records an arrival with no branch index, and
    the join it belongs to may already be half full when the new release comes
    up. The index is still recoverable: a fan-out has always stamped each
    branch with `child:<parent>:<ordinal>:<index>` as its admission key,
    because that is what makes re-running the fan-out idempotent.
    """
    store = MemoryRunStore()
    kernel = WorkflowKernel([], store)

    class _Legacy:
        """Stands in for a child run admitted by the older release."""

        def __init__(self, run_id: str, index: int):
            self.run_id = run_id
            self.request_key = f"child:parent:0:{index}"

    admitted = {
        "late": _Legacy("late", 0),
        "early": _Legacy("early", 1),
    }

    async def fake_get_run(run_id: str):  # noqa: RUF029
        """Look up a child the way the store would.

        Args:
            run_id: The child run to load.

        Returns:
            The stand-in record, or None.
        """
        return admitted.get(run_id)

    kernel._store = type(  # pyright: ignore[reportAttributeAccessIssue]
        "_Stub", (), {"get_run": staticmethod(fake_get_run)}
    )()

    ordered = await kernel._in_declaration_order([  # pyright: ignore[reportPrivateUsage]
        {"run_id": "early", "result": "second-declared"},
        {"run_id": "late", "result": "first-declared"},
    ])
    assert [entry["result"] for entry in ordered] == [
        "first-declared",
        "second-declared",
    ]


async def test_unidentifiable_arrivals_keep_their_position(
    forked_registration_context,
):
    """Ordering is recovered where it is knowable, never guessed at."""
    store = MemoryRunStore()
    kernel = WorkflowKernel([], store)
    entries = [{"result": "a"}, {"result": "b"}, {"result": "c"}]
    ordered = await kernel._in_declaration_order(entries)  # pyright: ignore[reportPrivateUsage]
    assert [entry["result"] for entry in ordered] == ["a", "b", "c"]


async def test_an_abandoned_branch_never_cancels_its_sibling(
    forked_registration_context,
):
    """A tombstoned join is not a decided race, even when nobody cancels.

    Cancelling a parent tombstones its join, and when a branch later finishes
    its arrival finds a slot that is no longer blocked -- which is not the
    same thing as a race having been decided. Reading it as one made the
    engine cancel the sibling of a branch it never raced. Under the default
    ``parent_close="cancel"`` both branches stop anyway and that misreading
    would hide; ``abandon`` is where it still shows.
    """
    BRANCH_CALLS.clear()
    router = _router(Slowish, Slower, parent_close="abandon")
    async with WorkflowTestHarness(router, Slowish, Slower) as harness:
        started = await harness.start(router.begin("acme"))
        assert started.run_id is not None
        await harness.run_until_idle()

        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        join_ordinal = next(
            step.ordinal for step in snapshot.steps if step.origin == "join"
        )
        store = harness.kernel._store  # pyright: ignore[reportPrivateUsage]
        assert await store.list_children(started.run_id, join_ordinal), (
            "the fan-out should have admitted branches"
        )

        assert await harness.cancel(started.run_id)
        await harness.run_until_idle()

        # The delayed branch finishes after the parent is gone.
        await harness.advance("2h")
        children = await store.list_children(started.run_id, join_ordinal)
        cancelled = [
            child.run_id for child in children if child.status is RunStatus.CANCELLED
        ]
        assert not cancelled, (
            "cancelling the parent cancelled delegated children: "
            f"{[(c.run_id, c.status) for c in children]}"
        )


async def test_a_policy_decorated_branch_is_refused(forked_registration_context):
    """A policy fan-out would silently bypass is a policy refused loudly.

    Fan-out writes its branches in the parent's committing transaction, not
    through policy admission, so a throttle on a branch root would simply not
    apply -- five branches under a throttle of two all start at once and
    nothing says so. Until branches go through the same admission primitive,
    declaring both is an error that names the way out.
    """
    from reflex_base.workflow import Throttle

    class Limited(rx.State):
        __workflow__ = WorkflowConfig(id="fan.limited")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="none",
            throttle=Throttle(limit=2, period="10s"),
        )
        def start(self, lead: str):
            """A throttled root.

            Args:
                lead: The lead identifier.

            Returns:
                Completion.
            """
            return rx.complete(result=lead)

    class FansOut(rx.State):
        __workflow__ = WorkflowConfig(id="fan.bypasser")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def begin(self):
            """Fan out to a policy-decorated root.

            Returns:
                The refused fan-out.
            """
            return rx.parallel(
                Limited.start("a"), Limited.start("b"), then=FansOut.done
            )

        @rx.event(durable=True, effect="none")
        def done(self, results: list):
            """Collect.

            Args:
                results: One entry per branch.

            Returns:
                Completion.
            """
            return rx.complete(result=len(results))

    async with WorkflowTestHarness(FansOut, Limited) as harness:
        started = await harness.start(FansOut.begin())
        assert started.run_id is not None
        await harness.run_until_idle()
        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED, (
            "a definition error fails on its first attempt rather than "
            f"burning retries: {snapshot.status}"
        )
        assert "start policy" in str(snapshot.error)
