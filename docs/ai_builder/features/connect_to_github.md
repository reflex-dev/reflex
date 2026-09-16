---
tags: DevTools
description: Connect Reflex Build to GitHub to version your app, sync code locally, and revert to previous checkpoints.
---

# Connecting to GitHub

```python exec
import reflex as rx
```

Use this workflow to create and synchronize a GitHub repository for an individual Builder app through the `reflex-build` GitHub App. It gives the app a version history, lets you edit the code locally, and records each push as an ordinary Git commit.

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/git_integration_connect.webp",
        alt="Connecting a Reflex Build app to GitHub",
        class_name="rounded-md h-auto mb-4",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
)
```

The GitHub integration allows you to:

- Save your app progress as commits you control
- Work on your code locally and push your local changes back to Reflex Build
- Pull changes made elsewhere back into the editor
- Revert to any previous version of your app

## How the Connection Works

Reflex Build connects to GitHub through the `reflex-build` GitHub App using OAuth. The first time you connect, GitHub prompts you to install the app and authorize access. It then links your GitHub account to Reflex Build, which stores an encrypted access token and uses it to create repositories and push commits for you.

Pushes, pulls, and reverts use short-lived GitHub App installation tokens that Reflex Build requests as needed. Your personal OAuth token identifies you and refreshes access. Both are encrypted at rest.

## Team and Multi-User Access

**Each user connects their own GitHub account.** Connections are stored per user; there is no shared or organization-level token. If one teammate connects GitHub, another teammate who wants to push or pull has to run the same connect flow and authorize the `reflex-build` app with their own account.

Commits are attributed to the GitHub user who made them, and each person's access to a repository follows their own GitHub permissions.

The GitHub App installation is separate from per-user authorization. An organization owner can install the `reflex-build` app once and choose which repositories it may access, which controls what is reachable from Reflex Build. Each user still authorizes the app once to link their own account before they can push or pull.

## Where Repositories Are Created

When you connect a Build app to GitHub, Reflex Build creates a Git repository for it:

- If the `reflex-build` app is installed on a **GitHub organization**, the repository is created inside that organization.
- Otherwise, the repository is created under your **personal GitHub account**.

New repositories use the `main` branch and are private, unless you make them public when connecting.

## Pushing and Pulling Changes

The GitHub popover in the editor syncs in both directions:

- **Push**: commit the current state of your app and push it to GitHub.
- **Pull**: fetch the latest commits from GitHub and update the files in the editor.
- **Switch branch**: check out a different branch and sync its files into the editor.

You can also clone the repository, edit it locally, and push your changes back.

Before switching branches or pulling remote work:

1. Finish or review the active generation.
2. Save any manual edits.
3. Check the current branch and pending changes in the Git controls.
4. Pull the latest remote changes before starting another overlapping task.

If a teammate is changing the same app, coordinate the affected work and avoid overlapping generations. See [Generation Controls & Collaboration](/docs/ai/features/generation-controls/).

## GitHub Commit History

Use commit history to review changes and return the app to an earlier version when needed. Check the affected files before reverting so you do not discard newer work that should be preserved.

## Other Git Providers

To connect a repository hosted somewhere other than GitHub, such as GitLab, Bitbucket, or a self-hosted Git server, use the generic Git connection instead. See [Connecting to Git Providers](/docs/ai/features/connect-to-git-providers/) for details.

## Requirements

Git integration is available on plans that include the Git connection feature. If your plan does not include it, connecting will prompt you to upgrade.
