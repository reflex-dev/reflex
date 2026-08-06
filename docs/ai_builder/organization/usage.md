---
tags: Organization
description: Review AI credit and Cloud resource usage across projects, members, apps, and time ranges.
---

# Usage

The organization **Usage** pages show AI credit consumption and Cloud resource usage. Use the project and time filters to investigate changes without mixing unrelated workloads.

## AI usage

Open **Usage > AI** in the organization sidebar. The page includes:

- A project filter.
- A date-range filter.
- The current monthly credit balance.
- An AI credit-usage chart, broken down by member.
- A detailed table with the date, reason, and credits for each event.

Select **All projects** for an organization-wide view or choose one project to investigate it. Change the date range to compare a recent period with normal usage.

The project [overview](/docs/ai/overview/project-overview/) also includes a summary chart with **Daily**, **Weekly**, and **Cumulative** views and a link to this detail page.

## Cloud usage

Open **Usage > Cloud** to review resource consumption for deployed apps. Use the project and app filters to narrow the charts.

The page reports:

- **Memory**: RAM usage for app instances over the displayed time period.
- **CPU**: processor usage for app instances over the displayed time period.

An empty chart can mean there was no usage for the selected project, app, or period. Check the filters before assuming the deployment has a problem.

## Investigating unexpected usage

1. Confirm the selected organization, project, and date range.
2. For AI usage, compare the member series and inspect the detailed event table.
3. For Cloud usage, narrow the view to one app and compare CPU with memory.
4. Check [recent project activity](/docs/ai/overview/project-overview/) and [audit logs](/docs/ai/organization/audit-logs/) for related changes.
5. Review [billing](/docs/hosting/billing/) when you need to understand seat and Cloud compute charges.

Usage data is operational and billing-sensitive. Share screenshots only after removing member identities, customer data, and project names that are not approved for publication.
