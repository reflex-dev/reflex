"""04 · Sort support requests and prepare replies.

Pass condition: urgent requests reach the escalation queue; uncertain
classifications reach a person; duplicate events produce one ticket.
"""

from __future__ import annotations

import uuid

import pytest
from examples.ex04_support_triage import SupportRequest, receive
from examples.services import world

from .conftest import eventually

pytestmark = pytest.mark.asyncio(loop_scope="module")


def reaches(event_id: str, status: str):
    """Build a check that a request has reached a status.

    Args:
        event_id: The provider's event id.
        status: The status to wait for.

    Returns:
        An async predicate.
    """

    async def check() -> bool:
        """Tell whether the request has reached the status.

        Returns:
            Whether it has.
        """
        row = await SupportRequest.by(SupportRequest.event_id == event_id).get()
        return row is not None and row.status == status

    return check


async def test_an_urgent_request_goes_straight_to_the_escalation_queue(running):
    event = uuid.uuid4().hex
    assert await receive(event, "acme", "Site is down", "Our whole site is down")
    await eventually(reaches(event, "escalated:urgent"))

    [escalation] = world.effects("helpdesk.escalate")
    assert escalation["queue"] == "escalation-queue"
    assert not world.effects("helpdesk.draft")


async def test_a_confident_classification_gets_a_drafted_reply(running):
    event = uuid.uuid4().hex
    assert await receive(event, "globex", "Refund request", "Please refund my charge")
    await eventually(reaches(event, "drafted"))

    [draft] = world.effects("helpdesk.draft")
    assert draft["queue"] == "billing-queue"


async def test_an_uncertain_request_waits_for_a_person_and_takes_their_label(running):
    event = uuid.uuid4().hex
    assert await receive(event, "initech", "A question", "Wondering about something")
    await eventually(reaches(event, "awaiting-label"))

    ticket = SupportRequest.by(SupportRequest.event_id == event)
    row = await ticket.get()
    assert row is not None
    assert row.waiting_for == "label"
    # Nothing has been sent anywhere while it waits.
    assert not world.calls

    assert (
        await ticket.deliver(
            SupportRequest.label("billing", "normal", by="sam"), key=f"label-{event}"
        )
        == 1
    )
    await eventually(reaches(event, "drafted"))

    row = await ticket.get()
    assert row is not None
    assert (row.labelled_by, row.queue) == ("sam", "billing-queue")


async def test_a_second_label_for_the_same_request_changes_nothing(running):
    event = uuid.uuid4().hex
    assert await receive(event, "initech", "Another question", "Just wondering")
    await eventually(reaches(event, "awaiting-label"))

    ticket = SupportRequest.by(SupportRequest.event_id == event)
    assert (
        await ticket.deliver(
            SupportRequest.label("how-to", "low", by="sam"), key=f"label-{event}"
        )
        == 1
    )
    await eventually(reaches(event, "drafted"))
    # The agent clicks again; the request has already moved on.
    assert (
        await ticket.deliver(
            SupportRequest.label("billing", "urgent", by="sam"), key=f"label-{event}"
        )
        == 0
    )

    row = await ticket.get()
    assert row is not None
    assert row.category == "how-to"
    assert len(world.effects("helpdesk.draft")) == 1
    assert not world.effects("helpdesk.escalate")


async def test_a_redelivered_webhook_produces_one_ticket(running):
    event = uuid.uuid4().hex
    assert await receive(event, "acme", "Outage", "Everything is down")
    # The provider retries the same event; it must not open a second ticket.
    assert not await receive(event, "acme", "Outage", "Everything is down")
    await eventually(reaches(event, "escalated:urgent"))

    assert len(world.effects("helpdesk.escalate")) == 1


async def test_a_signal_word_inside_another_word_is_not_a_signal(running):
    event = uuid.uuid4().hex
    # "download" contains "down", which on its own would mean an outage.
    assert await receive(
        event, "initech", "Docs", "How do I download the documentation?"
    )
    await eventually(reaches(event, "drafted"))

    [draft] = world.effects("helpdesk.draft")
    assert draft["queue"] == "how-to-queue"
    assert not world.effects("helpdesk.escalate")
