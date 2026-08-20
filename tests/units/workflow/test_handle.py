"""Tests for the typed run handle.

`start()` answers "what happened to my submission"; a handle is what a caller
actually works with afterwards. These cover the operations it carries and the
one case it refuses, since a handle with no run behind it would be a null
waiting to surface later.
"""

import pytest
from pydantic import BaseModel
from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import RateLimit, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.handle import RunHandle
from reflex.workflow.records import RunStatus
from reflex.workflow.testing import WorkflowTestHarness


class Echo(rx.State):
    """Completes immediately with what it was given."""

    __workflow__ = WorkflowConfig(id="handle.echo")
    said: str = ""

    @rx.event(durable=True, trigger=manual(), effect="none")
    def go(self, said: str):
        """Say it back.

        Args:
            said: What to echo.

        Returns:
            Completion.
        """
        self.said = said
        return rx.complete(result={"said": said})


async def test_a_handle_carries_the_run_and_its_result(forked_registration_context):
    """The common path: submit, wait, read what it produced."""
    async with WorkflowTestHarness(Echo) as harness:
        handle = await rx.workflows.submit(Echo.go("hello"))
        assert isinstance(handle, RunHandle)
        assert handle.started
        assert handle.run_id

        # The harness pumps on demand rather than running a worker, so the
        # run is advanced explicitly before the handle reads its outcome.
        await harness.run_until_idle()
        assert await handle.result() == {"said": "hello"}
        assert await handle.status() is RunStatus.COMPLETED
        snapshot = await handle.snapshot()
        assert snapshot is not None
        assert snapshot.state["said"] == "hello"
        _ = harness


async def test_waiting_on_a_run_that_fails_says_so(forked_registration_context):
    """`result()` is for the value, so a failed run raises rather than lying."""

    class Doomed(rx.State):
        __workflow__ = WorkflowConfig(id="handle.doomed")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            """Give up immediately.

            Returns:
                Failure.
            """
            return rx.fail(reason="nope")

    async with WorkflowTestHarness(Doomed) as harness:
        handle = await rx.workflows.submit(Doomed.go)
        await harness.run_until_idle()
        with pytest.raises(WorkflowRuntimeError, match="FAILED"):
            await handle.result()
        # wait() reports the outcome instead of raising on it.
        snapshot = await handle.wait()
        assert snapshot.status is RunStatus.FAILED
        _ = harness


async def test_waiting_past_the_timeout_explains_itself(forked_registration_context):
    """A run that never finishes gets a message naming the likely cause."""

    class Slow(rx.State):
        __workflow__ = WorkflowConfig(id="handle.slow")

        answered = rx.Signal(dict)

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            """Wait forever.

            Returns:
                An unbounded wait.
            """
            return rx.wait_for(Slow.answered, then=Slow.done, timeout=rx.never)

        @rx.event(durable=True, effect="none")
        def done(self, payload: dict):
            """Never reached.

            Args:
                payload: The delivered answer.
            """

    async with WorkflowTestHarness(Slow) as harness:
        handle = await rx.workflows.submit(Slow.go)
        await harness.run_until_idle()
        with pytest.raises(WorkflowRuntimeError, match="still WAITING"):
            await handle.wait(timeout="0.05s", poll_interval=0.01)
        _ = harness


async def test_a_handle_can_signal_and_cancel(forked_registration_context):
    """The operations that belong to a run travel with it."""

    class Paused(rx.State):
        __workflow__ = WorkflowConfig(id="handle.paused")

        answered = rx.Signal(dict)
        answer: str = ""

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            """Wait for an answer.

            Returns:
                An unbounded wait.
            """
            return rx.wait_for(Paused.answered, then=Paused.done, timeout=rx.never)

        @rx.event(durable=True, effect="none")
        def done(self, payload: dict):
            """Record the answer.

            Args:
                payload: The delivered answer.

            Returns:
                Completion.
            """
            self.answer = payload["say"]
            return rx.complete(result={"answer": self.answer})

    async with WorkflowTestHarness(Paused) as harness:
        handle = await rx.workflows.submit(Paused.go)
        await harness.run_until_idle()
        assert await handle.signal(Paused.answered({"say": "yes"})) == "resolved"
        await harness.run_until_idle()
        assert await handle.result() == {"answer": "yes"}

        second = await rx.workflows.submit(Paused.go)
        await harness.run_until_idle()
        assert await second.cancel()
        _ = harness


async def test_a_rejected_submission_refuses_to_hand_back_a_handle(
    forked_registration_context,
):
    """A handle with no run behind it would be a null surfacing later.

    A rate limit rejects outright: there is no run to hold, so submit() says
    so and points at start(), which reports dispositions honestly.
    """

    class Limited(rx.State):
        __workflow__ = WorkflowConfig(id="handle.limited")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="none",
            rate_limit=RateLimit(limit=1, period="1h"),
        )
        def go(self):
            """Do nothing."""

    async with WorkflowTestHarness(Limited) as harness:
        first = await rx.workflows.submit(Limited.go)
        await harness.run_until_idle()
        assert first.started
        with pytest.raises(WorkflowRuntimeError, match="rejected"):
            await rx.workflows.submit(Limited.go)
        _ = harness


class Receipt(BaseModel):
    """What a completed order produces."""

    order: str
    total: int


class Ordering(rx.State):
    """A workflow that completes with a structured result."""

    __workflow__ = WorkflowConfig(id="handle.ordering")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def place(self, order: str):
        """Complete with a receipt.

        Args:
            order: The order identifier.

        Returns:
            Completion carrying the receipt.
        """
        return rx.complete(result={"order": order, "total": 250})

    @rx.event(durable=True, trigger=manual(), effect="none")
    def wrong(self):
        """Complete with something that is not a receipt.

        Returns:
            Completion carrying the wrong shape.
        """
        return rx.complete(result={"order": "ord_1"})


async def test_a_typed_result_comes_back_as_the_declared_shape(
    forked_registration_context,
):
    """A result crosses the store as JSON; ``as_type`` restores the shape.

    Args:
        forked_registration_context: Isolates workflow registration.
    """
    async with WorkflowTestHarness(Ordering) as harness:
        handle = await rx.workflows.submit(Ordering.place("ord_1"))
        await harness.run_until_idle()
        assert await handle.result() == {"order": "ord_1", "total": 250}

        receipt = await handle.result(as_type=Receipt)
        assert isinstance(receipt, Receipt)
        assert receipt.total == 250
        assert receipt.order == "ord_1"


async def test_a_result_that_does_not_fit_names_the_run(forked_registration_context):
    """Validation is real, and its error points at the run that produced it.

    A cast would hand the caller a dict that fails with AttributeError
    somewhere else entirely, long after the information needed to explain it
    has gone.

    Args:
        forked_registration_context: Isolates workflow registration.
    """
    async with WorkflowTestHarness(Ordering) as harness:
        handle = await rx.workflows.submit(Ordering.wrong())
        await harness.run_until_idle()
        with pytest.raises(WorkflowRuntimeError, match="does not fit Receipt"):
            await handle.result(as_type=Receipt)
        assert await handle.result() == {"order": "ord_1"}
