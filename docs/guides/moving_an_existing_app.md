---
title: Move an Existing Python App to Reflex
meta_description: Plan a Streamlit, Dash, Gradio, or NiceGUI workflow migration to Reflex. Map inputs, state, events, and outputs before porting the rest of your app.
---

# Move an existing Python app to Reflex

Begin a migration with one complete user workflow. Keep independently testable Python calculations and service code where practical, then express the interface with Reflex components, state, and events. UI code and framework-specific execution behavior need deliberate translation.

This guide maps the work to runnable Reflex examples. It is not an automatic converter or a claim that replacing a UI preserves every source framework's runtime feature.

## Describe the behavior before translating code

Choose a workflow such as filtering a chart and table, submitting a model request, or editing a record. Record its inputs, state, outputs, failure behavior, and persistence requirements. Run the original application and keep those observations as acceptance criteria for the port.

| Existing application concept | Reflex implementation | Working starting point |
| --- | --- | --- |
| A Python calculation behind a form | A form submission calls an event handler, which calls the function | [Function-to-app tutorial](/docs/getting-started/python-function-to-app/) |
| Filters shared by charts and a table | Store selection in state and derive all views from it | [Linked charts tutorial](/docs/getting-started/linked-charts-tutorial/) |
| An editable record workflow | Validate and persist in a handler, then update visible state | [Dashboard tutorial](/docs/getting-started/dashboard-tutorial/) and [internal tools guide](/docs/guides/dashboards-and-internal-tools/) |
| A streamed model response | Consume the provider stream and publish incremental state updates | [Chat tutorial](/docs/getting-started/chatapp-tutorial/) |
| A local prediction function | Keep inference separate and build custom inputs and results | [Model interface](/docs/guides/model-and-media-interfaces/) |

## Coming from Streamlit

Inventory session values, data-loading and caching choices, form submission behavior, and work triggered by widget changes. Decide which values become Reflex state and which remain backend data or service results. Place computation in the relevant handler or derived value rather than copying a whole script into each event.

Port a filter, chart, and table together so you can verify that they stay consistent. Preserve loading, empty-result, and error behavior. Use the existing [Streamlit migration page](https://reflex.dev/migration/streamlit/) and [comparison](https://reflex.dev/compare/streamlit/) for additional context.

## Coming from Dash

Map the dependencies between inputs, callbacks, and outputs before choosing state ownership. Reflex can link charts: the [linked charts example](/docs/getting-started/linked-charts-tutorial/) demonstrates selection driving a second chart and a table. The migration question is how to express your existing relationships and operating requirements.

Check the actual chart event payload, especially if the source application uses Plotly `customdata` or multiple traces. The linked tutorial uses XY selection envelopes, not Plotly callback payloads; translate the source event contract and map canonical row positions to stable IDs. Verify deselection, sorting, URL-based filters, and large-data behavior in the port. See the [Dash comparison](https://reflex.dev/compare/dash/) for evaluation context.

## Coming from Gradio

Separate the inference function from its UI, then define the input controls, progress, errors, and output components in Reflex. The model function or remote inference service may remain reusable; the interface and surrounding workflow are rewritten.

List any queueing, generated API, sharing, streaming, cancellation, or media-capture behavior your existing app relies on. Give each an explicit implementation and test in the new app. A UI replacement alone does not reproduce those facilities. Use the [model interface guide](/docs/guides/model-and-media-interfaces/) and [Gradio comparison](https://reflex.dev/compare/gradio/).

## Coming from NiceGUI

Port a complete form-and-table workflow first. Separate validation and service calls from component creation, then map user actions and state changes into Reflex handlers and vars. Verify asynchronous work, layout, table selection, and styling against the original behavior.

If your source application depends on a desktop window, native integration, or a particular third-party component, evaluate that requirement separately from a browser-based port. Use [React component wrapping](/docs/wrapping-react/overview/) for the extension path and the [internal tools guide](/docs/guides/dashboards-and-internal-tools/) for the application workflow.

## Validate before expanding the port

Run the same inputs through both applications and compare visible results. Include empty and invalid input, a failed backend operation, repeated submission, two users, and a refresh or reconnect. Verify persistence and authorization separately from session-state behavior.

Measure production builds with equivalent data and UI using [performance and execution](/docs/advanced-onboarding/performance-and-execution/). Complete one workflow before porting the rest of the application; keep the original available until the replacement meets its acceptance criteria.
