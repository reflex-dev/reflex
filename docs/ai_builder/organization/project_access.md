---
tags: Organization
description: Give organization members access to specific Reflex projects and assign each person a project role.
---

# Managing Project Access

```python exec
import reflex as rx
```

Organization membership lets someone join projects, but not any specific one. You control access per project: who can open it and what they can do.

Manage this under each project's **Settings → Members** tab.

## Who already has access

Some people have access without being added:

- **Organization admins** can open every project. They show an **Organization admin** badge in the member list, and their access can't be changed here because it comes from their organization role.
- **Managers and members** have no access to a project until you add them.

## Adding members to a project

Select **Add user** to open the member picker. It lists organization members who aren't on the project yet. Choose one or more, assign each a [project role](/docs/ai/organization/roles-and-permissions/), and select **Add to project**.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/organization/project-access/add_project_members.webp",
    alt="The Add project members dialog showing selectable organization members and a role dropdown for each",
    class_name="rounded-md h-auto",
)
```

You can only add people who already belong to your organization. If someone isn't in the list, they aren't a member yet.

```md alert info
# Can't find someone?
They need to join the organization first. If you're an admin, add them under the organization's **Settings → Team** (see [Members & seats](/docs/ai/organization/members/)); otherwise, ask an admin to add them.
```

## Changing a member's project role

Each member has a role dropdown next to their name. Pick a new role to change their access.

Two cases can't be edited here:

- **Your own role**, so you can't lock yourself out.
- **Organization admins**, whose access is inherited from the organization.

Assigning project roles requires the project **Admin** role or organization admin.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/organization/project-access/project_member_roles.webp",
    alt="A project member list with a role dropdown open, and an organization admin shown with a non-editable badge",
    class_name="rounded-md h-auto",
)
```

## Removing a member from a project

Select the delete icon next to a member and confirm. They lose access to this project but remain in the organization and keep access to their other projects.

To remove someone from the organization entirely, use the organization's Members tab instead (see [Members & seats](/docs/ai/organization/members/)).

```md alert info
# Inviting teammates is an Enterprise feature
Collaborating with teammates on projects is part of the Enterprise plan. If you don't see the option to add members, [contact sales](https://reflex.dev/pricing/).
```

## Related

- [Roles & permissions](/docs/ai/organization/roles-and-permissions/) — what each project role can do.
- [Custom roles](/docs/ai/organization/custom-roles/) — define a role with specific permissions.
