"""06 · Collect and approve supplier invoices.

An invoice arrives as an upload, its details are extracted, it is checked against
the invoices already recorded, and then it waits for a person. The wait is open
for a week, so the approval usually arrives long after the upload, and neither a
re-uploaded file nor a second click on the approve button records a second bill.
"""

from __future__ import annotations

import datetime
import json

from reflex_workflow import Workflow, step, wait_for
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from examples.base import Base
from examples.services import world

APPROVAL_DEADLINE = datetime.timedelta(days=7)
# Anything above this needs a second pair of eyes rather than a single approver.
SECOND_SIGNATURE_CENTS = 500_000

# Providers here fail in bursts; a few quick attempts clear most of it.
RETRIES = 3
BACKOFF = datetime.timedelta(milliseconds=50)


class Invoice(Base, Workflow):
    """One uploaded invoice, from the file to the recorded bill."""

    __tablename__ = "example_invoice"

    id: Mapped[int] = mapped_column(primary_key=True)
    # The same file can be uploaded twice; the upload is what makes it one run.
    upload_id: Mapped[str] = mapped_column(String, unique=True)
    supplier: Mapped[str | None] = mapped_column(String, default=None)
    number: Mapped[str | None] = mapped_column(String, default=None)
    amount_cents: Mapped[int | None] = mapped_column(Integer, default=None)
    approver: Mapped[str | None] = mapped_column(String, default=None)
    decided_by: Mapped[str | None] = mapped_column(String, default=None)
    bill_id: Mapped[str | None] = mapped_column(String, default=None)
    status: Mapped[str] = mapped_column(String, default="uploaded")

    @property
    def reference(self) -> str:
        """Identify the invoice by what is printed on it, not by its file.

        Returns:
            The supplier's name and invoice number, encoded so that no two
            different pairs share a reference whatever characters they hold.
        """
        return json.dumps([self.supplier, self.number])

    @step(retries=RETRIES, backoff=BACKOFF)
    async def extract(self):
        """Read the supplier, number, and amount off the file.

        Returns:
            The duplicate check.
        """
        fields = await world.call(
            "ocr.extract", key=self.upload_id, upload=self.upload_id
        )
        # A field the reader could not make out comes back as null, not absent.
        self.supplier = fields.get("supplier") or "unknown"
        self.number = fields.get("number") or self.upload_id
        self.amount_cents = int(fields.get("amount_cents") or 0)
        self.status = "extracted"
        return Invoice.check_duplicate

    @step(retries=RETRIES, backoff=BACKOFF)
    async def check_duplicate(self):
        """Stop if this invoice has already been through.

        Returns:
            The approval request, or None when it is a duplicate.
        """
        already = await Invoice.by(
            Invoice.supplier == self.supplier,
            Invoice.number == self.number,
            Invoice.id != self.id,
            Invoice.bill_id.is_not(None),
        ).get()
        if already is not None:
            self.status = f"duplicate-of:{already.upload_id}"
            return None
        return Invoice.request_approval

    @step(retries=RETRIES, backoff=BACKOFF)
    async def request_approval(self):
        """Ask the right person, and wait as long as it takes.

        Returns:
            The wait for their decision.
        """
        self.approver = (
            "finance-director"
            if (self.amount_cents or 0) >= SECOND_SIGNATURE_CENTS
            else "team-lead"
        )
        await world.call(
            "chat.post",
            key=f"approve-{self.upload_id}",
            to=self.approver,
            text=f"{self.supplier} {self.number}: {(self.amount_cents or 0) / 100:.2f}",
        )
        self.status = "awaiting-approval"
        return wait_for(
            Invoice.decide, timeout=APPROVAL_DEADLINE, on_timeout=Invoice.escalate
        )

    @step(retries=RETRIES, backoff=BACKOFF)
    async def decide(self, verdict: str, *, by: str):
        """Take the decision, whenever it arrives.

        Args:
            verdict: ``approve`` or ``reject``.
            by: Who decided.

        Returns:
            The bill, or None when the invoice was rejected.
        """
        self.decided_by = by
        if verdict != "approve":
            self.status = "rejected"
            return None
        return Invoice.record_bill

    @step(retries=RETRIES, backoff=BACKOFF)
    async def record_bill(self):
        """Book the bill, keyed by what is printed on the invoice."""
        bill = await world.call(
            "ledger.record",
            key=self.reference,
            supplier=self.supplier,
            number=self.number,
            amount_cents=self.amount_cents,
        )
        self.bill_id = bill["id"]
        self.status = "recorded"

    @step(retries=RETRIES, backoff=BACKOFF)
    async def escalate(self):
        """Chase an invoice nobody decided on."""
        await world.call(
            "chat.post",
            key=f"overdue-{self.upload_id}",
            to="finance-director",
            text=f"Invoice {self.number} from {self.supplier} has waited a week",
        )
        self.status = "overdue"


async def upload(upload_id: str) -> bool:
    """Take an uploaded invoice.

    Args:
        upload_id: The upload's id, which a re-upload repeats.

    Returns:
        Whether this upload started a new run.
    """
    return await Invoice(upload_id=upload_id).start(Invoice.extract)
