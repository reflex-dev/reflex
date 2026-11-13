"""01 · Route new leads to the right salesperson.

A form is submitted, the lead is qualified against rules, a rep is assigned, the
CRM is updated, and the owner is notified. Submitting the same lead twice must
update one contact, and a lead that matches no rule goes to a fallback owner.
"""

from __future__ import annotations

import datetime

from reflex_workflow import Workflow, step
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

# Which rep owns which segment, and who picks up whatever matches nothing.
TERRITORIES = (
    ("enterprise", 500, "dana"),
    ("mid-market", 50, "ravi"),
)
FALLBACK_OWNER = "inbound-desk"

# Providers here fail in bursts; a few quick attempts clear most of it.
RETRIES = 3
BACKOFF = datetime.timedelta(milliseconds=50)


def qualify_lead(employees: int) -> tuple[str, str]:
    """Pick the segment and owner for a lead.

    Args:
        employees: How many people the lead's company has.

    Returns:
        The segment and the owner's name.
    """
    for segment, threshold, owner in TERRITORIES:
        if employees >= threshold:
            return segment, owner
    return "unqualified", FALLBACK_OWNER


class Lead(Base, Workflow):
    """One submitted lead, from the form to the notified owner."""

    __tablename__ = "example_lead"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The form can be submitted twice; the address is what makes it one lead.
    email: Mapped[str] = mapped_column(String, unique=True)
    company: Mapped[str] = mapped_column(String)
    employees: Mapped[int] = mapped_column(Integer)
    segment: Mapped[str | None] = mapped_column(String, default=None)
    owner: Mapped[str | None] = mapped_column(String, default=None)
    contact_id: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str] = mapped_column(String, default="received")

    @step
    async def qualify(self):
        """Apply the territory rules.

        Returns:
            The CRM update.
        """
        self.segment, self.owner = qualify_lead(self.employees)
        self.status = "qualified"
        return Lead.update_crm

    @step(retries=RETRIES, backoff=BACKOFF)
    async def update_crm(self):
        """Create or update the contact, keyed by the lead's address.

        Returns:
            The owner's notification.
        """
        contact = await world.call(
            "crm.upsert",
            key=self.email,
            email=self.email,
            company=self.company,
            owner=self.owner,
            segment=self.segment,
        )
        self.contact_id = contact["id"]
        return Lead.notify_owner

    @step(retries=RETRIES, backoff=BACKOFF)
    async def notify_owner(self):
        """Tell the owner, once per lead."""
        await world.call(
            "chat.post",
            key=f"lead-{self.email}",
            to=self.owner,
            text=f"New {self.segment} lead: {self.company}",
        )
        self.status = "routed"


async def submit(email: str, company: str, employees: int) -> bool:
    """Take a form submission.

    Args:
        email: The lead's address.
        company: The lead's company.
        employees: How many people that company has.

    Returns:
        Whether this submission started a new run.
    """
    return await Lead(email=email, company=company, employees=employees).start(
        Lead.qualify
    )
