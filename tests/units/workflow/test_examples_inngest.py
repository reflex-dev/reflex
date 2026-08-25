"""Executable Reflex translations of canonical Inngest workflow examples.

Official sources:

* https://www.inngest.com/docs/features/inngest-functions/steps-workflows/wait-for-event
* https://www.inngest.com/docs/guides/fan-out-jobs
* https://www.inngest.com/docs/learn/inngest-steps
"""

from pydantic import BaseModel
from reflex_base.workflow import Retry, TransientWorkflowError, WorkflowConfig, manual

import reflex as rx
from reflex.workflow.records import HistoryEventType, RunStatus, StepStatus
from reflex.workflow.testing import WorkflowTestHarness

ONBOARDING_EMAILS: list[tuple[str, str]] = []
FANOUT_EFFECTS: list[tuple[str, str]] = []
CRM_ATTEMPTS: list[str] = []
CHECKPOINT_CALLS: list[str] = []


class OnboardingCompleted(BaseModel):
    """The event that releases an onboarding drip campaign."""

    user_id: str


def _send_onboarding_email(email: str, template: str) -> dict[str, str]:
    """Simulate an email provider call.

    Args:
        email: The recipient.
        template: The email template.

    Returns:
        The provider response.
    """
    ONBOARDING_EMAILS.append((email, template))
    return {"email": email, "template": template}


class OnboardingDrip(rx.State):
    """Welcome a user, then send tips or a timeout nudge."""

    __workflow__ = WorkflowConfig(id="examples.inngest.onboarding")

    completed = rx.Signal(OnboardingCompleted)
    user_id: str = ""
    email: str = ""

    @rx.event(durable=True, trigger=manual(), effect="idempotent_write")
    async def account_created(self, user_id: str, email: str):
        """Send the welcome email and wait up to three days.

        Args:
            user_id: The user's business identity and run request key.
            email: The user's email address.

        Returns:
            A durable wait for onboarding completion.
        """
        self.user_id = user_id
        self.email = email
        await rx.step("welcome-email", _send_onboarding_email, email, "welcome")
        return rx.wait_for(
            OnboardingDrip.completed,
            then=OnboardingDrip.send_tips,
            timeout="3d",
            on_timeout=OnboardingDrip.send_nudge,
        )

    @rx.event(durable=True, effect="idempotent_write")
    async def send_tips(self, completion: OnboardingCompleted):
        """Send the successful-onboarding tips email.

        Args:
            completion: The completion event addressed to this user's run.

        Returns:
            Completed campaign result, or a correlation failure.
        """
        if completion.user_id != self.user_id:
            return rx.fail(
                "correlation_mismatch",
                details={
                    "expected_user_id": self.user_id,
                    "received_user_id": completion.user_id,
                },
            )
        await rx.step("tips-email", _send_onboarding_email, self.email, "tips")
        return rx.complete(result={"path": "completed", "user_id": completion.user_id})

    @rx.event(durable=True, effect="idempotent_write")
    async def send_nudge(self):
        """Send the timeout nudge.

        Returns:
            Completed campaign result.
        """
        await rx.step("nudge-email", _send_onboarding_email, self.email, "nudge")
        return rx.complete(result={"path": "timeout", "user_id": self.user_id})


def _record_signup_effect(service: str, user_id: str) -> dict[str, str]:
    """Record one successful downstream signup integration.

    Args:
        service: The downstream service name.
        user_id: The signed-up user.

    Returns:
        The service result.
    """
    FANOUT_EFFECTS.append((service, user_id))
    return {"service": service, "user_id": user_id}


def _create_crm_contact(user_id: str) -> dict[str, str]:
    """Fail CRM once to demonstrate branch-level independence.

    Args:
        user_id: The signed-up user.

    Returns:
        The CRM result after recovery.

    Raises:
        TransientWorkflowError: On the first provider attempt.
    """
    CRM_ATTEMPTS.append(user_id)
    if len(CRM_ATTEMPTS) == 1:
        msg = "CRM temporarily unavailable"
        raise TransientWorkflowError(msg)
    return _record_signup_effect("crm", user_id)


class SignupWelcome(rx.State):
    """The welcome-email branch of signup fan-out."""

    __workflow__ = WorkflowConfig(id="examples.inngest.signup.welcome")

    @rx.event(durable=True, trigger=manual(), effect="idempotent_write")
    async def send(self, user_id: str, email: str):
        """Send the welcome email.

        Args:
            user_id: The signed-up user.
            email: The user's email address.

        Returns:
            The branch completion.
        """
        del email
        result = await rx.step(
            "welcome-email", _record_signup_effect, "welcome", user_id
        )
        return rx.complete(result=result)


class StripeTrial(rx.State):
    """The Stripe-trial branch of signup fan-out."""

    __workflow__ = WorkflowConfig(id="examples.inngest.signup.stripe")

    @rx.event(durable=True, trigger=manual(), effect="idempotent_write")
    async def start(self, user_id: str, email: str):
        """Create the user's Stripe trial.

        Args:
            user_id: The signed-up user.
            email: The user's email address.

        Returns:
            The branch completion.
        """
        del email
        result = await rx.step("stripe-trial", _record_signup_effect, "stripe", user_id)
        return rx.complete(result=result)


class CrmContact(rx.State):
    """The CRM branch of signup fan-out."""

    __workflow__ = WorkflowConfig(id="examples.inngest.signup.crm")

    @rx.event(
        durable=True,
        trigger=manual(),
        effect="idempotent_write",
        retry=Retry(max_attempts=2, initial_delay="1s", jitter="none"),
    )
    async def add(self, user_id: str, email: str):
        """Create the CRM contact, retrying a transient outage.

        Args:
            user_id: The signed-up user.
            email: The user's email address.

        Returns:
            The branch completion.
        """
        del email
        result = await rx.step("crm-contact", _create_crm_contact, user_id)
        return rx.complete(result=result)


class MailingList(rx.State):
    """The mailing-list branch of signup fan-out."""

    __workflow__ = WorkflowConfig(id="examples.inngest.signup.mailing_list")

    @rx.event(durable=True, trigger=manual(), effect="idempotent_write")
    async def subscribe(self, user_id: str, email: str):
        """Subscribe the user to the mailing list.

        Args:
            user_id: The signed-up user.
            email: The user's email address.

        Returns:
            The branch completion.
        """
        del email
        result = await rx.step(
            "mailing-list", _record_signup_effect, "mailing-list", user_id
        )
        return rx.complete(result=result)


class SignupFanout(rx.State):
    """Run four signup integrations independently, then join them."""

    __workflow__ = WorkflowConfig(id="examples.inngest.signup")
    services: list[str] = []

    @rx.event(durable=True, trigger=manual(), effect="none")
    def signup(self, user_id: str, email: str):
        """Fan one signup out to all downstream services.

        Args:
            user_id: The signed-up user.
            email: The user's email address.

        Returns:
            A parallel branch join.
        """
        return rx.parallel(
            SignupWelcome.send(user_id, email),
            StripeTrial.start(user_id, email),
            CrmContact.add(user_id, email),
            MailingList.subscribe(user_id, email),
            then=SignupFanout.join,
        )

    @rx.event(durable=True, effect="none")
    def join(self, results: list[dict]):
        """Collect all four independent branch results.

        Args:
            results: Child outcomes in declaration order.

        Returns:
            Completion with every service name.
        """
        self.services = [entry["result"]["service"] for entry in results]
        return rx.complete(result={"services": self.services})


def _create_external_customer(user_id: str) -> dict[str, str]:
    """Simulate a non-repeatable external customer creation.

    Args:
        user_id: The user being provisioned.

    Returns:
        The external customer identity.
    """
    CHECKPOINT_CALLS.append("create-customer")
    return {"customer_id": f"cus_{user_id}"}


def _finalize_profile(customer_id: str) -> dict[str, str]:
    """Fail once after customer creation, then finalize the profile.

    Args:
        customer_id: The already-created external customer.

    Returns:
        The finalized profile.

    Raises:
        TransientWorkflowError: On the first attempt.
    """
    CHECKPOINT_CALLS.append("finalize-profile")
    if CHECKPOINT_CALLS.count("finalize-profile") == 1:
        msg = "profile service temporarily unavailable"
        raise TransientWorkflowError(msg)
    return {"customer_id": customer_id, "status": "ready"}


class CheckpointedSignup(rx.State):
    """Demonstrate Inngest ``step.run``-style replay with ``rx.step``."""

    __workflow__ = WorkflowConfig(id="examples.inngest.checkpoint")

    @rx.event(
        durable=True,
        trigger=manual(),
        effect="idempotent_write",
        retry=Retry(max_attempts=2, initial_delay="1s", jitter="none"),
    )
    async def provision(self, user_id: str):
        """Create a customer once even when a later step retries.

        Args:
            user_id: The user being provisioned.

        Returns:
            Completion with the finalized profile.
        """
        customer = await rx.step("create-customer", _create_external_customer, user_id)
        profile = await rx.step(
            "finalize-profile", _finalize_profile, customer["customer_id"]
        )
        return rx.complete(result=profile)


async def test_onboarding_completion_sends_tips_before_timeout(
    forked_registration_context,
):
    """A matching business-key signal chooses tips, never the nudge."""
    ONBOARDING_EMAILS.clear()
    async with WorkflowTestHarness(OnboardingDrip) as harness:
        started = await harness.start(
            OnboardingDrip.account_created("user-complete", "done@example.com"),
            request_key="user-complete",
        )
        assert started.run_id is not None
        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.WAITING
        assert ONBOARDING_EMAILS == [("done@example.com", "welcome")]

        await harness.advance("2d")
        assert (
            await rx.workflows.signal_by_key(
                OnboardingDrip,
                "user-complete",
                OnboardingDrip.completed(OnboardingCompleted(user_id="user-complete")),
                key="onboarding-completed:user-complete",
            )
            == "resolved"
        )
        await harness.run_until_idle()

        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {"path": "completed", "user_id": "user-complete"}
        assert ONBOARDING_EMAILS == [
            ("done@example.com", "welcome"),
            ("done@example.com", "tips"),
        ]

        await harness.advance("2d")
        assert ("done@example.com", "nudge") not in ONBOARDING_EMAILS


async def test_onboarding_timeout_sends_nudge_not_tips(
    forked_registration_context,
):
    """No completion within three days deterministically chooses the nudge."""
    ONBOARDING_EMAILS.clear()
    async with WorkflowTestHarness(OnboardingDrip) as harness:
        started = await harness.start(
            OnboardingDrip.account_created("user-timeout", "late@example.com"),
            request_key="user-timeout",
        )
        assert started.run_id is not None

        await harness.advance("3d")

        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {"path": "timeout", "user_id": "user-timeout"}
        assert ONBOARDING_EMAILS == [
            ("late@example.com", "welcome"),
            ("late@example.com", "nudge"),
        ]


async def test_onboarding_signal_before_wait_is_buffered(
    forked_registration_context,
):
    """An admitted run keeps a completion that beats welcome-email execution."""
    ONBOARDING_EMAILS.clear()
    async with WorkflowTestHarness(OnboardingDrip) as harness:
        started = await harness.start_only(
            OnboardingDrip.account_created("user-early", "early@example.com"),
            request_key="user-early",
        )
        assert started.run_id is not None
        assert (
            await rx.workflows.signal_by_key(
                OnboardingDrip,
                "user-early",
                OnboardingDrip.completed(OnboardingCompleted(user_id="user-early")),
                key="onboarding-completed:user-early",
            )
            == "buffered"
        )

        await harness.run_until_idle()

        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {"path": "completed", "user_id": "user-early"}
        assert ONBOARDING_EMAILS == [
            ("early@example.com", "welcome"),
            ("early@example.com", "tips"),
        ]


async def test_onboarding_rejects_mismatched_signal_payload(
    forked_registration_context,
):
    """Addressing a run by key cannot silently substitute another user."""
    ONBOARDING_EMAILS.clear()
    async with WorkflowTestHarness(OnboardingDrip) as harness:
        started = await harness.start(
            OnboardingDrip.account_created("user-a", "a@example.com"),
            request_key="user-a",
        )
        assert started.run_id is not None

        assert (
            await rx.workflows.signal_by_key(
                OnboardingDrip,
                "user-a",
                OnboardingDrip.completed(OnboardingCompleted(user_id="user-b")),
                key="onboarding-completed:user-b",
            )
            == "resolved"
        )
        await harness.run_until_idle()

        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.FAILED
        assert snapshot.error == {
            "reason": "correlation_mismatch",
            "details": {
                "expected_user_id": "user-a",
                "received_user_id": "user-b",
            },
        }
        assert ONBOARDING_EMAILS == [("a@example.com", "welcome")]


async def test_signup_fanout_is_independent_and_joins(
    forked_registration_context,
):
    """Three integrations finish while CRM retries; the parent waits for all."""
    FANOUT_EFFECTS.clear()
    CRM_ATTEMPTS.clear()
    workflows = (SignupFanout, SignupWelcome, StripeTrial, CrmContact, MailingList)
    async with WorkflowTestHarness(*workflows) as harness:
        started = await harness.start(
            SignupFanout.signup("user-42", "user42@example.com")
        )
        assert started.run_id is not None

        parent = await harness.get_run(started.run_id)
        assert parent is not None
        assert parent.status is RunStatus.WAITING
        assert parent.steps[1].status is StepStatus.BLOCKED
        assert parent.steps[1].join_expected == 4
        assert parent.steps[1].join_arrived == 3
        assert sorted(FANOUT_EFFECTS) == [
            ("mailing-list", "user-42"),
            ("stripe", "user-42"),
            ("welcome", "user-42"),
        ]
        assert CRM_ATTEMPTS == ["user-42"]

        runs = await harness.kernel.list_runs()
        children = [run for run in runs if run.parent_run_id == started.run_id]
        assert len(children) == 4
        assert sum(run.status is RunStatus.COMPLETED for run in children) == 3

        await harness.advance("1s")

        parent = await harness.get_run(started.run_id)
        assert parent is not None
        assert parent.status is RunStatus.COMPLETED
        assert parent.result == {
            "services": ["welcome", "stripe", "crm", "mailing-list"]
        }
        assert sorted(FANOUT_EFFECTS) == [
            ("crm", "user-42"),
            ("mailing-list", "user-42"),
            ("stripe", "user-42"),
            ("welcome", "user-42"),
        ]
        assert CRM_ATTEMPTS == ["user-42", "user-42"]

        runs = await harness.kernel.list_runs()
        children = [run for run in runs if run.parent_run_id == started.run_id]
        assert len(children) == 4
        assert all(run.status is RunStatus.COMPLETED for run in children)


async def test_completed_step_is_not_repeated_after_later_failure(
    forked_registration_context,
):
    """A later retry replays the customer result instead of creating another."""
    CHECKPOINT_CALLS.clear()
    async with WorkflowTestHarness(CheckpointedSignup) as harness:
        started = await harness.start(CheckpointedSignup.provision("user-7"))
        assert started.run_id is not None
        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.status is not RunStatus.COMPLETED
        assert CHECKPOINT_CALLS == ["create-customer", "finalize-profile"]

        await harness.advance("1s")

        snapshot = await harness.get_run(started.run_id)
        assert snapshot is not None
        assert snapshot.status is RunStatus.COMPLETED
        assert snapshot.result == {
            "customer_id": "cus_user-7",
            "status": "ready",
        }
        assert CHECKPOINT_CALLS.count("create-customer") == 1
        assert CHECKPOINT_CALLS.count("finalize-profile") == 2

        history = await harness.kernel.store.get_history(started.run_id)
        recorded = [
            event.data["key"]
            for event in history
            if event.type is HistoryEventType.SUBSTEP_RECORDED
        ]
        assert recorded == ["create-customer", "finalize-profile"]
