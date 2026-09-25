"""Tests for reflex_workflow.model: typed steps and their runtime guards.

The ``pyright: ignore`` comments below mark calls that must fail type checking; with
unnecessary ignores reported, pyright fails if one of them stops being an error.
"""

# pyright: reportUnnecessaryTypeIgnoreComment=true

from __future__ import annotations

import datetime
from typing import Literal

import pytest
from reflex_workflow import (
    Call,
    Limit,
    RateBucket,
    RunHandle,
    Wait,
    WakeIn,
    Workflow,
    every,
    model,
    step,
    wait_for,
    wake_in,
)
from reflex_workflow.engine import claim
from reflex_workflow.model import check_call
from sqlalchemy import String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from typing_extensions import assert_type


class Base(DeclarativeBase):
    """Declarative base for the test tables."""


class Expense(Base, Workflow):
    """An expense waiting for a decision."""

    __tablename__ = "wf_model_expense"

    id: Mapped[int] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(String, default="new")

    @step(retries=3, backoff=datetime.timedelta(seconds=10))
    async def notify(self):
        """Wait two days for a decision.

        Returns:
            The escalation, two days from now.
        """
        return wake_in(Expense.escalate(), datetime.timedelta(days=2))

    @step
    async def decide(
        self, decision: Literal["approve", "reject"], *, by: str = "manager"
    ):
        """Record a decision.

        Args:
            decision: The decision.
            by: Who decided.
        """
        self.status = f"{decision}:{by}"

    @step
    async def escalate(self):
        """Escalate a stale expense."""
        self.status = "escalated"


class Other(Base, Workflow):
    """An unrelated workflow."""

    __tablename__ = "wf_model_other"

    id: Mapped[int] = mapped_column(primary_key=True)

    @step
    async def go(self):
        """Do nothing."""


class Mistaken(Base, Workflow):
    """Steps that return things a step may not return."""

    __tablename__ = "wf_model_mistaken"

    id: Mapped[int] = mapped_column(primary_key=True)

    @step  # pyright: ignore[reportArgumentType]
    async def returns_a_number(self):
        """Return a value that is not a transition.

        Returns:
            A number.
        """
        return 42

    @step  # pyright: ignore[reportArgumentType]
    async def returns_another_workflows_step(self):
        """Return a step of a different workflow.

        Returns:
            Another workflow's step call.
        """
        return Other.go()

    @step  # pyright: ignore[reportArgumentType]
    async def waits_on_another_workflows_step(self):
        """Wait for a step of a different workflow.

        Returns:
            A wait belonging to another workflow.
        """
        return wait_for(Other.go)


class Shared(Workflow):
    """Steps several tables share; unmapped, so each table maps its own."""

    id: Mapped[int] = mapped_column(primary_key=True)

    @step
    async def begin(self):
        """Do nothing."""


class First(Base, Shared):
    """One table using the shared steps."""

    __tablename__ = "wf_model_first"


class Second(Base, Shared):
    """Another table using the shared steps."""

    __tablename__ = "wf_model_second"


def test_step_calls_are_typed_by_their_workflow():
    assert_type(Expense.decide("approve"), Call[Expense])
    assert_type(
        wake_in(Expense.escalate(), datetime.timedelta(hours=1)), WakeIn[Expense]
    )
    assert_type(Expense.by(Expense.id == 1), RunHandle[Expense])
    assert_type(wake_in(Expense.escalate, datetime.timedelta(hours=1)), WakeIn[Expense])


def test_a_wait_is_typed_by_the_step_it_waits_on():
    assert_type(
        wait_for(
            Expense.decide,
            timeout=datetime.timedelta(days=1),
            on_timeout=Expense.escalate,
        ),
        Wait[Expense],
    )
    wait_for(
        Expense.decide,
        timeout=datetime.timedelta(days=1),
        on_timeout=Other.go,  # pyright: ignore[reportArgumentType]
    )


def test_steps_defined_on_a_shared_base_belong_to_each_table():
    assert (
        First.__workflow_steps__ == Second.__workflow_steps__ == {"begin": Shared.begin}
    )
    check_call(First, Shared.begin())
    check_call(Second, Shared.begin())


def test_step_arguments_are_checked():
    Expense.decide("maybe")  # pyright: ignore[reportArgumentType]
    Expense.decide("approve", by=1)  # pyright: ignore[reportArgumentType]
    Expense.decide()  # pyright: ignore[reportCallIssue]
    Expense.escalate("now")  # pyright: ignore[reportCallIssue]


async def _never_called() -> None:
    """Hold calls that must not type-check; never run."""
    await Expense().start(Other.go())  # pyright: ignore[reportArgumentType]
    await Expense().start(Expense.decide)  # pyright: ignore[reportArgumentType]
    await Expense.by(Expense.id == 1).run(Other.go())  # pyright: ignore[reportArgumentType]
    await Expense.by(Expense.id == 1).deliver(Other.go())  # pyright: ignore[reportArgumentType]
    # A step of a shared base is a step of every table that inherits it.
    await First().start(Shared.begin)
    await Second.by(Second.id == 1).run(Shared.begin())


def test_steps_are_collected_with_their_retry_policy():
    assert set(Expense.__workflow_steps__) == {"notify", "decide", "escalate"}
    notify = Expense.__workflow_steps__["notify"]
    assert (notify.retries, notify.backoff) == (3, datetime.timedelta(seconds=10))


def test_a_call_keeps_its_arguments_as_json():
    call = Expense.decide("approve", by="ops")
    assert call.encode() == {"args": ["approve"], "kwargs": {"by": "ops"}}


def test_arguments_that_are_not_json_are_rejected():
    call = Expense.decide(datetime.date(2026, 1, 1))  # pyright: ignore[reportArgumentType]
    with pytest.raises(TypeError, match="JSON-serializable"):
        call.encode()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), "circular"])
def test_arguments_json_cannot_hold_are_rejected(value: object):
    if value == "circular":
        value = []
        value.append(value)
    call = Expense.decide(value)  # pyright: ignore[reportArgumentType]
    with pytest.raises(TypeError, match="JSON-serializable"):
        call.encode()


def test_an_interval_has_to_be_positive():
    for interval in (datetime.timedelta(0), datetime.timedelta(seconds=-1)):
        with pytest.raises(ValueError, match="positive interval"):
            every(Expense.escalate, interval)


def test_a_bare_step_is_a_call_without_arguments():
    assert wake_in(Expense.escalate, datetime.timedelta(0)).call == Expense.escalate()


def test_a_bare_step_that_needs_arguments_is_rejected():
    with pytest.raises(TypeError, match="takes arguments"):
        wake_in(Expense.decide, datetime.timedelta(days=1))  # pyright: ignore[reportArgumentType]


def test_another_workflows_step_is_rejected_at_runtime():
    with pytest.raises(TypeError, match="not a step of Expense"):
        check_call(Expense, Other.go())


def test_a_class_of_the_same_name_from_another_module_cannot_take_a_table():
    with pytest.raises(ValueError, match="already used by Expense"):
        type(
            "Expense",
            (Workflow,),
            {"__module__": "somewhere.else", "__tablename__": "wf_model_expense"},
        )


def test_two_workflows_cannot_share_a_table():
    with pytest.raises(ValueError, match="already used by Expense"):

        class Duplicate(Workflow):
            __tablename__ = "wf_model_expense"


class Metered(Base, Workflow):
    """A workflow that limits how often it calls a provider."""

    __tablename__ = "wf_model_metered"
    __workflow_limit__ = Limit(
        by="provider", rate=60, per=datetime.timedelta(minutes=1)
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String)

    @step
    async def call(self):
        """Call the provider."""


def test_a_limit_has_to_cap_something():
    with pytest.raises(ValueError, match="at_most, rate, or both"):
        Limit(by="customer")


@pytest.mark.parametrize(
    "caps",
    [
        {"at_most": 0},
        {"rate": 0, "per": datetime.timedelta(minutes=1)},
        {"rate": 5, "per": datetime.timedelta(0)},
    ],
)
def test_a_limit_has_to_be_positive(caps: dict[str, object]):
    with pytest.raises(ValueError, match="must be positive"):
        Limit(by="customer", **caps)  # pyright: ignore[reportArgumentType]


def test_a_rate_needs_the_period_it_is_counted_over():
    with pytest.raises(ValueError, match="rate and per together"):
        Limit(by="customer", rate=60)
    # A period without a rate says nothing, even alongside a concurrency cap.
    with pytest.raises(ValueError, match="rate and per together"):
        Limit(by="customer", at_most=2, per=datetime.timedelta(minutes=1))


async def test_a_rate_without_a_bucket_table_says_so(monkeypatch):
    monkeypatch.setattr(model, "BUCKET", None)
    spec = Metered.__workflow_limit__
    assert spec is not None
    with pytest.raises(TypeError, match="rate bucket table must be mapped"):
        await claim.take_tokens(None, Metered, spec, "stripe", 1)  # pyright: ignore[reportArgumentType]


def test_only_one_bucket_table_may_be_mapped(monkeypatch):
    # Whichever test module ran first has mapped one; this is about the second.
    monkeypatch.setattr(model, "BUCKET", None)

    class Buckets(Base, RateBucket):
        __tablename__ = "wf_model_rate"

    assert model.BUCKET is Buckets
    with pytest.raises(ValueError, match="already mapped"):

        class Second(Base, RateBucket):
            __tablename__ = "wf_model_rate_again"


def test_arguments_a_step_cannot_take_are_rejected_where_the_call_is_made():
    # A webhook body that does not fit the step it addresses is refused while
    # there is still a caller to tell.
    with pytest.raises(TypeError, match="cannot take those arguments"):
        check_call(Expense, Expense.decide(verdikt="approve"))  # pyright: ignore[reportCallIssue]
    with pytest.raises(TypeError, match="cannot take those arguments"):
        check_call(Expense, Expense.decide("approve", "again"))  # pyright: ignore[reportCallIssue]
    check_call(Expense, Expense.decide("approve"))
