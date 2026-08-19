# The execution contract

This document freezes what the workflow engine promises. Every statement here
is load-bearing: code that violates it is a bug even if every test passes, and
a change that needs different semantics must change this document in the same
commit. The conformance suite (`reflex.workflow.CONFORMANCE_CHECKS`) and the
crash tests are the executable form of this contract; prose here and checks
there are meant to be read together.

The engine's one architectural bet, from which everything below follows:
**state is snapshotted, never replayed.** A handler's committed state is data
in the store. No user code is ever re-executed to reconstruct anything. The
price is that control flow is expressed as return transitions rather than
imperative code; the payoff is that handlers are ordinary Python with no
determinism constraints, no versioning patches, and no replay-divergence bug
class.

## 1. What is atomic

One attempt commits in **one store transaction**, containing all of:

- the executed step's terminal status (`SUCCEEDED`, `FAILED`, `RETRY_WAIT`,
  `NEEDS_ATTENTION`, `BLOCKED` for waits) and error payload,
- the run-state snapshot and its incremented `state_version`,
- every successor slot the transition scheduled (with preallocated ordinals),
- every child run and child root slot a fan-out admitted,
- tombstones for slots a terminal transition abandoned,
- the run's status, result, and error,
- the history events describing all of the above,
- **and, when the transition ends a child run: the arrival delivered to its
  parent's join slot.**

There is no state in which a step "happened" but its consequences are missing.
Either the whole transition is visible or none of it is.

Admission is likewise one transaction: run row, root slot, dedupe reservation,
history. A webhook is acknowledged only after that transaction commits
(admit-before-ack), so a `202` means the run exists durably.

Substep results (`rx.step`) are the deliberate exception: each records in its
**own** transaction the moment the callable returns, because their purpose is
to survive a crash that prevents the attempt from ever committing.

## 2. When handlers re-execute

A handler runs more than once in exactly two situations, both bounded:

1. **Business retry.** The attempt raised (or timed out) and the resolved
   retry policy grants another attempt. Consumes one attempt from
   `Retry.max_attempts`; scheduled with backoff and jitter.
2. **Crash recovery.** A worker died (or lost its lease) mid-attempt. The
   step's lease lapses, recovery moves it to `RECOVERY_WAIT`, and any worker
   re-executes it. Consumes one *recovery* (budget: 10 per logical step, then
   the run fails), never a business attempt.

There is no third case. Completed steps are never re-run; a deploy never
re-runs anything; reading a run never runs anything.

Re-execution is therefore **at-least-once per attempt boundary**. The tools
that turn it into effectively-once for side effects are, in order of strength:

- `rx.step(name, fn, ...)`: records the result durably at return; every later
  execution of the same handler replays the recorded value instead of calling
  `fn`. Fenced by claim epoch, so a zombie worker cannot write (§7).

  Its one requirement on your code: **a handler's sequence of `rx.step` calls
  must be the same on every attempt.** Keys are the step name plus its
  occurrence (`send`, `send#2`, …), so a re-execution lines its calls up
  against the journal positionally. Branching on the payload, on run state, or
  on anything else already durable is fine — that decides the same way twice.
  Branching on something that can differ between attempts (a clock reading, a
  random draw, a live API's answer taken *outside* a step) can shift the
  sequence, and a shifted sequence replays one call's recorded result into a
  different call. Put anything nondeterministic that later steps depend on
  inside its own `rx.step` first: recorded, it is the same on every attempt,
  and the branch built on it is stable.

  This is far narrower than a replay engine's determinism rule, which governs
  the whole handler body. Here it governs only the order of `rx.step` calls,
  and only within one handler.
- `rx.current_run().idempotency_key()`: stable across retries and recoveries
  of one step, distinct across steps — hand it to providers that accept
  idempotency keys. This covers the one window `rx.step` cannot: a crash
  after the provider acted but before the record landed.
- `effect="non_idempotent_write"`: one business attempt only; an error
  suspends the run as `NEEDS_ATTENTION` instead of retrying. Note this
  governs *retries*, not recoveries: a crash mid-attempt still re-executes
  after the lease lapses. Money-moving code must use `rx.step` and/or
  provider keys; the effect class alone is not an exactly-once guarantee, and
  nothing can be while the process can die between the provider call and any
  record of it.

## 3. Effects and retries

| effect | default retry | on exhaustion / error |
|---|---|---|
| `none`, `read`, `idempotent_write` | any `Exception`, backoff+jitter, per declared `Retry` (or its defaults) | run `FAILED` (after `on_failure` hook, if declared) |
| `non_idempotent_write` | 1 attempt; no implicit retry | run `NEEDS_ATTENTION`; operator resumes or fails |

- `TransientWorkflowError` is always retryable regardless of `retry_on`.
- **Code bugs are never retried.** `TypeError`, `AttributeError`, `NameError`,
  `ImportError`, `SyntaxError`, `IndentationError` and `NotImplementedError`
  fail the step on the first attempt. A retry re-runs the handler against the
  same committed state, so a deterministic failure fails identically every
  time; retrying one spends the budget proving the code is still wrong and
  delays the operator seeing it by the length of the backoff. A handler that
  wants one of them retried names it in `retry_on`, and then it is honored.
  `KeyError`, `IndexError` and `ValueError` stay retryable: they routinely
  come from a dependency returning a body missing a field.
- `timeout=` bounds one attempt; a timed-out attempt counts as a failed one
  and follows the same policy (`on_timeout` hook runs on final timeout).
  `timeout=` is a compile error on sync handlers: a thread cannot be
  interrupted, and a "timed out" attempt still running concurrently with its
  retry would be a lie.
- Run-level `timeout` (`WorkflowConfig.run_timeout`) finalizes the run
  `TIMED_OUT` once drained; the in-flight attempt is cancelled cooperatively.

## 4. Releases and versions

A run is **not** pinned to the code that started it. On every claim the engine
gates per step: the handler id must still exist and the recorded payload must
still bind to its signature. If both hold, the current code runs — new fields,
tuned retries, edited bodies all apply immediately. If either fails, the run
suspends as `NEEDS_ATTENTION` naming the handler; `resume()` re-opens it after
the operator ships a compatible release or intervenes.

Consequences, stated plainly:

- Adding state fields, handlers, or hooks never strands an in-flight run.
- Deleting a handler (or removing a parameter its recorded payloads carry)
  suspends exactly the runs whose *next* step needs it, and only when that
  step comes due.
- Two releases running simultaneously (rolling deploy) may execute different
  steps of one run with different code. Steps are the consistency boundary;
  the contract makes no promise that one run sees one release.

## 5. Cancellation, deadlines, and children

- `cancel(run_id)` records intent and cancels any in-flight attempt
  cooperatively. The run finalizes `CANCELLED` only once no step is claimed
  (drained), tombstoning open slots. Cancellation is never delivered as an
  exception into a *different* run's handler.
- A run past its deadline finalizes `TIMED_OUT` the same drained way.
- Every terminal path of a child — commit, cancellation, run timeout,
  recovery-budget exhaustion — delivers exactly one arrival to its parent's
  join slot, atomically with the terminal transition (§1). A join can wait
  forever only on a child that is still genuinely running.
- `rx.parallel(..., mode="first")`: the join resolves on the first arrival;
  the engine then requests cancellation of the losing branches. That request
  is best-effort follow-up, not part of the winning transaction: if the
  process dies first, losers run to completion and their arrivals are
  refused as late (`counted`/`duplicate`/terminal), which is harmless.
- Child runs are ordinary runs; cancelling the parent does not implicitly
  cancel children (fan-out is delegation, not ownership). A cancelled
  parent's join tombstones; late child arrivals are refused.

## 6. Identity: who is "the same" as whom

Checked in this order at start:

1. **`request_key`** (explicit, or webhook `dedupe_by`, or schedule
   occurrence key `schedule:{workflow}:{handler}:{epoch}`): resolved *before
   any start policy*, so a provider redelivery returns the original run and
   can never trip a singleton, throttle, or debounce against it. Reserved
   atomically at admission; concurrent duplicate admissions yield one run.
2. **Flow key** (`Singleton`/`RateLimit`/`Throttle`/`Debounce` `key=`): a
   handler parameter, or a field of exactly one model parameter (ambiguity is
   a compile error). Groups runs for policy decisions.
3. Approval links: single-use by delivery key (default: hash of
   run+channel+payload), expiring, HMAC over all claims; a `GET` never
   delivers — only the confirming `POST` does.
4. Signals: sender-supplied `key` makes redelivery a no-op; an expired wait
   refuses its signal rather than letting it resolve a later wait on the
   same channel.

## 7. Workers

- A **claim** takes the run's frontier step (lowest unresolved ordinal) —
  strictly one open obligation per run, so per-run order is total. Claims are
  fenced by `(CLAIMED, epoch, state_version)`; every commit re-validates the
  fence and a fenced writer's work is discarded (`abandoned`, in history).
- **Leases** renew on a real-time cadence; expiry is injected-clock time. A
  worker that cannot renew abandons its attempt *before* the lease lapses
  rather than run work it can no longer prove it owns. Recovery reclaims only
  lapsed leases — a slow worker is never raced, and takeover is delayed by at
  most one lease.
- The substep journal is epoch-fenced: a reclaimed worker's late
  `rx.step` write is refused, and the attempt kills itself instead of
  duplicating a side effect.
- **Queues**: every step carries its handler's queue (`"default"` if none);
  a worker claims only queues it serves. Order within a run holds across
  queues — a run whose frontier is on an unserved queue waits. Recovery is
  queue-agnostic (any worker recovers; the reclaimed step is then claimed by
  the right one).
- **Stopping** is not a decision about a run. A worker asked to stop (SIGTERM,
  Ctrl-C, or an app lifespan ending) stops claiming immediately and gives the
  attempts it is already running a drain budget — `REFLEX_WORKFLOW_DRAIN` or `reflex workflows worker --drain`, 30s by default — to commit their own outcome. Anything still
  running when that budget expires is cancelled and *keeps its claim*: it is
  reclaimed after the lease lapses, exactly as if the process had been killed.
  A claim is never released early, because cancelling an attempt does not stop
  work it handed to a thread, and the lease is what keeps a peer off it. A
  drained attempt costs nothing; a cancelled one costs one recovery.
- **Clients are not workers.** A process that opens
  `rx.workflows.connect(...)` can admit runs, read them, signal and cancel
  them, and executes nothing: it claims no step and runs no handler. Only a
  process that starts the kernel's worker (an app serving workflows, or
  `reflex workflows worker`) executes. This is what lets a web request start a
  run without running it.
- Multiple workers share one Postgres store via `SKIP LOCKED` claims; SQLite
  is a one-process store (calls off-loop, contention bounded); memory is for
  tests. All three answer the same conformance suite.
### Tenancy and who runs the workers

Managed and customer-hosted are a deployment split, not a semantic one. A
worker is any process with `REFLEX_WORKFLOW_DATABASE` pointed at the store and
optionally `workflow_queues` narrowed; everything above holds identically
whether that process runs on a platform or on a laptop. Nothing in the engine
asks which it is, and no behaviour changes with the answer.

Isolation between tenants is the store's boundary, and there are exactly three
supported arrangements:

1. **A store per tenant.** Separate databases, or `PostgresRunStore(schema=)`
   inside a shared one. Nothing crosses, because nothing is shared: a query,
   a claim, and a recovery sweep all see one tenant by construction. This is
   the arrangement to pick when tenants must not be able to observe each
   other even through a bug.
2. **A shared store, isolated by workflow id.** One deployment's workflows are
   its own; `list_runs(workflow_id=...)` and the CLI's filters are how an
   operator stays inside them. Fine for one product's own workloads, not for
   mutually distrusting tenants -- a caller that can reach the store can reach
   every run in it.
3. **A shared store, partitioned by queue.** Workers serve named queues, so
   compute is separated even where data is not: a tenant's slow work cannot
   starve another's, and a worker can be dedicated to one tenant's steps.
   This partitions *execution*, never *visibility*.

What the engine does not do: there is no tenant column, no per-tenant
authorization inside the store, and no filter that a caller with store access
cannot lift. Anything stronger than "shared store, separate workflow ids" must
come from arrangement 1. Say so plainly rather than implying a boundary that
is not enforced -- a tenancy story that overstates itself is worse than one
that admits its edges.

Credentials follow the same rule everywhere. Webhook secrets, approval-link
signing keys, and the API token are read from the environment at use time, so
they never enter run state, history, or a browser bundle, and rotating one is
a restart rather than a migration.

## 8. The failure matrix

"Kill" means SIGKILL — no cleanup runs. Each row states the one permitted
outcome.

| killed at | outcome |
|---|---|
| before admission commits | nothing exists; provider retry/redelivery admits normally (dedupe makes it one run) |
| after admission, before webhook ack | run exists; provider redelivers; `request_key` returns the same run (`deduplicated`) |
| after claim, before handler code runs | lease lapses → recovery → re-executed; costs one recovery, no business attempt |
| mid-handler, after a `rx.step` recorded | re-execution replays the recorded substeps; only un-recorded work repeats |
| mid-handler, provider call sent but `rx.step` not yet recorded | re-execution repeats the call; the provider-side idempotency key (`idempotency_key()`) is the defense — this window is why it exists |
| after commit (any transition) | everything in §1 is durable, including successors, children, and parent arrival; the worker's post-commit follow-ups (observer notify, loser cancellation, wakeups) are advisory and their loss is harmless |
| between a child's terminal commit and anything else | nothing is pending: the parent arrival was inside the commit |
| during recovery sweep | idempotent; re-run by the next sweep |
| worker dies holding N claims | each lease lapses independently; each step recovered independently |
| worker asked to stop mid-attempt | attempt gets the drain budget to commit; if it commits, nothing is lost and nothing is spent; if it does not, it is cancelled and the step stays claimed until its lease lapses |
| store unreachable at commit | attempt abandoned (fence unverifiable); step recovered later; `rx.step` records already made stand |
| everything down for an hour | timers/waits/retries fire on restart (due-time semantics); schedule occurrences catch up from the durable cursor, capped at `MAX_SCHEDULE_CATCHUP` per schedule, remainder skipped with a history record |

## 9. Operator actions

Every action is legal only from the states listed; anything else is a refused
no-op with a reason.

- `cancel(run)` — any nonterminal run.
- `resume(run)` — `NEEDS_ATTENTION` only; re-opens the suspended step with a
  fresh attempt budget.
- `retry(run)` — a `FAILED` run: re-opens its failed step with a fresh
  attempt budget and re-runs from there. History keeps the failure; a retry
  never rewrites the record of why it was needed.
- `skip(run)` — a run stopped for attention or failure: marks the blocking
  step `SKIPPED` (terminal, recorded as a decision rather than an outcome)
  and lets the run continue at whatever comes next. With nothing left to run,
  the run completes with no result rather than sitting pending forever.
- `force_complete(run, result)` / `force_fail(run, reason)` — a nonterminal,
  drained run: finalizes immediately, tombstoning open slots, recording the
  operator origin and (for completion) the result to treat it as having
  produced. Parent joins receive the arrival like any terminal path. Refused
  while a step is claimed, so it never races a working attempt — cancel
  first if a worker still holds one.

All of these are store transactions under the same atomicity rules as §1, and
every one of them is reachable without writing Python: `reflex workflows
cancel | resume | retry | skip | complete | fail <run>`.
