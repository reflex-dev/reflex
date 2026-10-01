---
meta_description: Start reflex-workflow runs from Reflex event handlers and webhooks without duplicates, look them up, run a step on demand, and cancel them.
---

# Starting and Controlling Runs

Code outside a run, such as an event handler, a webhook, or an admin action, starts runs and steers them. This page covers starting a run exactly once, finding runs, running a step on demand, and cancelling.

These calls need the engine set up in the process that makes them: either `run_workflows` or, in a process that doesn't run steps, `connect_workflows`. See [Running workers](/docs/workflows/workers/). Without one, they raise a `RuntimeError`.

## Start a run

Create a row with your columns set, and call `start` with the first step:

```python
class ExpenseState(rx.State):
    @rx.event
    async def file_expense(self, form: dict):
        started = await Expense(
            request_id=form["request_id"],
            amount=int(form["amount"]),
        ).start(Expense.submit)
```

`start` inserts the row, schedules the first step to run straight away, and wakes a worker. It returns `True` if it started a run.

If the new row would break a unique constraint, such as a second row with the same `request_id`, `start` inserts nothing and returns `False`. Give each workflow a unique column that identifies its work, and a retried request or a double click can't start a second run.

When the database generates the primary key, `start` sets it on the instance, so you can address the run you just started:

```python
expense = Expense(request_id=request_id, amount=amount)
if await expense.start(Expense.submit):
    return expense.id
```

`start` commits in a transaction of its own, separate from any session you have open. If your handler writes other rows too, the run has started even if those writes later fail.

## Find runs

`Workflow.by` addresses the runs that match a SQL condition. It doesn't query anything until you call a method on the result:

```python
expense = await Expense.by(Expense.id == expense_id).get()
pending = await Expense.by(Expense.status == "pending").all()
every_run = await Expense.by().all()
```

`get` returns the first matching row or `None`, and `all` returns every matching row. The rows are ordinary model instances, so you can also query the table with your own sessions, joins, and filters. [Inspecting runs](/docs/workflows/inspecting-runs/) shows how to tell from a row where its run is.

## Run a step now

`run` makes every matching run go to a step straight away, replacing whatever it was going to do next:

```python
await Onboarding.by(Onboarding.user_id == user_id).run(Onboarding.activated("pro"))
```

Use it to advance a run from outside, for example when a webhook reports that a user upgraded. It returns how many runs it scheduled.

The new step replaces everything the run had planned:

- A step that was scheduled, or retrying, doesn't run.
- A wait for an event ends, and any event held for it is discarded.
- A fan-out stops waiting for its children.

If a step is running on the row at that moment, the new step waits for it to finish instead of running beside it, and that step's result is discarded. The wait lasts only while the running step holds its lease: if its worker stops renewing the lease, the new step can start before the old one has finished.

`run` also works on runs that have finished or given up, so it is how you restart a run after fixing what made it fail:

```python
await Invoice.by(Invoice.last_error.is_not(None)).run(Invoice.charge)
```

## Cancel runs

`cancel` stops every matching run where it stands:

```python
cancelled = await Onboarding.by(Onboarding.user_id == user_id).cancel()
```

Nothing scheduled runs, a wait ends, and a held event is discarded. If a step is running, its result is discarded. `cancel` returns how many runs it stopped; runs that had already finished aren't counted.

Cancelling doesn't undo anything. Emails already sent stay sent, and your columns keep their values. If you show a run's status in your app, set it yourself after cancelling. Address the run by its primary key, so the status changes only if `cancel` actually stopped that run:

```python
if await Onboarding.by(Onboarding.id == run_id).cancel():
    async with sessions() as session, session.begin():
        await session.execute(
            update(Onboarding)
            .where(
                Onboarding.id == run_id,
                Onboarding.next_step.is_(None),
                Onboarding.waiting_for.is_(None),
            )
            .values(status="cancelled")
        )
```

`cancel` and the status update are separate transactions. The conditions on `next_step` and `waiting_for` skip the update if something started the run again in between.

A cancelled child of a [fan-out](/docs/workflows/fan-out/) counts as finished, so its parent doesn't wait for it forever.

## Show a run's progress in your app

Workers don't push changes to the page. To show progress, read the row in an event handler, such as an `on_load` handler or a **Refresh** button:

```python
class ExpenseState(rx.State):
    expense_id: int = 0
    status: str = ""

    @rx.event
    async def load(self):
        expense = await Expense.by(Expense.id == self.expense_id).get()
        self.status = expense.status if expense else "not found"
```

To update the page while a user watches, poll from a [background event](/docs/events/background-events/). Keep a status column that the steps update, so the page reads one column rather than the engine's internals.
