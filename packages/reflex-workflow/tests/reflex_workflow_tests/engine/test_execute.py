"""Tests for reflex_workflow.engine.execute that don't need a database."""

from __future__ import annotations

import datetime
from typing import Literal

import pytest
from reflex_workflow import Workflow, step, wait_for, wake_in
from reflex_workflow.engine.execute import Scheduled, backoff_for, resolve
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


class Lookalike(Base, Workflow):
    """A workflow with a step named like one of Review's."""

    __tablename__ = "wf_execute_lookalike"

    id: Mapped[int] = mapped_column(primary_key=True)

    @step
    async def decide(self, decision: str):
        """Record something else entirely.

        Args:
            decision: Whatever it is.
        """


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


def test_resolve_rejects_a_wait_on_another_workflows_step_of_the_same_name():
    with pytest.raises(TypeError, match="not a step of Review"):
        resolve(Review, wait_for(Lookalike.decide))


@step(retries=50)
async def retried(self):
    """A step with the usual 30s backoff and one hour cap."""


@pytest.mark.parametrize(
    ("attempts", "seconds"),
    [(1, 30), (2, 60), (3, 120), (7, 1920), (8, 3600), (40, 3600), (1000, 3600)],
)
def test_a_retry_waits_twice_as_long_as_the_last_up_to_the_cap(attempts, seconds):
    # Doubling for good runs past what a timestamp can hold, and past what a
    # timedelta can before that, so the wait stops growing at the cap.
    assert backoff_for(retried, attempts) == datetime.timedelta(seconds=seconds)


def test_a_step_that_gives_its_own_cap_is_held_to_it():
    @step(
        backoff=datetime.timedelta(seconds=1), max_backoff=datetime.timedelta(seconds=5)
    )
    async def brisk(self):
        """A step that retries quickly."""

    assert [backoff_for(brisk, n).total_seconds() for n in (1, 2, 3, 4, 20)] == [
        1,
        2,
        4,
        5,
        5,
    ]


def test_a_cap_below_the_first_wait_is_still_the_cap():
    @step(
        backoff=datetime.timedelta(minutes=5),
        max_backoff=datetime.timedelta(seconds=30),
    )
    async def odd(self):
        """A step whose first wait already passes its cap."""

    assert backoff_for(odd, 1) == datetime.timedelta(seconds=30)
