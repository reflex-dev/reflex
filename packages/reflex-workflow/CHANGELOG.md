## v0.1.0 (2026-11-17)

First release. `reflex-workflow` runs durable workflows on Postgres: each workflow is a SQLAlchemy table, each row is a run, and workers in your app claim due rows and run their steps. Requires Python 3.11 or newer and SQLAlchemy 2.0.20 or newer. The [documentation](https://reflex.dev/docs/workflows/overview/) covers defining workflows, running workers, and how the engine works.

### Features

- Define a workflow by mixing `Workflow` into a SQLAlchemy model and marking methods with `@step`. A step returns what runs next: another step, `wake_in(step, delay)`, `wait_for(step, ...)`, `every(step, schedule)`, `fan_out(children, then=step)`, or `None` to stop. `@step(retries=N, backoff=...)` retries a failing step with doubling backoff.
- Start and control runs with `await Model(...).start(step)`, `Model.by(...).run(step)`, `.deliver(event)`, and `.cancel()`. Starting a row that hits a unique constraint starts nothing, so a key never starts two runs.
- Wait for outside events: a step returns `wait_for(step, timeout=..., on_timeout=...)` and `deliver(step(args), key=...)` hands the event to every matching run that is waiting for it. A `key` makes delivery idempotent, and `restart=True` lets a finished run take the event by starting again.
- Run a step on a schedule with `every(step, interval)` or `every(step, Cron("0 9 * * MON-FRI", "America/Los_Angeles"))`.
- Fan out with `fan_out(children, then=step)`: the children run as ordinary runs with their own retries, the parent continues when the last one finishes, and `self.children(Child)` reads them back.
- Cap concurrency and rate per group with `__workflow_limit__ = Limit(by="customer", at_most=3, rate=60, per=timedelta(minutes=1))`, counted across every worker. Rates use a table the application maps with `RateBucket`.
- Pin steps to dedicated workers with `@step(lane="media")` and `run_workflows(..., lanes=["media"])`.
- Record what each step attempt did by mapping `AttemptLog`, then read it with `await run.history()`.
- Set up a process that starts runs and delivers events without running steps with `connect_workflows(Session)`.
- Workers pick up new runs and events at once through Postgres `LISTEN`/`NOTIFY`, with polling as the fallback. `run_workflows(on_idle=...)` and `reflex_workflow.wake(timeout)` let a platform wake a deployment that suspends when idle, and `run_workflows(suspends_when_idle=True)` keeps an idle worker from holding a database such as Neon awake.
- Models on a `MappedAsDataclass` base import `Workflow`, `AttemptLog`, and `RateBucket` from `reflex_workflow.dataclass` instead.
- Trace every step attempt with OpenTelemetry when `reflex-otel` is instrumented. Step arguments and row columns are never recorded.
