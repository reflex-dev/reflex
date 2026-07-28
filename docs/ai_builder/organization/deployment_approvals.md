---
tags: Organization
description: Require deployments in a Reflex project to be approved before they go live, and manage the approval queue.
---

# Deployment Approvals

```python exec
import reflex as rx
```

You can require every deployment in a project to be **approved** before it runs. With approvals on, anyone can request a deployment, but it waits for sign-off from someone with permission. This gives the team a checkpoint before changes reach production.

Deployment approvals are configured per project, under **Settings → Deploy approvals**.

## Turning on approvals

On the **Deploy approvals** tab, switch on **Require approval to deploy**. Deployments in the project are then held until approved.

Only **project admins** can change this setting; others can see it but not change it.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/organization/deployment-approvals/approval_policy.webp",
    alt="The Deploy approvals tab with the Require approval to deploy toggle switched on",
    class_name="rounded-md h-auto",
)
```

## Who can approve

Anyone with the **Approve deployments** permission can approve a deployment:

- **Project admins**, who have it by default.
- Anyone with a [custom role](/docs/ai/organization/custom-roles/) that grants **Approve deployments**.

This separates who can request a deployment from who can approve one. For example, editors can deploy to staging while a release manager signs off on production.

## The approval flow

1. A team member starts a deployment as usual.
2. With approvals on, the deployment is held instead of running.
3. It appears under **Pending deployments** on the **Deploy approvals** tab, showing the app, who requested it, and where it would deploy (provider, region, and machine size).
4. An approver selects **Approve** to run it, or **Reject** to stop it.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/organization/deployment-approvals/pending_deployments.webp",
    alt="A pending deployments list showing an app, the requester, deployment details, and Approve and Reject buttons",
    class_name="rounded-md h-auto",
)
```

## Related

- [Custom roles](/docs/ai/organization/custom-roles/) — grant the Approve deployments permission.
- [Audit logs](/docs/ai/organization/audit-logs/) — review approvals and other activity.
