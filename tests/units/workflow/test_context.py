"""Tests for the per-attempt run context."""

import pytest
from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import Retry, TransientWorkflowError, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.context import RunContext, current_run, require_run
from reflex.workflow.testing import WorkflowTestHarness

SEEN: list = []


class Reporter(rx.State):
    """Records the context each of its steps ran in."""

    __workflow__ = WorkflowConfig(id="ctx.reporter")
    n: int = 0

    @rx.event(durable=True, trigger=manual(), effect="none")
    def first(self):
        """Note the context, then move on.

        Returns:
            The second step.
        """
        SEEN.append(current_run())
        return Reporter.second

    @rx.event(durable=True, effect="none")
    def second(self):
        """Note the context again."""
        SEEN.append(current_run())


class SyncReporter(rx.State):
    """A synchronous handler, which runs in a worker thread."""

    __workflow__ = WorkflowConfig(id="ctx.sync")

    @rx.event(durable=True, trigger=manual(), effect="none")
    def go(self):
        """Note the context from off the event loop."""
        SEEN.append(current_run())


class Flaky(rx.State):
    """Fails once, so its attempts can be told apart."""

    __workflow__ = WorkflowConfig(id="ctx.flaky")

    @rx.event(
        durable=True,
        trigger=manual(),
        effect="read",
        retry=Retry(max_attempts=3, initial_delay="1s", jitter="none"),
    )
    def go(self):
        """Record the attempt, failing the first time.

        Raises:
            TransientWorkflowError: On the first attempt.
        """
        context = require_run("test")
        SEEN.append((context.attempt, context.idempotency_key()))
        if context.attempt == 1:
            msg = "not yet"
            raise TransientWorkflowError(msg)


async def test_each_step_sees_its_own_identity(forked_registration_context):
    """A handler can learn the run and slot it is executing."""
    SEEN.clear()
    async with WorkflowTestHarness(Reporter) as harness:
        result = await harness.start(Reporter.first)

    assert len(SEEN) == 2
    first, second = SEEN
    assert isinstance(first, RunContext)
    assert isinstance(second, RunContext)
    assert first.run_id == result.run_id == second.run_id
    assert first.workflow_id == "ctx.reporter"
    assert (first.handler_id, second.handler_id) == ("first", "second")
    assert first.ordinal < second.ordinal


async def test_a_sync_handler_sees_it_too(forked_registration_context):
    """Running off the event loop must not lose the context."""
    SEEN.clear()
    async with WorkflowTestHarness(SyncReporter) as harness:
        await harness.start(SyncReporter.go)

    assert len(SEEN) == 1
    assert isinstance(SEEN[0], RunContext)
    assert SEEN[0].workflow_id == "ctx.sync"


async def test_the_idempotency_key_survives_a_retry(forked_registration_context):
    """Retrying a step is the same logical call, so the key must not move.

    A payment API keyed on this would otherwise charge twice on a retry, which
    is the exact failure the key exists to prevent.
    """
    SEEN.clear()
    async with WorkflowTestHarness(Flaky) as harness:
        await harness.start(Flaky.go)
        await harness.advance("2s")

    assert [attempt for attempt, _ in SEEN] == [1, 2]
    assert len({key for _, key in SEEN}) == 1


async def test_different_steps_get_different_keys(forked_registration_context):
    """Two steps of one run must not share an idempotency key."""
    SEEN.clear()
    async with WorkflowTestHarness(Reporter) as harness:
        await harness.start(Reporter.first)

    first, second = SEEN
    assert isinstance(first, RunContext)
    assert isinstance(second, RunContext)
    assert first.idempotency_key() != second.idempotency_key()
    assert first.idempotency_key() != first.idempotency_key(scope="second-call")


def test_there_is_no_context_outside_a_handler():
    """Ordinary application code sees None, not a stale attempt."""
    assert current_run() is None
    with pytest.raises(WorkflowRuntimeError, match="durable"):
        require_run("something")
