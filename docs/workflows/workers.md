---
meta_description: Run reflex-workflow workers inside a Reflex app, scale them across processes, tune leases and concurrency, use connection poolers, and deploy to databases and hosts that suspend when idle.
---

# Running Workers

A worker is a process that runs workflow steps. Every process that enters `run_workflows` is a worker, and workers coordinate through the database, so you scale by running more processes. This page covers starting workers, tuning them, and deploying them on poolers and on databases and hosts that suspend when idle.

## Start workers with your app

Enter `run_workflows` from a [lifespan task](/docs/utility-methods/lifespan-tasks/), passing the session factory for the database that holds your workflow tables:

```python
import contextlib
from datetime import timedelta

import reflex as rx
from reflex.model import get_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker

from reflex_workflow import run_workflows

sessions = async_sessionmaker(get_async_engine(None), expire_on_commit=False)


@contextlib.asynccontextmanager
async def workflows():
    async with run_workflows(sessions, max_concurrency=8):
        yield


app = rx.App()
app.register_lifespan_task(workflows)
```

Every backend process of your app now runs steps. Workers claim different rows, so two workers never run the same step at the same time, and you can add or remove processes at any time.

By default a worker runs every workflow class defined in the process. To run only some, pass `workflows=[Expense, Invoice]`.

## Configure a worker

`run_workflows` takes these keyword arguments:

| Argument | Default | Meaning |
| --- | --- | --- |
| `max_concurrency` | `8` | How many steps this process runs at once. |
| `lease` | 5 minutes | How long a claim on a row lasts. The worker renews it while the step runs. If the worker dies, another worker can take the run over once the lease expires. |
| `poll_interval` | 1 second | How soon the worker checks again when work is due but it couldn't take it, because of a [limit](/docs/workflows/concurrency/) or because the worker is full. |
| `max_idle_interval` | 30 seconds | The longest the worker sleeps between checks for new work. An hour with `suspends_when_idle`. |
| `shutdown_timeout` | 30 seconds | How long running steps get to finish when the process shuts down. |
| `lanes` | `("default",)` | The [lanes](/docs/workflows/concurrency/#route-steps-to-dedicated-workers) this worker serves. |
| `workflows` | All defined | The workflow classes this worker runs. |
| `listen_engine` | `None` | A separate engine to listen for notifications on. See [Connection poolers](#connection-poolers). |
| `suspends_when_idle` | `False` | Whether the database suspends itself when idle. See [Databases that suspend when idle](#databases-that-suspend-when-idle). |
| `on_idle` | `None` | A callback told when the worker next has work due. See [Hosts that suspend when idle](#hosts-that-suspend-when-idle). |

The lease only matters when a worker dies: its runs wait up to `lease` before another worker takes them over. A step can run longer than its lease, because the worker keeps renewing it. A shorter lease recovers from crashes faster, but keep it well above the longest time a worker might stall, such as a slow database or a blocked event loop, or another worker can take over a step that is still running.

## How workers find work

A worker with nothing to do asks the database when its next run is due, and sleeps until then. An idle app doesn't poll the database on a timer.

Workers also wake straight away when new work appears. These send a Postgres `NOTIFY` in the same transaction as their write:

- `start`, `run`, and `deliver`.
- A step that returns the next step to run now.
- The last child of a fan-out finishing.

Every worker listens for these notifications, so a run started by one process is picked up at once by a worker in another. A transaction that rolls back announces nothing.

A worker sleeps at most `max_idle_interval` between checks. That bound matters in two cases:

- **Rows you write directly.** A row inserted or updated with plain SQL announces nothing, so a worker finds it at its next check. Use `start` and `run` to have workers hear about it immediately.
- **Drivers that can't listen.** Workers only receive notifications through the psycopg 3 driver. With other drivers, or if the listening connection drops, workers find new work at their next check. Timers, retries, and schedules aren't affected, because the worker already knows when they are due.

## Processes that only start runs

To start and steer runs from a process that shouldn't run steps, such as a web process in a deployment with separate worker processes, enter `connect_workflows` instead:

```python
@contextlib.asynccontextmanager
async def workflows():
    async with connect_workflows(sessions):
        yield
```

`start`, `run`, `deliver`, `cancel`, `get`, and `all` all work. The workers hear about the changes through notifications. If no worker is running at the time, the work waits in the table until one starts.

## Connection poolers

A connection pooler in transaction mode, such as PgBouncer or Neon's pooled endpoint, can't hold a `LISTEN`. To keep instant notifications, point `listen_engine` at a direct connection and keep the pooled one for the steps:

```python
from sqlalchemy.ext.asyncio import create_async_engine

async with run_workflows(
    sessions,
    listen_engine=create_async_engine(os.environ["DIRECT_DATABASE_URL"]),
):
    yield
```

If the database suspends itself when idle, don't do this. See the next section.

## Databases that suspend when idle

Serverless Postgres services such as Neon suspend the database when nothing is connected, and charge for the time it is running. A held `LISTEN` connection counts as activity, so a listening worker keeps the database running for nothing.

On such a database, pass `suspends_when_idle=True`:

```python
async with run_workflows(sessions, suspends_when_idle=True):
    yield
```

The worker stops listening and sleeps up to an hour instead of 30 seconds, so the database can suspend between runs. Timers, retries, and schedules still run on time, because the worker asked the database when they are due before it went to sleep. The cost is latency for new work written by another process, such as another replica: it waits for the worker's next check rather than starting at once. Work started in the worker's own process wakes it immediately.

`suspends_when_idle` and `listen_engine` contradict each other, so passing both raises a `ValueError`.

## Hosts that suspend when idle

On a host that stops your app when no requests arrive, a sleeping worker can't wake itself for the next timer. The engine provides two hooks for a platform that can wake the app at a given time.

`on_idle` is called with the time the worker next has work due, or `None` when nothing is scheduled. It is called only when that time changes, so you can register the time with your platform on every call:

```python
async def register_wakeup(at: datetime | None) -> None:
    if at is None:
        await platform.cancel_wakeup("my-app")
    else:
        await platform.schedule_wakeup("my-app", at=at, path="/wake")


async with run_workflows(sessions, on_idle=register_wakeup):
    yield
```

`wake` is the other half. When the platform calls your app at that time, have the route call `wake`, which wakes the worker in that process and holds the request open until the worker has taken all the work it can:

```python
from datetime import timedelta

import reflex_workflow
from fastapi import FastAPI, Response

api = FastAPI()


@api.post("/wake")
async def wake_workflows() -> Response:
    caught_up = await reflex_workflow.wake(timedelta(seconds=50))
    return Response(status_code=200 if caught_up else 503)


app = rx.App(api_transformer=api)
```

Holding the request open matters on hosts that only give an app CPU time while it answers a request. `wake` returns `True` once the worker has nothing left that it can take and has reported its next due time to `on_idle`, so the platform can safely suspend the app. It returns `False` if the timeout passes first, so the platform knows to call again.

You can call `wake` as often as you like. At most eight callers wait at once; any more wake the worker and return `False` immediately.

## Shut down and deploy

When the process shuts down, the worker stops claiming new work and gives running steps up to `shutdown_timeout` to finish. Steps still running after that are cancelled, and their rows are released straight away, so another worker can run them without waiting for the lease to expire.

A cancelled step runs again from the beginning, so a deploy is one of the ordinary ways a step runs twice. The same happens in development whenever hot reload restarts the backend. See [Make steps safe to repeat](/docs/workflows/steps/#make-steps-safe-to-repeat).
