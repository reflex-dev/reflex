"""Tests for start policies: singleton, debounce, rate limit, and throttle."""

import pytest
from pydantic import BaseModel
from reflex_base.utils.exceptions import WorkflowDefinitionError
from reflex_base.workflow import (
    Debounce,
    RateLimit,
    Singleton,
    Throttle,
    WorkflowConfig,
    after,
    manual,
)

import reflex as rx
from reflex.workflow.definition import compile_workflow
from reflex.workflow.records import RunStatus
from reflex.workflow.testing import WorkflowTestHarness


def _singleton_flow(mode: str = "skip"):
    """Build a workflow allowing one active run per customer.

    Args:
        mode: The singleton mode to apply.

    Returns:
        The workflow class.
    """

    class SyncFlow(rx.State):
        __workflow__ = WorkflowConfig(id="flow.sync")
        cid: str = ""

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="idempotent_write",
            singleton=Singleton(key="cid", mode=mode),  # pyright: ignore[reportArgumentType]
        )
        def start(self, cid: str):
            """Begin a long sync.

            Args:
                cid: The customer identifier.

            Returns:
                A delayed finish step.
            """
            self.cid = cid
            return after("1h", SyncFlow.finish)

        @rx.event(durable=True, effect="none")
        def finish(self):
            """Finish the sync."""

    return SyncFlow


async def test_singleton_skips_a_second_start(forked_registration_context):
    flow = _singleton_flow()
    async with WorkflowTestHarness(flow) as harness:
        first = await harness.start(flow.start("acme"))
        second = await harness.kernel.start(flow.start("acme"))
        assert first.disposition == "started"
        assert second.disposition == "skipped"
        assert second.run_id == first.run_id
        assert len(await harness.kernel.list_runs()) == 1


async def test_singleton_is_per_key(forked_registration_context):
    flow = _singleton_flow()
    async with WorkflowTestHarness(flow) as harness:
        await harness.start(flow.start("acme"))
        other = await harness.kernel.start(flow.start("globex"))
        assert other.disposition == "started"
        assert len(await harness.kernel.list_runs()) == 2


async def test_singleton_cancel_mode_replaces_the_active_run(
    forked_registration_context,
):
    flow = _singleton_flow(mode="cancel")
    async with WorkflowTestHarness(flow) as harness:
        first = await harness.start(flow.start("acme"))
        assert first.run_id is not None
        second = await harness.start(flow.start("acme"))
        assert second.disposition == "started"
        assert second.run_id != first.run_id

        superseded = await harness.get_run(first.run_id)
        assert superseded is not None
        assert superseded.status is RunStatus.CANCELLED


async def test_singleton_frees_the_key_when_the_run_finishes(
    forked_registration_context,
):
    flow = _singleton_flow()
    async with WorkflowTestHarness(flow) as harness:
        first = await harness.start(flow.start("acme"))
        assert first.run_id is not None
        await harness.advance("1h")
        assert (await harness.get_run(first.run_id)).status is RunStatus.COMPLETED  # pyright: ignore[reportOptionalMemberAccess]

        again = await harness.kernel.start(flow.start("acme"))
        assert again.disposition == "started"


async def test_debounce_collapses_a_burst(forked_registration_context):
    calls = []

    class BurstFlow(rx.State):
        __workflow__ = WorkflowConfig(id="flow.burst")
        cid: str = ""

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="none",
            debounce=Debounce(period="30s", key="cid"),
        )
        def start(self, cid: str):
            """Handle the collapsed burst.

            Args:
                cid: The customer identifier.
            """
            calls.append(cid)
            self.cid = cid

    async with WorkflowTestHarness(BurstFlow) as harness:
        first = await harness.kernel.start(BurstFlow.start("acme"))
        second = await harness.kernel.start(BurstFlow.start("acme"))
        third = await harness.kernel.start(BurstFlow.start("acme"))
        assert first.disposition == "started"
        assert second.disposition == "coalesced"
        assert third.disposition == "coalesced"
        assert second.run_id == first.run_id

        # Nothing has run yet: the window is still open.
        await harness.kernel.run_until_idle()
        assert calls == []

        await harness.advance("31s")
        assert calls == ["acme"]
        assert len(await harness.kernel.list_runs()) == 1


async def test_rate_limit_drops_the_excess(forked_registration_context):
    class CappedFlow(rx.State):
        __workflow__ = WorkflowConfig(id="flow.capped")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="none",
            rate_limit=RateLimit(limit=2, period="1m"),
        )
        def start(self):
            """Do the capped work."""

    async with WorkflowTestHarness(CappedFlow) as harness:
        dispositions = [
            (await harness.kernel.start(CappedFlow.start)).disposition for _ in range(4)
        ]
        assert dispositions == ["started", "started", "rejected", "rejected"]

        rejected = await harness.kernel.start(CappedFlow.start)
        assert rejected.retryable
        assert rejected.retry_after == pytest.approx(60.0)

        # The window rolls forward and starts are allowed again.
        await harness.advance("61s")
        assert (await harness.kernel.start(CappedFlow.start)).disposition == "started"


async def test_throttle_delays_the_excess(forked_registration_context):
    calls = []

    class ThrottledFlow(rx.State):
        __workflow__ = WorkflowConfig(id="flow.throttled")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="none",
            throttle=Throttle(limit=1, period="1m"),
        )
        def start(self):
            """Do the throttled work."""
            calls.append(1)

    async with WorkflowTestHarness(ThrottledFlow) as harness:
        first = await harness.start(ThrottledFlow.start)
        assert first.disposition == "started"
        assert len(calls) == 1

        # The excess is admitted but held back rather than dropped.
        second = await harness.start(ThrottledFlow.start)
        assert second.disposition == "started"
        assert len(calls) == 1

        await harness.advance("61s")
        assert len(calls) == 2


def test_start_policy_key_must_name_a_parameter(forked_registration_context):
    class BadKey(rx.State):
        __workflow__ = WorkflowConfig(id="flow.bad_key")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="none",
            singleton=Singleton(key="customer"),
        )
        def start(self, cid: str):
            """Start with a mismatched key.

            Args:
                cid: The customer identifier.
            """

    with pytest.raises(WorkflowDefinitionError, match="neither a parameter"):
        compile_workflow(BadKey)


def test_start_policies_require_a_trigger():
    with pytest.raises(WorkflowDefinitionError, match="needs a trigger"):

        @rx.event(durable=True, effect="none", singleton=Singleton())
        def handler(self):
            pass


def test_only_one_start_policy_per_root():
    with pytest.raises(WorkflowDefinitionError, match="one start policy"):

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="none",
            singleton=Singleton(),
            rate_limit=RateLimit(limit=1, period="1m"),
        )
        def handler(self):
            pass


def test_browser_throttle_still_works_on_session_handlers(
    forked_registration_context,
):
    """The int form of throttle and debounce stays a browser event action."""

    class Clicky(rx.State):
        @rx.event(throttle=200, debounce=100)
        def click(self):
            pass

    assert Clicky.event_handlers["click"].event_actions == {
        "throttle": 200,
        "debounce": 100,
    }


async def test_singleton_cancel_keeps_one_active_run_per_key(
    forked_registration_context,
):
    """Replacing the active run must not leave both of them active."""
    flow = _singleton_flow(mode="cancel")
    async with WorkflowTestHarness(flow) as harness:
        for _ in range(3):
            await harness.kernel.start(flow.start("acme"))
        active = await harness.kernel.store.count_active("flow.sync", "start:'acme'")
        assert active == 1


async def test_throttle_spaces_a_backlog_instead_of_bunching_it(
    forked_registration_context,
):
    """A held-back burst must not all fire at the same instant.

    Deferring every excess start by one window turns a burst of a hundred into
    a burst of ninety, one window later. The provider the throttle exists to
    protect sees the same spike, just delayed.
    """
    calls: list[int] = []

    class Spaced(rx.State):
        __workflow__ = WorkflowConfig(id="flow.spaced")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="none",
            throttle=Throttle(limit=2, period="10s"),
        )
        def start(self):
            """Record that this run ran."""
            calls.append(1)

    async with WorkflowTestHarness(Spaced) as harness:
        begin = harness.now
        run_ids = []
        for _ in range(6):
            result = await harness.start(Spaced.start)
            assert result.disposition == "started"
            assert result.run_id is not None
            run_ids.append(result.run_id)
        assert len(calls) == 2

        due = []
        for run_id in run_ids:
            steps = await harness.kernel.store.get_steps(run_id)
            due.append(max(steps[0].due_at, begin) - begin)
        assert due == [0.0, 0.0, 10.0, 10.0, 20.0, 20.0]

        await harness.advance("10s")
        assert len(calls) == 4
        await harness.advance("10s")
        assert len(calls) == 6


async def test_singleton_can_key_on_a_model_field(forked_registration_context):
    """A webhook root's key lives inside its one typed parameter.

    ``dedupe_by=`` already reaches into the payload; a grouping key that could
    not was an inconsistency every generated workflow would trip over, because
    a webhook root's whole payload is a single model argument.
    """

    class Order(BaseModel):
        order_id: str
        amount: int

    class PerOrder(rx.State):
        __workflow__ = WorkflowConfig(id="flow.perorder")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="none",
            singleton=Singleton(key="order_id", mode="skip"),
        )
        def start(self, evt: Order):
            """Hold the run open so a duplicate can be judged.

            Args:
                evt: The order payload.

            Returns:
                A long deferral.
            """
            return after("1h", PerOrder.finish)

        @rx.event(durable=True, effect="none")
        def finish(self):
            """Complete."""

    async with WorkflowTestHarness(PerOrder) as harness:
        first = await harness.start(PerOrder.start(Order(order_id="A", amount=1)))
        duplicate = await harness.start(PerOrder.start(Order(order_id="A", amount=2)))
        other = await harness.start(PerOrder.start(Order(order_id="B", amount=3)))

    assert first.disposition == "started"
    assert duplicate.disposition == "skipped"
    assert other.disposition == "started"


def test_a_key_matching_nothing_is_a_compile_error(forked_registration_context):
    """A key that is neither parameter nor model field is named at compile."""

    class Payload(BaseModel):
        order_id: str

    with pytest.raises(WorkflowDefinitionError, match="neither a parameter"):

        class Mistyped(rx.State):
            __workflow__ = WorkflowConfig(id="flow.mistyped")

            @rx.event(
                durable=True,
                trigger=manual(),
                effect="none",
                singleton=Singleton(key="order_number"),
            )
            def start(self, evt: Payload):
                """Never compiles.

                Args:
                    evt: The payload.
                """

        from reflex.workflow.definition import compile_workflow

        compile_workflow(Mistyped)


def test_an_ambiguous_key_is_a_compile_error(forked_registration_context):
    """Two model parameters carrying the field cannot silently pick one."""

    class Left(BaseModel):
        order_id: str

    class Right(BaseModel):
        order_id: str

    with pytest.raises(WorkflowDefinitionError, match="ambiguous"):

        class TwoSources(rx.State):
            __workflow__ = WorkflowConfig(id="flow.twosources")

            @rx.event(
                durable=True,
                trigger=manual(),
                effect="none",
                singleton=Singleton(key="order_id"),
            )
            def start(self, a: Left, b: Right):
                """Never compiles.

                Args:
                    a: One source.
                    b: The other.
                """

        from reflex.workflow.definition import compile_workflow

        compile_workflow(TwoSources)


async def test_a_singleton_holds_under_concurrent_starts(
    forked_registration_context,
):
    """Two starts racing for one key admit one run, not two.

    Checking "is anything active?" before admitting is a check-then-act race:
    both callers look, both see nothing, both insert. For a singleton that is
    precisely the duplicate the policy exists to prevent -- two dunning runs
    for one invoice, two charges. The limit is therefore enforced inside the
    admitting transaction, and this races six starts to prove it.
    """
    import asyncio

    class OnePerOrder(rx.State):
        __workflow__ = WorkflowConfig(id="flow.oneperorder")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="none",
            singleton=Singleton(key="order_id", mode="skip"),
        )
        def start(self, order_id: str):
            """Hold the run open so the race has something to collide with.

            Args:
                order_id: The order this run belongs to.

            Returns:
                A far-future continuation.
            """
            return after("1h", OnePerOrder.finish)

        @rx.event(durable=True, effect="none")
        def finish(self):
            """Never reached in this test."""

    async with WorkflowTestHarness(OnePerOrder) as harness:
        results = await asyncio.gather(
            *(harness.kernel.start(OnePerOrder.start("ord-1")) for _ in range(6))
        )

        started = [r for r in results if r.disposition == "started"]
        skipped = [r for r in results if r.disposition == "skipped"]
        assert len(started) == 1, f"{len(started)} runs admitted for one key"
        assert len(skipped) == 5
        # Every loser points at the winner, so a caller can find the live run.
        assert {r.run_id for r in skipped} == {started[0].run_id}

        runs = await harness.kernel.list_runs(workflow_id="flow.oneperorder")
        assert len(runs) == 1
