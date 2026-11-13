"""07 · Approval workflow with long waits.

Pass condition: restart during the wait; accept a delayed reply once; branch
correctly on approve/reject; finish without repeating completed external actions.

These tests run the worker themselves, stopping and starting it around a wait the
way a deploy would.
"""

from __future__ import annotations

import uuid

import pytest
from examples.ex07_long_wait_approval import Request, receive
from examples.services import world
from reflex_workflow import connect_workflows
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .conftest import eventually, worker

pytestmark = pytest.mark.asyncio(loop_scope="module")

COMPLETE = {"applicant": "dana", "amount": 250, "purpose": "conference"}


def reaches(request_id: str, status: str):
    """Build a check that a request has reached a status.

    Args:
        request_id: The submission's id.
        status: The status to wait for.

    Returns:
        An async predicate.
    """

    async def check() -> bool:
        """Tell whether the request has reached the status.

        Returns:
            Whether it has.
        """
        row = await Request.by(Request.request_id == request_id).get()
        return row is not None and row.status == status

    return check


async def submitted(document: dict[str, object]) -> str:
    """Submit a request whose parsed document is known in advance.

    Args:
        document: What the parser will report.

    Returns:
        The submission's id.
    """
    request_id = uuid.uuid4().hex
    world.plan("forms.parse", request_id, dict(document))
    assert await receive(request_id)
    return request_id


async def read_directly(
    factory: async_sessionmaker[AsyncSession], request_id: str
) -> Request:
    """Read a row without going through the engine, as an operator would.

    Args:
        factory: The session factory for the test database.
        request_id: The submission's id.

    Returns:
        The row.
    """
    async with factory() as session:
        row = (
            (
                await session.execute(
                    select(Request).where(Request.request_id == request_id)
                )
            )
            .scalars()
            .first()
        )
    assert row is not None
    return row


async def test_a_complete_request_waits_for_a_decision_and_is_filed(database):
    async with worker(database):
        request_id = await submitted(COMPLETE)
        await eventually(reaches(request_id, "awaiting-decision"))

        assert (
            await Request.by(Request.request_id == request_id).deliver(
                Request.decide("approve", by="sam"), key=f"decision-{request_id}"
            )
            == 1
        )
        await eventually(reaches(request_id, "filed"))

    row = await read_directly(database, request_id)
    assert (row.decided_by, row.filing_id is not None) == ("sam", True)
    assert len(world.effects("registry.file")) == 1


async def test_a_rejected_request_is_never_filed(database):
    async with worker(database):
        request_id = await submitted(COMPLETE)
        await eventually(reaches(request_id, "awaiting-decision"))

        assert (
            await Request.by(Request.request_id == request_id).deliver(
                Request.decide("reject", by="sam"), key=f"decision-{request_id}"
            )
            == 1
        )
        await eventually(reaches(request_id, "rejected"))

    row = await read_directly(database, request_id)
    assert (row.next_step, row.filing_id) == (None, None)
    assert not world.effects("registry.file")


async def test_a_wait_survives_the_worker_it_was_started_by(database):
    # The request is incomplete, so it parks until the applicant answers.
    async with worker(database):
        request_id = await submitted({"applicant": "dana"})
        await eventually(reaches(request_id, "needs-information"))

    # Nothing is running now: the wait is a row, not a process.
    parked = await read_directly(database, request_id)
    assert (parked.status, parked.waiting_for) == ("needs-information", "supply")
    assert sorted(parked.missing or []) == ["amount", "purpose"]

    # The applicant answers while the workers are down. The web process only
    # addresses runs; it does not run them.
    async with connect_workflows(database):
        request = Request.by(Request.request_id == request_id)
        assert (
            await request.deliver(
                Request.supply({"amount": 250, "purpose": "conference"}),
                key=f"info-{request_id}",
            )
            == 1
        )
        held = await read_directly(database, request_id)
        assert held.status == "needs-information"

    async with worker(database):
        request = Request.by(Request.request_id == request_id)
        await eventually(reaches(request_id, "awaiting-decision"))
        # The applicant's browser retries the same submission.
        assert (
            await request.deliver(
                Request.supply({"amount": 999}), key=f"info-{request_id}"
            )
            == 0
        )

        assert (
            await request.deliver(
                Request.decide("approve", by="sam"), key=f"decision-{request_id}"
            )
            == 1
        )
        await eventually(reaches(request_id, "filed"))

    row = await read_directly(database, request_id)
    assert (row.document or {})["amount"] == 250
    # Parsing happened before the restart and is never repeated after it.
    assert world.attempts("forms.parse") == 1
    assert len(world.effects("registry.file")) == 1
