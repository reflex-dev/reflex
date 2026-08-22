---
tags: Organization
description: How Reflex roles and permissions work at the organization and project level, and which role to give each person.
---

# Roles & Permissions

Roles decide what each person can do. Reflex has two levels of roles:

- **Organization roles** apply across the whole organization: creating projects, viewing audit activity, managing billing, and administering the organization.
- **Project roles** apply within a single project: building apps, editing secrets, and approving protected actions. They can be assigned directly to a member or inherited through a team.

The two are assigned separately. Organization roles govern running the organization; project roles govern the work done inside a project.

## Built-in organization roles

Every member has one organization role.

| | **Member** | **Manager** | **Admin** |
| --- | :---: | :---: | :---: |
| Belong to the organization and use the projects they're added to | ✓ | ✓ | ✓ |
| Create new projects | | ✓ | ✓ |
| View the organization audit log | | ✓ | ✓ |
| Add and remove members, change roles | | | ✓ |
| Rename or delete the organization | | | ✓ |
| Manage billing, seats, and credits | | | ✓ |
| Verify domains and configure single sign-on | | | ✓ |
| Connect cloud providers | | | ✓ |
| Automatically an **Admin** of every project | | | ✓ |

- **Member**: has access only to the projects they're added to, with the project role they're given there.
- **Manager**: a member who can also create projects and view organization audit activity. Suited to team leads who don't manage people or billing.
- **Admin**: manages members and billing, and is an admin of every project in the organization.

Manage these roles from **Roles** in the organization sidebar.

### Custom organization roles

When the built-in roles grant too much or too little access, an organization admin can select **New role** and create a custom organization role. Each custom role starts with Member access and can add:

- **Create projects**
- **Manage billing**
- **View audit logs**

For example, a billing manager can manage billing without receiving Admin access to every project. Custom organization roles do not replace Admin for managing organization members or administering every project.

## Project roles

When you add a member or [team](/docs/ai/organization/teams/) to a project, you assign a **project role**. Reflex has three built-in roles, plus [custom roles](/docs/ai/organization/custom-roles/) for cases the built-ins don't cover.

Team assignments have additional role restrictions. See [Adding a team to a project](/docs/ai/organization/project-access/#adding-a-team-to-a-project).

| | **Viewer** | **Editor** | **Admin** |
| --- | :---: | :---: | :---: |
| View the project, its apps, and activity | ✓ | ✓ | ✓ |
| Create apps | | ✓ | ✓ |
| Create threads (Build chats) | | ✓ | ✓ |
| See that secrets exist (view names) | | ✓ | ✓ |
| Reveal secret values | | | ✓ |
| Add and edit secrets | | | ✓ |
| Manage integrations | | | ✓ |
| Approve deployments | | | ✓ |
| Approve project changes | | | ✓ |
| View the project audit log | | | ✓ |
| Rename the project | | | ✓ |
| Delete the project | | | ✓ |
| Add and remove project members, assign roles | | | ✓ |
| Create and edit custom roles | | | ✓ |

- **Viewer**: read-only. Can see the project and its apps but can't edit, deploy, or reveal secret values.
- **Editor**: creates and edits apps, works in Build, and manages app secrets. Can see that project secrets exist but not reveal their values.
- **Admin**: full control of the project, including members, roles, integrations, secrets, approval policies, and deletion.

## Service-account roles

[Service accounts](/docs/ai/organization/service-accounts/) can have the organization Member or Manager role, but never organization Admin. Grant their project access separately from the service account's **Manage** dialog, where they can receive Viewer, Editor, or Admin.

Use the lowest organization and project roles required by the automation.

## How the two levels combine

A person's effective access to a project can combine their organization role, team assignments, and a directly assigned project role:

- **Organization admins** are admins of every project automatically; you don't add them.
- **Managers and members** have no project access until they receive a direct project role or inherit one through a team. See [Managing project access](/docs/ai/organization/project-access/).
- **Team assignments** grant the team's project role to every member of that team.
- Changing someone's project role doesn't change their organization role, and the reverse is also true.

For instructions on reviewing direct and inherited access, see [Viewing effective permissions](/docs/ai/organization/project-access/#viewing-effective-permissions).

## Choosing a role

Guidelines for most teams:

- Give organization **Admin** only to the few people who manage the team and its billing.
- Use **Manager** for team leads who create projects but shouldn't manage people or billing.
- Keep most people as **Member** and control their access project by project.
- Use a custom organization role when someone needs only project creation, billing management, or audit-log access.
- Use [teams](/docs/ai/organization/teams/) when the same group needs consistent access, and reserve direct assignments for exceptions.
- Within a project, make builders **Editors**, reserve **Admin** for project owners, and use **Viewer** for anyone who only needs to view.
- When a built-in project role is close but not exact, create a [custom role](/docs/ai/organization/custom-roles/) rather than over-granting Admin.

## Custom permissions at each level

Organization custom roles add selected organization permissions to Member access. Project custom roles start from a project access level and add selected project permissions. See [Custom project roles](/docs/ai/organization/custom-roles/) for the complete project permission list and setup steps.

## Related

- [Managing project access](/docs/ai/organization/project-access/) — add members to a project and assign roles.
- [Teams](/docs/ai/organization/teams/) — group members and grant inherited project access.
- [Custom project roles](/docs/ai/organization/custom-roles/) — define a project role with specific permissions.
