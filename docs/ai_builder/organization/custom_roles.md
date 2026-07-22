---
tags: Organization
description: Create custom project roles in Reflex, built on a base access level with the specific permissions your team needs.
---

# Custom Roles

```python exec
import reflex as rx
```

The built-in project roles (Viewer, Editor, and Admin) cover most cases, but sometimes you need something in between: a contractor who can build and deploy apps but nothing else, or a reviewer who can approve deployments without editing. A **custom role** defines that combination.

Custom roles are created per project, under **Settings → Roles**, by anyone with the project **Admin** role.

```md alert info
# Custom roles are for teams
Custom roles matter once you have teammates on a project. Inviting teammates is an Enterprise feature; see [Managing project access](/docs/ai/organization/project-access/).
```

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/organization/custom-roles/roles_list.webp",
    alt="The project Roles tab listing built-in roles and a custom role, with a New role button",
    class_name="rounded-md h-auto",
)
```

## How a custom role is built

A custom role has two parts:

1. **Base access level**: Viewer, Editor, or Admin. The role includes everything that level can do.
2. **Additional permissions**: individual abilities you add on top of the base level.

Pick the closest built-in level, then add the permissions you need.

## Creating a role

Select **New role** and fill in:

- **Role name**: a label your team will recognize, such as *Support lead* or *Release manager*.
- **Base access**: the starting level (Viewer, Editor, or Admin).
- **Additional permissions**: the abilities to add on top.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/organization/custom-roles/create_role_dialog.webp",
    alt="The Create role dialog showing a name field, a base access dropdown, and grouped permission checkboxes",
    class_name="rounded-md h-auto",
)
```

Permissions that come with the base level are shown ticked and greyed out; they're part of the role and can't be removed. You choose everything else.

### The permissions you can add

| Group | Permission | What it allows |
| --- | --- | --- |
| **Project** | Create apps | Add new apps to the project |
| | Create threads | Start new Build chats in the project |
| | Rename project | Change the project's name |
| | Delete project | Permanently delete the project |
| **Secrets & integrations** | Manage integrations | Connect and configure integrations |
| | View secret names | See which secrets exist (names only) |
| | Reveal secret values | See the value of a secret |
| | Edit secrets | Add, change, and remove secrets |
| **Deployments** | Approve deployments | Approve or reject deployments that need sign-off |
| **Activity** | View audit log | See the project's activity history |

```md alert info
# Some permissions come as a set
Revealing or editing secret values requires seeing the secret names, so turning on **Reveal secret values** or **Edit secrets** also includes **View secret names**.
```

## Permissions you can't delegate

Two abilities stay with the built-in **Admin** role and can't be added to a custom role:

- **Managing members** (adding people and changing their roles)
- **Managing roles** (creating and editing roles)

Either one amounts to admin control. If someone needs it, give them the Admin role. Billing isn't part of project roles either; it comes from a person's [organization role](/docs/ai/organization/roles-and-permissions/).

## Assigning a custom role

A custom role appears in the role dropdown wherever you assign project roles: when [adding members](/docs/ai/organization/project-access/) and when changing an existing member's role. Each custom role shows its base level and how many permissions it adds.

## Editing and deleting roles

From the Roles tab, **edit** a custom role to rename it or change its permissions. Built-in roles can't be edited and carry a **Built-in** badge.

To **delete** a custom role, first reassign any members using it to another role. Reflex won't delete a role while members are still assigned to it.

## Related

- [Managing project access](/docs/ai/organization/project-access/) — assign a role to members.
- [Roles & permissions](/docs/ai/organization/roles-and-permissions/) — how the built-in roles are made up.
