---
tags: Organization
description: Create organization-owned service accounts for CI, scripts, and integrations.
---

# Service Accounts

A **service account** is a machine identity owned by the organization. Use one for CI, scripts, and integrations instead of running automation as a person.

Because the organization owns the identity, its credentials can keep working when the person who created it leaves. An organization admin can disable the service account without changing anyone's personal account.

```md alert info
# Plan availability
Service accounts are available on supported plans and only to organization admins. If you are not an admin, ask one to create or manage the account. If an admin cannot see the creation control, [contact sales](https://reflex.dev/pricing/) to confirm plan availability.
```

## Create a service account

Open **Service Accounts** in the organization sidebar and select **New service account**. Provide:

- **Name**: a clear identity such as `CI deploy`.
- **What it's used for**: an optional explanation of the workload or owner.
- **Organization role**: Member or Manager. Service accounts cannot be organization admins.

Select **Create**, then select **Manage** on the new account to issue credentials and grant project access.

## Grant project access

In **Manage service account**, choose a project and assign Viewer, Editor, or Admin. Grant access only to the projects and actions the automation needs.

You can review and revoke the account's project roles from the same dialog.

```md alert warning
# A credential carries the account's access, not yours
A token bound to a service account acts as that account, and nothing about the person who issued it is carried along. Automation that worked while you tested it with your own credential will return 403 once it switches to the service account's, unless the account itself holds a role on the projects involved.
```

## Issue a credential

Under **Credentials**:

1. Enter a name, such as `github-actions`.
2. Set the credential lifetime in days.
3. Select **Issue**.
4. Copy the credential immediately. Reflex will not show it again.
5. Send it in the `X-API-Token` header from your CI job, script, or integration.

The credential list shows names, creation dates, and expiration dates. Revoke a credential when it is no longer used or may have been exposed.

```md alert warning
# Service-account credentials are secrets
Store credentials in the workload's secret manager. Do not paste them into source code, Builder prompts or knowledge, logs, screenshots, or documentation.
```

## Disable or delete an account

Disabling a service account revokes all of its credentials and removes its organization access. Its project-role assignments are kept, so you can restore the setup later, but you must issue new credentials after enabling it.

Deleting a service account permanently revokes its credentials and project roles.

## Keep access safe

- Start with the Member organization role unless the automation must create projects.
- Keep the description current so admins know the workload and human owner.
- Rotate credentials and remove unused project access regularly.
- Use [audit logs](/docs/ai/organization/audit-logs/) to review activity.
- Use a personal account for interactive work; do not share personal credentials with automation.

## Related

- [Roles & permissions](/docs/ai/organization/roles-and-permissions/) — choose organization and project roles.
- [Provisioning](/docs/ai/organization/provisioning/) — manage human membership through SCIM.
- [Automated provisioning](/docs/ai/organization/automated-provisioning/) — use a service account to drive directory-based onboarding.
