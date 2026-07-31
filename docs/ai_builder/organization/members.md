---
tags: Organization
description: Add people to a Reflex organization, manage invitations, and understand how seats are counted.
---

# Members & Seats

```python exec
import reflex as rx
```

An organization's **members** are the people who can work in it. Once someone is a member, you can add them to specific projects.

Manage members under your organization's **Settings → Team** tab.

## Seats

Each member uses one **seat**. A pending invitation also holds a seat until the person joins or you revoke it.

The Members tab shows how many seats are in use, such as *4 of 10 seats used*. When seats run out, remove a member, revoke an invitation, or add seats to your plan.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/organization/members/members_list.webp",
    alt="The organization Members tab showing the seat counter and a list of members with their roles",
    class_name="rounded-md h-auto",
)
```

```md alert info
# Seats and billing
Your seat count is part of your plan; see [Billing](/docs/hosting/billing/) to review or change it. If you're out of seats or don't see the option to add members, [contact sales](https://reflex.dev/pricing/).
```

## Adding a member

Select **Add member**, enter an email address, and choose the [organization role](/docs/ai/organization/roles-and-permissions/) the person should have.

- If they already have a Reflex account, they're added right away.
- If they don't, Reflex emails them an invitation, and they join once they sign up.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/organization/members/add_member_dialog.webp",
    alt="The Add member dialog with fields for an email address and an organization role",
    class_name="rounded-md h-auto",
)
```

```md alert info
# Organization membership is not project access
Adding someone to the organization doesn't give them access to any project. Grant that separately from each project's settings. See [Managing project access](/docs/ai/organization/project-access/).
```

## Pending invitations

Invited people who haven't joined appear under **Pending invitations**, with the role they'll receive. Each pending invitation holds a seat until it's accepted.

To withdraw an invitation, select it and choose **Revoke**. You can re-invite the person later.

## Awaiting a seat

With [verified domains](/docs/ai/organization/domains/), people whose email matches your domain join automatically. If the organization is out of seats when that happens, they go into an **Awaiting a seat** queue.

Queued people hold no seat and have no access. When a seat frees up, select **Activate** to admit them.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/organization/members/awaiting_seat.webp",
    alt="The Awaiting a seat section listing a user who joined by verified domain, with an Activate button",
    class_name="rounded-md h-auto",
)
```

## Changing a member's role

A member's **organization role** appears next to their name. Pick a new role from the dropdown to change it. See [Roles & permissions](/docs/ai/organization/roles-and-permissions/) for what each role can do.

You can't change your own role; ask another admin if it needs to change.

## Removing a member

Select the delete icon next to a member and confirm. They lose access to the organization and all of its projects. You can add them back later.

## Related

- [Roles & permissions](/docs/ai/organization/roles-and-permissions/) — what each role can do.
- [Managing project access](/docs/ai/organization/project-access/) — add members to projects.
- [Verified domains & auto-join](/docs/ai/organization/domains/) — automatic joining by email domain.
