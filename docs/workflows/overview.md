---
meta_description: Run durable, multi-step workflows in a Reflex app on Postgres. Retries, timers, approvals, schedules, and fan-out that survive restarts, with no queue or extra service to run.
---

# Workflows Overview

`reflex-workflow` runs long-lived, multi-step processes from your app's own Postgres database: an onboarding sequence that sends emails over a week, an expense that waits for a manager's approval, a report that goes out every Monday, an import that processes ten thousand rows in parallel. A run survives restarts and deploys, retries the steps that fail, and can wait days for a timer or a reply without holding a process open.

There is no queue, broker, or orchestration server to deploy. The workers run inside your Reflex app, and everything they need is stored in your tables.

## Key takeaways

- A **workflow** is an ordinary SQLAlchemy table. Each **row is one run**, and the columns are that run's state.
- A **step** is an async method that does some work, updates the row, and returns what happens next: another step, a timer, a wait for an event, a schedule, or nothing.
- **Workers** are your app's own processes. Each one claims rows that are due and runs their steps.
- Steps run **at least once**. Write them so that running one twice is safe.
- Requires **PostgreSQL**. SQLite and other databases are not supported.

## When to use a workflow

Reflex has three ways to run work outside a single event handler. Pick the one that matches how long the work lives and what has to happen if the server restarts.

| | [Background event](/docs/events/background-events/) | [Lifespan task](/docs/utility-methods/lifespan-tasks/) | Workflow |
| --- | --- | --- | --- |
| Started by | A user action in one session | App startup | Any code: an event handler, a webhook, a schedule, another workflow |
| After a restart | Lost | Starts again from the beginning | Resumes at the step it was on |
| Retries | Written by you | Written by you | Declared on each step |
| Waiting hours or days | Keeps a task open the whole time | Keeps a task open the whole time | Stored as a timestamp; nothing stays open |
| Updates the page | Directly, through state | No | Indirectly: the page reads the row |

Use a background event for work a user is watching, such as a progress bar for a file they just uploaded. Use a workflow when the work has to finish even if nobody is watching and the server restarts halfway through.

## How it works

The following workflow welcomes a new user, waits three days, and nudges them up to twice if they haven't activated their account:

```python
from datetime import timedelta

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from reflex_workflow import Workflow, step, wake_in


class Onboarding(Base, Workflow):
    __tablename__ = "onboarding"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    nudges: Mapped[int] = mapped_column(default=0)

    @step(retries=3)
    async def welcome(self):
        await send_email(self.email, "welcome")
        return wake_in(Onboarding.check, timedelta(days=3))

    @step
    async def check(self):
        if await has_activated(self.email):
            return None
        self.nudges += 1
        await send_email(self.email, "nudge")
        if self.nudges < 2:
            return wake_in(Onboarding.check, timedelta(days=4))
        return None
```

To start a run, create a row and name its first step:

```python
await Onboarding(email="ada@example.com").start(Onboarding.welcome)
```

Here is what happens next:

1. `start` inserts the row with `welcome` scheduled to run now.
2. A worker claims the row, calls `welcome`, and commits the result: any columns the step changed, and `check` scheduled for three days from now.
3. For three days, the run is a row with a timestamp. No worker is busy with it, and a deploy in the meantime changes nothing.
4. When the timestamp passes, whichever worker is free claims the row and runs `check`.

If `send_email` raises, the worker discards the step's changes and schedules `welcome` again with a growing delay, up to three more times. If the worker's process dies mid-step, another worker takes the run over once the first one's claim expires.

The `Workflow` mixin adds the columns that track this — which step is next, when it is due, how many attempts have failed — next to your own columns. Your migrations create them like any other column.

## Requirements

- Python 3.10 or later.
- PostgreSQL. The engine relies on Postgres row locking and `LISTEN`/`NOTIFY`.
- SQLAlchemy 2.0 with an async driver. Use [psycopg 3](https://www.psycopg.org/psycopg3/): with other drivers, workers can't hear about new runs immediately and find them on their next periodic check instead.

## Next steps

- [Build your first workflow](/docs/workflows/tutorial/) in a Reflex app, step by step.
- [Define workflows](/docs/workflows/defining-workflows/) and learn what each [step](/docs/workflows/steps/) can return.
- Read [how workflows work](/docs/workflows/how-it-works/) for the guarantees the engine makes and the ones it leaves to you.
- Look up every function and argument in the [API reference](/docs/workflows/reference/).

<!-- faqs-start -->
<!-- faqs-visible -->

## FAQ

### Do I need Redis, a message queue, or a workflow server?

No. Runs, timers, retries, and events are stored in your Postgres tables, and the workers run inside your Reflex app's own processes. Postgres notifications let a worker hear about new runs started by another process.

### Does each step run exactly once?

No. A step runs at least once. If a worker crashes after a step's side effect but before its commit, another worker runs the step again. Make steps safe to repeat with unique constraints and the idempotency keys most payment and email providers accept.

### Can I use SQLite or MySQL?

No. The engine depends on PostgreSQL features: `FOR UPDATE SKIP LOCKED` to claim rows, advisory locks for concurrency limits, JSONB columns, and `LISTEN`/`NOTIFY` to wake workers.

<!-- faqs-end -->
