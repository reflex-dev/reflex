# Workflows

A workflow is durable automation that survives restarts, deploys, and crashes. Where an ordinary
event handler runs once inside a browser session and is gone, a workflow run has its own identity,
its own persisted state, and a history you can inspect long after the request that started it
finished.

Workflows are ordinary Reflex code. There is no separate service to operate, no DSL, and no
determinism rules to learn: a workflow is an `rx.State` class, a step is an `@rx.event` handler, and
control flow is what the handler returns.

You do not need a Reflex app, a page, or a frontend build to use them. The workflow-only path is
three commands:

```bash
reflex init --workflow          # writes workflows.py: one runnable module, nothing else
reflex workflows dev workflows.py Workflows.start --arg order=ord-1 --fast-forward   # run it once
reflex workflows worker workflows.py                                # serve it; start runs from any code
```

`reflex workflows doctor workflows.py` checks what a deployment needs before you deploy it, and
`reflex workflows serve workflows.py` runs ingress, API, and worker in one process for a
workflow-only service.

Code in the same deployment starts runs through `rx.workflows.connect(...)`, which shares the
store. Code anywhere else — another service, a script, a partner — uses the HTTP API through
`RemoteWorkflows`, holding a scoped API token instead of database credentials:

```python
from reflex.workflow import RemoteWorkflows

async with RemoteWorkflows("https://flows.internal", token) as flows:
    started = await flows.start(
        "orders.orders", "start", {"order": "ord-1"}, request_key="ord-1"
    )
    receipt = await flows.result(started.run_id, as_type=Receipt)
```

A workflow class reads top to bottom as the process it runs:

```python
import reflex as rx


class Onboarding(rx.State):
    __workflow__ = rx.WorkflowConfig(id="growth.onboarding", run_timeout="30d")

    user_id: str = ""
    email: str = ""
    nudges_sent: int = 0

    @rx.event(id="signup", durable=True, trigger=rx.manual(), effect="none")
    def signup(self, user_id: str, email: str):
        self.user_id, self.email = user_id, email
        return Onboarding.send_welcome

    @rx.event(durable=True, effect="idempotent_write", timeout="30s")
    async def send_welcome(self):
        await send_email(self.email, "welcome")
        return rx.after("3d", Onboarding.check_activation)

    @rx.event(durable=True, effect="read")
    async def check_activation(self):
        if await has_activated(self.user_id):
            return rx.complete(result={"outcome": "activated"})
        if self.nudges_sent >= 2:
            return rx.complete(result={"outcome": "gave_up"})
        return Onboarding.send_nudge

    @rx.event(durable=True, effect="idempotent_write")
    async def send_nudge(self):
        self.nudges_sent += 1
        await send_email(self.email, f"nudge_{self.nudges_sent}")
        return rx.after("4d", Onboarding.check_activation)


app = rx.App()
app.add_workflow(Onboarding)
```

Register the class with `app.add_workflow(...)` and start a run from anywhere on the server:

```python
result = await rx.workflows.start(
    Onboarding.signup("u_1", "ada@example.com"),
    request_key="u_1",
)
```

`request_key` makes starting idempotent: submitting the same key again returns the original run with
disposition `"deduplicated"` instead of starting a second one.

## The three-day wait is not a sleeping process

`rx.after("3d", ...)` commits a mailbox slot with a due time and nothing else exists in between: no
open coroutine, no held connection, no memory. Deploy, restart, or hard-crash the server on day two
and the step still runs on day three. That is the difference between a workflow and a background
task.

## Steps

Every public handler on a workflow class is a durable step and must declare `durable=True` and an
`effect`. A step runs, commits its state changes, and schedules what comes next — all atomically.
A step commits exactly once, so it can never half-succeed.

Because state is snapshotted per step rather than reconstructed by re-running your code, there are no
determinism rules: `datetime.now()`, `random`, and ordinary I/O are all fine inside a step.

### Effect classes

`effect` declares what a step does to the outside world, which decides whether it is safe to retry.

| Effect | Meaning | Retries |
| --- | --- | --- |
| `"none"` | pure orchestration, no external I/O | yes |
| `"read"` | reads something external | yes |
| `"idempotent_write"` | a write that is safe to repeat | yes |
| `"non_idempotent_write"` | a write that is not safe to repeat | never |

A `non_idempotent_write` that fails gets exactly one business attempt and suspends the run as
`NEEDS_ATTENTION`: the runtime cannot prove the write did not already land, so it asks a human
rather than guessing and charging a customer twice.

The effect class governs *retries*, not crash recovery. If the worker dies mid-attempt, the
step's lease lapses and another worker re-executes the handler — so the write can still run
twice. The effect class alone is not an exactly-once guarantee; nothing can be while a process
can die between the provider call and any record of it. Money-moving code wraps the call in
`rx.step` and hands the provider `rx.current_run().idempotency_key()`, which covers the one
window `rx.step` cannot: a crash after the provider acted but before the record landed.

### Retries and timeouts

```python
@rx.event(
    durable=True,
    effect="idempotent_write",
    retry=rx.Retry(max_attempts=5, initial_delay="2s", multiplier=2),
    timeout="30s",
    on_failure="alert_billing",
)
async def charge(self): ...
```

Failures retry with exponential backoff by default. Narrow that with
`rx.Retry(do_not_retry_on=(ValueError,))` when a specific error should fail fast. `timeout` bounds a
single attempt, and requires an `async def` handler: a synchronous one runs on a worker thread that
cannot be interrupted, so the timeout would fire while the body kept running. `on_failure` and
`on_timeout` name a handler on the same class that runs once the step is finally out of attempts.

Backoff is a persisted timer, not a sleep, so a retry scheduled for tomorrow survives a deploy
tonight.

## Transitions

A durable handler returns what happens next. It never calls another handler directly — doing so
would run it inline and lose its retries and effect tracking, which the compiler rejects.

| Return | Meaning |
| --- | --- |
| `None` | this branch is done |
| `MyFlow.next_step` | run that step next |
| `MyFlow.next_step(arg)` | run it with an argument |
| `[MyFlow.a, MyFlow.b]` | run both, in order |
| `rx.after("2d", MyFlow.later)` | run it after a durable delay |
| `rx.wait_for(...)` | block until a signal or a deadline |
| `rx.parallel(a, b, then=...)` | run branches concurrently, then join (`mode="first"` races) |
| `rx.complete(result=...)` | finish the run successfully |
| `rx.fail("reason")` | finish the run as failed |
| `rx.needs_attention("reason")` | suspend for a human |

## Waiting for the outside world

Declare a typed channel and wait on it. Whichever of the signal and the deadline arrives first wins;
the loser can no longer resolve the wait.

```python
from pydantic import BaseModel


class Decision(BaseModel):
    approved: bool
    by: str


class Expense(rx.State):
    __workflow__ = rx.WorkflowConfig(id="finance.expense")

    review = rx.Signal(Decision)

    @rx.event(durable=True, trigger=rx.manual(), effect="none")
    def submit(self):
        return rx.wait_for(
            Expense.review,
            then=Expense.decide,
            timeout="3d",
            on_timeout=Expense.escalate,
        )

    @rx.event(durable=True, effect="none")
    def decide(self, decision: Decision):
        return rx.complete(result={"approved": decision.approved})

    @rx.event(durable=True, effect="none")
    def escalate(self): ...
```

Deliver the signal from an ordinary page handler — the approve button in your own app:

```python
class ReviewPage(rx.State):
    @rx.event
    async def approve(self, run_id: str):
        await rx.workflows.signal(
            run_id,
            Expense.review(Decision(approved=True, by="ada")),
            key=run_id,
        )
```

Use `timeout=rx.never` to wait indefinitely. A signal that arrives before the run reaches its wait is
buffered and applied as soon as the wait arms, so a fast approver never blocks the run.

### Approving from an email

Not every approver will open your app. `rx.approval_link()` builds a signed URL that delivers one
decision to the run that created it, so the reply can come straight from a message:

```python
@rx.event(durable=True, effect="idempotent_write")
async def ask(self):
    approve = rx.approval_link(
        Expense.review(Decision(approved=True, by="manager")),
        base_url="https://app.example.com",
    )
    reject = rx.approval_link(
        Expense.review(Decision(approved=False, by="manager")),
        base_url="https://app.example.com",
    )
    await send_email(self.manager, approve_url=approve, reject_url=reject)
    return rx.wait_for(
        Expense.review, then=Expense.decide, timeout="3d", on_timeout=Expense.escalate
    )
```

Set `REFLEX_WORKFLOW_APPROVAL_SECRET` to a long random string; links are signed with it and there is
no default, because a built-in secret would make every deployment's links forgeable. The signature
covers the run, the channel, the payload, and the expiry, so an edited link is refused rather than
believed.

Following a link shows a confirmation page, and only submitting it records the decision. That is not
politeness: mail clients and link scanners fetch URLs before a person reads the message, so a link
that decided on `GET` would approve itself in transit. A link is spent once — replaying it, or
following the other choice afterwards, changes nothing.

### Knowing which run you are

`rx.current_run()` returns the attempt a durable handler is executing, which is what you need to
correlate logs — and to make an outbound call safely:

```python
@rx.event(durable=True, effect="non_idempotent_write")
async def charge(self):
    run = rx.current_run()
    await stripe.charge(self.amount, idempotency_key=run.idempotency_key())
```

The key is stable across retries of that step and different for every other step, which is exactly
the contract a payment API's idempotency key wants: a retry must not charge twice, and the next step
must not be mistaken for this one.

## Running work in parallel

Each branch of a fan-out becomes its own run, with its own state, retries, and history, so a slow or
failing branch never blocks its siblings. The parent blocks until every branch reports.

```python
class Router(rx.State):
    __workflow__ = rx.WorkflowConfig(id="sales.router")

    @rx.event(durable=True, trigger=rx.manual(), effect="none")
    def begin(self, lead_id: str):
        return rx.parallel(
            Enrich.start(lead_id),
            Score.start(lead_id),
            then=Router.route,
        )

    @rx.event(durable=True, effect="none")
    def route(self, results: list):
        # One entry per branch: run_id, status, result, error.
        return rx.complete(result={"branches": len(results)})
```

A branch that fails still reports, so the join handler decides what a partial success means rather
than the engine guessing. Child runs are ordinary runs: they appear in `list_runs()` and can be
inspected and cancelled on their own.

Pass `mode="first"` to race the branches instead of waiting for all of them. The join handler runs
as soon as one reports, receiving that single result, and the losing branches are cancelled.

```python
return rx.parallel(
    PrimaryVendor.quote(order_id),
    BackupVendor.quote(order_id),
    then=Order.book,
    mode="first",
)
```

A cancelled loser stops at its next step boundary; a step already in flight finishes. Race only
where a discarded branch is harmless, or give the losers an `on_failure` handler that undoes their
work.

## Triggers

A root handler declares how runs of it begin.

```python
@rx.event(durable=True, trigger=rx.manual(), effect="none")
def start(self): ...


@rx.event(
    durable=True,
    effect="none",
    trigger=rx.webhook(
        "stripe.invoice_failed",
        model=Invoice,
        verify=rx.hmac_signature(secret_env="STRIPE_SECRET", header="Stripe-Signature"),
        dedupe_by="id",
    ),
)
def on_failed(self, invoice: Invoice): ...


@rx.event(durable=True, effect="read", trigger=rx.schedule("0 3 * * *"))
def nightly_sweep(self): ...
```

Webhook roots are served at `POST /_workflow/webhook/{topic}`. The endpoint verifies the provider's
signature over the raw body, validates the payload, and durably accepts the run before
acknowledging, so a provider that never sees a response can safely redeliver — `dedupe_by` sends the
redelivery to the same run. A webhook trigger without a verifier is a compile error; if an endpoint
really is public, say so with `allow_unverified=True` and a reason.

Schedules are evaluated in UTC and fire once per occurrence even across restarts. Deploying a
schedule does not backfill history, and catch-up after an outage is bounded.

## Controlling how runs start

A root can declare one start policy, which the engine applies before a run is admitted. Each groups
runs by a payload field, or globally when no `key` is given.

```python
@rx.event(
    durable=True,
    trigger=rx.manual(),
    effect="idempotent_write",
    singleton=rx.Singleton(key="customer_id"),
)
def sync(self, customer_id: str): ...
```

| Policy | Behavior |
| --- | --- |
| `rx.Singleton(key=..., mode="skip")` | one active run per key; a second start returns the first |
| `rx.Singleton(key=..., mode="cancel")` | one active run per key; a second start replaces the first |
| `rx.Debounce(period=..., key=...)` | collapse a burst into one run once things go quiet |
| `rx.RateLimit(limit=..., period=..., key=...)` | cap starts per window, dropping the excess |
| `rx.Throttle(limit=..., period=..., key=...)` | cap starts per window, delaying the excess |

`start()` reports what happened through its disposition: `"started"`, `"skipped"`,
`"coalesced"`, `"deduplicated"`, or `"rejected"` — a rejected start carries `retry_after`.

Debounce is the one to reach for with chatty webhooks: ten deliveries in a second become one run.
Rate limiting drops excess starts, which is what you want when a provider can flood you; throttling
delays them instead, which is what you want when every start matters but the downstream is slow. A
throttled backlog is spaced out rather than released together: with `limit=2, period="10s"`, a burst
of six runs starts two now, two in ten seconds, and two in twenty.

## Inspecting and steering runs

```python
snapshot = await rx.workflows.get_run(run_id)
runs = await rx.workflows.list_runs(workflow_id="finance.expense", limit=20)
await rx.workflows.cancel(run_id)
await rx.workflows.resume(run_id)
```

`labels` passed at start are server-derived indexing data you can filter on later:

```python
await rx.workflows.start(Expense.submit(), labels={"customer": customer.id})
await rx.workflows.list_runs(labels={"customer": customer.id})
```

A suspended run is waiting for you, not finished: fix whatever made the outcome uncertain, then
`resume()` to give the step a fresh attempt budget.

The same operations are available from a terminal, reading the app's own database:

```bash
reflex workflows list --status NEEDS_ATTENTION
```

```bash
reflex workflows show <run-id> --history
```

`reflex workflows cancel <run-id>` and `reflex workflows resume <run-id>` steer a run without
opening the app, and `--json` on `list` and `show` makes the output scriptable.

## Throughput

The kernel runs several attempts at once, defaulting to eight. Each belongs to a different run --
a run has exactly one open step, so its own work stays strictly in order no matter how many other
runs are executing. Tune it with `rx.App(workflow_concurrency=...)`.

Concurrency is per process. A step that blocks the event loop, rather than awaiting, still stalls
its neighbours, so prefer `async def` handlers for anything that waits on the network.

## Observability

Pass an observer to see every recorded transition, correlated to its run, workflow, step, and
attempt:

```python
from reflex.workflow import WorkflowObserver


class Telemetry(WorkflowObserver):
    def on_event(self, event_type, run_id, workflow_id, data):
        metrics.increment(
            f"workflow.{event_type.value}", tags={"workflow": workflow_id}
        )


app = rx.App(workflow_observer=Telemetry())
```

`rx.workflow.LoggingObserver` is a ready-made one that writes a structured line per transition.
An observer that raises is reported and ignored — instrumentation never breaks a run.

## Testing

The test harness runs your real workflow on a virtual clock, so a three-day wait takes microseconds
and nothing is mocked.

```python
from reflex.workflow import WorkflowTestHarness


async def test_drip_nudges_then_gives_up():
    async with WorkflowTestHarness(Onboarding) as harness:
        result = await harness.start(Onboarding.signup("u_1", "ada@example.com"))

        await harness.advance("3d")
        await harness.advance("4d")

        snapshot = await harness.get_run(result.run_id)
        assert snapshot.state["nudges_sent"] == 2
```

`harness.advance(...)` moves the clock and runs whatever became due. `harness.signal(...)` delivers
to a waiting run, and `harness.cancel(...)` and `harness.resume(...)` drive the operator paths.

## Deploying

Runs persist to a SQLite file next to your app by default, which is the right choice for local
development and for a single-process deployment. Run **one worker process per SQLite database
file**: the store's calls are synchronous on the event loop that also serves your app, so two
processes writing the same file contend for it. Contention is bounded to a short busy timeout and
surfaces as a transient error the kernel retries, but throughput does not improve.

For more than one process, point the app at Postgres:

```python
from reflex.workflow.postgres import PostgresRunStore

app = rx.App(workflow_store=PostgresRunStore("postgresql://user:pw@host/db"))
```

Every process that opens the same database is a worker. A claim locks one run's next step with
`FOR UPDATE ... SKIP LOCKED`, so workers never queue behind each other and never take the same
step; adding a process adds throughput. A worker that dies mid-step holds a lease, and the step is
reclaimed by another worker once that lease lapses -- not before, so a slow step is never
duplicated. Install it with `pip install 'psycopg[binary,pool]'`.

Pass `schema=` to keep a deployment's tables in their own namespace inside a shared database.

The `reflex workflows` commands take the same target: `--database postgresql://...`, or set
`REFLEX_WORKFLOW_DATABASE` once.

`RunStore` is a supported extension point, and the invariants a store must satisfy ship as runnable
checks rather than prose:

```python
import pytest
from reflex.workflow import CONFORMANCE_CHECKS


@pytest.mark.parametrize("check", CONFORMANCE_CHECKS, ids=lambda c: c.__name__)
async def test_my_store_conforms(check):
    await check(MyRunStore())
```

Deploying new code does not disturb runs already in flight. Adding state fields, retuning retries and
timeouts, and changing hooks all apply to future steps. Only a change that makes a pending step
undispatchable — deleting the handler it names, or removing parameters its payload carries —
suspends that run, with a message naming the handler.
