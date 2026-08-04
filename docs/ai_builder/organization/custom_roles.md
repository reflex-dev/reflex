---
tags: Organization
description: Create custom project roles with a base access level and the specific permissions your team needs.
---

# Custom Project Roles

The built-in project roles (Viewer, Editor, and Admin) cover most cases, but sometimes you need something in between: a contractor who can build apps but not manage secrets, or a reviewer who can approve deployments or project access changes without editing. A **custom project role** defines that combination.

Custom roles are created per project from **Roles** in the project sidebar, by anyone with the project **Admin** role.

Organization custom roles are separate. They start with Member access and add organization permissions such as creating projects, managing billing, or viewing audit logs. See [Organization roles](/docs/ai/organization/roles-and-permissions/#custom-organization-roles).

```md alert info
# Custom roles require collaboration
Custom roles matter once you have teammates on a project. Inviting teammates is an Enterprise feature; see [Managing project access](/docs/ai/organization/project-access/).
```

## Create a custom role

Select **New role**, then define:

1. **Role name**: a label your team will recognize, such as *Support lead* or *Release manager*.
2. **Base access**: Viewer, Editor, or Admin. The role includes everything that level can do.
3. **Additional permissions**: individual abilities to add on top of the base level.

Pick the closest built-in level, then add the permissions you need.

```md alert info
# Roles assigned to teams cannot be based on Admin
Teams can use custom roles based on Viewer or Editor. Assign the built-in Admin role directly to a person when they need full project control.
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
| **Approvals** | Approve deployments | Approve or reject deployments that need sign-off |
| | Approve project changes | Approve or reject member additions, removals, role changes, and team access grants |
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

A custom role appears in the role dropdown on the project's **Members** page. Assign it directly to a member or, when it is based on Viewer or Editor, to a [team](/docs/ai/organization/teams/). Each custom role shows its base level and how many permissions it adds.

## Editing and deleting roles

From the Roles tab, **edit** a custom role to rename it or change its permissions. The preview shows which capabilities will be added or removed and identifies the directly assigned members and teams affected.

Saving changes updates access for everyone who holds the role, including every member of an assigned team. A role held by a team cannot be changed to the Admin base level; reassign the team first.

To **delete** a custom role, first reassign every member and team using it. Reflex will not delete a role while a direct member or team assignment remains.

## Related

- [Managing project access](/docs/ai/organization/project-access/) — assign a role to members.
- [Teams](/docs/ai/organization/teams/) — assign a role once for a group.
- [Roles & permissions](/docs/ai/organization/roles-and-permissions/) — how the built-in roles are made up.
