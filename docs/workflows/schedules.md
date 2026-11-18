---
meta_description: Run reflex-workflow steps on a fixed interval or a cron expression in any timezone. Register schedules on startup without duplicates and catch up after downtime.
---

# Schedules

A step that returns `every(...)` runs again on a schedule: a fixed interval, a cron expression, or a function of your own. A schedule is an ordinary run, so it survives restarts, retries like any other step, and runs on one worker at a time however many workers you have.

## Run a step on an interval

Return `every` with the step and a `timedelta`:

```python
from datetime import timedelta

from reflex_workflow import Workflow, every, step


class Sync(Base, Workflow):
    __tablename__ = "sync"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(64), unique=True)

    @step(retries=3)
    async def pull(self):
        await pull_changes(self.source)
        return every(Sync.pull, timedelta(minutes=15))
```

An interval counts from when the step was scheduled, not from when it finished, so a slow run doesn't push later runs back.

## Run a step on a cron schedule

Pass a `Cron` in place of the interval. Give it the timezone the times are written in:

```python
from reflex_workflow import Cron, every


class Digest(Base, Workflow):
    __tablename__ = "digest"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(64), unique=True)

    @step(retries=5)
    async def send(self):
        await email_digest(self.name)
        return every(Digest.send, Cron("0 9 * * MON-FRI", "America/Los_Angeles"))
```

`Cron` takes the five standard fields: minute, hour, day of month, month, and day of week. Each field accepts `*`, lists (`1,15`), ranges (`1-5`), steps (`*/10`), and names such as `MON-FRI` or `JAN`. The timezone defaults to UTC.

A few details follow standard cron behavior:

- **Day fields.** If either day field is `*`, both must match. If both name specific days, either one can match, so `0 0 13 * FRI` runs on the 13th of every month and on every Friday.
- **Daylight saving time.** A time that the clock skips in spring still runs once that day. A time that the clock repeats in autumn runs only the first time.
- **Invalid expressions.** An expression that is malformed or can never run, such as `0 0 30 2 *`, raises a `ValueError` when you create the `Cron`.

## Use your own schedule

Any function that takes the current time and returns the next run time works as a schedule, so you can use another cron library or your own rules:

```python
def next_business_morning(now: datetime) -> datetime:
    day = now + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day.replace(hour=9, minute=0, second=0, microsecond=0)


return every(Report.send, next_business_morning)
```

The function receives the database's current time as a timezone-aware `datetime`. If it raises, the run stops and records the error in `last_error`.

## Register a schedule on startup

A schedule is a run, so you create it with `start`. Because `start` does nothing when a row with the same unique key already exists, you can declare your schedules in a lifespan task every time the app starts:

```python
@contextlib.asynccontextmanager
async def workflows():
    async with run_workflows(sessions):
        await Digest(name="daily").start(Digest.send)
        await Sync(source="crm").start(Sync.pull)
        yield
```

The first time, this creates each schedule. After that, the rows already exist and `start` returns `False`.

`start` runs the first step straight away. To wait for the first scheduled time instead, start the run at a step that only returns the schedule:

```python
@step
async def begin(self):
    return every(Digest.send, Cron("0 9 * * MON-FRI", "America/Los_Angeles"))
```

## Catch up after downtime

If no worker was running when occurrences came due, for example during a long outage, the missed occurrences collapse into one. The step runs once when a worker is back, and the schedule continues from the next occurrence. It doesn't run once for every hour the app was down.

## Keep a schedule running

A schedule continues only as long as its step keeps succeeding. When a scheduled step uses up its retries, the run stops and so does the schedule. Starting it again on the next boot doesn't revive it, because the row still exists.

Give a scheduled step enough retries to outlast the outages it is likely to meet. To resume a stopped schedule, run its step again:

```python
await Digest.by(Digest.name == "daily").run(Digest.send)
```

To stop a schedule on purpose, [cancel](/docs/workflows/runs/#cancel-runs) its run.
