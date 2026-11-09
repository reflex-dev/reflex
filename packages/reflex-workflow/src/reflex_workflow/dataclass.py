"""The same mixins, for applications whose models are dataclasses.

An application that maps its tables on a ``MappedAsDataclass`` base cannot mix
in a class that is not one itself: SQLAlchemy warns about it in 2.0 and refuses
it in 2.1. The mixins here are that same class declared as a dataclass, so::

    from sqlalchemy.orm import DeclarativeBase, MappedAsDataclass
    from reflex_workflow.dataclass import Workflow


    class Base(MappedAsDataclass, DeclarativeBase, kw_only=True):
        pass


    class Onboarding(Base, Workflow):
        __tablename__ = "onboarding"

        id: Mapped[int] = mapped_column(primary_key=True, init=False)
        email: Mapped[str]

Everything else is unchanged: the same columns, the same steps, the same
engine. The columns the engine owns are ``init=False``, so they stay out of the
constructor and ``Onboarding(email=...)`` reads as it did before the mixin was
added.

Which import to take is decided by the base, not by preference. On a plain
``DeclarativeBase`` these would make the model a dataclass, which is a change
the application did not ask for, so that base takes ``reflex_workflow`` itself.
"""

from __future__ import annotations

import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, MappedAsDataclass, declared_attr, mapped_column

from reflex_workflow import model
from reflex_workflow.model import ZERO

__all__ = ["AttemptLog", "RateBucket", "Workflow"]


class Workflow(MappedAsDataclass, model.Workflow):
    """``reflex_workflow.Workflow``, for a model that is a dataclass.

    Each row is one run. The engine's own columns are ``init=False``: they are
    the engine's to set, and a run is started with ``start`` rather than by
    passing them.
    """

    next_step: Mapped[str | None] = mapped_column(
        String(128), default=None, index=True, init=False
    )
    next_args: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), default=None, init=False
    )
    wake_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, index=True, init=False
    )
    attempts: Mapped[int] = mapped_column(
        Integer, default=0, server_default=ZERO, init=False
    )
    last_error: Mapped[str | None] = mapped_column(Text, default=None, init=False)
    claimed_until: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, init=False
    )
    waiting_for: Mapped[str | None] = mapped_column(
        String(128), default=None, index=True, init=False
    )
    parent: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), default=None, init=False
    )
    children_left: Mapped[int | None] = mapped_column(Integer, default=None, init=False)
    pending_event: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), default=None, init=False
    )
    recent_event_keys: Mapped[list[str] | None] = mapped_column(
        JSONB(none_as_null=True), default=None, init=False
    )
    wf_version: Mapped[int] = mapped_column(
        Integer, default=0, server_default=ZERO, init=False
    )


class AttemptLog(MappedAsDataclass, model.AttemptLog):
    """``reflex_workflow.AttemptLog``, for a model that is a dataclass.

    Every column is ``init=False``: the engine writes these rows with an insert
    of its own, and nothing constructs one.
    """

    __tablename__: ClassVar[str]

    id: Mapped[int] = mapped_column(
        Integer, primary_key=True, autoincrement=True, init=False
    )
    workflow: Mapped[str] = mapped_column(String(128), init=False)
    run: Mapped[list[Any]] = mapped_column(JSONB, init=False)
    step: Mapped[str] = mapped_column(String(128), init=False)
    attempt: Mapped[int] = mapped_column(Integer, init=False)
    outcome: Mapped[str] = mapped_column(String(16), init=False)
    error: Mapped[str | None] = mapped_column(Text, default=None, init=False)
    took_ms: Mapped[int] = mapped_column(Integer, init=False)
    finished_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), init=False
    )

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Any, ...]:  # noqa: N805
        """Index the history by the run it belongs to.

        Returns:
            The table's arguments.
        """
        return (Index(f"ix_{cls.__tablename__}_run", "workflow", "run"),)


class RateBucket(MappedAsDataclass, model.RateBucket):
    """``reflex_workflow.RateBucket``, for a model that is a dataclass.

    Every column is ``init=False``: the engine keeps these rows itself, with an
    upsert that creates a group's bucket the first time it is seen.
    """

    key: Mapped[str] = mapped_column(String(256), primary_key=True, init=False)
    tokens: Mapped[float] = mapped_column(
        Float, default=0.0, server_default=ZERO, init=False
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), init=False
    )
