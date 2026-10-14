---
title: Scaling Reflex Apps
meta_description: Horizontal scaling for Reflex apps, durable jobs, regional state, Redis Sentinel support limits, database read routing, OpenTelemetry compatibility, Redis spikes, and scale-down recovery.
---

# Scaling Reflex Apps

Scale Reflex horizontally: run many small, replaceable instances of the same application. Keep interactive events quick, move long-running work to independent workers, and keep session state close to the region serving the user.

This guide describes an architecture for self-hosted Reflex applications. Choose instance sizes, replica counts, and operational settings from production-mode load tests on the supported Reflex version. Managed hosting may expose different controls.

## Prefer horizontal scaling

Horizontal scaling adds application instances behind a load balancer. It provides capacity in small increments and lets an instance be replaced or removed without making it the permanent owner of a user’s work. Each replica runs the same application code and uses the shared services for its region.

Vertical scaling gives an existing instance more CPU or memory. It can help a resource-heavy process, but it has a machine-size ceiling and does not remove a single-instance failure risk. Use it selectively when measurements justify it; prefer horizontal growth for the interactive backend.

### Design for small replaceable instances

- Serve the frontend independently, such as a static frontend through a CDN, and place the Python backends behind a WebSocket-capable load balancer.
- Share one region-local session Redis service across the backend replicas in that region. Store durable records, files, and jobs outside individual processes and local disks.
- Set process counts deliberately. Increasing replicas should not accidentally multiply an oversized worker pool and exhaust database or Redis connections.
- Scale down gracefully: stop routing new connections to a retiring instance, drain work that can finish quickly, and test reconnects to another healthy instance.

For a small backend instance, one server process can be a useful starting point for measurement. This is a per-instance command; the deployment platform controls the number of replicas:

```bash
REFLEX_USE_GRANIAN=true GRANIAN_WORKERS=1 reflex run --env prod \
    --backend-only --backend-port 8000
```

Configure the exported frontend’s API URL for the load-balanced backend. One process is an example, not a universal sizing rule. See the [self-hosting guide](/docs/hosting/self-hosting/) for production commands and networking.

## Pin versions and plan state-store upgrades

Use the same application code, dependency lockfile, and compatible state schema on every replica sharing a state store. This guide's source checks are pinned to [Reflex revision d02ba5409579e24e67401f9dd6eb2fc4d3ef5e1b](https://github.com/reflex-dev/reflex/tree/d02ba5409579e24e67401f9dd6eb2fc4d3ef5e1b). They establish implementation and dependency constraints, not a load-test or failover certification for every release.

| Deployment | Verified constraint | Deployment action |
| --- | --- | --- |
| Reflex 0.9 and 0.10 together | Reflex 0.9 and 0.10 cannot share a state store. 0.10 can load 0.9 state; 0.9 discards 0.10 state. | Do not use a mixed-version rolling deployment against the same Redis store or disk state directory. Upgrade all instances together, or use separate stores and accept session reset at cutover. |
| Rollback from 0.10 to 0.9 | Sessions saved by 0.10 reset when they reach 0.9. | Use a fresh state store, or clear only the app's dedicated state store as part of an approved rollback procedure. Keep durable records outside session state. |
| `reflex-otel==0.1.0` | Its release manifest declares Python >=3.10 and `reflex-base >=0.9.11`. | This is a release-specific dependency floor, not a guarantee for every 0.9 deployment. Pin the compatible framework, SDK, and exporter, and test the features used by that release. |
| `reflex-otel==0.2.0` and the reviewed source | Python >=3.11 and `reflex-base >=0.10.0`. Both instrumentor releases declare `opentelemetry-api >=1.30.0,<2.0` and instrumentation/ASGI instrumentation >=0.49b0,<1.0. | Resolve and pin the exact instrumentor, SDK, exporter, and compatible framework versions in your lockfile. Verify backend and optional browser export together before rollout. Do not install 0.2.0 against 0.9. |

The table records constraints from [self-hosting](https://github.com/reflex-dev/reflex/blob/d02ba5409579e24e67401f9dd6eb2fc4d3ef5e1b/docs/hosting/self-hosting.md), the [0.1.0 instrumentor manifest](https://github.com/reflex-dev/reflex/blob/3d47357ac158c51a0c131ec48c41232830bd9031/packages/reflex-otel/pyproject.toml), and the [0.2.0 instrumentor manifest](https://github.com/reflex-dev/reflex/blob/40ffab8124ba257053c395309c87f1c818b4e0a2/packages/reflex-otel/pyproject.toml). For another release, recheck those files at that exact tag or commit. Record the resolved Python, Reflex, reflex-base, reflex-otel, Redis client/server, broker, and result-store versions with your load and recovery test results. A dependency lower bound is not evidence that an arbitrary combination has been tested.

## Keep interactive events quick

An event should validate the request, perform bounded work, update a small amount of UI state, and return. Paginate large result sets, separate unrelated views into their own state classes, and avoid blocking I/O or long computation while holding a state lock.

Adding replicas will not shorten one oversized event or remove contention within one session. Measure handler duration and state acquisition separately, then address the work responsible. The [performance and execution guide](/docs/advanced-onboarding/performance-and-execution/) explains these boundaries.

## Run long work in independent workers

Send long-running work to a queue system such as Taskiq or Celery, with workers deployed separately from the Reflex backend. Design the handoff so the backend that accepts a job can be removed after durable acceptance. Another backend must still be able to find the job, show its progress, and retrieve its result; verify this behavior with the selected broker, workers, and result store.

Reflex background events run inside an application backend. They can keep short-lived UI work responsive, but they do not give a job an independent lifetime. Use an external worker whenever the task must survive removal of its originating backend. See [background event lifecycle](/docs/events/background-events/).

### Hand off jobs durably

Consider a report export. The UI needs confirmation that the job was accepted; it should not need its original backend to stay alive until the report finishes.

1. **Accept the request.** Check authorization and validate inputs. Create a durable job record with a stable job ID, owner or tenant, input reference, and initial status.
2. **Persist the handoff.** Record the enqueue intent reliably. For example, write the job and an outbox entry in one database transaction. A dispatcher publishes the outbox entry to the broker and marks it delivered only after broker confirmation, retrying with the same job ID. A crash after publication can cause duplicate delivery, so the consumer must be idempotent. Monitor and retry pending outbox records so recorded work is not silently left unqueued.
3. **Return to the UI.** Keep the job ID and a short status in session state, then return from the event. Do not wait for the worker’s result inside the event.
4. **Process independently.** The worker receives the job ID, loads authorized inputs from shared storage, and executes the task. It must not depend on the original backend’s memory, local files, or WebSocket.
5. **Persist progress and results.** Write completion, failure, and result references to shared durable storage. Store large outputs in shared object storage.
6. **Read from any backend.** After checking access, the backend handling the next request reads the job record by ID. Use bounded polling or a notification that triggers a fresh read. Reopening the app should recover outstanding jobs from durable records.

An illustrative record makes the ownership boundary explicit:

```text
job_id: stable identifier
owner_id: authenticated user or tenant
input_ref: shared data or object reference
status: queued | running | succeeded | failed
result_ref: shared output reference when complete
```

### Configure recovery rather than assuming it

A queue library alone does not guarantee durability. Choose a broker and result store with the required persistence, configure acknowledgements and redelivery, and test worker crashes. Use a tenant-scoped idempotency key with a database uniqueness constraint for repeated submissions, and idempotent or transactional worker effects so redelivery does not duplicate side effects. Persist the outcome before acknowledging success. If an external effect cannot be committed atomically with the outcome, use that service's idempotency support or a reconciliation procedure; there is no general exactly-once guarantee. Bound retries, add timeouts, and make permanently failed jobs visible.

Celery acknowledgement timing and worker-loss behavior affect whether work is redelivered. Taskiq likewise needs a suitable broker and an actual result backend or application job store. Specify result retention, backups, and expiry independently of broker delivery; keep the authoritative job status in the application store if broker results expire sooner than users need them. Avoid process-local queues and in-memory-only results for work that must survive scale-down. Scale workers by backlog and oldest-job age independently of app replicas.

References: [Celery task semantics](https://docs.celeryq.dev/en/stable/userguide/tasks.html), [Taskiq architecture](https://taskiq-python.github.io/guide/architecture-overview.html), and [Celery worker shutdown](https://docs.celeryq.dev/en/stable/userguide/workers.html).

## Keep session state local to each region

For a multi-region application, use region-local Redis for Reflex session state. Put more persistent or cross-region data in a database or a separately designed global Redis service. Frequent session-state access stays close to the backend, while important records remain independent of a UI session.

- **Regional sessions:** each region’s backends share that region’s session Redis. Route an active session consistently to its region; individual backend instances remain replaceable.
- **Persistent records:** business data, preferences, and jobs belong in a store available to the regions that need them. Define consistency, write ownership, replication, residency, and recovery expectations.
- **Global Redis:** configure persistence, replication, expiry, and recovery for the items it holds. A globally reachable endpoint alone does not guarantee durability.
- **Regional failover:** moving a user to another region may create a fresh UI session. Reconstruct useful state from persistent records, including outstanding jobs. Do not promise seamless transfer of region-local session state.

For example, a user starts an export in Region A and reconnects in Region B. The independent worker continues. Region B checks authorization and reads the durable job and result without needing the original backend or Region A’s session Redis.

See [Redis persistence and recovery tradeoffs](https://redis.io/docs/latest/operate/oss_and_stack/management/persistence/).

### Redis Sentinel availability versus Redis Cluster sharding

Redis Sentinel monitors non-clustered Redis and coordinates promotion of a replica when the primary fails; it does not shard data. Redis Cluster partitions data across shards and requires a cluster-aware client. Horizontal application scaling and Redis sharding are separate decisions: adding backend instances does not itself require Cluster.

**No built-in Sentinel adapter has been verified for the Reflex source reviewed here.** The Redis factory accepts `redis://`, `rediss://`, and `unix://` URLs and creates ordinary synchronous or asynchronous Redis clients. It does not construct a Sentinel client, discover a primary through Sentinel, or construct a Redis Cluster client. Do not point `REFLEX_REDIS_URL` at a Sentinel control port or invent a Sentinel URL scheme. Redis Cluster is not a supported session-state configuration in this reviewed client path.

A provider may expose a stable ordinary Redis primary endpoint backed by its own failover system. That is a provider-specific deployment choice, not native Sentinel integration. Validate that endpoint's primary switching, connection recovery, state locks, and persistence with your exact Reflex and Redis client versions before relying on it. A custom Sentinel adapter needs its own implementation and integration tests before it can be documented as supported.

Sentinel's Redis replication is asynchronous, so failover can lose recent acknowledged writes. Define recovery behavior and capacity on the remaining nodes. Persistent business records and jobs need their own durability guarantees. See [Redis Sentinel requirements](https://redis.io/docs/latest/operate/oss_and_stack/management/sentinel/) and [Redis Cluster specification](https://redis.io/docs/latest/operate/oss_and_stack/reference/cluster-spec/).

### Separate caching from session state

Use separate Redis services for application caching and Reflex session state. Reflex reads `REFLEX_REDIS_URL` for state. Application cache code can read a separate variable such as `APP_CACHE_REDIS_URL`; that second name is an application convention, not another built-in Reflex cache setting.

Different key prefixes or logical database numbers on one server do not isolate resource usage or failure.

```bash
# Illustrative ordinary regional endpoints, not Sentinel setup.
REFLEX_REDIS_URL=rediss://state.eu.example:6379/0
APP_CACHE_REDIS_URL=rediss://cache.eu.example:6379/0
```

Supply real endpoints and credentials through deployment configuration. Use bounded cache TTLs, reuse clients, and prevent cache misses from causing unlimited database work. Keep cache clients outside serialized session state.

## Route database queries explicitly

For a globally distributed app, consider a read-only database replica in each region that hosts Reflex backends. Eligible reads can stay local, reducing cross-region latency and read load on the primary. Make routing an explicit policy in the data-access layer that covers every query.

- **Primary:** route writes, migrations, locking reads, and read-write transactions to the current primary. Keep the operations in a transaction on its owning connection.
- **Regional replicas:** route read-only queries that tolerate replication lag to a healthy nearby replica. A `SELECT` that locks rows or participates in a write transaction is not an eligible replica read.
- **Consistency exceptions:** use the primary for read-after-write and freshness-critical reads unless the replica is verified to have caught up. For example, read a newly created job from the primary when immediately confirming submission.
- **Failures:** monitor lag and health. Use another healthy replica or a bounded fallback to the primary, with capacity protection. Never send writes to a replica outside a controlled promotion or failover process.

Test delayed replication, replica unavailability, and primary failover. Confirm that routing preserves transaction consistency and does not turn a regional outage into unlimited load on the primary. See [PostgreSQL replication tradeoffs](https://www.postgresql.org/docs/current/high-availability.html).

## Use OpenTelemetry to locate bottlenecks

Use Reflex's built-in OpenTelemetry trace points and metrics for a compatible release. They remain inactive until the optional `reflex-otel` package is enabled and an SDK/exporter is configured. The reviewed `reflex-otel` source requires Python >=3.11 and `reflex-base >=0.10.0`; it is not a universal add-on for 0.9 deployments. Pin the framework, instrumentor, OpenTelemetry SDK, and exporter together using the version table above, and verify that telemetry reaches the collector.

- **Event latency:** use event-handler spans and `reflex.event.duration` to identify slow handlers and failures. Use `reflex.state.acquire.duration` to distinguish state-acquisition waits from the rest of event execution.
- **Connection and payload load:** correlate `reflex.websocket.connections` and `reflex.websocket.message.size` with instance count and event latency. The instrumentor also provides ASGI request and connection tracing.
- **Browser visibility:** optional browser instrumentation connects frontend interactions to backend event traces.

See the [Reflex OpenTelemetry guide](/docs/api-reference/observability/) for the instrumentation scope and setup.

Database queries, queue publication, and external Taskiq/Celery workers need their own compatible instrumentation or application spans. Propagate trace context through the broker and restore it in the worker so enqueueing, execution, and database work can be correlated. Measure queue wait separately from execution; Reflex’s instrumentor does not automatically supply these external spans.

Identify service, region, deployment version, and database role in telemetry. Follow a slow event or job to determine whether time is spent acquiring state, crossing regions, querying a database, or waiting for worker capacity. Verify a representative end-to-end trace, choose sampling and redaction rules, and avoid sensitive payloads and high-cardinality job IDs in metric labels. See [OpenTelemetry context propagation](https://opentelemetry.io/docs/languages/python/propagation/).

## Validate scale down as well as scale out

Load-test realistic sessions and events in production mode. Record the Reflex version, instance size, process and replica counts, event rate, payload sizes, p50/p95 latency, error rate, and backend, database, and Redis resources. Measure queue delay and job completion separately from interactive latency.

- Add replicas under load and verify latency and errors stay within target. Watch for a downstream database or Redis bottleneck.
- Remove the backend that accepted a long job. Reconnect through another replica and confirm the job continues and its result remains accessible.
- Restart a worker mid-job. Verify the configured recovery behavior and that retries do not duplicate effects. Test worker drain separately from app scale-down.
- Repeat a submission and interrupt enqueueing. Verify idempotency and that accepted work is not silently lost between the job store and broker.
- Fail over the tested regional Redis endpoint or explicitly validated custom Sentinel integration. Measure recovery and exercise active sessions, locks, and reconnects; an unverified adapter is not a supported failover setup.
- Move a user to another region. Verify session-reset behavior, authorization, and retrieval of persistent records and jobs.
- Delay or disable a database replica. Verify freshness-sensitive reads, transaction routing, and bounded primary fallback.
- Follow an event-to-worker-to-database trace and check that missing telemetry does not hide a bottleneck.

Scale backends using resource pressure, event latency, connection load, and errors. Scale workers using queue backlog and oldest-job age. Allow enough time for the chosen drain and recovery policies. There is no universal sessions-per-instance figure.

## Diagnose Redis spikes before resizing

Record the affected region and endpoint, time window, deployment changes, active sessions, and event rate. Compare state and cache services separately. Start with provider metrics and bounded read-only diagnostics using approved operator access:

```text
INFO memory
INFO stats
INFO clients
INFO commandstats
INFO keyspace
SLOWLOG GET 20
```

- **Memory growth:** compare key counts, state sizes, expirations, and evictions. Look for full datasets copied into each session, unbounded histories, and cache entries without useful TTLs.
- **CPU and commands:** correlate event frequency, polling, serialization, and refill bursts. Reduce unnecessary work before adding instances that repeat it.
- **Connections:** check replica and process counts, pool sizes, client reuse, and retry or reconnect bursts. More app instances also mean more connections.
- **Latency and locks:** inspect slow I/O and lock-held time. Move long work to the external worker path; increasing a timeout does not add throughput.

`SLOWLOG` measures server execution, excludes network latency, and can expose private arguments. Redact before sharing. Alert on state eviction and memory pressure. A `noeviction` policy prevents eviction but rejects new writes at the limit.

References: [Redis INFO](https://redis.io/docs/latest/commands/info/), [slow log](https://redis.io/docs/latest/commands/slowlog-get/), and [eviction policies](https://redis.io/docs/latest/develop/reference/eviction/).
