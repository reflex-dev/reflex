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

A start policy (`Singleton`/`RateLimit`/`Throttle`/`Debounce`) is part of that
same transaction, serialized under a durable lock on the run's
`(workflow_id, flow_key)` — a Postgres advisory transaction lock, SQLite's
database write lock, the store lock in memory. Every policy read, any policy
mutation (a debounce extending and re-payloading its pending run, a
cancel-mode singleton requesting its incumbent's cancellation), and the
insert commit or roll back together. Two processes admitting concurrently
under a limit of one therefore cannot both pass: nothing about policy
enforcement assumes the admitters share a process. Concretely:

- `Singleton(mode="skip")`: at most one *admitted* active run per key, at
  every instant, from any number of processes; the loser is told which run
  holds the key. Operator retry/skip may re-open a failed run alongside a
  later admission — a human override, stated in §9.
- `Singleton(mode="cancel")`: the replacement is admitted and every
  incumbent's cancellation intent is recorded in one transaction, so at most
  one *non-cancelling* run exists per key at every instant. Incumbents drain
  to `CANCELLED` asynchronously, exactly as any cancelled run does.
- `RateLimit`: the (limit+1)th start inside the window is `rejected` with a
  `retry_after`, counted against committed admissions only.
- `Throttle`: every start is admitted, each due one window after the limit-th
  most recent scheduled start, so a racing burst is spaced, not replayed.
- `Debounce`: a start that lands inside the quiet period is `coalesced` into
  the pending run, which takes the **latest** payload and a fresh deadline; a
  debounced burst starts once, with its final revision.

Fan-out branches are written by the parent's committing transaction rather
than through policy admission, so a branch root that declares a start policy
is refused at fan-out time instead of having its policy silently bypassed.

Substep results (`rx.step`) are the deliberate exception: each records in its
**own** transaction the moment the callable returns, because their purpose is
to survive a crash that prevents the attempt from ever committing.

### One validation semantics at every boundary

Python starts, HTTP starts, webhooks, signal deliveries, and worker dispatch
all validate arguments the same way (`reflex.workflow.validation`): required
parameters must bind, and supplied values must satisfy the declared types.
A **boundary** refuses before anything is written — an invalid webhook or
HTTP payload is a 400 and zero runs; an invalid Python start or signal is an
exception at the call site. **Dispatch** — which judges payloads recorded
before a redeploy changed the code — suspends the run `NEEDS_ATTENTION`
instead (§8, `incompatible_payload`) and never consumes retry attempts.
A payload model declared on a webhook (`model=...`) or channel
(`rx.Signal(Model)`) is enforced on every route in, including deliveries
built without `Signal.__call__`, and what goes onward is the **canonical**
form — coercions applied, defaults filled — not the raw input. A single
root parameter receives the whole payload when the payload satisfies its
declared type, and otherwise its same-named field of an object payload; an
unknown channel is rejected at the sender when the workflow is registered
in the sending process.

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
  The deadline is fenced at commit: an attempt that outruns cooperative
  cancellation and tries to commit after the deadline is refused and
  abandoned, so "drained" is guaranteed and TIMED_OUT is the *only* outcome a
  past-deadline run can reach. Deliveries to a past-deadline run are refused
  as `expired` for the same reason.

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

The engine deliberately does not pin runs to releases, and nothing here
should be read as planning to. Pinning is a *deployment* concern: a hosting
layer that wants one run to see one release does it by routing — admitting
new runs to the new release while old runs finish on the old one — not by
asking the engine to keep old code alive. That routing is not built yet; when
it is, it constrains which workers exist, and every rule above still holds
underneath it.

### Release-pinned execution

Two identities per run, doing different jobs. The **definition digest**
(structural) decides whether code *can* run a payload — mismatches suspend
at dispatch (§8). The **release id** (identity of the deployed artifact,
from `REFLEX_RELEASE_ID` or `WorkflowRuntime(release=...)`) decides whether
code *may*: a run pins to the release that admitted it, children included,
and a worker of a different release never claims it — the run drains on the
code that recorded its payloads, so one run never silently mixes two
releases. A run or worker with no declared release is unconstrained (dev,
tests, pre-release deployments): pinning binds only when both sides declare.

Workers register their identity — release, queues, capacity — at startup,
heartbeat on the lease-renewal cadence, and deregister on clean shutdown;
a crashed worker stays listed with a stale heartbeat, which is what a
fleet page should show (`reflex workflows fleet`, `RunStore.list_workers`).
Rolling deploys are then reads, not ceremonies: new admissions carry the
new release the moment its workers start; the old release's workers drain
what they own; rollback is starting old-release workers again; and the
retirement gate is a count — `reflex workflows fleet --can-retire R` exits
nonzero while any active run is pinned to R, because stopping R's workers
early strands those runs until their leases lapse.

## 5. Cancellation, deadlines, and children## 5. Cancellation, deadlines, and children

- `cancel(run_id)` records intent and cancels any in-flight attempt
  cooperatively. The run finalizes `CANCELLED` only once no step is claimed
  (drained), tombstoning open slots. Cancellation is never delivered as an
  exception into a *different* run's handler.
- A run past its deadline finalizes `TIMED_OUT` the same drained way.
- Every terminal path of a child — commit, cancellation, run timeout,
  recovery-budget exhaustion — delivers exactly one arrival to its parent's
  join slot, atomically with the terminal transition (§1). A join can wait
  forever only on a child that is still genuinely running.
- **Branches close with their parent.** When a run reaches a terminal state
  — cancelled, failed, timed out, force-finalized, or completed — every
  branch it fanned out that is still running has cancellation requested *in
  the same store transaction as the terminal transition*. Not follow-up: an
  operator cancels a rollout to stop the regional deploys, and a worker that
  died mid-follow-up would leave them deploying.
  - Each level closes only its own branches. A branch blocked on its own join
    holds no claim, so it is control-pending the moment it is marked,
    finalizes `CANCELLED`, and closes the level beneath it in turn. Depth is
    not a loophole and there is no waiting-for-grandchildren deadlock.
  - A branch that already finished is left exactly as it finished.
  - `rx.parallel(..., parent_close="abandon")` opts a fan-out out, for
    delegated work that should genuinely outlive its starter. An operator who
    wants an abandoned branch stopped anyway cancels it directly; it is an
    ordinary run.
- `rx.parallel(..., mode="first")`: the join resolves on the first arrival;
  the engine then requests cancellation of the losing branches. That request
  is best-effort follow-up, not part of the winning transaction, and it is
  sent by the one worker that saw the winner arrive. Losers are also closed
  durably when the parent itself goes terminal (above), which backstops a
  worker that died — but only from that moment, so for a parent that runs on
  for hours after the race, this remains true meanwhile:
  - A loser already executing on another worker receives the intent but is
    not fenced at commit, so it finishes its attempt.
  - **A loser that runs on therefore performs its side effects.** Its arrival
    is refused as late (`counted`/`duplicate`/terminal), so the parent's
    result is unaffected — that part is harmless — but the charge, the email,
    the provisioning call already happened. A branch that moves money or is
    otherwise not safe to run twice must use `rx.step` with a provider
    idempotency key, exactly as a retried step must; losing a race is not a
    guarantee of not having acted. Racing branches whose effects cannot be
    made idempotent is the wrong shape for `mode="first"`.
- A closed parent's join tombstones; late child arrivals are refused.

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

### Correlated webhook delivery

A signal channel can be fed directly by a provider:
`rx.Signal(Model, trigger=rx.webhook(topic, verify=..., dedupe_by="event_id",
correlate_by="order_id"))`. Root webhooks start runs; channel webhooks locate
them: `correlate_by` names the payload field carrying the business key,
matched against runs' request keys (§6), and `dedupe_by` names the
provider's event identity. Both are required on a channel trigger, and one
topic identifies exactly one target — root or channel, never both.

The delivery is durable from the moment it is acknowledged. Ingest writes
the channel-inbox row keyed by the event id and routes it in the **same
transaction**: to the run when the correlation key admitted one, to
`PENDING` when none exists yet, to a `DEAD` letter when the run is terminal
or past its deadline. Admission — through either door, plain or policy —
flushes `PENDING` rows for its request key inside the admitting
transaction, so a crash cannot separate "the run exists" from "its early
mail reached it". A `PENDING` row unclaimed past the TTL (30 days) becomes
a `DEAD` letter with reason `unclaimed`, swept by recovery and warned about.

Dead letters are never silent: they list with their reason
(`reflex workflows deadletters`, `GET /deadletters`) and replay
(`--replay`, `POST /deadletters/{id}/replay`) through the same routing with
the same event-id idempotency — replaying a delivered row is a `duplicate`,
never a second signal. The acceptance shape, held by a real SIGKILL test:
delivery before the run, killed after the ack, redelivered twice, run
started later — exactly one signal arrives.

### Business-key addressing

The request key is a durable unique index per workflow (`§6`), so it doubles
as a run's business address: `rx.workflows.get_by_key(Order, "order_123")`
and `rx.workflows.signal_by_key(Order, "order_123", Order.shipped(p),
key=event_id)` reach the run the key admitted, without the caller ever
storing the engine's run id. Over HTTP the same pair is
`GET /workflows/{id}/keys/{request_key}` and `POST .../signals/{channel}`.
A key that admitted nothing answers `unknown_key` (HTTP 404) — the caller
decides whether that means "not yet" (buffer upstream, or start the run) or
"never". Signal dedupe stays the sender's idempotency key; the business key
addresses, the event id deduplicates.

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
- **Time authority.** A worker on the default clock derives time from the
  store: its offset against the store's clock is measured at startup and on
  every recovery pass, so every scheduling comparison — lease expiry, due
  times, schedule occurrence keys — uses one time base across the fleet, and
  a machine with a fast wall clock can no longer reclaim a peer's live lease
  or admit a schedule occurrence early. Skew among synced workers is bounded
  by half a round trip plus local drift per recovery interval. Stores that
  never leave one host (SQLite, memory) answer that the process clock is the
  authority. An explicitly injected clock — the test harness, the dev CLI's
  fast-forward — is authoritative as given and never synced.
- **Stopping** is not a decision about a run. A worker asked to stop (SIGTERM,
  Ctrl-C, or an app lifespan ending) stops claiming immediately and gives the
  attempts it is already running a drain budget — `REFLEX_WORKFLOW_DRAIN` or `reflex workflows worker --drain`, 30s by default — to commit their own outcome. Anything still
  running when that budget expires is cancelled and *keeps its claim*: it is
  reclaimed after the lease lapses, exactly as if the process had been killed.
  A claim is never released early, because cancelling an attempt does not stop
  work it handed to a thread, and the lease is what keeps a peer off it. A
  drained attempt costs nothing; a cancelled one costs one recovery.
  A **synchronous** handler cannot be cancelled at all — a thread cannot be
  interrupted, which is the same reason `timeout=` is a compile error on sync
  handlers — so a stopping worker holds until the sync call in flight
  returns, however short the drain budget: the budget bounds how long
  *cancellable* work is waited for, never how fast a thread can be made to
  stop. Sync handlers doing long work should be async around `rx.step`.
- **Clients are not workers.** A process that opens
  `rx.workflows.connect(...)` can admit runs, read them, signal and cancel
  them, and executes nothing: it claims no step and runs no handler. Only a
  process that starts the kernel's worker (an app serving workflows, or
  `reflex workflows worker`) executes. This is what lets a web request start a
  run without running it.
- Multiple workers share one Postgres store via `SKIP LOCKED` claims; SQLite
  is a one-process store (calls off-loop, contention bounded); memory is for
  tests. All three answer the same conformance suite.
### The standalone service

`reflex workflows serve module.py` is the deployment shape for a workflow
with no frontend: webhook and approval ingress, the run HTTP API
(`POST /runs`, `GET /runs`, `GET /runs/{id}`, `POST /runs/{id}/signals/
{channel}`, `POST /runs/{id}/cancel|retry|resume`), `/healthz`, `/readyz`,
`/metrics`, `/openapi.json`, and the worker loop in one process.
`--ingress-only` and `--worker-only` split the halves for separate scaling
against the same store; both keep the probes and metrics. Shutdown is the
graceful sequence: the server stops accepting, then running attempts get
the drain budget (§ drain) to commit.

API authorization is scoped bearer tokens: `REFLEX_WORKFLOW_API_TOKEN`
grants every scope; `REFLEX_WORKFLOW_API_TOKEN_READ`, `_START`, `_SIGNAL`,
and `_OPERATE` grant exactly one each, so a dashboard's credential cannot
cancel runs and a relay's credential cannot read them. No valid token is
401; a valid token without the route's scope is 403. Webhooks and approval
links do not use these tokens — they authenticate with provider signatures
and signed link tokens respectively. HTTP signal deliveries pass through
the same kernel path as Python ones, so dispositions, channel validation,
and payload canonicalization are identical by construction.

### The operator console

`reflex workflows console` serves a Reflex app over the store — runs, one
run's story (state, steps, attempts, history, children), the worker fleet
with per-release active counts, and channel deliveries with replay — so an
operator finds and repairs a stuck run without SQL or the CLI. It is a
read-and-repair surface, never a worker: its runtime opens the store
without claiming anything, exactly like `rx.workflows.connect`. Every
action goes through the same kernel operations the CLI uses and carries
the operator's name and reason, so it lands in the run's history like any
other operator mutation (§9). Login reuses the service's token model: an
operator signs in with a scoped API token; `read` views, `operate`
mutates. A token bound to a principal (`REFLEX_WORKFLOW_API_TOKEN_PRINCIPALS`,
`name=token;name=token`) signs actions as that principal; an unbound token
records the name the operator typed, as a claim. With no token configured
the console is open — that is the loopback default, and exposing it then is
a deliberate choice behind an authenticating proxy. Pages stay live by
re-reading the store every few seconds while mounted; because the store is
what every worker shares, the view survives any worker restart without
depending on one being alive. Started with the workflow module
(`reflex workflows console workflows.py`), the console also registers the
definitions read-only and shows what starts each workflow — every webhook
URL with whether it is verified and whether its verifier's secret is
present, every schedule with its next occurrence and durable-cursor lag —
from the same summary `reflex workflows triggers` and `GET /triggers`
report, so the three surfaces cannot disagree. The same holds for connections and
secrets: `reflex workflows doctor`, `GET /connections`, and the console's
Connections page share one summary of every dependency a deployment relies
on — each verifier's secret variable and whether it is present, unverified
webhooks and their declared reason, the approval key, the API token,
schedules that need a serving process — reported by name and presence only,
never by value.

Schedules can be **paused** (`reflex workflows schedules pause KEY`,
`POST /schedules/{key}/pause`, the console's Triggers page; `operate`
scope). A paused schedule skips its occurrences and keeps its cursor
moving, so resuming never backfills the pause: an operator who paused a
nightly job for a week gets one run on resume, not seven. Skipped
occurrences are said out loud in the worker log but feed no lost-work
counter — they were asked for. Pause and resume are run-less actions and
are audited (`pause_schedule`, `resume_schedule`) with actor and reason.

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
| attempt finishes after the run's deadline passed | the commit is refused (`deadline_passed`, `attempt_abandoned` in history), the slot is released, and the sweep finalizes the run `TIMED_OUT` — a run past its deadline has exactly one outcome, never COMPLETED-after-the-fact. Recorded substeps stand: this is crash-equivalent, not an undo |
| signal or approval arrives for a run past its deadline | refused as `expired` — the continuation can never execute (claims exclude past-deadline runs), so answering "resolved" would record a decision the timeout sweep is about to discard |
| store unreachable at commit | attempt abandoned (fence unverifiable); step recovered later; `rx.step` records already made stand |
| everything down for an hour | timers/waits/retries fire on restart (due-time semantics); schedule occurrences catch up from the durable cursor, capped at `MAX_SCHEDULE_CATCHUP` per schedule; a remainder beyond the cap is skipped with a **warning naming the count and window** (there is no run to attach history to), and can be started by hand |

### Failures that are not crashes

Nothing was killed; the engine refused to proceed. Each has one outcome and
one stable `reason` on the run, so an operator (or an alert) matches on the
reason rather than on message text.

| what happened | `reason` | outcome |
|---|---|---|
| the run's workflow class is not registered in this process | `unknown_workflow` | step and run `NEEDS_ATTENTION`; re-register and `resume(run)`. Not a failure: a worker that does not serve a workflow must not decide that workflow's fate |
| the next step's handler no longer exists | `unknown_handler` | step and run `NEEDS_ATTENTION`; restore the handler and `resume(run)`, or cancel |
| a recorded payload carries arguments the handler no longer accepts — names it no longer declares, required names it cannot fill, or values its declared types no longer fit | `incompatible_payload` | step and run `NEEDS_ATTENTION`, naming the arguments; restore the parameters (or their types) or cancel. Never consumes retry attempts: retrying cannot change what the code declares |
| a run allocated more steps than `WorkflowConfig.max_steps` | `max_steps_exceeded` | the committing step succeeds, every other open slot is tombstoned, run `FAILED`. The bound is on a runaway loop, so it fails rather than suspending for a person to approve more of the same |
| a step's lease lapsed more times than `max_recoveries` | `recovery_budget_exhausted` | run `FAILED` — the complete terminal transition, identical to any other failure: remaining open slots are tombstoned, children are told to stop, and the parent's join hears one `FAILED` arrival. Infrastructure recoveries are free of the retry budget precisely so they can be bounded separately; the bound is what stops a poison step cycling forever |
| an error's `details` cannot be serialized | — | the reason is preserved and the details are replaced by `{"unserializable": repr(...)}`. Losing the payload never turns a failure into a crash |

Nothing on this table is silent: each writes its reason to the run's error and
its own history event.

### How this section is held to

Every rule above is asserted somewhere, but two kinds of test back different
claims and only one of them is evidence about crashes.

- **In-process simulation** (most of the suite) abandons a claim, expires a
  lease, or commits behind a fence. It is a fair test of store logic and no
  test at all of what reached the disk, because the process that was supposed
  to have died is still there to tidy up.
- **Real kills** (`tests/units/workflow/test_crash_boundaries.py`) SIGKILL a
  worker in a separate process at a named boundary and make a fresh process
  produce the documented outcome. Effects are recorded in an fsynced ledger,
  so an effect that really happened cannot be lost in a way that flatters the
  result, and each scenario asserts the worker died by signal rather than
  exiting — a scenario whose worker exits cleanly proves nothing while
  passing everything.

Boundaries covered by real kills: between claim and handler (work simply
undone); after an unguarded effect (repeats, §2, which is the cost `rx.step`
exists to remove); after a substep journal write (replays, never repeats);
and immediately after a parent's finalize transaction (branches are already
marked on disk, §5 — the case that distinguishes an in-transaction close from
follow-up).

## 9. Operator actions

Every operator mutation records **who asked and why** when the surface
knows: the CLI stamps the invoking user (`REFLEX_ACTOR` overrides) and its
`--reason`; the HTTP API names the actor from the credential when the token
is bound to a principal, else records the caller's `X-Actor` claim as given,
else `api` (naming the surface beats naming nobody), and takes the body's
`reason`. Attribution rides the same history events,
in the same transactions, as the mutations they describe — the record that
answers "what happened" answers "who did this", and cannot drift from it.

Actions with **no run** to carry history — replaying a dead letter, purging
finished runs — are written to a separate append-only **audit log**
(`list_audit`; `reflex workflows audit`; `GET /audit`) in the operation's
own transaction, with actor, action, target, outcome, and reason. Only
attributed actions are recorded: automation (the TTL sweep, recovery) leaves
no entry, so the log is operator decisions rather than noise. This mirrors
the split Temporal makes between workflow history and its control-plane
audit stream.

Every action is legal only from the states listed; anything else is a refused
no-op with a reason.

- `cancel(run)` — any nonterminal run. Closes the branches it fanned out,
  per §5.
- `resume(run)` — `NEEDS_ATTENTION` only; re-opens the suspended step with a
  fresh attempt budget.
- `retry(run)` — a `FAILED` run: re-opens its failed step with a fresh
  attempt budget and re-runs from there. History keeps the failure; a retry
  never rewrites the record of why it was needed.
- `skip(run)` — a run stopped for attention or failure: marks the blocking
  step `SKIPPED` (terminal, recorded as a decision rather than an outcome)
  and lets the run continue at whatever comes next. With nothing left to run,
  the run completes with no result rather than sitting pending forever — and
  completing by decision is the same terminal transition as completing by
  execution: children are told to stop, and a parent joined on this run
  receives one `COMPLETED` arrival (`result: null`) instead of waiting
  forever on a run that no longer will. If the run already delivered its
  arrival when it first reached a terminal state, the join keeps what it
  heard: a run delivers exactly one arrival (§5), and operator repair does
  not rewrite a result the parent has already counted.
- Both restore the successors the stopping failure tombstoned (`step_restored`
  in history, fresh budgets), so a preallocated chain's remaining steps —
  including its finalizer — still run. What was waiting comes back waiting:
  a tombstoned join or wait slot is restored `BLOCKED` with its arrival
  count and timeout deadline intact — never `READY`, which would run it
  immediately with a missing or partial payload — and a delayed slot keeps
  its original due time rather than firing the moment an operator retries. Only that failure's casualties come
  back: a `CANCELLED` slot in a run these actions accept can have no other
  source, because run-level cancellation ends in a `CANCELLED` run they
  refuse and force-finalization leaves them no step to target.
- `force_complete(run, result)` / `force_fail(run, reason)` — a nonterminal,
  drained run: finalizes immediately, tombstoning open slots, recording the
  operator origin and (for completion) the result to treat it as having
  produced. Parent joins receive the arrival like any terminal path. Refused
  while a step is claimed, so it never races a working attempt — cancel
  first if a worker still holds one.

All of these are store transactions under the same atomicity rules as §1, and
every one of them is reachable without writing Python: `reflex workflows
cancel | resume | retry | skip | complete | fail <run>`.

Operator actions deliberately do not re-check start policies. Retrying a
failed `Singleton` run while its replacement is already active puts two runs
on one key — the singleton promise in §1 governs *admissions*, and an
operator re-opening a run is a human override, not an admission. The operator
can see what holds the key (`reflex workflows list -w <workflow>`) and decide;
the engine does not silently refuse a repair because a policy would have.

## 10. The observable vocabulary

Everything above describes behaviour; this is the complete list of words the
engine uses to describe it. An operator reading a run sees exactly these
values and nothing else, and a value that appears here but is never produced
(or is produced but never appears here) is a defect — `test_contract_vocabulary.py`
fails on either.

**Run status.** Nonterminal: `PENDING` (admitted, nothing claimed yet),
`RUNNING` (an attempt holds a claim), `RETRYING` (an attempt failed and the
next is scheduled with backoff), `WAITING` (blocked on a signal, a timer, or
a join), `CANCELLING` (cancellation recorded, draining), `NEEDS_ATTENTION`
(suspended for a person; §8 names every reason). Terminal: `COMPLETED`,
`FAILED`, `CANCELLED`, `TIMED_OUT`.

**Step status.** In flight: `READY` (claimable once it is the frontier),
`BLOCKED` (a wait or join slot not yet satisfied), `CLAIMED` (a worker holds
it under a lease), `RETRY_WAIT` (business retry scheduled), `RECOVERY_WAIT`
(lease lapsed, awaiting re-execution). Terminal: `SUCCEEDED`, `FAILED`,
`TIMED_OUT`, `CANCELLED`, `NEEDS_ATTENTION`, `SKIPPED`.

**Start disposition** — what admission did with a submission: `started`,
`deduplicated` (§6 request key), `coalesced` (debounce), `skipped`
(singleton), `rejected` (rate limit, with `retry_after`).

**Delivery disposition** — what the store did with a signal or arrival:
`resolved`, `buffered` (arrived before its wait was armed), `counted` (a join
arrival that is not the last), `duplicate` (repeated sender key),
`expired` (run past its deadline), `unknown_run`, `run_terminal`,
`unknown_key` (a business key that admitted nothing), `parked` (a correlated
webhook delivery accepted before its run exists — durable in the channel
inbox, flushed inside the admitting transaction when the run arrives), and
`dead_letter` (a correlated delivery nothing can take: its run is terminal or
past deadline, or the parked delivery went unclaimed past its TTL; visible
via the channel inbox and replayable by an operator with the same event-id
idempotency, so a replay of a delivered row is a `duplicate`, never a second
signal).

**History events.** Append-only, one run's whole story:

| event | means |
|---|---|
| `run_admitted` | the run exists; admission committed |
| `step_scheduled` | a slot was preallocated for future work |
| `attempt_started` | a claimed attempt began executing |
| `attempt_succeeded` | the attempt committed its transition |
| `attempt_failed` | the attempt raised |
| `attempt_timed_out` | the attempt exceeded its `timeout=` |
| `attempt_cancelled` | the attempt was cancelled cooperatively |
| `attempt_abandoned` | the attempt's work was discarded: fenced claim, lost lease, or a commit refused past the run deadline |
| `step_retry_scheduled` | the next business attempt was scheduled with backoff |
| `step_recovered` | a lapsed lease was reclaimed; costs one recovery, not an attempt |
| `step_tombstoned` | a terminal transition closed a slot that will now never run |
| `step_restored` | `retry`/`skip` brought back a slot a failure had tombstoned |
| `step_skipped` | an operator marked a blocking step `SKIPPED` |
| `run_completed`, `run_failed`, `run_timed_out`, `run_cancelled` | the run reached that terminal state |
| `run_cancel_requested` | cancellation intent recorded; `cause: parent_close` when a closing parent did it (§5) |
| `run_needs_attention` | suspended, carrying the `reason` from §8 |
| `run_resumed` | reopened; `origin` distinguishes `resume` from `retry` |
| `child_started` | a fan-out admitted a branch |
| `child_resolved` | a branch's arrival reached its parent's join |
| `wait_armed` | a wait or timer slot was armed |
| `wait_resolved` | a delivery satisfied a wait |
| `wait_expired` | a wait reached its deadline; the `on_timeout` branch runs |
| `signal_buffered` | a signal arrived before its wait was armed |
| `signal_duplicate` | a repeated sender key was ignored |
| `substep_recorded` | an `rx.step` result was journalled |

Both wait outcomes are recorded, deliberately: "the approval came through" and
"nobody answered in time" lead to different handlers and different
conversations, and a history that showed only which handler ran next would
make an operator infer the difference instead of read it.
