---
title: Build Python Dashboards and Internal Tools with Reflex
meta_description: Combine Python charts, tables, forms, and database queries in a Reflex dashboard. Connect shared filters, record workflows, and background refresh.
---

# Dashboards and internal tools

A Reflex dashboard combines charts, tables, filters, and forms in one web application. Shared state connects controls to the views, and Python event handlers load data and perform actions. The same components can form an internal tool for reviewing and changing records.

## Start with a complete workflow

The [dashboard tutorial](/docs/getting-started/dashboard-tutorial/) provides a runnable table, add-record form, and chart. Adding a record updates both views. The [linked charts tutorial](/docs/getting-started/linked-charts-tutorial/) adds a different interaction: selecting points filters a second chart and a table, with explicit reset and empty-result behavior.

For a file-based analysis app, the [pandas tutorial](/docs/getting-started/pandas-data-app/) adds CSV validation, filtering, aggregation, and summary download. Its preview is bounded independently of the aggregate.

Use the first example for an operational workflow and the second for analytical exploration. Both use shared state, but selecting a chart is not the same operation as changing a stored record.

## Coordinate filters and views

Store filter choices separately from the underlying records. Derive the visible rows and chart summaries from the same filter definition so totals and tables agree. Keep stable record IDs across sorting and pagination; chart point indexes and table positions are view-specific.

| Interaction | State change | Result |
| --- | --- | --- |
| Choose a date range | Update start and end dates | Reload the allowed records and chart aggregates |
| Select chart points | Update selected record IDs | Filter related charts and the table |
| Clear filters | Restore the unfiltered selection | Show the default view and clear selection indicators |
| Change table page | Update page or cursor | Fetch the next bounded set of rows |
| Save an edit | Validate and persist the record | Reload the affected row and summaries |

Document whether a filter runs in the browser, against Python state, or in a database query. These have different payload and latency costs. For large data, aggregate charts and paginate tables at the data source instead of sending every row to the browser.

## Replace sample records with a database

Follow the [database guide](/docs/database/overview/) to connect the app to PostgreSQL or another supported database using SQLAlchemy or SQLModel. Read the authenticated user's permitted records in the backend. Choose when to query: page load, filter submission, explicit refresh, or a bounded background refresh loop.

An edit flow should validate submitted values and authorize the operation, write in a transaction, then update the visible result after a successful save. If the write fails, keep the user's input and show an error. Do not show “Saved” merely because a local state variable changed. For concurrent edits, use a record version or other conflict-detection strategy appropriate to the database.

The tutorial's in-memory records are a learning example. They are not shared durable storage. Two users need a database or service if their workflows must operate on the same records.

## Refresh and streaming data

A database change outside the app does not automatically update a chart. Choose the mechanism that carries the change to the UI:

- **Manual refresh:** a button queries the current data. This is a useful starting point for an operational tool.
- **Polling:** a background event periodically awaits a data source and updates state. Bound the interval and data size; stop the loop when it is no longer needed.
- **Streaming service:** consume the service's messages, aggregate or batch updates, and publish bounded state changes. Plan for reconnection and missed messages.

Use the runnable [background event example](/docs/events/background-events/) to learn start/stop controls and short state-lock sections. Copy the control pattern, then replace its counter with your data query. Await network work outside `async with self`; acquire the lock to read current settings or update results. Re-check whether refresh is still enabled before applying a late result.

## Add a review or approval workflow

Represent status in persistent data, such as draft, submitted, approved, or rejected. A backend action checks the actor's permission and the record's current status before performing the transition. Record who changed it and when. Hiding an Approve button is useful UI behavior, but it is not authorization.

Use an explicit confirmation screen when the user needs to review a proposed change, and make retried operations safe. Database writes and external actions can succeed even if the browser loses the response; design the status check and retry path together.

## Check the finished tool

Test filters with no matches, a failed query, a failed save, unauthorized operations, stale selections, and conflicting edits. Test with two users and a realistic record count. Measure query duration and event-to-render latency separately using [performance and execution](/docs/advanced-onboarding/performance-and-execution/), then use [self-hosting](/docs/hosting/self-hosting/) to deploy.
