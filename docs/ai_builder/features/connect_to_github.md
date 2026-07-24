---
tags: DevTools
description: Connect Reflex Build to GitHub to version your app, sync code locally, and revert to previous checkpoints.
---

# Connecting to GitHub

```python exec
import reflex as rx
```

Connecting your app to GitHub gives it a version history and lets you edit the code locally. Each sync is a commit in an ordinary Git repository.

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/connecting_to_github.avif",
        alt="Connecting a Reflex AI Builder app to GitHub",
        class_name="rounded-md h-auto",
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

New repositories use the `main` branch. Repository visibility depends on your plan: on **Pro** you choose public or private when connecting; on the **Free** plan new repositories are public; on **Enterprise** they are always private.

## Pushing and Pulling Changes

The GitHub popover in the editor syncs in both directions:

- **Push**: commit the current state of your app and push it to GitHub.
- **Pull**: fetch the latest commits from GitHub and update the files in the editor.
- **Switch branch**: check out a different branch and sync its files into the editor.

You can also clone the repository, edit it locally, and push your changes back.

## GitHub Commit History

The commit history is a great way to see the changes that you have made to your app. You can also revert to previous versions of your app from here.

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/github_commit_history.avif",
        alt="GitHub commit history for a Reflex AI Builder app",
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
)
```

Reverting resets your app's files to an earlier commit.

## Other Git Providers

To connect a repository hosted somewhere other than GitHub, such as GitLab, Bitbucket, or a self-hosted Git server, use the generic Git connection instead. See [Connecting to Git Providers](/docs/ai/features/connect-to-git-providers/) for details.

## Requirements

Git integration is available on plans that include the Git connection feature. If your plan does not include it, connecting will prompt you to upgrade.
