# reflex-workflow

Prototype. Durable workflows where each workflow is an ordinary SQLAlchemy table: rows
are runs, columns are their state, and workers in your app claim due rows and run their
steps. Requires Postgres; there is nothing else to run.

```python
from datetime import timedelta
from typing import Literal

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column
from reflex_workflow import Workflow, step, wake_in


class Onboarding(Base, Workflow):
    __tablename__ = "onboarding"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[str] = mapped_column(String, unique=True)
    email: Mapped[str] = mapped_column(String)
    nudges: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String, default="welcoming")

    @step(retries=3)
    async def welcome(self):
        await send_email(self.email, "welcome")
        self.status = "waiting"
        return wake_in(Onboarding.check, timedelta(days=3))

    @step
    async def check(self):
        if await has_activated(self.user_id):
            self.status = "activated"
            return None
        self.nudges += 1
        await send_email(self.email, f"nudge_{self.nudges}")
        return wake_in(Onboarding.check, timedelta(days=4)) if self.nudges < 2 else None

    @step
    async def activated(self, plan: Literal["free", "pro"]):
        self.status = f"activated:{plan}"
```

A step that takes no arguments is passed as is: `Onboarding.check`. A step that takes
arguments is called with them, `Onboarding.activated("pro")`, which builds a
`Call[Onboarding]` for the engine to schedule rather than running the step. Arguments
are type-checked against the step's signature, a bare step that needs arguments is a
type error, and so is passing one workflow's step to another.

- **Start a run**: `await Onboarding(user_id=u, email=e).start(Onboarding.welcome)`. A
  row that hits a unique constraint is not inserted, so a key never starts two runs. It
  returns whether a run was started, and a row the database keyed itself is given that
  key, so `row.id` addresses the run that was just started.
- **Stop a run**: `await Onboarding.by(Onboarding.user_id == u).cancel()` ends every
  matching run where it stands — nothing scheduled, no wait, no held event — and what
  the run has already done stays. A cancelled run counts as finished to the run that
  fanned it out, as one that gave up does, so a parent is never left waiting on it.
- **Advance a run from outside** (a webhook, a button):
  `await Onboarding.by(Onboarding.user_id == u).run(Onboarding.activated("pro"))` runs the
  step now on every matching row, replacing whatever was scheduled. A step already running
  keeps its lease, so the new step waits for it rather than starting beside it, and starts
  as soon as it is done or its lease runs out.
- **A step returns** another step (run now), `wake_in(step, delay)` (run later),
  `wait_for(step, ...)` (run when an event arrives), `every(step, schedule)` (run again
  and again), `fan_out(children, then=step)` (run many at once), or `None` (stop). Step
  arguments are stored as JSON until the step runs, so they must be JSON-serializable.
- **Failures**: `@step(retries=N, backoff=timedelta(seconds=30))` retries with doubling backoff, up to
  `max_backoff` (an hour by default); after the last attempt the row stops with `last_error` set. A
  failed step's changes to the row are discarded. A step whose body succeeds but whose commit the
  database refuses — a value too long for its column, a child that breaks a constraint — counts as a
  failed attempt too, and is retried the same way.

The mixin adds twelve columns: `next_step`, `next_args`, `wake_at`, `attempts`,
`last_error`, `claimed_until`, `waiting_for`, `pending_event`, `recent_event_keys`,
`parent`, `children_left`, `wf_version`. They're ordinary mapped columns, so Alembic picks them up with the rest of
the table.

## Waiting for an event

A run can park until something outside it happens — an approval, a webhook, a reply —
without holding a process open. The step it waits on is the channel, and the arguments
travel with the event.

```python
class Expense(Base, Workflow):
    __tablename__ = "expense"

    id: Mapped[int] = mapped_column(primary_key=True)
    amount: Mapped[int] = mapped_column()
    status: Mapped[str] = mapped_column(String, default="draft")

    @step
    async def request_approval(self):
        await notify_manager(self.id)
        self.status = "pending"
        return wait_for(
            Expense.decide,
            timeout=timedelta(days=2),
            on_timeout=Expense.escalate,
        )

    @step
    async def decide(self, verdict: Literal["approve", "reject"], *, by: str):
        self.status = f"{verdict} by {by}"
```

The handler delivers the event to whichever runs are waiting for it:

```python
await Expense.by(Expense.id == expense_id).deliver(
    Expense.decide("approve", by=manager), key=request_id
)
```

`deliver` returns how many runs accepted the event. An event that arrives before the run
gets to its wait is held and applied as soon as the wait arms, so a fast reply is never
lost; a run that goes on to wait for something else, or stops, discards it. A wait takes
one event: while a run is holding an answer for the wait it is on, a second delivery is
refused and `deliver` returns 0 for it, rather than replacing an answer already given.
Passing a `key` makes delivery idempotent: a run refuses a key it has already taken,
remembering the last sixteen. Arguments are checked against the step they address, so a
payload that does not fit it is refused rather than failing once it runs. `timeout` and
`on_timeout` go together and are optional; without them the run waits indefinitely.

A run that has finished refuses events. For one that lives as long as its events keep
coming, such as a conversation that closes when it goes quiet, `restart=True` has a
finished run take the event by starting again with the step it names.

## Schedules

A step that returns `every(...)` keeps running on a schedule, which is either an interval
or a cron expression:

```python
from reflex_workflow import Cron, every


class Digest(Base, Workflow):
    __tablename__ = "digest"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String, unique=True)

    @step
    async def send(self):
        await email_digest()
        return every(Digest.send, Cron("0 9 * * MON-FRI", "America/Los_Angeles"))
```

A schedule is an ordinary run, so it is registered by starting one. `start` does nothing
when the row already exists, so a lifespan hook can declare the same schedule on every
boot:

```python
await Digest(name="daily").start(Digest.send)
```

A schedule lives in the step's return value, so it lasts only as long as the step keeps
succeeding: once a scheduled step has used up its retries, the run stops and the schedule
is over. Declaring it again on boot does not bring it back, because the row is still
there. Give a step that has to keep its schedule enough retries to ride out what it
depends on, and re-arm a stopped one with `run`:

```python
await Digest.by(Digest.name == "daily").run(Digest.send)
```

An interval counts from the run's last scheduled time rather than from the moment the
step finished, so a slow step doesn't push the schedule later and later. Occurrences that
passed while nothing was running collapse into one: the step runs once and carries on,
instead of firing once per hour the app was down.

`Cron` takes the five standard fields — minute, hour, day of month, month, day of week —
with `*`, lists, ranges, steps, and names like `MON-FRI` or `JAN`. It follows Debian's
cron: when a day field is written as a star both day fields have to match, and otherwise
either one does, so `0 0 13 * FRI` means the 13th *or* any Friday. Times are read on the
clock of the timezone given, so a daily time the clock skips over in spring still fires
once, and one the clock repeats in autumn fires on its first pass only. A malformed
expression, and one that can never fire like `0 0 30 2 *`, raise `ValueError` when the
`Cron` is built.

Any function of the current time works in place of a `Cron`, so another cron library or a
schedule of your own can be plugged in:

```python
return every(Digest.send, lambda now: now.replace(hour=9) + timedelta(days=1))
```

## Running many at once

A step returns `fan_out(...)` to split into runs that go at the same time, and names the
step to run once they are all finished.

```python
class Research(Base, Workflow):
    __tablename__ = "research"

    @step
    async def research_all(self):
        return fan_out(
            (
                child(Lookup(key=f"{self.name}:{c}", company=c), Lookup.research)
                for c in self.companies
            ),
            then=Research.report,
        )

    @step
    async def report(self):
        lookups = await self.children(Lookup).all()
        self.found = sum(lookup.summary is not None for lookup in lookups)
```

Each child is an ordinary run: claimed by whichever worker is free, retried on its own
schedule, and holding its own `last_error`. A company whose provider is down retries by
itself while the others carry on, and `self.children(Lookup)` reads them back afterwards.

The parent holds nothing open while they run — it is a row with nothing scheduled — and
`then` runs once the last child finishes, whether that child succeeded or gave up, so one
item nobody can process does not strand the batch. Children are started inside the
parent's own commit: a parent whose row was taken over mid-step starts none of them.

A child that hits a unique constraint is not started, and the parent does not count it,
so keying children by the work they do is what keeps a repeated fan-out to one run each.

## Limits and fairness

A workflow can say how much of one group may run at once. The group is a column —
a customer, a tenant, a provider — and the limit is counted across every worker,
not per process.

```python
class Lookup(Base, Workflow):
    __tablename__ = "lookup"
    __workflow_limit__ = Limit(by="customer", at_most=3)

    customer: Mapped[str] = mapped_column(String, index=True)
```

A limited workflow is claimed a group at a time, longest-waiting group first, and a
group already at its limit is skipped rather than allowed to spend the pass. So a
customer who imports ten thousand rows holds three slots, and the customer behind
them with two rows is not waiting for the ten thousand. Index the column you limit
by: every pass groups on it.

Claims for the same group serialize on a Postgres advisory lock for the length of
one short transaction, which is what makes the count exact when several workers ask
at the same moment. Different groups never wait for each other.

The same declaration says how often a group may start, which is the other half of a
provider's quota:

```python
class Charge(Base, Workflow):
    __workflow_limit__ = Limit(
        by="provider", at_most=5, rate=60, per=timedelta(minutes=1)
    )
```

Rates count in a token bucket that refills continuously and holds one period's
worth, so a provider that has been quiet may start a burst and one that has been
busy waits. The bucket needs a table, which the application maps onto its own base
so its migrations carry it:

```python
from reflex_workflow import RateBucket


class WorkflowRate(Base, RateBucket):
    __tablename__ = "workflow_rate"
```

One row per group, and nothing else reads it: truncating it only means every limit
starts full again.

Between tables, a worker takes them in turn and gives each a share of the pass, so a
table with a backlog cannot hold the whole worker, even when there are more tables
than slots.

## Which workers run what

A step can name the kind of worker it belongs on, and a worker is started to serve
particular lanes. A step in a lane of its own runs only where that lane is served,
so heavy work stays off the machines that answer requests.

```python
class Upload(Base, Workflow):
    __tablename__ = "upload"

    @step(lane="media")
    async def transcode(self): ...

    @step
    async def notify(self): ...
```

```python
async with run_workflows(Session, lanes=["media"], max_concurrency=2):
    ...
```

Routing costs nothing at the database: the row already names the step it will run
next, so a worker claims only the steps it serves. A worker skips a table it can run
nothing of, and a table it can run all of is claimed exactly as before.

A worker serves the `default` lane unless told otherwise, and a step is in `default`
unless it says otherwise, so nothing changes until a lane is named. The other side of
that: work in a lane nobody serves waits — the run is not lost, it simply sits until
such a worker exists.

## What a run has tried

The row says where a run is now. To see how it got there, map a history table onto
your own base and the engine writes a row per attempt:

```python
from reflex_workflow import AttemptLog


class WorkflowAttempt(Base, AttemptLog):
    __tablename__ = "workflow_attempt"
```

```python
for attempt in await expense.history():
    print(attempt.step, attempt.outcome, attempt.error, attempt.took_ms)
```

Each row holds the step, which attempt it was, what came of it (`ok`, `retry`,
`failed`), the error if there was one, how long it took, and when it finished. The
record is written in the same transaction as the step's own commit, so history never
shows an attempt that did not happen and never misses one that did — and an attempt
whose commit was refused leaves nothing behind, because it changed nothing.

Nothing in the engine reads this table. Prune it on whatever schedule suits, and skip
mapping it entirely if you do not want it: a deployment without one pays nothing.

## Running

Enter `run_workflows` from the app's lifespan. Every process that does so is a worker;
they claim different rows.

```python
import contextlib
from datetime import timedelta

from reflex_workflow import run_workflows


@app.register_lifespan_task
@contextlib.asynccontextmanager
async def workflows():
    async with run_workflows(
        Session,  # async_sessionmaker for the database with the workflow tables
        max_concurrency=8,
        lease=timedelta(minutes=5),
    ):
        yield
```

A worker with nothing to do asks the database when its next run comes due and sleeps
until then, so an idle deployment stops querying rather than polling on a timer. It
waits at most `max_idle_interval` (30 seconds by default), which is also how long it
waits when nothing is scheduled at all. Set that above the point a managed database
suspends itself — Neon's five minutes, say — and idle workers will not hold it open.
`poll_interval` is the floor instead: how soon it looks again when something is due but
could not be taken, because a limit or this worker's own concurrency held it back.

A worker is woken before any of that by anything that leaves work ready: a start, a
`run`, a delivered event, a step that asked for the next one, or the last child of a
fan-out. The news travels through Postgres itself — `NOTIFY` in the same transaction as
the write, so a transaction that rolls back announces nothing — which means a run
started by the web process is picked up by a worker in another process straight away
rather than at its next poll. A worker ignores news about tables it does not run.

A row written straight into the table announces nothing, so it waits for the next
wake-up: up to `max_idle_interval`. Use `start` and the workers hear about it at once.

Connection poolers in transaction mode — Neon's pooled endpoint, PgBouncer — cannot
hold a `LISTEN`, so pass `listen_engine` pointing at the direct endpoint and leave the
pooled one to the steps:

```python
async with run_workflows(
    Session,
    listen_engine=create_async_engine(os.environ["REFLEX_DB_DIRECT_URL"]),
    max_idle_interval=timedelta(minutes=10),
):
    yield
```

Polling stays the floor: a worker that is not listening — a driver that cannot, a
connection that broke — holds to `poll_interval` throughout rather than sleeping past
it, since asking is then the only way it would ever find work another process wrote. So
losing the listener costs latency and nothing else. The one case that cannot be detected
is a pooler that accepts a `LISTEN` and never delivers on it, which is what
`listen_engine` is for. On shutdown a worker stops claiming, gives
running steps `shutdown_timeout` to finish, and hands back the rows of any it had to
cancel so the next worker can take them straight away.

A process that starts runs and takes approvals but should not run anything — a web
process, usually — enters `connect_workflows` instead:

```python
@app.register_lifespan_task
@contextlib.asynccontextmanager
async def workflows():
    async with connect_workflows(Session):
        yield
```

Everything that addresses runs works there: `start`, `deliver`, `run`, `cancel`,
`get`, `all`.
Nothing runs steps here, and what it writes wakes the workers that do — or waits on the
row for them, if every worker is down at the time.

## Guarantees

- A step runs at least once. A worker claims a row with a lease that it renews while
  the step runs; if the worker dies, the row is claimed again once the lease expires. A
  worker shutting down gives back the lease of any step it has to cancel, so a deploy
  that interrupts a long step does not cost that run a whole lease.
  So a step can run twice: make it safe to repeat (unique constraints, provider
  idempotency keys).
- A step commits only if the row hasn't moved since it was claimed. A step whose lease
  was taken over, or which was preempted by `.run(...)`, discards its changes rather than
  overwriting newer state.
- Timers survive restarts: `wake_at` is a column, compared against the database clock.
- A wait ends once. An event that lands while the timeout is already running wins, and
  the timeout's changes are discarded — never both.
