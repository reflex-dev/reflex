---
title: Reflex Performance — Rendering, Python Events and Background Work
meta_description: Understand Reflex browser rendering, Python state events, network round trips, and background work. Measure application latency with reproducible workloads.
---

# Performance and execution

Reflex performance depends on the interaction being measured. Browser rendering, a Python event, a database query, and model inference have different costs. Identify the path a user action takes before deciding what to optimize.

## Where work runs

| Work | Where it runs | What to measure |
| --- | --- | --- |
| Python component construction | During app compilation | Build time and generated frontend size |
| React rendering and component-local interaction | Browser | Load time, rendering, and responsiveness |
| Var expressions compiled to JavaScript | Browser | Expression and render cost |
| Ordinary Python state event handler | Backend | Queueing, handler time, and state-update size |
| Database query or provider call | Backend and external service | Network and service duration |
| Background event | Backend task | Work duration and time spent holding the state lock |

Reflex compiles the UI to React. Ordinary Python state handlers execute on the backend, with events and state updates carried over the connection to the browser. It is inaccurate to say that no logic runs in the browser: component-local interactions, compiled expressions, and explicitly added JavaScript can run there. See [how Reflex works](/docs/advanced-onboarding/how-reflex-works/) and [custom code and hooks](/docs/wrapping-react/custom-code-and-hooks/).

## Avoid repeating unrelated work

An ordinary Reflex event invokes its handler; it does not re-execute the entire Python page definition. The state system tracks changed values and sends state updates to the frontend. Keep a database load in the event that needs it, and let a separate UI event update only the selection or display state it owns.

For example, the [model demo](/docs/guides/model-and-media-interfaces/) runs `predict_flower` when the form is submitted. Editing an input does not run inference. In the [linked XY charts](/docs/getting-started/linked-charts-tutorial/), drawing a selection is local to the chart; the completed selection triggers the Python cross-filter. Those boundaries give you control over when backend work runs.

This architecture provides a way to avoid repeated work, rather than a guarantee that every Reflex app outperforms every alternative. An event handler can still call an expensive function, and a computed value can still perform an expensive calculation. Measure those costs with the same inputs and cache policy when comparing implementations.

## Follow one interaction

In the [linked charts example](/docs/getting-started/linked-charts-tutorial/), XY handles drawing the selection locally. A completed selection sends a bounded selection envelope to a Python handler. The handler records selected IDs, computed values produce the linked chart data and rows, and the browser renders the changed views.

That path includes a network round trip and backend work. A chart's local hover effect may follow a different path. Do not use one interaction's timing as a claim about every interaction or every framework.

## Keep data and updates bounded

Load only records the current view needs. Use database aggregation for chart summaries, server-side pagination for large tables, and bounded history for chat and streaming feeds. Backend-only data avoids transmitting it as ordinary frontend state, but backend memory and serialization requirements still matter.

Use [computed vars](/docs/vars/computed-vars/) for derived data, and understand their dependencies before putting expensive queries in them. A UI re-evaluation should not accidentally become an unbounded database workload. Profile the actual handler and query instead of assuming that a slow response means React rendering is slow.

## Use background events deliberately

An async handler can await I/O, but a background event is the mechanism for work that may proceed alongside other state events. In a background event, enter `async with self` to obtain fresh state and make changes. Keep those sections short: copy the inputs you need, release the lock, await the service, and reacquire the lock to apply the result.

The [background events guide](/docs/events/background-events/) and [streaming chat tutorial](/docs/getting-started/chatapp-tutorial/) demonstrate this pattern. A result can arrive after the user changes a filter or cancels a request, so check whether it still belongs to the current operation before applying it.

Async code does not make CPU-heavy Python work non-blocking. Use an appropriate worker or process strategy for expensive computation. Background events also do not provide durable queue semantics such as persisted jobs, restart recovery, or guaranteed retries. Put those requirements in a worker system and store job status explicitly.

## Measure an equivalent workload

Before comparing two implementations, record:

- Framework and dependency versions, production build configuration, hardware, and process count.
- The same dataset, displayed rows, chart traces, mounted controls, and user action.
- Client location, backend location, network latency, and relevant service dependencies.
- Cold and warm runs separately, concurrent sessions, and the number of completed measurements.
- Median and p95 event-to-visible-result latency, payload size, backend memory, and error rate.

Measure first page load separately from a filter change, a streamed answer's first token, total generation time, compilation, and deployment preparation. A comparison of different mounted UI sizes or different network topologies cannot establish a general “fastest framework.”

## Production execution

Use the [self-hosting guide](/docs/hosting/self-hosting/) for the current production command and server configuration. Test long-lived connections, reconnects, state persistence, and concurrent sessions in your intended deployment topology. A local single-user benchmark is not evidence of capacity under production traffic.
