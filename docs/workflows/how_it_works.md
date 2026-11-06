---
meta_description: How reflex-workflow claims, leases, and commits runs on Postgres, the guarantees it makes about steps, timers, and events, and what it leaves to your code.
---

# How Workflows Work

This page explains how the engine runs workflows on your database, and the guarantees that follow from that design. You don't need it to write a workflow, but it helps when you design steps, size leases, or work out why a run did what it did.

## The row is the run

Most workflow engines keep their own record of each run: an event history in a separate service, or a journal of step results in tables of their own. `reflex-workflow` keeps the run in your table. Your columns are its state, and the mixin's columns say what happens next and when.

This has three consequences:

- **No replay.** A step reads the row as it is now, not a history replayed to rebuild it. Code outside steps doesn't need to be deterministic, and there are no workflow versioning rules beyond [keeping step names stable](/docs/workflows/defining-workflows/#change-a-workflow-that-has-runs).
- **Your data and the run's state can't disagree.** A step's changes to your columns and the decision about what runs next commit in the same transaction.
- **Ordinary queries work.** Joins, reports, admin pages, and migrations treat runs like any other rows.

The trade-off is that state lives at the granularity of a step. Inside a step, the engine knows nothing about what the step has done so far; if the step fails halfway, it runs again from the start.

## Life of a step

A step goes through four stages:

1. **Claim.** A worker selects rows whose `wake_at` has passed, skipping rows another worker has locked (`FOR UPDATE SKIP LOCKED`) or still holds a lease on. It sets `claimed_until` to now plus the lease, and commits. Claiming takes one short transaction, so no transaction stays open while the step runs.
2. **Run.** The worker loads the row and calls the step. While the step runs, the worker renews the lease in the background.
3. **Commit.** The worker writes the columns the step changed and the next step, in one transaction, but only if the row's `wf_version` is still the one it claimed. The commit increments `wf_version` and clears the lease.
4. **Fail.** If the step raises, the worker discards the step's changes and either schedules a retry or, after the last one, stops the run with `last_error` set.

The version check in step 3 is what keeps a slow or overtaken step from overwriting newer state. `run`, `cancel`, `deliver`, and every commit increment `wf_version`. A step whose run moved on while it was running finds the version changed, and its result is discarded.

## Time comes from the database

Every timestamp the engine writes or compares, such as `wake_at`, deadlines, and lease expiry, comes from the database clock (`now()`), never from a worker's. Workers with skewed clocks agree on what is due, and a timer survives any number of restarts because it is a column.

## Guarantees

The engine makes these guarantees:

1. **Every step runs at least once.** A claimed step runs to completion, or its lease expires and another worker runs it.
2. **A step commits only if its run hasn't moved on.** A step whose run was taken over, preempted by `run`, cancelled, or advanced by an event can't commit over the newer state.
3. **A run's state and its next step commit together.** No crash leaves your columns updated without the next step scheduled, or the reverse.
4. **Timers outlive processes.** A run scheduled for next month runs next month, whatever restarts and deploys happen in between. Occurrences of a schedule missed during downtime run once, not once each.
5. **A wait ends exactly once.** Either one event's step or the timeout step takes effect, never both. Once the deadline passes, the run refuses events, whether or not a worker has run the timeout step yet.
6. **An event key is accepted once per run**, among the last 16 keys the run accepted.
7. **A key starts one run.** `start` and `fan_out` never insert a row that breaks a unique constraint.
8. **A fan-out parent continues once.** It continues when the last of its children finishes, gives up, or is cancelled.

## What the engine leaves to you

The engine doesn't make these guarantees, and your steps have to account for them:

- **A step can run more than once.** Between a step's side effect and its commit, the worker can crash, the database can refuse the commit, or a deploy can cancel the step. The step then runs again. Use idempotency keys and unique constraints; see [Make steps safe to repeat](/docs/workflows/steps/#make-steps-safe-to-repeat).
- **Writes to other tables aren't part of the step's commit.** A step that opens its own session commits that work separately, before the step's result.
- **Steps aren't ordered across runs.** Two runs that are due at the same time can run in either order, or at once on different workers. Use a [limit](/docs/workflows/concurrency/) with `at_most=1` to run one group's steps one at a time.
- **A step that outlives its lease isn't stopped.** The worker renews the lease while the step runs, so this only happens when the worker can't reach the database or a blocking call stalls its event loop. If another worker then takes the run over, both run the step, and only one result can commit.
- **Timers fire when a worker is running.** If no worker is running at the due time, the step runs when one starts.

## Compared with other workflow engines

Engines such as Temporal, Inngest, Restate, and DBOS record each step's result and replay the workflow function to resume it. That supports workflows written as one long function, at the cost of determinism rules and a separate service or a set of tables for the journal.

`reflex-workflow` makes the opposite trade. A workflow is a state machine on your own table: each step decides what runs next, and the row holds everything a run needs. There is nothing to deploy beyond Postgres, and nothing to replay.
