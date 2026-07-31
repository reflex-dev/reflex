# Tokens

```python exec
import reflex as rx
```

A Reflex token authenticates CLI and API requests. Tokens created from the Builder are scoped to the selected organization, and their project scope and resource permissions limit what they can access.

The token is still owned by the person who creates it. For long-running automation that should not depend on a person's membership, use an organization-owned [service account](/docs/ai/organization/service-accounts/).

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/hosting/tokens.webp",
    alt="Organization-scoped Reflex tokens with expiration and access details",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

## Create a token

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/hosting/token_create.webp",
    alt="Creating a Reflex token with an expiration and access template",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

1. Open the organization workspace.
2. Select **Tokens** in the organization sidebar.
3. Select **Create Token**.
4. Enter a recognizable name and choose an expiration date.
5. Choose a template, project scope, and resource permissions.
6. Create the token and copy it when it is shown.
7. Store it in a password manager or secret store.

## Start from a template

Templates provide a safe starting point that you can adjust:

| Template | Starting access |
| --- | --- |
| **CI / auth only** | Authentication only, with no resource access |
| **Deploy** | Read and write access to Projects and Apps so the token can create and deploy apps |
| **Full access** | Read and write access to every resource group |

Review the resulting permissions before creating the token instead of assuming a template fits every workflow.

## Limit project access

Choose which projects the project-scoped permissions cover:

- **All projects** applies to every current and future project the token owner can access.
- **Only select projects** limits access to the projects you choose.

The project selection applies to Projects, Apps, and Threads. Organization permission is organization-wide.

## Set resource permissions

Each resource group supports **No access**, **Read-only**, or **Read & write**:

| Resource | What it covers |
| --- | --- |
| **Projects** | Project settings, members, audit logs, and deletion |
| **Apps** | Viewing, editing, deploying, starting, stopping, and deleting deployed apps |
| **Threads** | Conversations and their generated code and secrets |
| **Organization** | Organization members, billing, and creating projects or teams |

Use a token with commands that support `--token`, or set the recognized `REFLEX_ACCESS_TOKEN` environment variable.

```bash
export REFLEX_ACCESS_TOKEN="<token>"
reflex cloud scan --no-interactive
```

## Security

- Create each token for one purpose and grant only the required resources and projects.
- Prefer an expiration date that matches the workflow's lifetime.
- Store automation tokens in the platform's secret manager.
- Never commit a token or include it in a prompt, screenshot, or log.
- Revoke a token when it is no longer needed or may have been exposed.

Because a token is owned by its creator, it may stop being suitable when that person changes roles or leaves the organization. Use a [service account](/docs/ai/organization/service-accounts/) for organization-owned automation.
