---
tags: DevTools
description: Connect a project repository from GitHub, GitLab, Bitbucket, Azure DevOps, or another Git server.
---

# Project Repositories

```python exec
import reflex as rx
```

Connect a Git repository at the project level so Reflex Build can clone the code before the agent starts working. The current Repos interface supports GitHub, GitLab, Bitbucket, Azure DevOps, self-hosted Git servers, and other HTTPS Git remotes.

Use this workflow to start from an existing repository by providing its URL and a personal access token. To create and synchronize a GitHub repository for an individual Builder app through the `reflex-build` GitHub App, see [Connecting to GitHub](/docs/ai/features/connect-to-github/).

## Before You Connect

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/repos.webp",
    alt="Connected project repositories from several Git providers",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

Create a credential supported by your Git provider and grant it only the repository access required by this connection. The Repos page provides provider-specific instructions. For example, use a fine-grained GitHub token limited to the selected repository with **Contents: Read and write**.

Use the repository's HTTPS clone URL:

```text
https://gitlab.com/example/team-app.git
```

## Connect the Repository

1. Open **Repos** in the project sidebar.
2. Select the provider tab and follow its token instructions.
3. Select **Connect Repository**.
4. Enter the repository URL and personal access token.
5. Confirm the connection.

The repository is cloned before the agent starts, so the first prompt can work from the existing files rather than generating an unrelated app.

## Security

- Prefer a dedicated, least-privilege credential over a broad account token.
- Restrict the token to the required repository and permissions.
- Rotate or revoke the token when access changes.
- Do not paste the token into a prompt or commit it to the repository.

Repository connections are controlled by project permissions. If **Connect Repository** is unavailable, ask a project admin to check your role and plan.
