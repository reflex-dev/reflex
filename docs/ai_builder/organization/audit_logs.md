---
tags: Organization
description: Review a record of who did what in your Reflex organization and projects, with search, filtering, and CSV export.
---

# Audit Logs

```python exec
import reflex as rx
```

An **audit log** records the important actions taken in your organization: who did what, and when. It answers questions like *who removed this member?* or *when was this domain verified?* for security reviews, compliance, or day-to-day troubleshooting.

Reflex keeps audit logs at two levels: one for the **organization** and one for each **project**.

## The organization audit log

Open your organization's **Settings → Audit log** to see organization-wide activity, such as member and role changes, domain and single sign-on changes, and other administrative actions.

Each entry shows:

- **Time**: when the action happened.
- **Event**: what happened, with a short summary.
- **Actor**: who did it.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/organization/audit-logs/org_audit_log.webp",
    alt="The organization audit log table showing Time, Event, and Actor columns with a search box and event filter",
    class_name="rounded-md h-auto",
)
```

```md alert info
# Who can view the audit log
The organization audit log is available to organization **admins** and **managers**. Members don't have access.
```

### Finding an entry

The audit log supports:

- **Search** across events, actors, and details.
- **Filter** by event type.
- **Export to CSV** for reporting or to share with your security team.
- **Refresh** for the latest activity.

## Project audit logs

Each project has its own audit log, under the project's **Settings → Audit log**, covering activity within that project. Viewing it requires the **View audit log** permission, which comes with the project **Admin** role and can be added to a [custom role](/docs/ai/organization/custom-roles/).

## Related

- [Roles & permissions](/docs/ai/organization/roles-and-permissions/) — who can see each audit log.
- [Deployment approvals](/docs/ai/organization/deployment-approvals/) — a checkpoint before deployments run.
