---
meta_description: Write reflex-workflow steps that update a run, call other services, and return what happens next. Configure retries and backoff, and make steps safe to repeat.
---

# Steps

A step is an async method of a workflow that does one piece of work and returns what the run does next. This page covers what a step can change, what it can return, how failures are retried, and how to make a step safe to run twice.

## Define a step

Decorate an async method with `@step`:

```python
from reflex_workflow import Workflow, step, wake_in


class Invoice(Base, Workflow):
    __tablename__ = "invoice"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[str] = mapped_column(String(64))
    total: Mapped[int] = mapped_column(default=0)
    status: Mapped[str] = mapped_column(String(32), default="new")

    @step(retries=5)
    async def charge(self):
        await payments.charge(self.customer_id, self.total, key=f"invoice-{self.id}")
        self.status = "paid"
        return Invoice.send_receipt

    @step
    async def send_receipt(self):
        await email.send_receipt(self.customer_id, self.id)
```

`self` is the run's row. Read its columns to decide what to do, and assign to them to change the run's state.

The engine commits a step's result in one transaction after the step returns: the columns the step changed, together with the next step it scheduled. If the step raises, nothing it changed is saved.

## Choose what happens next

A step's return value tells the engine what to do with the run:

| Return | What happens |
| --- | --- |
| `None` | The run finishes. |
| `Invoice.send_receipt` | Runs `send_receipt` next, straight away. |
| `Invoice.notify("overdue")` | Runs `notify` next with these arguments. |
| `wake_in(Invoice.remind, timedelta(days=7))` | Runs `remind` after the delay. |
| `wait_for(Invoice.paid, timeout=..., on_timeout=...)` | Waits for an event. See [Waiting for events](/docs/workflows/events/). |
| `every(Invoice.sync, timedelta(hours=1))` | Runs `sync` again on a schedule. See [Schedules](/docs/workflows/schedules/). |
| `fan_out(children, then=Invoice.total_up)` | Starts many runs and continues when they finish. See [Fan-out](/docs/workflows/fan-out/). |

Returning anything else is an error, and counts as a failed attempt.

A step that returns the next step runs it in a new attempt, with its own retries and its own commit. Splitting work into several steps means a failure late in the sequence doesn't repeat the work before it.

## Pass arguments to a step

A step can take arguments after `self`. To schedule it, call the step with the arguments; this builds a `Call` for the engine and doesn't run anything:

```python
class Invoice(Base, Workflow):
    ...

    @step
    async def notify(
        self, reason: Literal["overdue", "disputed"], *, cc: str | None = None
    ):
        await email.send(self.customer_id, reason, cc=cc)


# From a step:
return Invoice.notify("overdue", cc="billing@example.com")

# From outside a run:
await Invoice.by(Invoice.id == invoice_id).run(Invoice.notify("disputed"))
```

The engine checks the arguments against the step's signature when the call is scheduled, not when the step runs: `start`, `run`, and `deliver` raise straight away, and a step that returns a call with the wrong arguments fails that attempt. Type checkers check them too: passing a step that needs arguments without calling it, or a step of a different workflow, is a type error.

The engine stores arguments in the `next_args` column until the step runs, so they must be JSON-serializable. Pass IDs rather than objects, and keep anything large in your own columns or tables.

## Retry failed steps

By default, a step that raises isn't retried: the run stops and records the error in `last_error`. To retry, set `retries`:

```python
@step(retries=5, backoff=timedelta(seconds=10), max_backoff=timedelta(minutes=10))
async def charge(self): ...
```

| Parameter | Default | Meaning |
| --- | --- | --- |
| `retries` | `0` | How many times to retry after the first attempt fails. |
| `backoff` | 30 seconds | The delay before the first retry. Each later retry waits twice as long as the one before. |
| `max_backoff` | 1 hour | The longest delay between two attempts. |

With the values above, the step runs up to six times, waiting 10, 20, 40, 80, and 160 seconds between attempts. While it waits, the run's `attempts` column counts the failures and `last_error` holds the most recent error.

An attempt fails when the step raises, when it returns something that isn't a valid transition, or when the database refuses its commit, for example because a value is too long for its column or breaks a constraint.

After the last retry fails, the run stops with `last_error` set and no next step. To try again, for example after fixing the cause, schedule the step again with [`run`](/docs/workflows/runs/#run-a-step-now).

## Make steps safe to repeat

```md alert warning
# A step can run more than once.

If a worker stops after a step has called a service but before the step's result is committed, the run's claim expires and another worker runs the step again. The engine guarantees each step runs at least once, not exactly once.
```

Design each step so that running it twice has the same effect as running it once:

- **Pass an idempotency key to external services.** Most payment, email, and messaging APIs accept one. Derive it from the run, such as `f"invoice-{self.id}-charge"`, so a repeat sends the same key.
- **Use unique constraints for records you create.** A second insert of the same record then fails or does nothing, instead of creating a duplicate.
- **Put one side effect in each step.** A retry repeats the whole step, so a step that charges a card and then sends an email charges the card again if the email fails. Charge in one step and send the email in the next.
- **Check before acting.** For a service without idempotency keys, look up whether the work is already done before doing it.

## Work with the database in a step

The row a step receives isn't attached to a database session, so it can't load relationships. To read or write other tables, open a session of your own, for example from the same session factory you pass to `run_workflows`:

```python
@step
async def reserve_stock(self):
    async with sessions() as session, session.begin():
        await session.execute(
            update(Stock)
            .where(Stock.sku == self.sku)
            .values(reserved=Stock.reserved + self.quantity)
        )
    self.status = "reserved"
```

That transaction is separate from the step's own commit. If the step fails afterwards, or runs again, your write has already happened, so apply the same rules as for any other side effect.

## Run slow or blocking work

Steps run on the worker's event loop, up to `max_concurrency` of them at a time in each process. Await asynchronous I/O directly. Move blocking calls, such as a synchronous SDK or CPU-heavy work, off the event loop with `asyncio.to_thread` so they don't stall the other steps:

```python
@step
async def render(self):
    self.pdf_path = await asyncio.to_thread(render_pdf, self.id)
```

A step can take as long as it needs. While it runs, the worker keeps renewing its claim on the row, so no other worker takes the run over. To run heavy steps only on dedicated workers, put them in a [lane](/docs/workflows/concurrency/#route-steps-to-dedicated-workers).
