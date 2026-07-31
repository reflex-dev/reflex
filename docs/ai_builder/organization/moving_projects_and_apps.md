---
tags: Organization
description: Move a Reflex project to another organization, or move an app to another project, as your team's structure changes.
---

# Moving Projects & Apps

```python exec
import reflex as rx
```

Reflex lets you move work as your team's structure changes: transfer a project to another organization, or move an app to another project.

## Moving a project to another organization

You can transfer a whole project, including its apps and settings, from one organization to another. This is useful when a project outgrows a personal organization or moves between teams.

Open the project's **Settings → General** and find the **Move project** card. Choose the destination organization and confirm.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/organization/moving/move_project.webp",
    alt="The Move project dialog with a dropdown to select a destination organization and a warning about members losing access",
    class_name="rounded-md h-auto",
)
```

### What you need

You must be an **admin of both organizations**: the current one and the destination. If you can't move a project, the card explains why:

- You're not an admin of the project's current organization, or
- You aren't an admin of any other organization to move it into.

### What happens to members

A project's members come from its current organization. When you move it, **members who aren't in the destination organization lose access.** Reflex lists those people before you confirm. To keep someone's access, add them to the destination organization first.

```md alert warning
# Check who loses access before moving
Moving a project isn't undone automatically; you'd have to move it back. Review who loses access before confirming, and add anyone who should keep it to the destination organization first.
```

## Moving an app to another project

You can move an app from one project to another **within the same organization**, for example to group it with related apps.

In Reflex Build, open the app's options menu (the **⋯** menu on the app), choose **Move app**, and pick the destination project.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/organization/moving/move_app.webp",
    alt="The Move app dialog listing other projects in the same organization to move the app into",
    class_name="rounded-md h-auto",
)
```

Notes:

- You can only move an app within the same organization. To move it across organizations, move the whole project instead.
- You need permission to **create apps** in the destination project.
- Integrations are connected per project, so you may need to reconnect them in the destination project after the move.

## Related

- [Managing project access](/docs/ai/organization/project-access/) — add members to a project before moving it.
- [Members & seats](/docs/ai/organization/members/) — add people to the destination organization.
