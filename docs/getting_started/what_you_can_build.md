---
title: What Can You Build with Reflex?
meta_description: Explore Python examples for dashboards, linked charts, streaming AI assistants, model interfaces, and internal tools built with Reflex.
---

# What you can build with Reflex

Reflex lets you build web applications with a Python-defined interface and Python backend logic. Combine forms, tables, interactive charts, and streamed model responses in one application. Start with a working example, then add the data access, authentication, and deployment configuration your application needs.

You can use Reflex for the data-app, dashboard, chat, model-demo, and internal-tool workflows commonly associated with Streamlit, Dash, Gradio, and NiceGUI. These patterns can share a custom, multi-page interface: a conversation can sit beside a chart, a model prediction can populate an editable form, and a dashboard selection can update a table. The examples below demonstrate the individual building blocks; the [framework comparisons](https://reflex.dev/compare/frameworks/) explain the different development models.

## Choose a starting point

| I want to build… | Start here | What the example demonstrates |
| --- | --- | --- |
| An analytics dashboard | [Dashboard tutorial](/docs/getting-started/dashboard-tutorial/) | A table, an input form, and a chart that update from the same records |
| Linked charts and cross-filtering | [Linked charts tutorial](/docs/getting-started/linked-charts-tutorial/) | Selecting points filters a second chart and a table |
| A custom AI chatbot | [Streaming chat tutorial](/docs/getting-started/chatapp-tutorial/) | Provider SDK calls, streamed responses, conversation state, and error handling |
| A web interface for a Python function | [Function-to-app tutorial](/docs/getting-started/python-function-to-app/) | Validated form input, a Python calculation, and a result view |
| An internal business tool | [Dashboards and internal tools](/docs/guides/dashboards-and-internal-tools/) | Record workflows, data loading, shared filters, and background refresh |
| An AI or document assistant | [AI applications](/docs/guides/ai-applications/) | Extending chat with retrieval, sources, persistence, and tool progress |
| A model or media interface | [Model and media interfaces](/docs/guides/model-and-media-interfaces/) | A local prediction function, custom controls, and media delivery choices |

These are application patterns, not separate Reflex products. The framework's [components](/docs/library/), [state](/docs/state/overview/), and [events](/docs/events/events-overview/) are the building blocks in each case. Reflex Build is a separate way to generate applications; you can write these framework examples directly in Python.

## Customize the whole interface

Reflex gives you control over the layout and behavior surrounding a chart, conversation, or model. You compose the interface from components and connect them to your application's state and events.

| What you want to change | How to do it | Working reference |
| --- | --- | --- |
| Page structure and navigation | Compose grids, sidebars, and multiple routes | [Layout recipes](/docs/recipes/layout/sidebar/) and [pages](/docs/pages/overview/) |
| Branding, spacing, and mobile layout | Set CSS properties, themes, responsive values, or custom stylesheets | [Styling](/docs/styling/overview/) and [responsive layouts](/docs/styling/responsive/) |
| A model's input and result experience | Arrange your own controls and result components around the prediction function | [Flower classifier demo](/docs/guides/model-and-media-interfaces/#a-local-prediction-demo) |
| Interaction across components | Store shared selections and derive the related views | [Linked XY charts](/docs/getting-started/linked-charts-tutorial/) |
| A specialized React component | Define a wrapper exposing the props and events your app needs | [Wrapping React](/docs/wrapping-react/overview/) |

You can change the model demo's form, result panel, and surrounding page without changing `predict_flower`. Likewise, a streaming chat's provider call can stay the same while you change its message layout or add a source panel. Existing supported components can be composed directly; integrating a new React library requires wrapper code.

## Understand the performance model

Reflex compiles Python component definitions into a React frontend. An ordinary interaction calls the associated Python event handler and synchronizes changed state; it does not rerun the whole Python page definition. Browser-local interactions and compiled Var expressions can run without a Python event. This lets you keep expensive data loading separate from controls that only change the view.

See [performance and execution](/docs/advanced-onboarding/performance-and-execution/) for the event path and measurement method. To establish which implementation is faster for your app, compare the same interaction, data, and deployment conditions; frontend architecture alone is not a benchmark.

## Connect data and services

An event handler can call a Python library, query a database, or await an external service. Follow the [database guide](/docs/database/overview/) for database access and the [background events guide](/docs/events/background-events/) for asynchronous work that can run alongside other events. Keep service credentials on the backend, and put access checks in the operation that reads or changes the data.

For an existing React component that is not exposed by the component library, use the [React wrapping guide](/docs/wrapping-react/overview/). Wrapping requires declaring the props and events your application uses; it is distinct from using an already supported component.

## Grow the example into an application

The tutorials deliberately start small. Before deploying a shared application, decide where records and generated files persist, how users authenticate, which operations each user may perform, and how failures are reported. In-memory session state is not a database or an authorization system.

Read [performance and execution](/docs/advanced-onboarding/performance-and-execution/) to understand browser work, Python events, network round trips, and background tasks. Use the [self-hosting guide](/docs/hosting/self-hosting/) for deployment instructions.

## Coming from another Python framework?

Explore the [framework comparisons](https://reflex.dev/compare/frameworks/) to find your current framework and understand how its interface, state, and backend fit into Reflex. Then choose a working tutorial above to implement your first workflow.
