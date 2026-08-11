---
tags: Organization
description: Wire an identity provider and a provisioning system to Reflex end to end, from service account credential through SCIM to project access and namespace placement.
---

# Automated Provisioning

This page is the end-to-end runbook for provisioning Reflex from an external system: an identity provider, a Terraform run, or a script that reconciles desired state on a schedule. Each individual piece has its own page. This one puts them in order and names the places where wiring half of them looks like a broken feature.

The shape of the flow is one idea: **a directory group is a team, and a team holds a role on a project.** The grant is made once per team, not once per person. After that, onboarding somebody is a directory add and nothing else. There is no separate "default permissions" mechanism to configure, because the team grant is it.

```md alert info
# Plan availability
Everything on this page is Enterprise. SCIM, service accounts, and granting a team a project role are all refused on lower plans. If a step returns a plan error, [contact sales](https://reflex.dev/pricing/).
```

## The four steps

| Step | What it establishes | Who can do it | Surface |
| --- | --- | --- | --- |
| Credential | The identity your provisioner acts as | Organization admin | Organization settings, then the token API |
| Identity | Who exists, and which groups they are in | The SCIM token | `/api/scim/v2` |
| Permissions | What a group can do on a project | The service account | `/api/v1/project/{id}/teams` |
| Placement | Which Kubernetes namespace a project's sandboxes run in | Instance admin | `/api/v1/admin/namespace` |

The base URL is your instance origin. On Reflex-hosted that is `https://build.reflex.dev`; on a self-hosted or on-premise install it is whatever origin your users reach the product at. All examples below use `$REFLEX_URL` for it.

Placement applies only to Kubernetes installs, which in practice means on-premise. Skip step 4 on Reflex-hosted.

## Step 1: the credential

### Create the service account

A provisioner should run as a [service account](/docs/ai/organization/service-accounts/), not as a person. A person's credentials die with their membership, and a provisioning system that stops working because somebody changed jobs is an outage nobody predicted.

Creating one is a one-time setup action in the product, not an API call. Open **Service Accounts** in the organization sidebar, select **New service account**, and give it the **Member** organization role. Service accounts cannot be organization admins.

### Grant it project access, and read this before you test anything

In **Manage service account**, grant the account a role on every project it will provision. Grant **Admin**, because managing a project's members is an admin-tier capability and no lesser role carries it.

This is the step that gets skipped, and skipping it fails in a confusing way:

```md alert warning
# The token carries the service account's permissions, not yours
A token bound to a service account authenticates as that account. Nothing about the person who minted it is carried along. If you develop your provisioning scripts with your own token, everything works, because you are an organization admin. The moment you switch the same script to the service account's token, every call returns 403 until the account itself holds a role on those projects.
```

The same applies in reverse: revoking the service account's project role stops the provisioner, whatever the operator who created it can still do by hand.

A service account's project access is managed only from organization settings. The project members API refuses to change it, and returns `a service account's project access is managed from organization settings.` if you try.

### Mint a token bound to it

With the account in place, mint its credential. This call is made by an organization admin, once:

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

The response is the token id, which is itself the credential you send in `X-API-Token`. Store it in the provisioning system's secret manager. Reflex does not show it again.

Notes on the fields:

- **`service_account_id`** is what makes the credential organization-owned from the start. Omit it and you get a personal token that dies with your membership.
- **`access`** is optional. Omitting it produces an unrestricted token. The scope shown above is the minimum for step 3: `project: write` covers reading, granting, and revoking team roles. Narrow `projects` from `"all"` to a list of project ids if the provisioner only manages some of them. Step 2 uses its own SCIM credential and step 4 cannot use this token at all, so neither needs anything added here.
- **`expiration`** is in days. Plan the rotation; there is no renewal, only a new token.

If you already have a working personal token and want to convert it in place rather than reissue, `POST /api/v1/user/token/{token_name}/service-account` with `{"service_account_id": "..."}` re-homes it. The secret value does not change, so a pipeline already using it keeps working, and from then on it is managed under the service account instead of in your own token list.

```md alert warning
# A scoped token cannot mint tokens
A token restricted with `access` is refused by the token endpoints themselves, as is any service-account credential. Token management stays with a human admin on purpose, so a compromised provisioning credential cannot widen itself.
```

## Step 2: identity, over SCIM

[Directory sync](/docs/ai/organization/provisioning/) is what creates people and groups. Open **Provisioning** in the organization sidebar, create a token, and copy the SCIM base URL, which is your instance origin followed by `/api/scim/v2`.

The SCIM token is separate from the service account token. SCIM authenticates with `Authorization: Bearer`, the rest of the API with `X-API-Token`. They are not interchangeable.

The service advertises PATCH and filtering, and does not support bulk operations, sorting, or ETags. `GET /api/scim/v2/ServiceProviderConfig` is unauthenticated and returns the current answer if your identity provider wants to discover it.

### `/Users`

A User is an organization membership.

- **Create** adds the person to the organization with the **Member** organization role. An email that is already a member added by an admin is adopted into directory management rather than rejected, so turning SCIM on for an existing organization does not require emptying it first.
- **A create for a user who is inactive in your directory is refused.** There is no "member but disabled" state to put them in. Activate them in the directory, and the next sync provisions them.
- **Deactivating a user (`active: false`) or deleting them removes the membership outright** and revokes their tokens and sessions. It is not a suspension you can reverse by flipping a flag: re-enabling them in the directory provisions a fresh membership.
- **SCIM only deprovisions what SCIM provisioned.** A break-glass admin added by hand is invisible to the directory and cannot be swept out by it.

### `/Groups`

A Group is a [team](/docs/ai/organization/teams/), and **the group's SCIM resource id is the team id you use in step 3.** Save it when you create the group; you do not have to look it up separately.

- **Only teams the directory created are visible here.** A team an admin made in the product cannot be seen, renamed, or deleted through SCIM, and the reverse also holds: a member an admin adds to a synced team is not echoed in the group's `members` array. That is deliberate. It keeps your identity provider from repeatedly trying, and failing, to remove somebody it did not put there.
- **Emptying a group leaves its project grants alone.** The access goes dormant, because nobody is left to inherit it, and comes back when the group refills. Which role a group holds is an administrator's decision made in the product, and a transient directory blip must not discard it.
- **Deleting a group deletes the team and its grants.** SCIM DELETE is permanent removal, not suspension, and Groups have no `active` attribute to suspend with. It means exactly what deleting the team in the product means.
- A PUT that omits `members` leaves membership alone; an explicit `[]` empties the group. A rename is a `displayName` change.

## Step 3: permissions, granted to the team

This is the step that turns a synced group into access. Three endpoints, all authenticated with the service account's token.

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

Read the current state, which a reconciling provisioner should do rather than blind-writing:

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

### Read `status`, not the HTTP code

Both writes are idempotent, because a provisioner asserts desired state instead of diffing first. Re-granting a role a team already holds succeeds, and revoking from a team that holds nothing answers `not_granted`.

The one thing you cannot infer from a 200 is that the access exists:

```md alert warning
# `pending_approval` is a 200
If the project requires approval for member changes, a grant parks as an approval request instead of applying. The response is `{"status": "pending_approval", ...}` with HTTP 200, and nobody has the access yet. A provisioner that treats 200 as success will record access that does not exist. Branch on `status`.
```

The gate is the project's [approval policy](/docs/ai/organization/deployment-approvals/) for member additions and role changes, and an organization can turn it on by default for every new project, so a project you have never configured can behave this way. The parked request also appears in the `pending` array of the listing, which is why the listing reports it: without it a parked grant reads as absent, your next pass re-asserts it, and every pass re-notifies the approver about a change they are already looking at. Re-asserting an identical request that is still pending is recognized and left alone.

Revocations park the same way, and the team keeps its access until an approver accepts.

### Constraints worth knowing before you hit them

- **A team cannot hold an admin-tier role.** Managing members and roles derives from project admin, and handing that to every current and future member of a directory group is not something a group grant should be able to do. Grant admin per person.
- **Everyone in a team must be an organization member first.** SCIM `/Users` before `/Groups`; most identity providers sequence this correctly on their own.
- **The team and the project must belong to the same organization.**
- Granting a team is collaboration, so it is refused on non-Enterprise plans the same way adding a person is.

## Step 4: placement, for Kubernetes installs

A project's Kubernetes namespace decides which cluster tenant its sandboxes run in. That is an infrastructure decision, so both endpoints below are **instance-admin only** and are not part of the organization admin's surface.

```md alert warning
# A service account can never be an instance admin
The provisioning token from step 1 will not work here, whoever created it. Instance admin is a property of a user account, and a service account can never hold it. Drive these two endpoints with an unrestricted token belonging to an operator who is an instance admin. On-premise, that is your own platform team, so this costs nothing beyond using a different credential for this step. A token restricted with `access` is also refused, even when its owner is an instance admin.
```

### The organization default, for projects that do not exist yet

```bash
curl -X POST "$REFLEX_URL/api/v1/admin/org/orgs/update-default-namespace" \
  -H "X-API-Token: $OPERATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"org_id": "<org-uuid>", "namespace": "platform-sandboxes"}'
```

New projects in the organization inherit this at creation. Inheritance happens once, at that moment; it is not a standing link. Changing the default later leaves existing projects where they are, and a blank namespace clears the default.

### Retargeting a project that already exists

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

`DELETE` on the same path clears the pin, as does a `PUT` with a blank namespace, so a provisioner asserting "no pin" does not have to know which verb this API prefers. `GET` on the path reads it back, and `GET /api/v1/admin/namespace/projects?namespace=&org_id=&limit=&offset=` lists projects for reconciliation.

Three behaviours to build against:

- **`applies_to` is not decoration.** Retargeting moves the *next* sandbox. Sandboxes that are already running keep the namespace they were created in and are still cleaned up there. A live migration of running work is not what this does, and would drop a user's running app mid-session.
- **`status` distinguishes `assigned` and `cleared` from `unchanged`.** A re-assert answers `unchanged` and writes no audit row, so a loop reconciling every few minutes does not fill the audit trail with its own passes.
- **The listing filters on the effective namespace**, which is the override if there is one and the deployment default otherwise. Asking for the default namespace therefore returns projects that carry no override, because their sandboxes really do run there.

## What does not work, and why

These are the wrong turns worth naming, because each one looks plausible.

**`POST /api/v1/project/users/invite` is not the provisioning path.** It is a per-user role write that takes a Reflex user id, works only for somebody who is already an organization member, and has to be repeated for every person on every project. That is precisely the work the team grant exists to remove. Reaching for it means you have rebuilt per-user provisioning on top of a directory that was already telling you the group.

**Organization invitations are not provisioning either.** An invitation is a promise that materializes when the invited person signs in and not before. Nothing you can poll turns it into access. SCIM `/Users` creates the membership directly, which is what a provisioner wants.

**Namespace is not a directory attribute.** There is no SCIM extension for it. Namespace is an infrastructure placement decision that belongs to an instance admin, and a directory that could set it would let whoever administers your identity provider choose which cluster tenant workloads run in.

**Do not sync service accounts through SCIM.** They are organization-owned machine identities, created in organization settings, and they hold a synthetic address under the reserved `.invalid` domain that no identity provider can ever assert. They are not directory users and there is nothing for the directory to manage.

**Do not add people to a synced team in the product.** The membership works, but it is invisible to the identity provider, so your directory is no longer a complete description of who has access. Add them to the group in the directory instead. Manual membership is for teams the directory does not manage.

## A worked example

An identity provider with a `reflex-platform-engineers` group, which should hold `editor` on one project.

**One-time setup, by an organization admin.**

1. Create the service account `idp-provisioner` with the Member organization role.
2. In **Manage service account**, grant it **Admin** on each project it will provision.
3. Mint its token with `POST /api/v1/user/token` and `service_account_id` set, as in step 1. Store it as `$PROVISIONER_TOKEN`.
4. On **Provisioning**, create a SCIM token and copy the base URL.

**One-time setup, in the identity provider.**

In Okta, add the SCIM application, set the base URL to `$REFLEX_URL/api/scim/v2`, set **Authentication Mode** to HTTP Header with the SCIM token as the bearer value, and enable **Create Users**, **Update User Attributes**, and **Deactivate Users**. Turn on **Push Groups** and push `reflex-platform-engineers`. In Microsoft Entra ID, the equivalents are the tenant URL, the secret token, and the default user and group mappings; leave the group mapping enabled.

Push a small group first and confirm it appears under **Teams** before rolling the rest of the directory out.

**Wiring the group to the project.**

Take the group's SCIM id, which is the team id, and grant it:

```bash
curl -X PUT "$REFLEX_URL/api/v1/project/$PROJECT_ID/teams/$TEAM_ID" \
  -H "X-API-Token: $PROVISIONER_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"role": "editor"}'
```

Check `status`. If it says `pending_approval`, the grant is parked and an approver has to accept it before anybody has access.

**Steady state.**

Adding a person to `reflex-platform-engineers` in the directory now gives them editor on that project, with no call against Reflex beyond the ones the identity provider already makes. Removing them takes it away. Nothing per-user runs on your side ever again.

A reconciliation loop, if you run one, should:

- `GET /api/v1/project/{id}/teams` and compare both `grants` and `pending` against desired state.
- Treat `pending_approval` as "not yet", and leave it alone rather than re-asserting.
- Re-assert grants freely otherwise. They are idempotent and write no audit row when nothing moves.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| Every call 403s after switching to the service account token | The service account does not hold a role on the project. Grant it Admin from organization settings. |
| 403 on the team grant with a mention of the plan | Granting a team project access is Enterprise. |
| A grant returns 200 but nobody has access | `status` is `pending_approval`. The project gates member changes, and an approver has to accept. |
| 400: teams cannot hold an admin-tier role | Grant admin per person; a group grant cannot carry it. |
| 400 on a SCIM create saying inactive users are not provisioned | The user is deactivated in your directory. Activate them there and let the next sync provision them. |
| A team an admin created is invisible over SCIM | Correct. Only directory-created teams appear on `/Groups`. |
| A group emptied in the directory still shows a project role | Correct. The grant stays and the access is dormant until the group refills. |
| 403 on the namespace endpoints with a service account token | Instance-admin only, and a service account can never be an instance admin. Use an operator's unrestricted token. |
| A retargeted project's running sandbox is still in the old namespace | Correct. Retargeting applies to the next sandbox, per `applies_to`. |
| 401 on SCIM with a working API token | SCIM uses `Authorization: Bearer`; the rest of the API uses `X-API-Token`. The two credentials are separate. |

## Related

- [Service accounts](/docs/ai/organization/service-accounts/) — create and manage machine identities.
- [Provisioning](/docs/ai/organization/provisioning/) — the SCIM connection itself.
- [Teams](/docs/ai/organization/teams/) — what a team is in the product.
- [Managing project access](/docs/ai/organization/project-access/) — roles, and inspecting effective permissions.
- [Project approvals](/docs/ai/organization/deployment-approvals/) — the gate behind `pending_approval`.
- [Audit logs](/docs/ai/organization/audit-logs/) — the record every step above writes.
