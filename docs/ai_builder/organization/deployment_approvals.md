---
tags: Organization
description: Require approval before deployments or project membership changes, and manage the pending queues.
---

# Project Approvals

Approvals add a checkpoint before sensitive project actions take effect. A project can require approval for deployments, member additions and role changes, or member removals.

Configure these policies from **Approvals** in the project sidebar.

## Approval policies

The page provides three independent policies:

- **Require approval to deploy**: holds deployments until someone with **Approve deployments** approves them.
- **Require approval to add members or change roles**: holds member additions, team access grants, and role changes until someone with **Approve project changes** approves them.
- **Require approval to remove members**: holds member removals until someone with **Approve project changes** approves them.

Only project admins can change these policies. Turn on only the checkpoints your project needs.

## Approval permissions

Project admins have both approval permissions by default. A [custom project role](/docs/ai/organization/custom-roles/) can grant either permission without granting full Admin access:

- **Approve deployments** covers deployment requests.
- **Approve project changes** covers member additions, removals, team access grants, and role changes.

This lets a release manager approve deployments while another trusted reviewer handles access changes.

## Pending requests

When an enabled policy applies, the action waits in its matching section:

- **Pending deployments**
- **Pending member additions and role changes**
- **Pending member removals**

An authorized reviewer can approve the request so it continues, or reject it so the requested change does not take effect.

## Related

- [Custom project roles](/docs/ai/organization/custom-roles/) — grant approval permissions without full Admin access.
- [Managing project access](/docs/ai/organization/project-access/) — add members and teams to a project.
- [Audit logs](/docs/ai/organization/audit-logs/) — review approvals and other activity.
