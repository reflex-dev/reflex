"""04 · Sort support requests and prepare replies.

A request is classified and prioritised, then routed: urgent goes straight to the
escalation queue, a confident classification gets a drafted reply, and anything
the classifier is unsure about waits for a person to label it. The wait has a
deadline, so an unanswered request escalates rather than sitting forever.
"""

from __future__ import annotations

import datetime
import re

from reflex_workflow import Workflow, step, wait_for
from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

# Words that place a request, and how sure that makes the classifier.
SIGNALS = (
    (("outage", "down", "breach"), "incident", "urgent", 0.95),
    (("refund", "charge", "invoice"), "billing", "normal", 0.9),
    (("how do i", "documentation"), "how-to", "low", 0.85),
)
UNSURE = ("general", "normal", 0.3)

# Below this the classifier does not get to decide on its own.
CONFIDENT = 0.7
LABEL_DEADLINE = datetime.timedelta(hours=4)

# Providers here fail in bursts; a few quick attempts clear most of it.
RETRIES = 3
BACKOFF = datetime.timedelta(milliseconds=50)


def classify(text: str) -> tuple[str, str, float]:
    """Read a request and place it.

    Args:
        text: The request's subject and body.

    Returns:
        The category, the priority, and how sure the classifier is.
    """
    lowered = text.lower()
    for words, category, priority, confidence in SIGNALS:
        # Whole words and phrases only: "download" is not "down".
        if any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in words):
            return category, priority, confidence
    return UNSURE


class SupportRequest(Base, Workflow):
    """One support request, from arrival to a drafted reply or an escalation."""

    __tablename__ = "example_support_request"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The provider redelivers webhooks; the event id is what makes it one ticket.
    event_id: Mapped[str] = mapped_column(String, unique=True)
    customer: Mapped[str] = mapped_column(String)
    subject: Mapped[str] = mapped_column(String)
    body: Mapped[str] = mapped_column(String)
    category: Mapped[str | None] = mapped_column(String, default=None)
    priority: Mapped[str | None] = mapped_column(String, default=None)
    confidence: Mapped[float | None] = mapped_column(Float, default=None)
    queue: Mapped[str | None] = mapped_column(String, default=None)
    labelled_by: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str] = mapped_column(String, default="received")

    @step(retries=RETRIES, backoff=BACKOFF)
    async def triage(self):
        """Classify the request and decide who should see it.

        Returns:
            The escalation, the draft, or a wait for a person to label it.
        """
        category, priority, confidence = classify(f"{self.subject} {self.body}")
        self.category, self.priority, self.confidence = category, priority, confidence
        if priority == "urgent":
            return SupportRequest.escalate("urgent")
        if confidence >= CONFIDENT:
            return SupportRequest.draft_reply
        # Not sure enough to answer: ask a person, but don't wait forever.
        self.status = "awaiting-label"
        return wait_for(
            SupportRequest.label,
            timeout=LABEL_DEADLINE,
            on_timeout=SupportRequest.escalate("unlabelled"),
        )

    @step(retries=RETRIES, backoff=BACKOFF)
    async def label(self, category: str, priority: str, *, by: str):
        """Take the label a person gave the request.

        Args:
            category: What they filed it as.
            priority: How urgent they made it.
            by: Who labelled it.

        Returns:
            The escalation or the draft, on their decision.
        """
        self.category, self.priority, self.labelled_by = category, priority, by
        self.confidence = 1.0
        if priority == "urgent":
            return SupportRequest.escalate("urgent")
        return SupportRequest.draft_reply

    @step(retries=RETRIES, backoff=BACKOFF)
    async def draft_reply(self):
        """Write a reply for an agent to send."""
        self.queue = f"{self.category}-queue"
        await world.call(
            "helpdesk.draft",
            key=self.event_id,
            queue=self.queue,
            customer=self.customer,
            text=f"Thanks for writing about {self.subject}. ",
        )
        self.status = "drafted"

    @step(retries=RETRIES, backoff=BACKOFF)
    async def escalate(self, reason: str):
        """Put the request in front of a human team.

        Args:
            reason: Why it was escalated.
        """
        self.queue = "escalation-queue"
        await world.call(
            "helpdesk.escalate",
            key=self.event_id,
            queue=self.queue,
            customer=self.customer,
            reason=reason,
        )
        self.status = f"escalated:{reason}"


async def receive(event_id: str, customer: str, subject: str, body: str) -> bool:
    """Take a support request from the provider's webhook.

    Args:
        event_id: The provider's event id, which a redelivery repeats.
        customer: Who wrote in.
        subject: The subject line.
        body: The message.

    Returns:
        Whether this delivery opened a new ticket.
    """
    return await SupportRequest(
        event_id=event_id, customer=customer, subject=subject, body=body
    ).start(SupportRequest.triage)
