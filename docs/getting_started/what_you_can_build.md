---
title: What Can You Build with Reflex?
meta_description: Explore Python examples for dashboards, linked charts, streaming AI assistants, model interfaces, and internal tools built with Reflex.
---

# What you can build with Reflex

Reflex lets you build web applications with a Python-defined interface and Python backend logic. Combine forms, tables, interactive charts, and streamed model responses in one application. Start with a working example, then add the data access, authentication, and deployment configuration your application needs.

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

## Connect data and services

An event handler can call a Python library, query a database, or await an external service. Follow the [database guide](/docs/database/overview/) for database access and the [background events guide](/docs/events/background-events/) for asynchronous work that can run alongside other events. Keep service credentials on the backend, and put access checks in the operation that reads or changes the data.

For an existing React component that is not exposed by the component library, use the [React wrapping guide](/docs/wrapping-react/overview/). Wrapping requires declaring the props and events your application uses; it is distinct from using an already supported component.

## Grow the example into an application

The tutorials deliberately start small. Before deploying a shared application, decide where records and generated files persist, how users authenticate, which operations each user may perform, and how failures are reported. In-memory session state is not a database or an authorization system.

Read [performance and execution](/docs/advanced-onboarding/performance-and-execution/) to understand browser work, Python events, network round trips, and background tasks. Use the [self-hosting guide](/docs/hosting/self-hosting/) for deployment instructions.

## Coming from another Python framework?

Use [moving an existing Python app](/docs/guides/moving-an-existing-app/) to map a Streamlit, Dash, Gradio, or NiceGUI workflow into Reflex. Start with one complete workflow and preserve its observable behavior before expanding the port.
