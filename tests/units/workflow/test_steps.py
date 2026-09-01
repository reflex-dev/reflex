"""Tests for recorded substeps inside a durable handler.

The contract under test: ``rx.step`` runs its callable exactly once per
logical step, no matter how many times the handler itself runs -- and what it
returns is the recorded serialized form on every attempt, so replays are
indistinguishable from first executions.
"""

import pytest
from pydantic import BaseModel
from reflex_base.utils.exceptions import WorkflowRuntimeError
from reflex_base.workflow import Retry, TransientWorkflowError, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.records import HistoryEventType, RunStatus
from reflex.workflow.steps import substep_results
from reflex.workflow.testing import WorkflowTestHarness

CALLS: list[str] = []


def charge_card(amount: int) -> dict:
    """Pretend to charge a card.

    Args:
        amount: Cents to charge.

    Returns:
        The provider's response.
    """
    CALLS.append("charge")
    return {"charge_id": "ch_1", "amount": amount}


def create_label(order: str) -> dict:
    """Pretend to create a shipping label, failing until the third try.

    Args:
        order: The order id.

    Returns:
        The label.

    Raises:
        TransientWorkflowError: While the carrier is down.
    """
    CALLS.append("label")
    if CALLS.count("label") < 3:
        msg = "carrier down"
        raise TransientWorkflowError(msg)
    return {"label_id": "lb_1", "order": order}


class Fulfil(rx.State):
    """Charge, then label; the charge must survive label retries."""

    __workflow__ = WorkflowConfig(id="steps.fulfil")
    order: str = ""

    @rx.event(
        durable=True,
        trigger=manual(),
        effect="idempotent_write",
        retry=Retry(max_attempts=5, initial_delay="1s", jitter="none"),
    )
    async def start(self, order: str):
        """Charge the card once, then keep trying the label.

        Args:
            order: The order id.

        Returns:
            Completion carrying both results.
        """
        self.order = order
        charge = await rx.step("charge", charge_card, 2500)
        label = await rx.step("label", create_label, order)
        return rx.complete(result={"charge": charge, "label": label})


async def test_a_recorded_substep_does_not_rerun_on_retry(
    forked_registration_context,
):
    """The reason this feature exists: retrying the label must not recharge.

    The handler fails twice at the label step. Without the journal each retry
    would call charge_card again -- three charges for one order. With it, the
    charge records on attempt one and replays on attempts two and three.
    """
    CALLS.clear()
    async with WorkflowTestHarness(Fulfil) as harness:
        result = await harness.start(Fulfil.start("ord_1"))
        assert result.run_id is not None
        await harness.advance("1s")
        await harness.advance("2s")

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {
            "charge": {"charge_id": "ch_1", "amount": 2500},
            "label": {"label_id": "lb_1", "order": "ord_1"},
        }
    assert CALLS.count("charge") == 1
    assert CALLS.count("label") == 3


async def test_substeps_survive_a_crashed_worker(forked_registration_context):
    """Work recorded before a crash is not repeated after recovery.

    A worker claims the step, records the charge, and dies without committing
    anything -- the exact shape of a SIGKILL between two API calls. The
    recovered attempt must replay the recorded charge rather than make it
    again, because the money already moved.
    """
    CALLS.clear()

    def charge_once() -> dict:
        """Make the charge, noting that it ran.

        Returns:
            The charge.
        """
        CALLS.append("charge")
        return {"charge_id": "ch_crash"}

    class Crashy(rx.State):
        __workflow__ = WorkflowConfig(id="steps.crashy")

        @rx.event(durable=True, trigger=manual(), effect="idempotent_write")
        async def go(self):
            """Charge exactly once across worker deaths.

            Returns:
                Completion.
            """
            charge = await rx.step("charge", charge_once)
            return rx.complete(result=charge)

    async with WorkflowTestHarness(Crashy, lease_duration="30s") as harness:
        store = harness.kernel.store
        result = await harness.start_only(Crashy.go)
        assert result.run_id is not None

        # A doomed worker claims the step and records the charge -- exactly
        # what the store sees when a real worker dies mid-handler -- then
        # never commits, renews, or releases.
        claim = await store.claim_next(harness.now, lease_duration=30.0)
        assert claim is not None
        recorded = await store.record_substep(
            claim.run.run_id,
            claim.step.ordinal,
            claim.step.epoch,
            "charge",
            {"charge_id": "ch_crash"},
            harness.now,
        )
        assert recorded

        # Its lease lapses; recovery reclaims the step and the surviving
        # worker runs the handler, which must skip the recorded charge.
        await harness.advance("31s")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {"charge_id": "ch_crash"}
    assert CALLS == []


async def test_a_looped_name_is_numbered_by_occurrence(forked_registration_context):
    """Each iteration of a loop is its own recorded step."""
    sent: list[str] = []

    def send(to: str) -> str:
        """Send one message.

        Args:
            to: The recipient.

        Returns:
            A receipt.
        """
        sent.append(to)
        return f"receipt-{to}"

    class Blast(rx.State):
        __workflow__ = WorkflowConfig(id="steps.blast")

        @rx.event(durable=True, trigger=manual(), effect="idempotent_write")
        async def go(self):
            """Send to three recipients with one step name.

            Returns:
                Completion carrying the receipts.
            """
            receipts = [await rx.step("send", send, name) for name in ("a", "b", "c")]
            assert set(substep_results()) == {"send", "send#2", "send#3"}
            return rx.complete(result={"receipts": receipts})

    async with WorkflowTestHarness(Blast) as harness:
        result = await harness.start(Blast.go)
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.result == {"receipts": ["receipt-a", "receipt-b", "receipt-c"]}
    assert sent == ["a", "b", "c"]


async def test_sync_handlers_use_the_same_call(forked_registration_context):
    """A sync handler calls rx.step without await and gets the value."""
    CALLS.clear()

    class SyncFulfil(rx.State):
        __workflow__ = WorkflowConfig(id="steps.sync")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="idempotent_write",
            retry=Retry(max_attempts=3, initial_delay="1s", jitter="none"),
        )
        def go(self):
            """Charge then flake, from a thread.

            Returns:
                Completion.

            Raises:
                TransientWorkflowError: On the first attempt.
            """
            charge = rx.step("charge", charge_card, 900)
            if CALLS.count("charge") == 1 and len(CALLS) == 1:
                CALLS.append("flake")
                msg = "later step failed"
                raise TransientWorkflowError(msg)
            return rx.complete(result=charge)

    async with WorkflowTestHarness(SyncFulfil) as harness:
        result = await harness.start(SyncFulfil.go)
        assert result.run_id is not None
        await harness.advance("1s")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {"charge_id": "ch_1", "amount": 900}
    assert CALLS.count("charge") == 1


async def test_model_results_come_back_as_plain_data(forked_registration_context):
    """The first attempt sees the same shape a replay would.

    If the first execution returned the live model while a retry returned the
    recorded dict, code would only break during retries. Both see the recorded
    form.
    """

    class Quote(BaseModel):
        price: int
        vendor: str

    def fetch_quote() -> Quote:
        """Produce a typed result.

        Returns:
            The quote.
        """
        return Quote(price=42, vendor="acme")

    seen: list = []

    class Quoted(rx.State):
        __workflow__ = WorkflowConfig(id="steps.quoted")

        @rx.event(durable=True, trigger=manual(), effect="read")
        async def go(self):
            """Fetch a typed quote through a step.

            Returns:
                Completion.
            """
            quote = await rx.step("quote", fetch_quote)
            seen.append(quote)
            return rx.complete(result=quote)

    async with WorkflowTestHarness(Quoted) as harness:
        result = await harness.start(Quoted.go)
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.result == {"price": 42, "vendor": "acme"}
    assert seen == [{"price": 42, "vendor": "acme"}]


async def test_an_unserializable_result_fails_in_place(forked_registration_context):
    """A result that cannot be recorded is an immediate, named failure."""

    class Sneaky(rx.State):
        __workflow__ = WorkflowConfig(id="steps.sneaky")

        @rx.event(durable=True, trigger=manual(), effect="none")
        async def go(self):
            """Return something no journal can hold.

            Returns:
                Never returns.
            """
            await rx.step("bad", lambda: object())
            return rx.complete(result=None)

    async with WorkflowTestHarness(Sneaky) as harness:
        result = await harness.start(Sneaky.go)
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is not RunStatus.COMPLETED
        steps = await harness.kernel.store.get_steps(result.run_id)
        assert "serialized" in str(steps[0].error)


async def test_substeps_appear_in_history(forked_registration_context):
    """An operator can see each recorded substep on the timeline."""
    CALLS.clear()
    async with WorkflowTestHarness(Fulfil) as harness:
        result = await harness.start(Fulfil.start("ord_2"))
        assert result.run_id is not None
        await harness.advance("1s")
        await harness.advance("2s")
        history = await harness.kernel.store.get_history(result.run_id)
    recorded = [
        event.data["key"]
        for event in history
        if event.type is HistoryEventType.SUBSTEP_RECORDED
    ]
    assert recorded == ["charge", "label"]


def test_step_outside_a_handler_is_refused():
    """Plain application code has no journal to record against."""
    with pytest.raises(WorkflowRuntimeError, match="durable"):
        rx.step("orphan", lambda: 1)


async def test_async_callable_in_a_sync_handler_is_refused(
    forked_registration_context,
):
    """The mistake is named instead of deadlocking the worker thread."""

    async def async_side_effect() -> int:  # noqa: RUF029
        """An async callable a sync handler cannot await.

        Returns:
            Nothing meaningful.
        """
        return 1

    class Mixed(rx.State):
        __workflow__ = WorkflowConfig(id="steps.mixed")

        @rx.event(durable=True, trigger=manual(), effect="none")
        def go(self):
            """Try to run an async callable synchronously.

            Returns:
                Completion.
            """
            rx.step("bad", async_side_effect)
            return rx.complete(result=None)

    async with WorkflowTestHarness(Mixed) as harness:
        result = await harness.start(Mixed.go)
        assert result.run_id is not None
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        steps = await harness.kernel.store.get_steps(result.run_id)
        assert "async" in str(steps[0].error)


async def test_a_step_can_carry_the_decision_a_later_branch_uses(
    forked_registration_context,
):
    """Recording a nondeterministic value first keeps the sequence stable.

    rx.step lines calls up by occurrence, so a handler whose step sequence
    can differ between attempts would replay one call's result into another.
    The documented remedy is to record the deciding value as its own step:
    once recorded it is identical on every attempt, so the branch built on it
    is too. This exercises exactly that shape across a real retry.
    """
    CALLS.clear()
    draws: list[int] = []

    def draw() -> int:
        """Produce a value that differs on every call.

        Returns:
            A fresh number each time.
        """
        draws.append(len(draws) + 1)
        return draws[-1]

    def paid(amount: int) -> dict:
        """Record a payment.

        Args:
            amount: What was charged.

        Returns:
            The receipt.
        """
        CALLS.append("paid")
        return {"amount": amount}

    class Branching(rx.State):
        __workflow__ = WorkflowConfig(id="steps.branching")

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="idempotent_write",
            retry=Retry(max_attempts=3, initial_delay="1s", jitter="none"),
        )
        async def go(self):
            """Branch on a recorded draw, then fail once after it.

            Returns:
                Completion on the second attempt.

            Raises:
                TransientWorkflowError: On the first attempt.
            """
            # Recorded first: the branch below decides the same way on every
            # attempt even though draw() itself never repeats a value.
            roll = await rx.step("roll", draw)
            if roll % 2 == 1:
                await rx.step("charge", paid, 100)
            CALLS.append("attempt")
            if CALLS.count("attempt") == 1:
                msg = "fails after the branch"
                raise TransientWorkflowError(msg)
            return rx.complete(result={"roll": roll})

    async with WorkflowTestHarness(Branching) as harness:
        result = await harness.start(Branching.go)
        assert result.run_id is not None
        await harness.advance("2s")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {"roll": 1}

    # draw() ran once; the retry replayed it, so the branch held and the
    # payment inside it did not repeat.
    assert draws == [1]
    assert CALLS.count("paid") == 1
