"""07 · Approval workflow with long waits.

A request is parsed once, validated, and then waits: for the missing information
if the form is incomplete, or for a decision if it is not. Either wait can last
days, and the run holds nothing open while it does. Parsing is a step of its own,
so revalidating after the applicant fills in a field does not parse the document
again.
"""

from __future__ import annotations

import datetime
from typing import Any

from reflex_workflow import Step, Wait, Workflow, step, wait_for
from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

# What a complete request has to carry before anyone is asked to approve it.
REQUIRED = ("applicant", "amount", "purpose")

REPLY_DEADLINE = datetime.timedelta(days=14)
# Providers here fail in bursts; a few quick attempts clear most of it.
RETRIES = 3
BACKOFF = datetime.timedelta(milliseconds=50)


class Request(Base, Workflow):
    """One submitted request, from the document to the filed decision."""

    __tablename__ = "example_request"

    id: Mapped[int] = mapped_column(primary_key=True)
    request_id: Mapped[str] = mapped_column(String, unique=True)
    document: Mapped[dict[str, Any] | None] = mapped_column(JSONB, default=None)
    missing: Mapped[list[str] | None] = mapped_column(JSONB, default=None)
    decided_by: Mapped[str | None] = mapped_column(String, default=None)
    filing_id: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str] = mapped_column(String, default="received")

    @step(retries=RETRIES, backoff=BACKOFF)
    async def parse(self):
        """Read the document, once, however often it is validated after.

        Returns:
            The validation.
        """
        self.document = await world.call(
            "forms.parse", key=self.request_id, request=self.request_id
        )
        self.status = "parsed"
        return Request.validate

    @step(retries=RETRIES, backoff=BACKOFF)
    # Annotated because validate and supply return each other: the two
    # signatures depend on one another, and inference has nowhere to start.
    async def validate(self) -> Wait[Request]:
        """Check what the document still needs, and wait for whoever must act.

        Returns:
            A wait for the missing information, or for a decision.
        """
        document = self.document or {}
        missing = [field for field in REQUIRED if not document.get(field)]
        self.missing = missing
        if missing:
            await world.call(
                "chat.post",
                key=f"info-{self.request_id}-{','.join(missing)}",
                to=str(document.get("applicant", "applicant")),
                text=f"Still needed: {', '.join(missing)}",
            )
            self.status = "needs-information"
            return wait_for(
                Request.supply, timeout=REPLY_DEADLINE, on_timeout=Request.abandon
            )
        self.status = "awaiting-decision"
        return wait_for(
            Request.decide, timeout=REPLY_DEADLINE, on_timeout=Request.abandon
        )

    @step(retries=RETRIES, backoff=BACKOFF)
    async def supply(self, fields: dict[str, Any]) -> Step[Request, []]:
        """Take the information the applicant sent in.

        Args:
            fields: The fields they filled in.

        Returns:
            The validation, which decides what is still needed.
        """
        self.document = {**(self.document or {}), **fields}
        self.status = "updated"
        return Request.validate

    @step(retries=RETRIES, backoff=BACKOFF)
    async def decide(self, verdict: str, *, by: str):
        """Take the approver's decision.

        Args:
            verdict: ``approve`` or ``reject``.
            by: Who decided.

        Returns:
            The filing, or None when rejected.
        """
        self.decided_by = by
        if verdict != "approve":
            self.status = "rejected"
            return None
        return Request.file

    @step(retries=RETRIES, backoff=BACKOFF)
    async def file(self):
        """Register the approved request."""
        filed = await world.call(
            "registry.file",
            key=self.request_id,
            request=self.request_id,
            approved_by=self.decided_by,
        )
        self.filing_id = filed["id"]
        self.status = "filed"

    @step(retries=RETRIES, backoff=BACKOFF)
    async def abandon(self):
        """Close a request nobody came back to."""
        self.status = "abandoned"


async def receive(request_id: str) -> bool:
    """Take a submitted request.

    Args:
        request_id: The submission's id.

    Returns:
        Whether this call started a new run.
    """
    return await Request(request_id=request_id).start(Request.parse)
