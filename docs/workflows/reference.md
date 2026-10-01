---
meta_description: Reference for the reflex-workflow Python API, including the Workflow mixin, steps, transitions, run handles, workers, Cron, Limit, AttemptLog, and RateBucket.
---

# Workflows API Reference

This page lists the public API of the `reflex_workflow` package. Import every name from `reflex_workflow`, except the dataclass variants, which come from `reflex_workflow.dataclass`.

## Workflow

```python
class Workflow
```

The mixin that turns a mapped SQLAlchemy model into a workflow. Each row is one run. The mixin adds [twelve columns](/docs/workflows/defining-workflows/#columns-the-mixin-adds) and their indexes.

| Class attribute | Type | Meaning |
| --- | --- | --- |
| `__workflow_limit__` | `Limit \| None` | Per-group concurrency and rate limits. `None`, the default, is unlimited. |

### Workflow.start

```python
async def start(self, first: Step | Call) -> bool
```

Inserts this row and schedules `first` to run now. Returns `True` if a run was started, or `False` if the row conflicted with an existing one on a unique constraint. Sets a database-generated primary key on the instance.

### Workflow.by

```python
@classmethod
def by(cls, *where: ColumnElement[bool]) -> RunHandle
```

Returns a handle for the runs that match all of the conditions. With no conditions, the handle matches every run of the workflow.

### Workflow.children

```python
def children(self, cls: type[Workflow]) -> RunHandle
```

Returns a handle for the runs of `cls` that this run started with `fan_out`.

### Workflow.history

```python
async def history(self, limit: int = 50) -> list[AttemptLog]
```

Returns this run's recorded attempts, most recent first. Returns an empty list if no `AttemptLog` table is mapped.

## step

```python
@step
@step(*, retries=0, backoff=timedelta(seconds=30), lane="default", max_backoff=timedelta(hours=1))
```

Declares an async method of a workflow as a step. The method receives the row as `self` and returns a [transition](#transitions).

| Parameter | Type | Default | Meaning |
| --- | --- | --- | --- |
| `retries` | `int` | `0` | How many times to retry after the first attempt fails. |
| `backoff` | `timedelta` | 30 seconds | The delay before the first retry. Each later retry doubles it. |
| `max_backoff` | `timedelta` | 1 hour | The longest delay between two attempts. |
| `lane` | `str` | `"default"` | Which workers may run the step. |

Calling a step, as in `Expense.decide("approve")`, doesn't run it. It returns a `Call` that binds the arguments, for `start`, `run`, `deliver`, or a transition to schedule. A step that takes no arguments can be passed without calling it.

## Transitions

A step returns one of these, or `None` to finish the run.

| Return | Effect |
| --- | --- |
| A `Step` or `Call` | Runs that step next, now. |
| `wake_in(call, delay)` | Runs `call` after `delay`. |
| `wait_for(then, *, timeout=None, on_timeout=None)` | Waits for an event that runs `then`. |
| `every(call, schedule)` | Runs `call` again on `schedule`. |
| `fan_out(children, *, then)` | Starts child runs, and runs `then` once they have all finished. |

### wake_in

```python
def wake_in(call: Step | Call, delay: timedelta) -> WakeIn
```

Runs `call` after `delay`.

### wait_for

```python
def wait_for(then: Step, *, timeout: timedelta | None = None, on_timeout: Step | Call | None = None) -> Wait
```

Waits for an event delivered to `then`. With `timeout`, runs `on_timeout` if no event arrives in time. Raises `ValueError` if only one of `timeout` and `on_timeout` is given. See [Waiting for events](/docs/workflows/events/).

### every

```python
def every(call: Step | Call, schedule: Schedule) -> Every
```

Runs `call` again on `schedule`: a positive `timedelta`, a `Cron`, or any function that takes the current time and returns the next run time. Raises `ValueError` for an interval that isn't positive. See [Schedules](/docs/workflows/schedules/).

### fan_out

```python
def fan_out(children: Iterable[Child], *, then: Step | Call) -> FanOut
```

Starts each child as its own run, and runs `then` once every child has finished, given up, or been cancelled. See [Fan-out](/docs/workflows/fan-out/).

### child

```python
def child(row: Workflow, first: Step | Call) -> Child
```

Pairs a new row with the step it starts at, for `fan_out`.

## RunHandle

The handle returned by `Workflow.by` and `Workflow.children`. It addresses every run that matches its conditions, and queries nothing until you call a method.

| Method | Returns | Effect |
| --- | --- | --- |
| `await get()` | `Workflow \| None` | Loads the first matching row. |
| `await all()` | `list[Workflow]` | Loads every matching row, in no particular order. |
| `await run(call)` | `int` | Runs `call` now on every matching run, replacing whatever was scheduled. Returns how many runs it scheduled. |
| `await deliver(call, *, key=None, restart=False)` | `int` | Delivers an event to matching runs. Returns how many accepted it. |
| `await cancel()` | `int` | Stops every matching run that hasn't finished. Returns how many it stopped. |

See [Starting and controlling runs](/docs/workflows/runs/) and [Waiting for events](/docs/workflows/events/).

## run_workflows

```python
@asynccontextmanager
async def run_workflows(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    workflows: Iterable[type[Workflow]] | None = None,
    max_concurrency: int = 8,
    poll_interval: timedelta = timedelta(seconds=1),
    lease: timedelta = timedelta(minutes=5),
    shutdown_timeout: timedelta = timedelta(seconds=30),
    lanes: Collection[str] = ("default",),
    max_idle_interval: timedelta | None = None,
    listen_engine: AsyncEngine | None = None,
    on_idle: OnIdle | None = None,
    suspends_when_idle: bool = False,
) -> AsyncIterator[None]
```

Runs workflow steps in this process while the block is active. The [Configure a worker](/docs/workflows/workers/#configure-a-worker) table describes each argument.

Raises `ValueError` if `max_concurrency` is below 1, `lease` or `poll_interval` isn't positive, `max_idle_interval` is shorter than `poll_interval`, or both `listen_engine` and `suspends_when_idle` are given.

## connect_workflows

```python
@asynccontextmanager
async def connect_workflows(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    lease: timedelta = timedelta(minutes=5),
) -> AsyncIterator[None]
```

Lets this process start, find, and steer runs without running any steps. See [Processes that only start runs](/docs/workflows/workers/#processes-that-only-start-runs).

## wake

```python
async def wake(timeout: timedelta) -> bool
```

Wakes the worker in this process and waits up to `timeout` for it to take all the work it can. Returns `True` once the worker has nothing left to take and has reported its next due time to `on_idle`, or `False` on timeout. If eight callers are already waiting, wakes the worker and returns `False` immediately. See [Hosts that suspend when idle](/docs/workflows/workers/#hosts-that-suspend-when-idle).

## OnIdle

```python
OnIdle = Callable[[datetime | None], Awaitable[None]]
```

The type of the `on_idle` callback. It receives the time the worker next has work due, or `None` when nothing is scheduled, each time that changes. An exception it raises is logged and ignored.

## Cron

```python
class Cron(expression: str, tz: str | tzinfo = timezone.utc)
```

A five-field cron expression evaluated in the timezone `tz`, for use with `every`. Raises `ValueError` if the expression is malformed or can never fire. See [Run a step on a cron schedule](/docs/workflows/schedules/#run-a-step-on-a-cron-schedule).

## Limit

```python
@dataclass(frozen=True)
class Limit(by: str, at_most: int | None = None, rate: int | None = None, per: timedelta | None = None)
```

A per-group limit, set as a workflow's `__workflow_limit__`.

| Field | Meaning |
| --- | --- |
| `by` | The name of the column that assigns each run to a group. |
| `at_most` | The most runs of one group that can run a step at once, across every worker. |
| `rate` | The most steps one group can start per `per`. Needs a mapped `RateBucket` table. |
| `per` | The period `rate` is counted over. |

Raises `ValueError` unless it sets `at_most`, `rate`, or both; if only one of `rate` and `per` is set; or if a value isn't positive. See [Concurrency, rate limits, and lanes](/docs/workflows/concurrency/).

## AttemptLog

```python
class AttemptLog
```

A mixin for the table that records each committed step attempt. Map it once onto your base to turn history on. Its columns are `id`, `workflow`, `run`, `step`, `attempt`, `outcome`, `error`, `took_ms`, and `finished_at`. See [Keep an attempt history](/docs/workflows/inspecting-runs/#keep-an-attempt-history).

## RateBucket

```python
class RateBucket
```

A mixin for the table that rate limits count in. Map it once onto your base if any workflow sets a `rate`. Its columns are `key`, `tokens`, and `updated_at`.

## DEFAULT_LANE

```python
DEFAULT_LANE = "default"
```

The lane a step is in, and a worker serves, unless told otherwise.

## Dataclass variants

`reflex_workflow.dataclass` provides `Workflow`, `AttemptLog`, and `RateBucket` for bases that use `MappedAsDataclass`. They behave identically, and declare their columns with `init=False`. See [Use dataclass models](/docs/workflows/defining-workflows/#use-dataclass-models).

## Other exported types

These names appear in signatures and are exported for type annotations. You don't construct them directly.

| Name | What it is |
| --- | --- |
| `Step` | A step method, as created by `@step`. |
| `Call` | A step bound to its arguments. |
| `WakeIn`, `Wait`, `Every`, `FanOut` | The transitions returned by `wake_in`, `wait_for`, `every`, and `fan_out`. |
| `Child` | A child run, as returned by `child`. |
| `Schedule` | `timedelta \| Callable[[datetime], datetime]`, the type of an `every` schedule. |
| `RunHandle` | The handle returned by `Workflow.by`. |
