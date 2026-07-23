# Organizations

> Every app you build in Reflex Build lives inside an **organization**. An organization holds your projects and apps, the people you collaborate with, and your plan and billing. This page explains how organizations are structured, how members and roles work, how apps, secrets, and deployments are scoped to an org, and how plans and billing work.

<!-- SCREENSHOT: The organization switcher open in the user popover (bottom-left), showing one or more orgs with their plan labels and a checkmark on the active org. Upload to web.reflex-assets.dev/ai_builder/organizations/org_switcher_{light,dark}.avif and embed with a `python exec` + rx.image block like the other pages. -->

## What is an organization?

An organization is the top-level container for your work in Reflex Build. It owns your **projects** (which in turn hold your apps), a set of **members**, and a **plan** with its own credits and spend limit.

When you first sign up, Reflex Build automatically creates an organization for you — named after your email (the part before the `@`), on the **Free** plan, with you as its **Admin**. You can start building in it right away.

Every organization is structurally identical; there is no separate "personal account" type. If your plan allows it (see [Plans and billing](#plans-and-billing)), you can create additional organizations — for example one per team or client — and [switch between them](#switching-organizations).

### Your first org vs. organizations you create

The organization created for you at sign-up starts on the **Free** plan and works immediately.

Organizations you create yourself start **inactive** — with a $0 spend limit and no credits or plan features — until you add a subscription to them. A brand-new organization therefore can't build anything until it's upgraded. This is expected: give a new org a plan before inviting your team to build in it.

## Switching organizations

You can belong to more than one organization. Use the **organization switcher** — in the user popover (bottom-left) and in the navbar dropdown — to change which one you're working in. The active organization scopes everything in your session: which projects and apps you see, which secrets and integrations are available, and which org your credits are spent against.

Your selection is remembered across sessions. Only **Admins** see a settings (gear) affordance next to an org in the switcher; every member can switch into any org they belong to.

<!-- SCREENSHOT: The navbar organization dropdown expanded, with the "Create organization" (or "Upgrade to Enterprise") entry at the bottom. -->

## Members and roles

Reflex Build has two layers of roles: **organization roles** (your standing in the org) and **project roles** (your access to a specific project). Organization Admins are automatically Admins on every project in the org.

### Organization roles

| Role | What it means |
|---|---|
| **Member** | Belongs to the organization. Project access is granted per project. |
| **Manager** | A member who can also create projects and view audit logs. |
| **Admin** | Manages members and billing, and is an Admin of every project in the org. |

What each org role can do:

| Capability | Member | Manager | Admin |
|---|:---:|:---:|:---:|
| View the organization | ✅ | ✅ | ✅ |
| Create projects | ❌ | ✅ | ✅ |
| View audit logs | ❌ | ✅ | ✅ |
| Create additional organizations | ❌ | ❌ | ✅ |
| Invite / remove / manage members | ❌ | ❌ | ✅ |
| Manage billing and plan | ❌ | ❌ | ✅ |
| Delete the organization | ❌ | ❌ | ✅ |

### Project roles

Within a project, members hold one of three roles. Access is nested: a Viewer can read, an Editor can also build, and an Admin can also manage the project.

| Capability | Viewer | Editor | Admin |
|---|:---:|:---:|:---:|
| View the project and its apps | ✅ | ✅ | ✅ |
| **Build** — create apps and generations | ❌ | ✅ | ✅ |
| **Deploy** an app | ❌ | ✅ | ✅ |
| View secret **keys** | ❌ | ✅ | ✅ |
| View secret **values** / edit secrets | ❌ | ❌ | ✅ |
| Approve a deploy | ❌ | ❌ | ✅ |
| Manage members, roles, integrations; rename or delete the project | ❌ | ❌ | ✅ |

Organization Admins inherit Admin on every project automatically, so you don't have to add them to each project individually.

### Inviting and managing members

Organization Admins manage the roster from the **Members** page (`/organization/members`). Use **Add member**, enter an email, and pick a role:

- If the email already belongs to a Reflex account, the person joins the organization immediately.
- If it doesn't, they receive an email invitation and join automatically when they sign up.

Admins can also change a member's role, remove a member, revoke a pending invite, and sign a member out of active sessions.

<!-- SCREENSHOT: The Members page with the roster (name, email, role dropdown) and the "Add member" dialog open showing the email field + role select. -->

### Seats

Your plan includes a number of **seats**. Both active members and **pending invites** count against your seats, so an outstanding invitation reserves a seat until it's accepted or revoked.

If your organization uses [verified email domains](#single-sign-on-and-email-domains) and runs out of seats, matching users who sign up are added as **inactive** members ("Awaiting a seat") — they hold no access until an Admin frees a seat and activates them.

### Single sign-on and email domains

Enterprise organizations can claim **verified email domains** so that anyone signing up with a matching address joins the organization automatically, and can enforce **single sign-on (SSO)** for their members. These are Enterprise features; see [Enterprise features](#enterprise-features).

## Apps, secrets, and deployments

Your work is organized as a hierarchy: an **organization** contains **projects**, a project contains **apps**, and an app can have **deployments**. Everything you build belongs to a project, and every project belongs to exactly one organization — so an app's organization is determined by the project it lives in.

**Secrets** (API keys, tokens, and other environment values) can be scoped at three levels:

- **App** — available to a single app only.
- **Project** — shared across every app in the project.
- **Integration** — attached to a connected integration.

There is no organization-wide secret store; the broadest scope is the project. (Secrets can also be turned off for an individual app.) See the **Secrets** feature page for details.

### Moving work between organizations

You can move an entire **project** (along with its apps) into another organization, with a few conditions:

- the destination organization must be on the **Enterprise** plan;
- a project can't be moved while any of its apps are deployed to a **custom cloud provider** — those deployments live in the original organization's cloud account, so remove them first;
- members who don't belong to the destination organization lose access to the project after the move.

Individual **apps** can be moved between projects **within the same organization**, but not across organizations.

## Plans and billing

Each organization has its own plan, credits, spend limit, and billing. **Billing is per organization, not per user**, and only **Admins** can manage it.

| Plan | Who it's for |
|---|---|
| **Free** | Getting started. Included with your first organization. |
| **Pro** | Individuals and small teams who want more credits and private apps. Self-serve upgrade. |
| **Enterprise** | Teams that need multiple organizations, SSO, bring-your-own-cloud, and more. Arranged with Reflex. |
| **Inactive** | An organization with no active plan — created but not yet subscribed. No credits or plan features until a plan is added. |

### Credits and spend

Building consumes **credits**, which belong to the organization (shared by everyone in it) rather than to individual members. Each plan comes with a monthly credit allotment:

- **Free** organizations get a fixed monthly amount that resets each month (it does not stockpile).
- **Pro** organizations get a larger monthly grant added to their balance.
- **Enterprise** organizations get a configurable monthly grant.

Each organization also has a monthly **spend limit** that caps usage-based costs.

### Upgrading and managing billing

An Admin upgrades to **Pro** from the organization's billing settings, which opens a checkout. From the billing portal an Admin can update the payment method, add **seats** for more members, or cancel. **Enterprise** is not sold through the in-app checkout — contact Reflex to set it up.

If a Pro subscription is cancelled, the organization becomes **Inactive** (a $0 spend limit with no credits) rather than reverting to Free, so you'll need to re-subscribe to keep building.

<!-- SCREENSHOT: The organization billing/plan settings page showing the current plan, credit balance, spend limit, and the upgrade / manage-plan button. -->

## Enterprise features

The **Enterprise** plan unlocks organization- and team-scale capabilities:

- **Create additional organizations** and **create projects** within them.
- **Invite teammates** and collaborate as a team.
- **Single sign-on (SSO)** and **verified email domains** for automatic, managed access (requires a company email domain, not a personal/consumer one).
- **Bring your own cloud** — deploy apps to your organization's own cloud provider from **Organization → Cloud providers**.
- **Custom integrations** and **static egress tunnels**.
- **MCP access** to Reflex Build's tools.
- Longer-lived API tokens (no forced expiration cap).
- Apps and Git repositories are **private by default**.

The **Pro** plan unlocks a smaller set: private apps and repositories, deploying Reflex Enterprise apps, deployment customization, security review, and a resizable sandbox. The **Free** plan covers the essentials — editing the file tree, downloading apps, and forking.

## Things to know

A few current behaviors worth being aware of:

- **New organizations start without a plan.** An org you create yourself has a $0 spend limit and no credits until you subscribe, so it can't build until upgraded. Your original sign-up org is on Free and works out of the box.
- **You can create up to 10 organizations.**
- **You can't delete your only organization**, an organization's last remaining project, or its last Admin. If you're the sole Admin of any organization, you'll need to hand off or remove it before you can delete your account.
- **Removing a member revokes access**, but an already-open session may persist briefly until it expires.
