---
tags: Organization
description: How Reflex roles and permissions work at the organization and project level, and which role to give each person.
---

# Roles & Permissions

```python exec
import reflex as rx
```

Roles decide what each person can do. Reflex has two levels of roles:

- **Organization roles** apply across the whole organization: managing members, billing, and creating projects.
- **Project roles** apply within a single project: building apps, editing secrets, and approving deployments.

The two are assigned separately. Organization roles govern running the organization; project roles govern the work done inside a project.

## Organization roles

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
- **Manager**: a member who can also create projects. Suited to team leads who don't manage people or billing.
- **Admin**: manages members and billing, and is an admin of every project in the organization.

```md alert info
# Organization admins have access to every project
An organization admin is a project admin everywhere, so you don't add them to projects individually. They appear in a project's member list with an **Organization admin** badge, and their access can't be edited there.
```

## Project roles

When you add a member to a project, you assign a **project role**. Reflex has three built-in roles, plus [custom roles](/docs/ai/organization/custom-roles/) for cases the built-ins don't cover.

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
| View the project audit log | | | ✓ |
| Rename the project | | | ✓ |
| Delete the project | | | ✓ |
| Add and remove project members, assign roles | | | ✓ |
| Create and edit custom roles | | | ✓ |

- **Viewer**: read-only. Can see the project and its apps but can't edit, deploy, or reveal secret values.
- **Editor**: creates and edits apps, works in Build, and manages app secrets. Can see that project secrets exist but not reveal their values.
- **Admin**: full control of the project, including members, roles, integrations, secrets, approvals, and deletion.

## How the two levels combine

A person's access to a project comes from either their organization role or their project role:

- **Organization admins** are admins of every project automatically; you don't add them.
- **Managers and members** have no project access until you add them to a project and assign a role. See [Managing project access](/docs/ai/organization/project-access/).
- Changing someone's project role doesn't change their organization role, and the reverse is also true.

```python eval
rx.image(
    src=rx.color_mode_cond(
        light="https://web.reflex-assets.dev/docs-preview/organization/roles-and-permissions/roles_overview.webp",
        dark="https://web.reflex-assets.dev/docs-preview/organization/roles-and-permissions/roles_overview_dark.webp",
    ),
    alt="Diagram showing organization roles on the left and project roles on the right, with an organization admin inheriting project admin across all projects",
    class_name="rounded-md h-auto",
)
```

## Choosing a role

Guidelines for most teams:

- Give organization **Admin** only to the few people who manage the team and its billing.
- Use **Manager** for team leads who create projects but shouldn't manage people or billing.
- Keep most people as **Member** and control their access project by project.
- Within a project, make builders **Editors**, reserve **Admin** for project owners, and use **Viewer** for anyone who only needs to view.
- When a built-in project role is close but not exact, create a [custom role](/docs/ai/organization/custom-roles/) rather than over-granting Admin.

## Permission reference

The built-in project roles are combinations of individual permissions, which you can also assemble into a [custom role](/docs/ai/organization/custom-roles/). Reflex groups them as:

- **Project:** Create apps, Create threads, Rename project, Delete project.
- **Secrets & integrations:** Manage integrations, View secret names, Reveal secret values, Edit secrets.
- **Deployments:** Approve deployments.
- **Activity:** View audit log.

**Managing members** and **managing roles** can't be granted on their own. Either one amounts to admin control, so both stay with the Admin role. Billing permissions come from your organization role, not from project roles.

## Related

- [Managing project access](/docs/ai/organization/project-access/) — add members to a project and assign roles.
- [Custom roles](/docs/ai/organization/custom-roles/) — define a role with specific permissions.
