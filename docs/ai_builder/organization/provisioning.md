---
tags: Organization
description: Configure SCIM directory sync to provision and remove organization members automatically.
---

# Provisioning

**Directory sync (SCIM)** lets your identity provider create and remove organization members automatically. When someone is disabled in your directory, Reflex ends their organization membership and active sessions as part of deprovisioning.

Use SCIM when your organization manages workforce access centrally and needs account changes in Reflex to follow the same lifecycle.

```md alert info
# Plan availability
Directory provisioning is available on supported plans. If the controls are unavailable, [contact sales](https://reflex.dev/pricing/).
```

## Configure directory sync

Open **Provisioning** in the organization sidebar. The page provides:

- A **SCIM base URL** to copy into your identity provider.
- A **Tokens** section for credentials used by the directory connection.

To create a token:

1. Enter a name that identifies the connection, such as `Okta production`.
2. Select **Create token**.
3. Copy the token immediately. Reflex will not show it again.
4. Add the displayed SCIM base URL and token to your identity provider.
5. Test with a small, approved group before rolling it out to the organization.

The token list shows each token's name, prefix, creation date, and last-used information so admins can identify active connections.

```md alert warning
# Treat provisioning tokens as secrets
Store tokens in your identity provider's secret storage. Never put one in Builder knowledge, source code, screenshots, issue trackers, or documentation.
```

## Revoke a token

Revoke a provisioning token when you rotate credentials, replace a connection, or suspect exposure. The identity provider immediately stops being able to provision or deprovision members with that token. Existing members keep their access.

## Groups and project access

Directory groups synced through SCIM appear as [teams](/docs/ai/organization/teams/) in Reflex. Group membership controls who belongs to the team, while project access remains under your control in Reflex.

Open a project's **Members** page and assign a role to the synced team. Current and future group members inherit that role.

Teams created manually in Reflex are not managed by the identity provider. If the identity provider deletes a synced group, Reflex removes its team and project-role assignments.

A synced team's project role can also be granted through the API, so that onboarding somebody is nothing more than a directory add. See [Automated provisioning](/docs/ai/organization/automated-provisioning/) for that flow end to end, including the credential a provisioning system should run as.

## Related

- [Automated provisioning](/docs/ai/organization/automated-provisioning/) — wire directory sync, permissions, and placement together.
- [Members & seats](/docs/ai/organization/members/) — understand membership and seats.
- [Teams](/docs/ai/organization/teams/) — grant project access to groups.
- [Single sign-on (SSO)](/docs/ai/organization/sso/) — authenticate through your identity provider.
- [Audit logs](/docs/ai/organization/audit-logs/) — review administrative activity.
