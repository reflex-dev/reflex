---
tags: DevTools
description: Connect Reflex Build to GitLab, Bitbucket, or any Git remote using a repository URL and fine-grained access token.
---

# Connecting to Git Providers

Besides the [GitHub integration](/docs/ai/features/connect-to-github/), Reflex Build can sync to any Git remote, including GitLab, Bitbucket, Azure DevOps, a self-hosted server, or an existing GitHub repository. You connect it with a repository URL and a fine-grained access token, then push and pull the same way you would with GitHub.

## What You Need

To connect, provide:

- **Remote URL**: the HTTPS clone URL of the repository (for example `https://gitlab.com/your-org/your-app.git`).
- **Branch**: the branch to sync with. Point at an existing branch, or name a new branch for an empty repository.
- **Fine-grained access token**: a token from your provider with permission to read and write the repository. It authenticates pushes and pulls.

Unlike the GitHub integration, which each user authorizes with their own account, the token is saved as one of the app's secrets (`GIT_PAT_TOKEN`). Anyone working on the app pushes and pulls with that stored token, so use a token whose repository access is appropriate to share with the app's collaborators.

## How It Works

The connection tracks two separate repositories: the internal history Reflex Build keeps for your app, and your external remote. Pushing copies your app's current files to the remote as a commit; pulling copies the remote's latest files back into the editor. The two histories stay independent, so a sync copies the files across, not the individual commits.

## Connecting

1. Open the Git connection dialog in the editor and choose the generic Git option.
2. Enter the remote URL, the branch, and your fine-grained access token.
3. Choose whether to pull the remote's files into the editor immediately after connecting.

After connecting, the **Push** and **Pull** actions work the same as with GitHub.

## Connecting to an Existing Repository

To bring in an existing repository, enter its remote URL and a token with access to it, then pull its files into the editor. Reflex Build syncs against that branch from then on.

If the repository is empty, name a new branch instead of an existing one, and Reflex Build initializes it on the first push.

## Requirements

Git integration is available on plans that include the Git connection feature. If your plan does not include it, connecting will prompt you to upgrade.
