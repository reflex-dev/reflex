"""The workflow mixin, typed steps, and step transitions."""

from __future__ import annotations

import dataclasses
import datetime
import inspect
import json
from collections.abc import Awaitable, Callable, Collection, Iterable
from typing import (
    TYPE_CHECKING,
    Any,
    ClassVar,
    Concatenate,
    Generic,
    ParamSpec,
    TypeAlias,
    TypeVar,
    overload,
)

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, literal
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

if TYPE_CHECKING:
    from sqlalchemy import ColumnElement

    from reflex_workflow.engine.handles import RunHandle

# Contravariant, so a step defined on a shared base class is a step of every
# table that inherits it.
W = TypeVar("W", bound="Workflow", contravariant=True)
# A second workflow variable, for the children a run fans out to. Invariant: a
# child is paired with its own first step, and both name the same class.
C = TypeVar("C", bound="Workflow")
P = ParamSpec("P")

DEFAULT_BACKOFF = datetime.timedelta(seconds=30)

# The lane a step runs in unless it says otherwise, and the one a worker serves
# unless it is told otherwise.
DEFAULT_LANE = "default"

# How many delivered event keys a row remembers, to refuse repeats of them.
EVENT_KEY_HISTORY = 16

# Workflow classes by table name, filled in as classes are defined.
REGISTRY: dict[str, type[Workflow]] = {}

# The columns the mixin adds; everything else on the row belongs to the user.
WORKFLOW_COLUMNS = frozenset({
    "next_step",
    "next_args",
    "wake_at",
    "attempts",
    "last_error",
    "claimed_until",
    "waiting_for",
    "pending_event",
    "recent_event_keys",
    "parent",
    "children_left",
    "wf_version",
})


@dataclasses.dataclass(frozen=True, slots=True)
class Call(Generic[W]):
    """A step of workflow ``W`` bound to the arguments it will be called with."""

    step: Step[W, Any]
    args: tuple[Any, ...]
    kwargs: dict[str, Any]

    def encode(self) -> dict[str, Any]:
        """Return the arguments in the form stored in ``next_args``.

        Returns:
            The JSON-serializable arguments.

        Raises:
            TypeError: If an argument cannot be stored as JSON.
        """
        payload = {"args": list(self.args), "kwargs": self.kwargs}
        try:
            # NaN and infinity are not JSON, and Postgres refuses them in JSONB.
            json.dumps(payload, allow_nan=False)
        except (TypeError, ValueError) as err:
            msg = (
                f"Arguments to step {self.step.name!r} must be JSON-serializable: {err}"
            )
            raise TypeError(msg) from None
        return payload


@dataclasses.dataclass(frozen=True, slots=True)
class Limit:
    """How much of one workflow may run, and how often it may start.

    Attributes:
        by: The column that says which group a run belongs to, such as the
            customer it is for or the provider it calls.
        at_most: How many of one group's runs may be running at the same moment,
            counted across every worker. None for no such cap.
        rate: How many of one group's steps may start per ``per``. None for no
            such cap.
        per: The period ``rate`` is counted over.
    """

    by: str
    at_most: int | None = None
    rate: int | None = None
    per: datetime.timedelta | None = None

    def __post_init__(self) -> None:
        """Check the limit says something, and says it completely.

        Raises:
            ValueError: If it caps nothing, gives a rate without a period, or
                gives a value that is not positive.
        """
        if self.at_most is None and self.rate is None:
            msg = "A Limit needs at_most, rate, or both."
            raise ValueError(msg)
        if (self.rate is None) != (self.per is None):
            msg = "A Limit takes rate and per together, or neither."
            raise ValueError(msg)
        # A cap of nothing would leave the group's runs waiting forever without
        # saying why, and a period of nothing cannot be divided by.
        if (
            (self.at_most is not None and self.at_most < 1)
            or (self.rate is not None and self.rate < 1)
            or (self.per is not None and self.per <= datetime.timedelta())
        ):
            msg = "A Limit's at_most, rate and per must be positive."
            raise ValueError(msg)


@dataclasses.dataclass(frozen=True, slots=True)
class Child:
    """A run to start, paired with the step it starts at."""

    row: Workflow
    first: Call[Any]


@dataclasses.dataclass(frozen=True, slots=True)
class FanOut(Generic[W]):
    """A transition that starts many runs and waits for all of them."""

    children: tuple[Child, ...]
    then: Call[W]


@dataclasses.dataclass(frozen=True, slots=True)
class Wait(Generic[W]):
    """A transition that waits for an event, optionally with a deadline."""

    then: Step[W, Any]
    timeout: datetime.timedelta | None
    on_timeout: Call[W] | None


# A repeating schedule: a fixed interval, or anything that answers with the next
# time to run, such as a ``Cron`` or a function wrapping another cron library.
Schedule: TypeAlias = (
    "datetime.timedelta | Callable[[datetime.datetime], datetime.datetime]"
)


@dataclasses.dataclass(frozen=True, slots=True)
class Every(Generic[W]):
    """A transition that repeats a step on a schedule."""

    call: Call[W]
    schedule: Schedule


@dataclasses.dataclass(frozen=True, slots=True)
class WakeIn(Generic[W]):
    """A transition that runs a step after a delay."""

    call: Call[W]
    delay: datetime.timedelta


StepFn: TypeAlias = Callable[
    Concatenate[W, P],
    Awaitable[
        "Call[W] | Step[W, []] | WakeIn[W] | Wait[W] | Every[W] | FanOut[W] | None"
    ],
]


class Step(Generic[W, P]):
    """A step method of workflow ``W`` taking parameters ``P``.

    Calling it does not run it: ``Expense.decide("approve")`` builds a ``Call`` that
    ``start``, ``run``, ``wake_in``, or a step's return value hands to the engine.
    """

    def __init__(
        self,
        fn: StepFn[W, P],
        retries: int,
        backoff: datetime.timedelta,
        lane: str = DEFAULT_LANE,
    ) -> None:
        """Wrap a step method.

        Args:
            fn: The method.
            retries: How many times to retry the step after it raises.
            backoff: Delay before the first retry; each retry doubles it.
            lane: Which workers may run it.
        """
        self.fn = fn
        self.name = fn.__name__
        self.retries = retries
        self.backoff = backoff
        self.lane = lane

    def __call__(self, *args: P.args, **kwargs: P.kwargs) -> Call[W]:
        """Bind arguments to this step.

        Args:
            *args: Positional arguments for the step.
            **kwargs: Keyword arguments for the step.

        Returns:
            The step call, to be scheduled by the engine.
        """
        return Call(self, args, kwargs)

    def __repr__(self) -> str:
        """Name the step in reprs and error messages.

        Returns:
            The step's repr.
        """
        return f"<step {self.name}>"


# A step reference: a call with its arguments, or a step that takes none.
StepRef: TypeAlias = "Call[W] | Step[W, []]"


def as_call(ref: StepRef[W]) -> Call[W]:
    """Turn a step reference into a call.

    Args:
        ref: A step call, or a step that takes no arguments.

    Returns:
        The step call.

    Raises:
        TypeError: If ``ref`` is a bare step that needs arguments.
    """
    if isinstance(ref, Call):
        return ref
    try:
        inspect.signature(ref.fn).bind(None)
    except TypeError:
        msg = f"{ref!r} takes arguments; call it with them, e.g. {ref.name}(...)."
        raise TypeError(msg) from None
    return Call(ref, (), {})


def same_class(a: type, b: type) -> bool:
    """Tell whether two classes are one definition, perhaps defined again.

    A module that is imported twice, or a test that defines a class again,
    produces a new class object for the same definition; one of the same name
    from another module is a different definition.

    Args:
        a: One class.
        b: The other.

    Returns:
        Whether they share a module and a qualified name.
    """
    return (a.__module__, a.__qualname__) == (b.__module__, b.__qualname__)


def check_owner(cls: type[Workflow], call: Call[Any]) -> None:
    """Reject a step call that belongs to a different workflow class.

    Args:
        cls: The workflow class the call is for.
        call: The step call.

    Raises:
        TypeError: If the step is not one of ``cls``'s steps.
    """
    if cls.__workflow_steps__.get(call.step.name) is not call.step:
        msg = f"{call.step!r} is not a step of {cls.__qualname__}."
        raise TypeError(msg)


@overload
def step(fn: StepFn[W, P], /) -> Step[W, P]: ...


@overload
def step(
    *,
    retries: int = 0,
    backoff: datetime.timedelta = DEFAULT_BACKOFF,
    lane: str = DEFAULT_LANE,
) -> Callable[[StepFn[W, P]], Step[W, P]]: ...


def step(
    fn: StepFn[W, P] | None = None,
    /,
    *,
    retries: int = 0,
    backoff: datetime.timedelta = DEFAULT_BACKOFF,
    lane: str = DEFAULT_LANE,
) -> Step[W, P] | Callable[[StepFn[W, P]], Step[W, P]]:
    """Declare a workflow step.

    A step changes the row, does its work, and returns the next transition: another
    step call to run now, ``wake_in(...)`` to run one later, or ``None`` to stop.

    Args:
        fn: The method, when used as a bare decorator.
        retries: How many times to retry the step after it raises.
        backoff: Delay before the first retry; each retry doubles it.
        lane: Which workers may run this step. A step in a lane of its own runs
            only on workers told to serve that lane, so work that needs a GPU, a
            browser, or a particular network can be kept off the others.

    Returns:
        The step, or a decorator that makes one.
    """

    def make(method: StepFn[W, P]) -> Step[W, P]:
        return Step(method, retries, backoff, lane)

    return make(fn) if fn is not None else make


def steps_in(cls: type[Workflow], lanes: Collection[str]) -> list[str]:
    """Name the steps of a workflow that a worker serving ``lanes`` may run.

    Args:
        cls: The workflow class.
        lanes: The lanes the worker serves.

    Returns:
        The step names, empty when the worker may run none of them.
    """
    return [name for name, spec in cls.__workflow_steps__.items() if spec.lane in lanes]


def child(row: C, first: StepRef[C]) -> Child:
    """Pair a run to start with the step it starts at.

    Args:
        row: A transient instance of a workflow class.
        first: That class's step to start at.

    Returns:
        The child, for ``fan_out``.
    """
    call = as_call(first)
    check_owner(type(row), call)
    return Child(row, call)


def fan_out(children: Iterable[Child], *, then: StepRef[W]) -> FanOut[W]:
    """Start many runs, and carry on once every one of them has finished.

    Each child is a run of its own: claimed by whichever worker is free, retried
    on its own, and recorded on its own row. The parent does nothing meanwhile --
    it holds no worker and no connection -- and ``then`` runs once the last child
    is done, whether the children succeeded or gave up.

    A child that hits a unique constraint is not started, which is what makes a
    fan-out that runs twice after a crash start each child once.

    Args:
        children: The runs to start, each from ``child(...)``.
        then: The step to run once they have all finished.

    Returns:
        The transition to return from a step.
    """
    return FanOut(tuple(children), as_call(then))


def wait_for(
    then: Step[W, Any],
    *,
    timeout: datetime.timedelta | None = None,
    on_timeout: StepRef[W] | None = None,
) -> Wait[W]:
    """Wait for an event that runs ``then`` with the arguments it carries.

    An event delivered before the wait arms is kept and applied as soon as it does.
    If the deadline passes first, ``on_timeout`` runs instead and the wait is over;
    whichever happens first wins, and the other is discarded.

    Args:
        then: The step a delivered event runs. Its name is the channel that
            ``deliver`` addresses.
        timeout: How long to wait before giving up; None waits indefinitely.
        on_timeout: The step to run when the deadline passes; required with a timeout.

    Returns:
        The transition to return from a step.

    Raises:
        ValueError: If only one of ``timeout`` and ``on_timeout`` is given.
    """
    if (timeout is None) != (on_timeout is None):
        msg = "wait_for takes timeout and on_timeout together, or neither."
        raise ValueError(msg)
    return Wait(then, timeout, as_call(on_timeout) if on_timeout is not None else None)


def every(call: StepRef[W], schedule: Schedule) -> Every[W]:
    """Run a step again on a schedule, and keep doing so.

    An interval counts from the run's last scheduled time rather than from now, so
    a slow step does not push the schedule later and later. Occurrences missed
    while nothing was running collapse into one: the step runs once, then carries
    on with the schedule.

    Args:
        call: The step call, or a step that takes no arguments.
        schedule: How often to run it: an interval, or something that answers with
            the next time to run, such as ``Cron("0 9 * * MON-FRI")``.

    Returns:
        The transition to return from a step.

    Raises:
        ValueError: If an interval is not positive.
    """
    if isinstance(schedule, datetime.timedelta) and schedule <= datetime.timedelta():
        msg = f"every() needs a positive interval; got {schedule}."
        raise ValueError(msg)
    return Every(as_call(call), schedule)


def wake_in(call: StepRef[W], delay: datetime.timedelta) -> WakeIn[W]:
    """Run a step after a delay.

    Args:
        call: The step call, or a step that takes no arguments.
        delay: How long to wait.

    Returns:
        The transition to return from a step.
    """
    return WakeIn(as_call(call), delay)


# The mapped classes holding rate-limit buckets and attempt history, once an
# application declares them. Neither is required.
BUCKET: type[RateBucket] | None = None
ATTEMPTS: type[AttemptLog] | None = None


class RateBucket:
    """Mixin for the table a rate limit counts in.

    An application that rate-limits a workflow maps one of these onto its own
    base, so the table is migrated with the rest of its schema:

    ```python
    class WorkflowRate(Base, RateBucket):
        __tablename__ = "workflow_rate"
    ```

    One row per group, holding tokens that refill over time. Nothing else reads
    it, and it is safe to truncate: the limits simply start full again.
    """

    key: Mapped[str] = mapped_column(String(256), primary_key=True)
    tokens: Mapped[float] = mapped_column(Float, default=0.0)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))

    def __init_subclass__(cls, **kwargs: Any):
        """Record the mapped bucket table the engine should use.

        Args:
            **kwargs: Passed through to other ``__init_subclass__`` hooks.

        Raises:
            ValueError: If a second bucket table is mapped.
        """
        super().__init_subclass__(**kwargs)
        global BUCKET
        if cls.__dict__.get("__tablename__") is None:
            return
        if BUCKET is not None and not same_class(BUCKET, cls):
            msg = f"A rate bucket is already mapped by {BUCKET.__qualname__}."
            raise ValueError(msg)
        BUCKET = cls


class AttemptLog:
    """Mixin for a table that records what each step attempt did.

    A row carries where a run is now. An application that wants to see how it got
    there -- what was tried, what failed, how long it took -- maps one of these
    onto its own base, and the engine writes a row per committed attempt:

    ```python
    class WorkflowAttempt(Base, AttemptLog):
        __tablename__ = "workflow_attempt"
    ```

    Nothing reads it but the application, and nothing depends on it: it can be
    pruned on whatever schedule suits, and a deployment that never maps it pays
    nothing. An attempt whose commit was refused writes no row, because it
    changed nothing.
    """

    # Declared for the type checker, as on Workflow: a mapped class has one.
    __tablename__: ClassVar[str]

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workflow: Mapped[str] = mapped_column(String(128))
    run: Mapped[list[Any]] = mapped_column(JSONB)
    step: Mapped[str] = mapped_column(String(128))
    attempt: Mapped[int] = mapped_column(Integer)
    outcome: Mapped[str] = mapped_column(String(16))
    error: Mapped[str | None] = mapped_column(Text, default=None)
    took_ms: Mapped[int] = mapped_column(Integer)
    finished_at: Mapped[datetime.datetime] = mapped_column(DateTime(timezone=True))

    @declared_attr.directive
    def __table_args__(cls) -> tuple[Any, ...]:  # noqa: N805
        """Index the history by the run it belongs to.

        Returns:
            The table's arguments.
        """
        return (Index(f"ix_{cls.__tablename__}_run", "workflow", "run"),)

    def __init_subclass__(cls, **kwargs: Any):
        """Record the mapped history table the engine should write to.

        Args:
            **kwargs: Passed through to other ``__init_subclass__`` hooks.

        Raises:
            ValueError: If a second history table is mapped.
        """
        super().__init_subclass__(**kwargs)
        global ATTEMPTS
        if cls.__dict__.get("__tablename__") is None:
            return
        if ATTEMPTS is not None and not same_class(ATTEMPTS, cls):
            msg = f"Attempt history is already mapped by {ATTEMPTS.__qualname__}."
            raise ValueError(msg)
        ATTEMPTS = cls


class Workflow:
    """Mixin that turns a mapped SQLAlchemy model into a durable workflow.

    Each row is one run. The mixin adds the columns the engine needs; the rest of
    the table is the run's state, owned and migrated by the application.
    """

    next_step: Mapped[str | None] = mapped_column(String(128), default=None, index=True)
    # none_as_null, so clearing one of these writes SQL NULL rather than a JSON
    # null: the engine's own predicates ask whether they are null.
    next_args: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), default=None
    )
    wake_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, default=None)
    claimed_until: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    waiting_for: Mapped[str | None] = mapped_column(
        String(128), default=None, index=True
    )
    # Which run fanned this one out, as {"table": ..., "pk": [...]}, and how many
    # children a run is still waiting for.
    parent: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), default=None
    )
    children_left: Mapped[int | None] = mapped_column(Integer, default=None)
    pending_event: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB(none_as_null=True), default=None
    )
    recent_event_keys: Mapped[list[str] | None] = mapped_column(
        JSONB(none_as_null=True), default=None
    )
    wf_version: Mapped[int] = mapped_column(Integer, default=0)

    # Declared for the type checker: every workflow is a mapped class, so it has
    # one, and children record it to name the run they belong to.
    __tablename__: ClassVar[str]

    #: How much of this workflow may run at once, per group; None is unlimited.
    __workflow_limit__: ClassVar[Limit | None] = None

    __workflow_steps__: ClassVar[dict[str, Step[Any, Any]]] = {}

    def __init_subclass__(cls, **kwargs: Any):
        """Collect the class's steps and register it by table name.

        Args:
            **kwargs: Passed through to other ``__init_subclass__`` hooks.

        Raises:
            ValueError: If two workflow classes use the same table name.
        """
        super().__init_subclass__(**kwargs)
        cls.__workflow_steps__ = {
            value.name: value
            for klass in reversed(cls.__mro__)
            for value in vars(klass).values()
            if isinstance(value, Step)
        }
        table = cls.__dict__.get("__tablename__")
        if table is None:
            return
        existing = REGISTRY.get(table)
        if existing is not None and not same_class(existing, cls):
            msg = (
                f"Workflow table {table!r} is already used by {existing.__qualname__}."
            )
            raise ValueError(msg)
        REGISTRY[table] = cls

    async def start(self: W, first: StepRef[W]) -> bool:
        """Insert this row and schedule its first step.

        A row that conflicts with an existing one on any unique constraint is not
        inserted, so the same key never starts two runs.

        Args:
            first: The first step call, or a step that takes no arguments.

        Returns:
            Whether a new run was started.
        """
        # Imported here: the engine imports this module for REGISTRY and the columns.
        from reflex_workflow.engine.handles import start

        return await start(self, as_call(first))

    def as_parent(self) -> dict[str, Any]:
        """Describe this run the way its children point at it.

        Returns:
            The table and primary key that identify this row.
        """
        from reflex_workflow.engine import rows

        cls = type(self)
        return {
            "table": cls.__tablename__,
            "pk": [getattr(self, key) for key in rows.pk_keys(cls)],
        }

    async def history(self, limit: int = 50) -> list[AttemptLog]:
        """Read what this run has tried, most recent first.

        Args:
            limit: Most attempts to return.

        Returns:
            The attempts recorded for this run, or nothing when no history table
            is mapped.
        """
        from sqlalchemy import desc, select

        from reflex_workflow.engine import rows
        from reflex_workflow.engine.runtime import current

        if ATTEMPTS is None:
            return []
        cls = type(self)
        stmt = (
            select(ATTEMPTS)
            .where(
                ATTEMPTS.workflow == cls.__tablename__,
                ATTEMPTS.run == [getattr(self, key) for key in rows.pk_keys(cls)],
            )
            .order_by(desc(ATTEMPTS.id))
            .limit(limit)
        )
        async with current().session_factory() as session:
            return list((await session.execute(stmt)).scalars().all())

    def children(self, cls: type[C]) -> RunHandle[C]:
        """Address the runs of one class that this run fanned out to.

        Args:
            cls: The children's workflow class.

        Returns:
            A handle for reading them.

        Raises:
            TypeError: If that class cannot be a child of anything.
        """
        from reflex_workflow.engine.handles import RunHandle

        if not hasattr(cls, "parent"):
            msg = f"{cls.__qualname__} is not a workflow."
            raise TypeError(msg)
        # Children point at the fan-out they belong to as well; any of this
        # run's fan-outs will do here.
        pointer = cls.parent.op("-", return_type=JSONB)(literal("fan_out", String))
        return RunHandle(cls, (pointer == self.as_parent(),))

    @classmethod
    def by(cls: type[W], *where: ColumnElement[bool]) -> RunHandle[W]:
        """Address existing runs by a SQL condition.

        Args:
            *where: Conditions on the table, e.g. ``Expense.id == 7``.

        Returns:
            A handle for reading or advancing the matching runs.
        """
        from reflex_workflow.engine.handles import RunHandle

        return RunHandle(cls, where)
