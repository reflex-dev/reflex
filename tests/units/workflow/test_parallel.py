"""Tests for parallel fan-out via child runs."""

from reflex_base.workflow import Retry, TransientWorkflowError, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.records import RunStatus, StepStatus
from reflex.workflow.testing import WorkflowTestHarness

BRANCH_CALLS: list[str] = []


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


def _router(*branches):
    """Build a parent workflow fanning out to the given branches.

    Args:
        branches: The branch classes to fan out to.

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
                *[branch.start(lead) for branch in branches], then=Router.route
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
        child = next(run for run in runs if run.parent_run_id == result.run_id)
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
