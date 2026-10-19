---
title: Scaling Reflex Apps
meta_description: Horizontal scaling for Reflex apps, durable jobs, regional state, Redis failover, database read routing, OpenTelemetry compatibility, Redis spikes, and scale-down recovery.
---

# Scaling Reflex Apps

Scale the interactive backend by adding small, replaceable replicas behind a load balancer. Keep UI events quick and give long-running jobs their own workers and durable storage.

This guide uses a report-export application to explain the boundaries: a user requests a report, leaves the page, and later retrieves the result through any healthy backend. Choose capacity and recovery settings from production-mode tests of your exact versions. Managed hosting may expose different controls.

## Reference production architecture

This is an illustrative deployment, not a list of required components. Start with the request path and stores your app needs. Add read replicas for lag-tolerant read load, a separate cache for expensive repeatable reads, and a queue when jobs must outlive a backend.

```python exec
import reflex as rx
```

```python eval
rx.el.figure(
    rx.el.div(
        rx.image(
            src=rx.asset("hosting/scaling-architecture.svg"),
            alt="Production architecture: browser and frontend, load balancer, backend replicas, databases, separate Redis roles, provider-managed failover endpoint, queue and workers. Text description follows.",
            width="100%",
            min_width="760px",
            height="auto",
        ),
        overflow_x="auto",
        width="100%",
        tab_index=0,
        role="region",
        custom_attrs={
            "aria-label": "Production architecture; scroll horizontally on narrow screens"
        },
    ),
    rx.el.figcaption(
        rx.el.a(
            "Open architecture diagram at full size",
            href="/hosting/scaling-architecture.svg",
            target="_blank",
            rel="noopener noreferrer",
            text_decoration="underline",
        ),
    ),
    width="100%",
    margin_y="1.5em",
)
```

### Architecture text alternative

The labeled arrows distinguish traffic types. On narrow screens, scroll the diagram or open it at full size.

- **Request/response:** browser ↔ static frontend/CDN for assets; browser frontend ↔ load balancer ↔ one healthy backend replica for events and state updates over WebSockets. Backends share the same application build.
- **Application data:** backend replicas ↔ regional Redis session state; optional application cache uses a separate Redis service. Backends and workers write durable records to the primary database. Only lag-tolerant reads go to read replicas; read-after-write and other freshness-critical reads use the primary.
- **Asynchronous jobs:** backend → durable job record/outbox → task queue → independent workers. Workers save status and results in shared storage; any authorized backend can read them. The job lifecycle below explains confirmation, retry and acknowledgement boundaries.
- **Replication:** primary database → read replica databases; Redis primary → Redis replica. These arrows copy data, not application requests. Asynchronous replication can lag and can lose recent writes on failover.
- **Redis failover:** backends use an ordinary Redis URL through a provider-managed failover endpoint, which routes application traffic to the current primary. Test connection recovery and the provider's persistence behavior during failover.

## Serve requests with replaceable backends

Host the exported frontend independently, for example on a CDN. Configure its API URL for the WebSocket-capable load balancer in front of the Python backends. Each region's replicas share that region's session Redis; durable records, files and jobs live outside individual processes and local disks.

Start with deliberate process counts so adding replicas does not multiply oversized database or Redis connection pools. One Granian process per small instance is a measurement starting point:

```bash
GRANIAN_WORKERS=1 reflex run --env prod \
    --backend-only --backend-port 8000
```

This command assumes Granian. If the environment also includes Uvicorn and Gunicorn, set `REFLEX_USE_GRANIAN=true` explicitly. The deployment platform controls replica count. See [self-hosting](/docs/hosting/self-hosting/) for production commands and networking.

More replicas do not shorten one oversized event or remove contention within one session. Paginate results, keep session state small, and measure handler duration separately from state acquisition. Use async database/API clients in [background events](/docs/events/background-events/), holding the state lock only briefly to update UI state. For unavoidable blocking I/O, use `await rx.run_in_thread(...)` from a background event; use process workers or a process executor for CPU-heavy Python work. See [performance and execution](/docs/advanced-onboarding/performance-and-execution/).

## Let jobs outlive a backend

A report export may take minutes. The UI needs a job ID and progress, while the worker needs to finish even if the accepting backend is scaled down. Use an independent queue/worker system such as [Taskiq](https://taskiq-python.github.io/guide/architecture-overview.html) or [Celery](https://docs.celeryq.dev/en/stable/userguide/tasks.html) for that requirement. Reflex background events run inside a backend and end with that process.

```python eval
rx.el.figure(
    rx.el.div(
        rx.image(
            src=rx.asset("hosting/scaling-job-lifecycle.svg"),
            alt="Job lifecycle: commit a job and outbox, confirm queue publication, process idempotently, save results before acknowledgement, and recover through bounded retries. Text description follows.",
            width="100%",
            min_width="760px",
            height="auto",
        ),
        overflow_x="auto",
        width="100%",
        tab_index=0,
        role="region",
        custom_attrs={
            "aria-label": "Job lifecycle; scroll horizontally on narrow screens"
        },
    ),
    rx.el.figcaption(
        rx.el.a(
            "Open job lifecycle diagram at full size",
            href="/hosting/scaling-job-lifecycle.svg",
            target="_blank",
            rel="noopener noreferrer",
            text_decoration="underline",
        ),
    ),
    width="100%",
    margin_y="1.5em",
)
```

### Job lifecycle text alternative

1. **Accept and record.** Authorize the request, validate inputs, and commit a job record and enqueue intent together, such as an outbox entry in the same database transaction. Store a stable job ID, owner/tenant, input reference and status. A tenant-scoped idempotency key with a uniqueness constraint handles repeated submissions.
2. **Return and dispatch.** Return the job ID after the transaction commits. A dispatcher publishes pending outbox entries, marks them delivered only after broker confirmation, and retries with the same job ID. Monitor pending entries: an accepted record does not itself prove the broker received it.
3. **Process independently.** Workers load authorized inputs from shared storage. They must not need the original backend's memory, local files or WebSocket. A crash after publication can cause duplicate delivery, so worker effects must be idempotent or transactionally deduplicated by job ID.
4. **Save, then acknowledge.** Persist progress, completion/failure and result references in shared durable storage before acknowledging success to the broker. Keep large outputs in object storage. For external effects that cannot commit atomically with the outcome, use the service's idempotency support or reconciliation; there is no general exactly-once guarantee.
5. **Recover and read.** Configure broker acknowledgements and redelivery, timeouts and bounded retries. Expose permanent failures. Any healthy backend can authorize access and read the job by ID; reopening the app can recover outstanding jobs from durable records.

A queue library alone does not guarantee durability. Select broker persistence and worker-loss behavior, then test them. Taskiq needs an actual result backend or application job store; Celery acknowledgement and worker-loss settings affect redelivery. Define result retention, backups and expiry independently of queue delivery. Avoid process-local queues and in-memory-only results for jobs that must survive scale-down. Scale workers by backlog and oldest-job age, independently of backend replicas.

### Connect a report job to Reflex state

The handler below awaits an application service outside the state lock, then applies its result only if the signed-in session and selected request are still current. `report_app.auth.AuthState` is your own authentication state, not a Reflex API: its backend-only `_owner_id` comes from verified authentication, and `_session_revision` changes on every login/logout, including signing back in as the same owner. Your logout handler also clears the report UI.

Supply asynchronous `report_app.reports` adapters backed by your database and broker:

- `accept_report(owner, request_key, report)` validates access and inputs, atomically commits the job and outbox, and returns only after commit. Enforce `UNIQUE(owner, request_key)`: the same key and inputs return the existing job; the same key with different inputs is rejected.
- `read_report(owner, job_id, request_key)` reads from the **primary**, filtering by owner and the selected job ID, or by owner and request key when no ID exists. Only when both are empty does it recover that owner's latest job for this report type. Return `None` for no match, without falling back to an older job for a selected key. Both adapters return a record with `id`, `status` and `request_key`; service failures raise your `ReportServiceError`.

```python
from uuid import uuid4

import reflex as rx
from report_app.auth import AuthState
from report_app.reports import ReportServiceError, accept_report, read_report


class ReportState(rx.State):
    job_id: str = ""
    status: str = ""
    error: str = ""
    _request_key: str = ""
    _generation: int = 0

    @rx.event
    def new_report(self):
        self._request_key = uuid4().hex
        self._generation += 1
        self.job_id = self.status = self.error = ""

    @rx.event(background=True)
    async def sync_report(self, submit: bool = False):
        async with self:
            auth = await self.get_state(AuthState)
            identity = (auth._owner_id, auth._session_revision)
            self._generation += 1
            generation = self._generation
            if not identity[0]:
                self.job_id = self.status = ""
                return
            if submit and not self._request_key:
                self._request_key = uuid4().hex
            request_key, job_id = self._request_key, self.job_id

        job, error = None, ""
        try:
            if submit:
                job = await accept_report(identity[0], request_key, "monthly-sales")
            else:
                job = await read_report(identity[0], job_id, request_key)
        except ReportServiceError:
            error = "Request not confirmed. Retry or refresh before starting anew."

        async with self:
            auth = await self.get_state(AuthState)
            if identity != (auth._owner_id, auth._session_revision):
                return
            if generation != self._generation:
                return
            self.error = error
            if not error:
                self.job_id = job.id if job else ""
                self.status = job.status if job else ""
                if job:
                    self._request_key = job.request_key


def report_panel():
    return rx.vstack(
        rx.button("New report", on_click=ReportState.new_report),
        rx.button("Submit / retry", on_click=ReportState.sync_report(True)),
        rx.button("Refresh / recover", on_click=ReportState.sync_report(False)),
        rx.text(ReportState.job_id, ": ", ReportState.status),
        rx.text(ReportState.error),
    )
```

Retries keep the same request key; **New report** deliberately creates a new logical request and key. After authentication, run `ReportState.sync_report` on page load to recover a job in a fresh session. If a session is lost before acceptance reaches the UI, recover from durable records before deliberately submitting a new request; a key held only in lost session state cannot deduplicate a new key. For multiple outstanding jobs, provide an authorized list/selection view instead of a latest-job lookup.

These adapters and the worker must implement the lifecycle above; a background event alone does not make the job durable.

## Keep regional state and durable data separate

Keep frequent session-state access close to the backends: each region uses its own Redis session store, and active sessions are routed consistently to that region. Business records, preferences and jobs belong in stores with explicit write ownership, consistency, replication and recovery policies.

Moving a user to another region may create a fresh UI session. Rebuild useful state from durable records rather than promising transfer of regional Redis state. For example, after an export starts in Region A, a backend in Region B can authorize the user and read its job/result without the original session. A globally reachable Redis endpoint alone does not make data durable; review its [persistence and recovery tradeoffs](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/).

### Use the primary for writes and fresh reads

Read replicas are useful when nearby, read-only copies reduce latency or primary load. Make routing explicit in the data-access layer:

| Operation | Destination |
| --- | --- |
| Writes, migrations, locking reads and read-write transactions | Current primary; keep each transaction on its owning connection. |
| Read-after-write or other freshness-critical reads | Primary unless a replica is verified to have caught up. Confirm a newly submitted job here. |
| Read-only queries that tolerate replication lag | Healthy read replica; a locking `SELECT` is not eligible. |
| Replica unavailable or too far behind | Another healthy replica or bounded primary fallback, with capacity protection. |

Test lag and outages before relying on regional routing. Never send writes to a replica outside a controlled promotion process. See [PostgreSQL replication tradeoffs](https://www.postgresql.org/docs/current/high-availability.html).

### Add a separate cache only for a measured need

For example, cache an expensive, repeatable lookup when bounded staleness is acceptable. Use a separate Redis service so cache churn, eviction and refill bursts do not compete with Reflex session state. Key prefixes or logical database numbers on one server do not isolate resources or failures.

`REFLEX_REDIS_URL` configures Reflex state. Application caching uses your own client/configuration, with bounded TTLs, reused clients and limits on cache-miss database work. Keep cache clients outside serialized session state. No cache is required by this architecture.

### Use a failover endpoint

Configure `REFLEX_REDIS_URL` with an ordinary Redis URL for a provider-managed endpoint that handles failover.

## Keep builds and state versions compatible

Use `uv` or another locking package manager to freeze dependencies across builds. Replicas sharing a state store must run compatible application code and state schemas.

- Compatible framework upgrades can preserve saved state; plan for session reset on downgrade/rollback and read the release notes for migration instructions.
- Changing stored base-variable names/types makes saved state incompatible. Changing defaults or method bodies does not change the saved-state schema hash.
- Rebuild and deploy the frontend alongside changes to fields, frontend computed-variable names/types or handler names. The frontend compatibility hash includes frontend computed variables and handler names; the saved-state schema hash does not.

See [self-hosting compatibility guidance](/docs/hosting/self-hosting/) for release-specific migration constraints.

## Use telemetry to choose the next change

Enable the optional `reflex-otel` instrumentor with a compatible SDK/exporter and verify data reaches the collector. Trace points and metrics remain inactive until configured. Start with the question you need to answer:

| Question | Measure and act |
| --- | --- |
| Is one handler slow, or is it waiting for state? | Compare event spans/`reflex.event.duration` with `reflex.state.acquire.duration`; shorten the handler or its lock-held work. |
| Are connections or payloads driving load? | Correlate `reflex.websocket.connections` and `reflex.websocket.message.size` with latency and replica count; reduce unnecessary events/payloads. |
| Is the report waiting or computing? | Measure queue wait and worker execution separately; increase worker capacity only when that is the bottleneck. |

Use service, region, deployment version and database role to locate the slow boundary. Database queries, queue publication and external workers need their own instrumentation; propagate trace context through the broker. Reflex does not automatically create those external spans. Verify one event-to-worker-to-database trace, set sampling/redaction rules, and keep sensitive payloads and high-cardinality job IDs out of metric labels. See [Reflex OpenTelemetry](/docs/api-reference/observability/) and [context propagation](https://opentelemetry.io/docs/languages/python/propagation/).

### Pin the telemetry combination

| Instrumentor release | Declared dependency floors |
| --- | --- |
| `reflex-otel==0.2.0` | Python >=3.11; `reflex-base >=0.10.0`. |

This release declares `opentelemetry-api >=1.30.0,<2.0` and instrumentation/ASGI instrumentation >=0.49b0,<1.0. These are dependency constraints, not certification of arbitrary SDK/exporter combinations. Lock the exact framework, instrumentor, SDK and exporter; verify backend and optional browser export together.

## Validate recovery under load

When scaling down, stop routing new connections to retiring backends, drain bounded work, and test reconnects to another healthy replica. Allow time for worker drain and recovery separately. There is no universal sessions-per-instance figure.

Here are example validation tasks for the components you choose to deploy. Run realistic sessions in production mode and record p50/p95 latency, errors, resource use, event rate, payload sizes, instance/process counts, queue delay and job completion:

- Add backends under load; check whether the database or Redis becomes the bottleneck.
- Remove the backend that accepted a report; reconnect elsewhere and retrieve the job/result.
- Restart a worker mid-job; verify redelivery/retry behavior and absence of duplicate side effects.
- Repeat a submission and interrupt queue publication; verify idempotency and recovery of pending outbox entries.
- Fail over the provider-managed Redis endpoint; exercise locks, active sessions and reconnects, and check which writes survive under its persistence policy.
- Move a user between regions; verify session reset, authorization and recovery of durable jobs.
- Delay or disable a read replica; verify primary routing for fresh reads and bounded fallback.

### Turn Redis spikes into an action

Compare session Redis and cache separately over the affected time window. Use provider metrics or bounded diagnostics such as `INFO memory`, `INFO clients`, `INFO commandstats` and `SLOWLOG GET 20` through authorized operator access.

| Signal | Next action |
| --- | --- |
| Memory, key count or evictions growing | Reduce per-session datasets/history; bound cache TTLs and monitor state eviction. |
| CPU/commands rise with event or polling rate | Reduce duplicate events/polling and limit cache refill concurrency before adding more clients. |
| Connections rise after scaling | Check process counts, pool limits, client reuse and reconnect backoff. |
| Latency tracks long-held state locks | Move slow work to the background/worker path; increasing timeouts does not add throughput. |

`SLOWLOG` excludes network latency and may expose private arguments; redact before sharing. A `noeviction` policy rejects new writes at the memory limit. See [Redis diagnostics](https://redis.io/docs/latest/commands/info/) and [eviction policies](https://redis.io/docs/latest/develop/reference/eviction/).
