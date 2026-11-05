## v0.0.1a1 (2026-11-05)

### Breaking Changes

- A wait's deadline now decides when the wait ends: once it has passed, `deliver` refuses the event and returns 0, even where no worker has reached the timeout step yet. Previously an event landing in that window won and the timeout's work was discarded, which let a caller delivering faster than the workers pass keep a deadline from ever being kept. An answer arriving just after the deadline is now refused rather than taken late. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- Require Python 3.11 or newer; Python 3.10 is no longer supported. ([#7449](https://github.com/reflex-dev/reflex/issues/7449))

### Features

- `run_workflows(suspends_when_idle=True)` is for a database that stops itself when nothing is querying it and charges for being up, such as Neon: the worker listens for nothing, because a held `LISTEN` is a connection such a database counts as work, and waits an hour between looks rather than thirty seconds. Measured on Neon, an idle worker with a listener never let compute suspend; without one it suspended five minutes after the last query. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- A workflow can declare `__workflow_limit__ = Limit(by="customer", at_most=3)` to cap how much of one group runs at once, counted across every worker. Workers also take their tables in turn and share each pass between them, so a table with a backlog no longer holds up the rest. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- Map `AttemptLog` onto your base and the engine records what each step attempt did — the step, the attempt number, the outcome, the error and how long it took — readable with `await run.history()`. Each record is written in the same transaction as the step it describes. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- `connect_workflows(Session)` sets up a process to start runs, deliver events and read their state without running any steps, so a web process no longer has to start a worker it does not want. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- Add `reflex-workflow`, a prototype of durable workflows where each workflow is a SQLAlchemy table and workers in the app run its steps on Postgres. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- A step can return `fan_out(children, then=step)` to run many child runs at once and carry on when the last one finishes. Each child is an ordinary run with its own retries and errors, and `self.children(Child)` reads them back. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- `Limit` now also says how often a group may start: `Limit(by="provider", at_most=5, rate=60, per=timedelta(minutes=1))`. Rates count in a token bucket that refills continuously, in a table the application maps with `RateBucket`. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- A workflow whose own attribute takes one of the engine's column names — a `parent` relationship, or a column of that name holding something else — is refused where it is declared, instead of failing on the first `start()` or the first claim. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- Workers hear about new work through Postgres `LISTEN`/`NOTIFY` rather than waiting for their next poll, so a run started or an event delivered by another process is picked up straight away. Polling remains the fallback. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- Runs can wait and repeat: a step returns `wait_for(step, timeout=..., on_timeout=...)` to
  park until `deliver(...)` hands it an event, or `every(step, schedule)` to run again on an
  interval or a `Cron("0 9 * * MON-FRI", "America/Los_Angeles")` expression. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- `@step(lane="media")` keeps a step on the workers started to serve that lane, with `run_workflows(..., lanes=["media"])`. Heavy work can have its own machines while ordinary steps run anywhere, and a worker skips tables it can run nothing of. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- `run_workflows(on_idle=...)` reports the instant a worker is next waiting for, on the database's clock and only when it changes, and `reflex_workflow.wake(timeout)` makes the worker in this process look now and holds until it has nothing left to take. Together they let a platform wake a deployment that suspends when idle, so its timers fire without anyone visiting the app. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- Workflows can be mixed into models on a `MappedAsDataclass` base by importing `Workflow`, `AttemptLog` and `RateBucket` from `reflex_workflow.dataclass`, which SQLAlchemy 2.1 requires and 2.0 warns about. The engine's columns stay out of the constructor, so a model reads as it did before the mixin was added. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- Steps are traced with OpenTelemetry when `reflex-otel` is instrumented: every attempt gets a `<table>.<step>` span linked to the handler, request, or step that scheduled it, with the attempt number, outcome, and error on it. Step arguments and row columns are never recorded, beyond what a failed attempt's exception message quotes. ([#7635](https://github.com/reflex-dev/reflex/issues/7635))

### Bug Fixes

- A rate-limit group too long to name in the bucket key is named by a digest of itself, rather than failing the insert; a group the engine cannot claim no longer stops the rest of its table from being claimed. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- `cancel()` no longer stops a run that began matching its predicate after it had read the rows to stop. Such a run was cancelled without its parent being told, leaving a fan-out waiting for a child that would never report. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- An event `key` is remembered when the run runs the event, not when it is buffered, so a resend of an event the run discarded unrun is accepted instead of being refused forever. A run going round an `every(...)` schedule no longer holds a buffered event it will never reach, which used to refuse every later delivery. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- `cancel()` over a large backlog no longer fails once the rows it matches would exceed a statement's parameter limit. It picks and stops them in one statement now, which is also one round trip rather than two. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- `start()` stores a column the caller set to `None` as `None`, rather than falling back to the column's default. `deliver(..., restart=True)` leaves a cancelled step its lease, as `run()` does, so the restarted step waits for it instead of running beside it. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- `reflex_workflow.wake` no longer returns while a step the worker took is still running, or before the step it continued into has run, so a host that suspends when it returns does not stop that work midway. ([#7382](https://github.com/reflex-dev/reflex/issues/7382))
- An event delivered while a run is running the event it held for a wait is now held for the run's next wait, instead of being refused and lost. A run that waits on the same step again, such as a conversation, no longer misses a message that arrives during that step. A second answer to a wait whose held event has not been taken yet is still refused. ([#7396](https://github.com/reflex-dev/reflex/issues/7396))

### Performance

- An idle worker now waits the same whether or not it can listen for notifications, and a listener that cannot reconnect backs off up to `max_idle_interval` instead of retrying every second. A database that suspends itself when nothing is querying — Neon, and other managed Postgres — is no longer held awake by a worker with nothing to do. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))
- Claiming from a limited table and asking when work is next due now read indexes rather than scanning the table. On a 700k-row table with 500 groups a claim took 11.7s and is now 5ms, and the idle question 18ms and is now 1ms. Workflow tables gain an `ix_<table>_lease` index, so autogenerate a migration after upgrading. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))

### Documentation

- The README covers using workflows from a Reflex app: why they go on their own `DeclarativeBase` rather than `rx.Model`, registering that base so `reflex db makemigrations` picks the tables up, and the session factory to give `run_workflows`. ([#7288](https://github.com/reflex-dev/reflex/issues/7288))

### Miscellaneous

- Type-check cleanly against SQLAlchemy 2.1. ([#7645](https://github.com/reflex-dev/reflex/issues/7645))
