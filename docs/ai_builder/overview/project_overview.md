---
tags: AI Builder
description: Use the Reflex project overview to monitor apps, deployments, AI usage, recent activity, and project resources.
---

# Project Overview

```python exec
import reflex as rx
```

The **project overview** is the starting point for a project in Reflex. It brings together the project's apps, deployments, AI usage, recent activity, and useful resources so you can understand its current state before opening an app or changing a setting.

Open a project from the organization home to see its overview.

## Project summary

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/project_overview.webp",
    alt="Project overview with app, deployment, credit, and usage summaries",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

The top of the page shows the project name, tier, member count, and remaining AI credits. Use it to confirm that you are working in the right project and to check its credit balance.

Project access is managed separately from organization membership. See [Managing project access](/docs/ai/organization/project-access/) for details.

## Getting started

New projects include a short checklist: create an app, deploy an app, and connect an integration. Each item links to the page where you can complete it. The checklist disappears after all three steps are complete.

## Apps

The **Apps** section shows the project's apps and provides a shortcut to create or open one. Select **View all apps** when you need the complete list.

An app contains the source, Builder conversations, previews, tests, and deployments for one application. See [What is Reflex Build?](/docs/ai/overview/what-is-reflex-build/) for the Builder workflow.

## Deployments

The **Deployments** section summarizes recent deployments and their current status. Select **View all deployments** to inspect the complete deployment list or open a deployment's overview, logs, history, domains, and settings.

See [Deploy an app](/docs/ai/app-lifecycle/deploy-app/) for the deployment workflow.

## Usage

The **Usage** chart summarizes AI credit consumption by member over the last year. Switch between **Daily**, **Weekly**, and **Cumulative** views to understand how usage changes over time.

Select **View more** for the detailed AI usage page, where you can filter by project and date range and inspect individual credit events. Organization admins can also review Cloud usage. See [Usage](/docs/ai/organization/usage/).

## Recent activity

**Recent Activity** shows the latest project events. Use it for a quick check of changes made by members, then select **View more** when you need the searchable project audit log.

See [Audit logs](/docs/ai/organization/audit-logs/) for project and organization audit history.

## Resources

The **Resources** section links to the Reflex documentation, hosting information, and on-premises deployment guidance. These links are useful when moving from an app prototype to a production deployment.
