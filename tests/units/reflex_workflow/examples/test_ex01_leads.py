"""01 · Route new leads to the right salesperson.

Pass condition: submitting the same lead twice updates one contact; unmatched
leads go to a fallback owner.
"""

from __future__ import annotations

import uuid

import pytest
from examples.ex01_leads import FALLBACK_OWNER, Lead, submit
from examples.services import world

from .conftest import eventually

pytestmark = pytest.mark.asyncio(loop_scope="module")


def address() -> str:
    """Build an address no other test has used.

    Returns:
        A unique email address.
    """
    return f"lead-{uuid.uuid4().hex}@example.com"


async def routed(email: str) -> bool:
    """Report whether a lead has reached its owner.

    Args:
        email: The lead's address.

    Returns:
        Whether the run finished.
    """
    lead = await Lead.by(Lead.email == email).get()
    return lead is not None and lead.status == "routed"


async def test_a_lead_is_qualified_assigned_and_synced(running):
    email = address()
    assert await submit(email, "Globex", employees=900)
    await eventually(lambda: routed(email))

    lead = await Lead.by(Lead.email == email).get()
    assert lead is not None
    assert (lead.segment, lead.owner) == ("enterprise", "dana")
    assert lead.contact_id is not None
    [contact] = world.effects("crm.upsert")
    assert contact["owner"] == "dana"


async def test_the_same_lead_submitted_twice_updates_one_contact(running):
    email = address()
    assert await submit(email, "Initech", employees=120)
    # The visitor submits the form again before the first run has finished.
    assert not await submit(email, "Initech", employees=120)
    await eventually(lambda: routed(email))

    assert len(world.effects("crm.upsert")) == 1
    assert len(world.effects("chat.post")) == 1


async def test_a_lead_that_matches_no_rule_goes_to_the_fallback_owner(running):
    email = address()
    assert await submit(email, "Two People Ltd", employees=2)
    await eventually(lambda: routed(email))

    lead = await Lead.by(Lead.email == email).get()
    assert lead is not None
    assert (lead.segment, lead.owner) == ("unqualified", FALLBACK_OWNER)


async def test_a_crm_outage_is_retried_without_a_second_contact(running):
    email = address()
    world.break_next("crm.upsert", times=2)
    assert await submit(email, "Hooli", employees=600)
    await eventually(lambda: routed(email))

    # Three attempts, one contact: the provider key makes the repeat harmless.
    assert world.attempts("crm.upsert") == 3
    assert len(world.effects("crm.upsert")) == 1
    lead = await Lead.by(Lead.email == email).get()
    assert lead is not None
    assert (lead.attempts, lead.last_error) == (0, None)
