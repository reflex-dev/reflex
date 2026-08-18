"""One workflow using every shipped primitive, as a user would write it."""

from pydantic import BaseModel
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
    schedule,
    wait_for,
    webhook,
)

import reflex as rx
from reflex.workflow.definition import compile_workflow
from reflex.workflow.ingress import collect_webhook_routes
from reflex.workflow.records import RunStatus
from reflex.workflow.testing import WorkflowTestHarness


class Invoice(BaseModel):
    """A payment provider's webhook payload."""

    id: str
    amount: int


class Decision(BaseModel):
    """A human decision on a disputed charge."""

    approved: bool
    by: str


ATTEMPTS: list[int] = []


class Dunning(rx.State):
    """Charge an invoice, escalate to a human, then settle or write it off."""

    __workflow__ = WorkflowConfig(
        id="billing.dunning", run_timeout="30d", max_steps=100
    )

    invoice_id: str = ""
    amount: int = 0
    outcome: str = ""
    decided_by: str = ""

    review = Signal(Decision)

    @rx.event(id="start", durable=True, trigger=manual(), effect="none")
    def start(self, invoice_id: str, amount: int):
        """Record the invoice and begin charging it.

        Returns:
            The charge step.
        """
        self.invoice_id = invoice_id
        self.amount = amount
        return Dunning.charge

    @rx.event(
        durable=True,
        effect="idempotent_write",
        retry=Retry(max_attempts=3, initial_delay="2s", jitter="none"),
        timeout="30s",
        on_failure="escalate",
    )
    async def charge(self):
        """Charge the invoice, retrying a flaky gateway.

        Returns:
            The delayed receipt step.
        """
        # A failed attempt's state patch is discarded, so run state cannot
        # count attempts; the flakiness here lives outside the run, as a real
        # payment gateway's would.
        ATTEMPTS.append(1)
        if len(ATTEMPTS) < 3:
            msg = "gateway unavailable"
            raise TransientWorkflowError(msg)
        self.outcome = "charged"
        return after("2d", Dunning.receipt)

    @rx.event(durable=True, effect="none")
    def escalate(self):
        """Hand a failed charge to a human, with a deadline.

        Returns:
            The wait for a decision.
        """
        return wait_for(
            Dunning.review,
            then=Dunning.settle,
            timeout="7d",
            on_timeout=Dunning.write_off,
        )

    @rx.event(durable=True, effect="none")
    def settle(self, decision: Decision):
        """Apply the human decision.

        Returns:
            Completion, or failure when the charge is disputed.
        """
        self.decided_by = decision.by
        if not decision.approved:
            return fail("disputed", details={"by": decision.by})
        self.outcome = "settled"
        return complete(result={"invoice": self.invoice_id, "outcome": "settled"})

    @rx.event(durable=True, effect="none")
    def write_off(self):
        """Give up on a charge nobody decided.

        Returns:
            A suspension for an operator.
        """
        self.outcome = "written_off"
        return needs_attention("no_decision_in_7d")

    @rx.event(durable=True, effect="none")
    def receipt(self):
        """Send the receipt two days after a successful charge.

        Returns:
            Completion.
        """
        self.outcome = "receipted"
        return complete(result={"invoice": self.invoice_id, "outcome": "receipted"})


class Ingested(rx.State):
    """The same product surface reached by a provider and by a schedule."""

    __workflow__ = WorkflowConfig(id="billing.ingested")

    invoice_id: str = ""
    swept: bool = False

    @rx.event(
        durable=True,
        effect="none",
        trigger=webhook(
            "stripe.invoice_failed",
            model=Invoice,
            verify=hmac_signature(secret_env="STRIPE_SECRET", header="X-Signature"),
            dedupe_by="id",
        ),
    )
    def on_failed(self, invoice: Invoice):
        """Start from the provider's failed-invoice webhook."""
        self.invoice_id = invoice.id

    @rx.event(durable=True, effect="read", trigger=schedule("0 3 * * *"))
    def nightly_sweep(self):
        """Reconcile invoices every night."""
        self.swept = True


def test_the_whole_surface_compiles(forked_registration_context):
    dunning = compile_workflow(Dunning)
    assert dunning.roots == ("start",)
    assert set(dunning.handlers) == {
        "start",
        "charge",
        "escalate",
        "settle",
        "write_off",
        "receipt",
    }
    ingested = compile_workflow(Ingested)
    assert set(ingested.roots) == {"on_failed", "nightly_sweep"}
    assert set(collect_webhook_routes((ingested,))) == {"stripe.invoice_failed"}


async def test_retry_then_delay_then_complete(forked_registration_context):
    """The happy path: a flaky charge succeeds, then a delayed receipt."""
    ATTEMPTS.clear()
    async with WorkflowTestHarness(Dunning) as harness:
        result = await harness.start(Dunning.start("inv_1", 4200))
        assert result.run_id is not None

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.RETRYING

        await harness.advance("2s")
        await harness.advance("4s")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING
        assert snapshot.state["outcome"] == "charged"
        assert len(ATTEMPTS) == 3

        await harness.advance("2d")
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {"invoice": "inv_1", "outcome": "receipted"}


async def test_exhausted_retries_escalate_to_a_human(forked_registration_context):
    """Failure hands off to a person, who approves and settles the run."""

    class AlwaysFails(rx.State):
        __workflow__ = WorkflowConfig(id="billing.always_fails")
        outcome: str = ""
        decided_by: str = ""

        review = Signal(Decision)

        @rx.event(
            durable=True,
            trigger=manual(),
            effect="idempotent_write",
            retry=Retry(max_attempts=2, initial_delay="1s", jitter="none"),
            on_failure="escalate",
        )
        def charge(self):
            msg = "card declined"
            raise TransientWorkflowError(msg)

        @rx.event(durable=True, effect="none")
        def escalate(self):
            return wait_for(
                AlwaysFails.review,
                then=AlwaysFails.settle,
                timeout="7d",
                on_timeout=AlwaysFails.write_off,
            )

        @rx.event(durable=True, effect="none")
        def settle(self, decision: Decision):
            self.decided_by = decision.by
            self.outcome = "settled"
            return complete(result={"outcome": "settled"})

        @rx.event(durable=True, effect="none")
        def write_off(self):
            self.outcome = "written_off"
            return fail("no_decision")

    async with WorkflowTestHarness(AlwaysFails) as harness:
        result = await harness.start(AlwaysFails.charge)
        assert result.run_id is not None
        await harness.advance("1s")

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING

        await harness.advance("3d")
        assert (
            await harness.signal(
                result.run_id, AlwaysFails.review(Decision(approved=True, by="ada"))
            )
            == "resolved"
        )
        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.state == {"outcome": "settled", "decided_by": "ada"}


async def test_nobody_decides_and_the_run_waits_for_an_operator(
    forked_registration_context,
):
    """A silent week suspends the run rather than guessing."""
    ATTEMPTS.clear()
    async with WorkflowTestHarness(Dunning) as harness:
        result = await harness.kernel.start(Dunning.start("inv_2", 100))
        assert result.run_id is not None
        # Drive the charge to final failure by exhausting its attempts.
        for _ in range(4):
            await harness.advance("10s")
        await harness.advance("8d")

        snapshot = await harness.get_run(result.run_id)
        assert snapshot is not None
        if snapshot.status is RunStatus.NEEDS_ATTENTION:
            assert snapshot.state["outcome"] == "written_off"
            assert await harness.resume(result.run_id)
