"""06 · Collect and approve supplier invoices.

Pass condition: an approval can arrive days later; duplicate uploads or approval
clicks do not create duplicate bills.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from examples.ex06_invoices import APPROVAL_DEADLINE, Invoice, upload
from examples.services import world

from .conftest import eventually

pytestmark = pytest.mark.asyncio(loop_scope="module")


def reaches(upload_id: str, status: str):
    """Build a check that an invoice has reached a status.

    Args:
        upload_id: The upload's id.
        status: The status to wait for.

    Returns:
        An async predicate.
    """

    async def check() -> bool:
        row = await Invoice.by(Invoice.upload_id == upload_id).get()
        return row is not None and row.status == status

    return check


async def arrives(supplier: str, number: str, amount_cents: int = 1000) -> str:
    """Upload an invoice whose contents the scanner will report.

    Args:
        supplier: Who sent it.
        number: Their invoice number.
        amount_cents: What it is for.

    Returns:
        The upload's id.
    """
    upload_id = uuid.uuid4().hex
    world.plan(
        "ocr.extract",
        upload_id,
        {"supplier": supplier, "number": number, "amount_cents": amount_cents},
    )
    assert await upload(upload_id)
    return upload_id


async def test_an_approval_days_later_records_one_bill(running):
    supplier = f"supplier-{uuid.uuid4().hex}"
    upload_id = await arrives(supplier, "INV-1")
    await eventually(reaches(upload_id, "awaiting-approval"))

    # Nothing is scheduled to run; the invoice is parked until someone replies.
    row = await Invoice.by(Invoice.upload_id == upload_id).get()
    assert row is not None
    assert row.waiting_for == "decide"
    assert row.wake_at is not None
    week = datetime.datetime.now(datetime.timezone.utc) + APPROVAL_DEADLINE
    assert abs((row.wake_at - week).total_seconds()) < 60

    invoice = Invoice.by(Invoice.upload_id == upload_id)
    assert (
        await invoice.deliver(
            Invoice.decide("approve", by="pat"), key=f"decision-{upload_id}"
        )
        == 1
    )
    await eventually(reaches(upload_id, "recorded"))
    assert len(world.effects("ledger.record")) == 1


async def test_a_second_click_on_approve_does_not_book_a_second_bill(running):
    supplier = f"supplier-{uuid.uuid4().hex}"
    upload_id = await arrives(supplier, "INV-2")
    await eventually(reaches(upload_id, "awaiting-approval"))

    invoice = Invoice.by(Invoice.upload_id == upload_id)
    decision = f"decision-{upload_id}"
    assert await invoice.deliver(Invoice.decide("approve", by="pat"), key=decision) == 1
    assert await invoice.deliver(Invoice.decide("approve", by="pat"), key=decision) == 0
    await eventually(reaches(upload_id, "recorded"))

    assert len(world.effects("ledger.record")) == 1


async def test_the_same_file_uploaded_twice_is_one_run(running):
    supplier = f"supplier-{uuid.uuid4().hex}"
    upload_id = await arrives(supplier, "INV-3")
    assert not await upload(upload_id)
    await eventually(reaches(upload_id, "awaiting-approval"))

    assert world.attempts("ocr.extract") == 1


async def test_the_same_invoice_arriving_on_a_second_file_is_not_booked_twice(running):
    supplier = f"supplier-{uuid.uuid4().hex}"
    first = await arrives(supplier, "INV-4")
    await eventually(reaches(first, "awaiting-approval"))
    assert (
        await Invoice.by(Invoice.upload_id == first).deliver(
            Invoice.decide("approve", by="pat"), key=f"decision-{first}"
        )
        == 1
    )
    await eventually(reaches(first, "recorded"))

    # The supplier emails the same invoice again, as a different file.
    second = await arrives(supplier, "INV-4")
    await eventually(reaches(second, f"duplicate-of:{first}"))

    row = await Invoice.by(Invoice.upload_id == second).get()
    assert row is not None
    assert (row.next_step, row.bill_id) == (None, None)
    assert len(world.effects("ledger.record")) == 1


async def test_a_large_invoice_goes_to_the_second_signature(running):
    supplier = f"supplier-{uuid.uuid4().hex}"
    upload_id = await arrives(supplier, "INV-5", amount_cents=900_000)
    await eventually(reaches(upload_id, "awaiting-approval"))

    row = await Invoice.by(Invoice.upload_id == upload_id).get()
    assert row is not None
    assert row.approver == "finance-director"


async def approved(upload_id: str) -> None:
    """Approve an invoice once it is waiting, and wait for it to be booked.

    Args:
        upload_id: The upload's id.
    """
    await eventually(reaches(upload_id, "awaiting-approval"))
    invoice = Invoice.by(Invoice.upload_id == upload_id)
    assert (
        await invoice.deliver(
            Invoice.decide("approve", by="pat"), key=f"decision-{upload_id}"
        )
        == 1
    )
    await eventually(reaches(upload_id, "recorded"))


async def test_fields_the_scanner_could_not_read_fall_back(running):
    upload_id = uuid.uuid4().hex
    world.plan(
        "ocr.extract",
        upload_id,
        {"supplier": None, "number": None, "amount_cents": None},
    )
    assert await upload(upload_id)
    await eventually(reaches(upload_id, "awaiting-approval"))

    row = await Invoice.by(Invoice.upload_id == upload_id).get()
    assert row is not None
    assert (row.supplier, row.number, row.amount_cents) == ("unknown", upload_id, 0)


async def test_invoices_whose_fields_run_together_are_booked_apart(running):
    tag = uuid.uuid4().hex
    # Joined with a colon, both of these would read "<tag>:a:b".
    first = await arrives(f"{tag}:a", "b")
    second = await arrives(tag, "a:b")
    for upload_id in (first, second):
        await approved(upload_id)

    assert len(world.effects("ledger.record")) == 2
