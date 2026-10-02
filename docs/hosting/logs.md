# Logs

Use the hosted app's **Logs** page to inspect runtime output.

## Runtime Logs in the Dashboard

Open **Deployments**, select the app, and then select **Logs**. The current log viewer provides:

- Full-text search.
- Oldest-first or newest-first ordering.
- UTC and local timezone display.
- Time-range selection.
- Region filtering.
- Refresh while the app is running.

Start with the smallest relevant time range and region, then broaden the filters when the expected event is missing.

## Runtime Logs from the CLI

```text
reflex cloud apps logs [OPTIONS] [APP_ID]
```

Use the CLI for local debugging, automation, or terminal-based inspection. It retrieves logs in batches and prompts before loading the next page.

## Deployment History and Build Output

Open **History** to view every deployment, then select a deployment ID to open its details and **Build logs** section.

List the same history from the CLI:

```text
reflex cloud apps history [OPTIONS] [APP_ID]
```

Retrieve build output for one deployment:

```text
reflex cloud apps build-logs <DEPLOYMENT_ID>
```

See [App Management](/docs/hosting/app-management/#history-and-rollback) for deployment details, notes, and rollback.
