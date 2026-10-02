---
tags: Organization
description: Group organization members into teams and grant project access to the group.
---

# Teams

A **team** groups organization members so you can grant a project role once instead of adding every person individually. Everyone in the team inherits that project access.

Use teams for stable groups such as Engineering, Design, or Support. They reduce repetitive access changes and make it easier to keep project membership consistent as people join or leave a group.

## Create and manage a team

Organization admins can open **Teams**, select **New team**, enter a descriptive name, and select **Create team**.

Select **Manage** on a team to rename it, add active organization members, remove members, and review its project access.

Each team member has one team role:

- **Member** inherits every project role granted to the team.
- **Admin** also manages the team's members.

## Grant project access

Add the team from the project's **Members** page and give it an appropriate project role. See [Adding a team to a project](/docs/ai/organization/project-access/#adding-a-team-to-a-project) for the complete procedure and role restrictions.

Every current and future team member inherits the role granted there.

A person's effective project access can combine:

- Access inherited from their organization role.
- Access inherited from one or more teams.
- A role assigned directly on the project.

Before adding a direct assignment for a team member, check whether their inherited access is already sufficient. See [Viewing effective permissions](/docs/ai/organization/project-access/#viewing-effective-permissions).

## Access-management guidelines

- Create teams around real responsibilities, not individual projects, when the same group works across several projects.
- Assign the least-privileged project role that lets the team do its work.
- Review team membership when someone changes responsibilities or leaves the organization.
- Use direct project assignments for exceptions rather than creating one-person teams.

Organization membership and team membership are separate. Add a person to the organization first from [Members & seats](/docs/ai/organization/members/), then add them to a team.

Teams created through [SCIM provisioning](/docs/ai/organization/provisioning/) get their name and directory-managed membership from the identity provider. Manage those values there rather than treating the team as a manually maintained group.

## Delete a team

Organization admins can delete a team from the **Teams** page. Deleting it removes every project role its members inherited through the team. Roles assigned directly to those people are unchanged.

Review the team's project access before deleting it. If someone must keep access, assign them directly or through another team first.

For a team created through SCIM, delete the group in the identity provider. Reflex removes the synced team and its project-role assignments.

## Related

- [Roles & permissions](/docs/ai/organization/roles-and-permissions/) — understand organization, team, and direct project access.
- [Managing project access](/docs/ai/organization/project-access/) — grant roles and inspect effective permissions.
- [Audit logs](/docs/ai/organization/audit-logs/) — review access-related activity.
