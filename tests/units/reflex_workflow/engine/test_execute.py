"""Tests for reflex_workflow.engine.execute that don't need a database."""

from __future__ import annotations

import datetime
from typing import Literal

import pytest
from reflex_workflow import Workflow, step, wait_for, wake_in
from reflex_workflow.engine.execute import Scheduled, resolve
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for the test tables."""


class Review(Base, Workflow):
    """A review waiting for a decision."""

    __tablename__ = "wf_execute_review"

    id: Mapped[int] = mapped_column(primary_key=True)

    @step
    async def decide(self, decision: Literal["approve", "reject"]):
        """Record a decision.

        Args:
            decision: The decision.
        """

    @step
    async def escalate(self):
        """Escalate a stale review."""


class Other(Base, Workflow):
    """An unrelated workflow."""

    __tablename__ = "wf_execute_other"

    id: Mapped[int] = mapped_column(primary_key=True)

    @step
    async def go(self):
        """Do nothing."""


def test_resolve_accepts_calls_bare_steps_and_none():
    call = Review.decide("reject")
    no_delay = datetime.timedelta()
    assert resolve(Review, None) == Scheduled(None, None)
    assert resolve(Review, call) == Scheduled(call, no_delay)
    assert resolve(Review, Review.escalate) == Scheduled(Review.escalate(), no_delay)
    assert resolve(Review, wake_in(call, datetime.timedelta(days=2))) == Scheduled(
        call, datetime.timedelta(days=2)
    )


def test_resolve_turns_a_wait_into_a_deadline_and_a_channel():
    day = datetime.timedelta(days=1)
    assert resolve(
        Review, wait_for(Review.decide, timeout=day, on_timeout=Review.escalate)
    ) == Scheduled(Review.escalate(), day, "decide")
    # Without a deadline the row only waits: nothing is scheduled to wake it.
    assert resolve(Review, wait_for(Review.decide)) == Scheduled(None, None, "decide")


def test_wait_for_needs_a_timeout_and_its_step_together():
    with pytest.raises(ValueError, match="together"):
        wait_for(Review.decide, timeout=datetime.timedelta(days=1))
    with pytest.raises(ValueError, match="together"):
        wait_for(Review.decide, on_timeout=Review.escalate)


def test_resolve_rejects_a_wait_on_a_foreign_step():
    with pytest.raises(TypeError):
        resolve(Review, wait_for(Other.go))
    with pytest.raises(TypeError):
        resolve(
            Review,
            wait_for(
                Review.decide,
                timeout=datetime.timedelta(days=1),
                on_timeout=Other.go,  # pyright: ignore[reportArgumentType]
            ),
        )


@pytest.mark.parametrize("returned", [42, Other.go(), Review.decide])
def test_resolve_rejects_anything_else(returned: object):
    with pytest.raises(TypeError):
        resolve(Review, returned)
