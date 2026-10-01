---
meta_description: Tell where a reflex-workflow run is from its row, find failed and waiting runs with SQL, and record a history of every step attempt.
---

# Inspecting Runs

Every run is a row, so you inspect runs with the same queries you use for the rest of your data. This page shows how to read a run's state from its row, find runs that need attention, and keep a history of every attempt.

## Read a run's state

The [columns the mixin adds](/docs/workflows/defining-workflows/#columns-the-mixin-adds) tell you where a run is:

| The run is | When |
| --- | --- |
| Scheduled | `next_step` is set and `wake_at` is in the future. |
| Due | `next_step` is set and `wake_at` has passed. |
| Running | `claimed_until` is in the future. |
| Retrying | `next_step` is set and `attempts` is above zero. `last_error` holds the latest error. |
| Waiting for an event | `waiting_for` is set. `wake_at` is the deadline, if there is one. |
| Waiting for its children | `children_left` is above zero. |
| Finished | `next_step` and `waiting_for` are both `NULL`, and `last_error` is `NULL`. |
| Failed | `next_step` and `waiting_for` are both `NULL`, and `last_error` is set. |

A run that waits for an event with a deadline also has `next_step` set, to its timeout step, so check `waiting_for` before `next_step`.

These columns describe the engine's view of the run. For your app's view, such as "awaiting approval" or "shipped", keep a status column of your own and set it in your steps. It reads better in your UI, and it can tell apart outcomes that look the same to the engine, such as a run that was cancelled and one that finished.

## Find runs that need attention

Query the mixin's columns with `Workflow.by` or with your own sessions.

Runs that gave up after their last retry:

```python
failed = await Invoice.by(
    Invoice.next_step.is_(None),
    Invoice.waiting_for.is_(None),
    Invoice.last_error.is_not(None),
).all()
```

Runs that are failing right now and will retry:

```python
retrying = await Invoice.by(Invoice.attempts > 0, Invoice.next_step.is_not(None)).all()
```

Runs that have been due for more than ten minutes without a worker taking them:

```python
from sqlalchemy import func, or_

stuck = await Invoice.by(
    Invoice.next_step.is_not(None),
    Invoice.wake_at < func.now() - timedelta(minutes=10),
    or_(Invoice.claimed_until.is_(None), Invoice.claimed_until < func.now()),
).all()
```

A due run that no worker takes usually means its step is in a [lane](/docs/workflows/concurrency/#route-steps-to-dedicated-workers) that no running worker serves, its group is at its [limit](/docs/workflows/concurrency/), or no worker is running at all.

To retry failed runs once you have fixed the cause, use [`run`](/docs/workflows/runs/#run-a-step-now).

## Record every attempt

The row shows where a run is now. To see how it got there, map an attempt history table onto your base:

```python
from reflex_workflow import AttemptLog


class WorkflowAttempt(Base, AttemptLog):
    __tablename__ = "workflow_attempt"
```

Generate a migration, and the engine writes a row for every attempt of every step, in every workflow. Read a run's history, most recent first, with `history`:

```python
for attempt in await invoice.history():
    print(
        attempt.step, attempt.attempt, attempt.outcome, attempt.error, attempt.took_ms
    )
```

`history` returns the 50 most recent attempts by default; pass `limit` to change that. Each row has these columns:

| Column | Holds |
| --- | --- |
| `workflow` | The workflow's table name. |
| `run` | The run's primary key, as a JSON list. |
| `step` | The step that ran. |
| `attempt` | Which attempt of that step it was, starting at 1. |
| `outcome` | `ok`, `retry` if the step failed and will be retried, or `failed` if it failed for the last time. |
| `error` | The error, for an attempt that failed. |
| `took_ms` | How long the step took, in milliseconds. |
| `finished_at` | When the attempt finished. |

The engine writes each history row in the same transaction as the step's own commit, so the history never shows an attempt that didn't happen and never misses one that did. An attempt whose commit was discarded, because the run had moved on without it, leaves no row.

The engine never reads this table, so you can prune it on any schedule, for example with a [scheduled](/docs/workflows/schedules/) workflow that deletes old rows. An app can map one history table, and if you don't map one, the engine writes no history and `history` returns an empty list.
