---
tags: Organization
description: How to provision Reflex from an identity provider or a script, covering the service account credential, SCIM directory sync, team project roles, and namespace placement.
---

# Automated Provisioning

This page is the runbook for provisioning Reflex from an external system such as an identity provider, a Terraform run, or a scheduled reconcile script. Each piece has its own page. This one puts them in order and covers what happens when only part of the flow is wired.

A directory group is a team in Reflex, and a team holds a role on a project. You grant that role once per team. Onboarding a person is then a directory add, and there is no separate default-permissions setting to configure.

```md alert info
# Plan availability
Steps 1 to 3 require the Enterprise plan. Service accounts, SCIM, and granting a team a project role are refused on lower plans; if one returns a plan error, [contact sales](https://reflex.dev/pricing/). Step 4 has no plan gate, only the instance-admin requirement described there. On a self-hosted deployment that does not enforce plans, SCIM is governed by a deployment switch instead of a tier.
```

## The four steps

| Step | What it establishes | Who can do it | Surface |
| --- | --- | --- | --- |
| Credential | The identity your provisioner acts as | Organization admin | Organization settings, then the token API |
| Identity | Who exists, and which groups they are in | The SCIM token | `/api/scim/v2` |
| Permissions | What a group can do on a project | The service account | `/api/v1/project/{id}/teams` |
| Placement | Which Kubernetes namespace a project's sandboxes run in | Instance admin | `/api/v1/admin/namespace` |

The base URL is your instance origin. On Reflex-hosted that is `https://build.reflex.dev`. On a self-hosted or on-premise install it is the origin your users reach the product at. The examples below use `$REFLEX_URL`.

Placement applies only to Kubernetes installs, so skip step 4 on Reflex-hosted.

## Step 1: the service account credential

### Create the service account

Run the provisioner as a [service account](/docs/ai/organization/service-accounts/) rather than as a person. A personal token stops working when its owner leaves the organization, which takes the provisioning system down with it.

There is no API for creating one. Open **Service Accounts** in the organization sidebar, select **New service account**, and give it the **Member** organization role. Service accounts cannot be organization admins.

### Grant it project access

In **Manage service account**, grant the account a role on every project it will provision. The role must be **Admin**, because managing a project's members is an admin-tier capability that no lesser role carries.

```md alert warning
# The token carries the service account's permissions, not yours
A token bound to a service account authenticates as that account. Nothing about the person who minted it is carried along. Scripts developed with your own token work because you are an organization admin; the same scripts return 403 on every call once they use the service account's token, until the account itself holds a role on those projects.
```

Revoking the account's project role stops the provisioner, regardless of what the operator who created it can still do by hand.

A service account's project access is granted only from organization settings. The project members API cannot do it. Because a service account holds no organization membership row, that call is refused with `user is not a member of this project's organization.` The message names membership, but the fix is to grant the role in organization settings.

### Mint its token

An organization admin makes this call once.

```bash
curl -X POST "$REFLEX_URL/api/v1/user/token" \
  -H "X-API-Token: $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "idp-provisioner",
    "expiration": 365,
    "service_account_id": "<service-account-uuid>",
    "access": {
      "permissions": {"project": "write"},
      "projects": "all"
    }
  }'
```

The response is the token id, and that id is the credential you send in `X-API-Token`. Store it in the provisioning system's secret manager. Reflex does not show it again.

- `service_account_id` makes the credential organization-owned from the start. Without it you get a personal token tied to your own membership.
- `access` is optional, and omitting it produces an unrestricted token. The scope above is the minimum for step 3, where `project: write` covers reading, granting, and revoking team roles. Narrow `projects` from `"all"` to a list of project ids if the provisioner manages only some of them. Step 2 uses its own SCIM credential and step 4 cannot use this token, so neither needs anything added here.
- `expiration` is in days. There is no renewal, so plan a rotation.

To convert a personal token you already use instead of issuing a new one, `POST /api/v1/user/token/{token_name}/service-account` with `{"service_account_id": "..."}` re-homes it. The secret value does not change, so a pipeline using it keeps working, and the token moves from your own token list to the service account's.

```md alert warning
# A scoped token cannot mint tokens
A token restricted with `access` is refused by the token endpoints, as is any service-account credential. Token management stays with a human admin, so a compromised provisioning credential cannot widen itself.
```

## Step 2: identity over SCIM

[Directory sync](/docs/ai/organization/provisioning/) creates the people and the groups. Open **Provisioning** in the organization sidebar, create a token, and copy the SCIM base URL, which is your instance origin followed by `/api/scim/v2`.

The SCIM token is separate from the service account token. SCIM authenticates with `Authorization: Bearer`, the rest of the API with `X-API-Token`.

The service supports PATCH and filtering. It does not support bulk operations, sorting, or ETags. `GET /api/scim/v2/ServiceProviderConfig` is unauthenticated, so an identity provider that discovers capabilities can read it.

### `/Users`

A User is an organization membership.

- A create adds the person to the organization with the **Member** organization role. An email an admin already added is adopted into directory management rather than rejected, so enabling SCIM on an existing organization does not require emptying it first.
- A create for a user who is inactive in your directory is refused. There is no member-but-disabled state. Activate the user in the directory and the next sync provisions them.
- Deactivating a user (`active: false`) or deleting them removes the membership and revokes their tokens and their session in that organization. Re-enabling them in the directory provisions a fresh membership rather than restoring the old one.
- SCIM deprovisions only the memberships SCIM created. A break-glass admin added by hand is invisible to the directory.

### `/Groups`

A Group is a [team](/docs/ai/organization/teams/). The group's SCIM resource id is the team id used in step 3, and it comes back in the create response, so there is nothing extra to look up.

- Only teams the directory created are visible. A team an admin made in the product cannot be seen, renamed, or deleted through SCIM, and a member an admin adds to a synced team is not echoed in the group's `members` array, so your identity provider never tries to remove somebody it did not add.
- Emptying a group leaves its project grants in place. The access is dormant while the group is empty and returns when the group refills, so a directory blip does not discard the role an admin gave the group.
- Deleting a group deletes the team and the project grants it held. Groups have no `active` attribute, so DELETE is the only removal and it is permanent.
- A PUT that omits `members` leaves membership alone. An explicit `[]` empties the group. A rename is a `displayName` change.

## Step 3: team roles on projects

Three team endpoints, plus the project's role listing, all authenticated with the service account's token.

Role names are per-project. List them first:

```bash
curl "$REFLEX_URL/api/v1/project/$PROJECT_ID/roles" \
  -H "X-API-Token: $PROVISIONER_TOKEN"
```

Grant the role. The team id is the SCIM group id from step 2:

```bash
curl -X PUT "$REFLEX_URL/api/v1/project/$PROJECT_ID/teams/$TEAM_ID" \
  -H "X-API-Token: $PROVISIONER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "editor"}'
```

```json
{"status": "granted", "team_id": "...", "role": "editor"}
```

Read the current grants, which a reconciling provisioner should do before writing:

```bash
curl "$REFLEX_URL/api/v1/project/$PROJECT_ID/teams" \
  -H "X-API-Token: $PROVISIONER_TOKEN"
```

```json
{
  "grants": [
    {"team_id": "...", "team_name": "Platform", "role": "editor",
     "base_tier": "editor", "permissions": [], "member_count": 12}
  ],
  "pending": []
}
```

`DELETE` on the same path revokes.

### Idempotency and the `status` field

Both writes are idempotent. Re-granting a role a team already holds succeeds, and revoking from a team that holds nothing answers `not_granted`.

```md alert warning
# `pending_approval` is a 200
If the project requires approval for member changes, a grant parks as an approval request instead of applying. The response is `{"status": "pending_approval", ...}` with HTTP 200, and nobody has the access yet. Branch on `status`, or you will record access that does not exist.
```

The gate is the project's [approval policy](/docs/ai/organization/deployment-approvals/) for member additions and role changes, and an organization can enable it by default for every new project, so a project you never configured can behave this way.

A parked grant is absent from `grants` and present in `pending`. Read both before deciding what access exists.

Re-asserting is safe. While the gate is on, asking again for the role a pending request already describes answers `pending_approval` without disturbing that request or notifying the approver a second time. Asking for a different role replaces the pending request and notifies again, which is correct, because the desired state changed. If the gate has since been turned off, the next call applies the grant and clears the stale request, so a loop recovers on its own.

Revocations park the same way, and the team keeps its access until an approver accepts.

### Constraints

- A team cannot hold an admin-tier role. Grant admin per person.
- Everyone in a team must be an organization member first. Sync `/Users` before `/Groups`; most identity providers already do.
- The team and the project must belong to the same organization.
- Granting a team a project role requires the Enterprise plan, as adding a person does.

## Step 4: namespace placement

A project's Kubernetes namespace decides which cluster tenant its sandboxes run in. Both endpoints below are instance-admin only, not part of the organization admin's surface.

```md alert warning
# A service account can never be an instance admin
The provisioning token from step 1 does not work here. Instance admin is a property of a user account and a service account can never hold it, so these two endpoints need a token belonging to an operator who is an instance admin. On-premise, that is your own platform team.
```

A token carrying an `access` map reaches these endpoints only if it grants account-level write, which is already most of an instance admin's power, so narrower scoping is refused here even when the owner is an instance admin. Treat this credential as privileged and keep it out of the provisioning system.

### Set the organization default

```bash
curl -X POST "$REFLEX_URL/api/v1/admin/org/orgs/update-default-namespace" \
  -H "X-API-Token: $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"org_id": "<org-uuid>", "namespace": "platform-sandboxes"}'
```

New projects inherit this value when they are created. Inheritance happens once, so changing the default later leaves existing projects where they are. A blank namespace clears the default.

### Retarget an existing project

```bash
curl -X PUT "$REFLEX_URL/api/v1/admin/namespace/projects/$PROJECT_ID" \
  -H "X-API-Token: $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"namespace": "research-sandboxes"}'
```

```json
{
  "project_id": "...", "project_name": "Research", "org_id": "...",
  "namespace": "research-sandboxes",
  "effective_namespace": "research-sandboxes",
  "status": "assigned",
  "previous_namespace": "platform-sandboxes",
  "applies_to": "sandboxes_created_after_this_change"
}
```

`DELETE` on the same path clears the pin, and so does a `PUT` with a blank namespace. `GET` on the path reads it back, and `GET /api/v1/admin/namespace/projects?namespace=&org_id=&limit=&offset=` lists projects for reconciliation.

Three parts of the response affect how a reconciler should read it:

- `applies_to` reports that the change is not retroactive. Retargeting moves the next sandbox. Sandboxes already running keep the namespace they were created in and are still cleaned up there. Migrating running work is out of scope, since a mid-session move would drop the user's app.
- `status` is `assigned`, `cleared`, or `unchanged`. A re-assert answers `unchanged` and writes no audit row, so a reconcile loop does not fill the audit trail with its own passes.
- The listing filters on the effective namespace, which is the override if there is one and the deployment default otherwise. Asking for the default namespace also returns projects that carry no override, because their sandboxes run there.

## What does not work

`POST /api/v1/project/users/invite` writes one user's role at a time. It takes a Reflex user id, works only for somebody who is already an organization member, and has to be repeated for every person on every project, which is the work a team grant removes.

Organization invitations wait for a sign-in. An invitation becomes a membership when the invited person signs in, and nothing a provisioner can poll turns it into access. SCIM `/Users` creates the membership directly.

Namespace has no SCIM attribute. There is no extension for it, and a directory that could set it would let whoever administers your identity provider choose which cluster tenant workloads run in.

Service accounts stay out of the directory. They are created in organization settings and hold a synthetic address under the reserved `.invalid` domain that no identity provider can assert, so there is nothing for the directory to manage.

Adding people to a synced team in the product hides them from the identity provider. The membership works, but your directory stops being a complete description of who has access. Add them to the group in the directory instead.

## A worked example

A directory group called `reflex-platform-engineers` should hold `editor` on one project.

### One-time setup in Reflex

1. Create the service account `idp-provisioner` with the Member organization role.
2. In **Manage service account**, grant it **Admin** on each project it will provision.
3. Mint its token with `POST /api/v1/user/token` and `service_account_id` set, as in step 1. Store it as `$PROVISIONER_TOKEN`.
4. On **Provisioning**, create a SCIM token and copy the base URL.

### One-time setup in the identity provider

In Okta, add the SCIM application, set the base URL to `$REFLEX_URL/api/scim/v2`, set **Authentication Mode** to HTTP Header with the SCIM token as the bearer value, and enable **Create Users**, **Update User Attributes**, and **Deactivate Users**. Turn on **Push Groups** and push `reflex-platform-engineers`. In Microsoft Entra ID, the equivalents are the tenant URL, the secret token, and the default user and group mappings; leave the group mapping enabled.

Push a small group first and confirm it appears under **Teams** before rolling out the rest of the directory.

### Wire the group to the project

Take the group's SCIM id, which is the team id, and grant it:

```bash
curl -X PUT "$REFLEX_URL/api/v1/project/$PROJECT_ID/teams/$TEAM_ID" \
  -H "X-API-Token: $PROVISIONER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "editor"}'
```

Check `status`. If it says `pending_approval`, the grant is parked and an approver has to accept it before anybody has access.

### Steady state

Adding a person to `reflex-platform-engineers` in the directory now gives them editor on that project, with no call against Reflex beyond the ones the identity provider already makes. Removing them from the group takes it away.

A reconciliation loop, if you run one, should:

- `GET /api/v1/project/{id}/teams` and compare both `grants` and `pending` against desired state.
- Treat `pending_approval` as access that does not exist yet, and do not record it as granted.
- Re-assert grants freely. They are idempotent, a pending request for the same role is left undisturbed, and nothing reaches the audit trail when nothing moves.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Every call 403s after switching to the service account token | The service account does not hold a role on the project. Grant it Admin from organization settings. |
| 400 `user is not a member of this project's organization.` when adding the service account to a project | A service account holds no organization membership row. Grant its project access from organization settings instead. |
| 403 on the team grant with a mention of the plan | Granting a team project access requires the Enterprise plan. |
| A grant returns 200 but nobody has access | `status` is `pending_approval`. The project gates member changes, and an approver has to accept. |
| 400: teams cannot hold an admin-tier role | Grant admin per person; a group grant cannot carry it. |
| 400 on a SCIM create saying inactive users are not provisioned | The user is deactivated in your directory. Activate them there and let the next sync provision them. |
| A team an admin created is invisible over SCIM | `/Groups` lists only teams the directory created. Manage that team in the product. |
| A group emptied in the directory still shows a project role | Emptying a group does not revoke its grant. The access is dormant until the group refills. |
| 403 on the namespace endpoints with a service account token | These endpoints are instance-admin only, and a service account can never be an instance admin. Use an operator's unrestricted token. |
| A retargeted project's running sandbox is still in the old namespace | Retargeting applies to sandboxes created after the change, as `applies_to` reports. |
| 401 on SCIM with a working API token | SCIM uses `Authorization: Bearer`; the rest of the API uses `X-API-Token`. The two credentials are separate. |

## Related

- [Service accounts](/docs/ai/organization/service-accounts/) — create and manage machine identities.
- [Provisioning](/docs/ai/organization/provisioning/) — the SCIM connection itself.
- [Teams](/docs/ai/organization/teams/) — what a team is in the product.
- [Managing project access](/docs/ai/organization/project-access/) — roles, and inspecting effective permissions.
- [Project approvals](/docs/ai/organization/deployment-approvals/) — the gate behind `pending_approval`.
- [Audit logs](/docs/ai/organization/audit-logs/) — the record every step above writes.
