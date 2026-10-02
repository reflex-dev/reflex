---
tags: AI Builder
description: Store project and app credentials securely, control their scope, and update or remove them without exposing their values.
---

# Secrets

Store API keys, tokens, database URLs, and other sensitive configuration in **Secrets** instead of prompts or source files. Apps receive the values as environment variables at runtime.

```python exec
import reflex as rx
```

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/app_secret_create.webp",
    alt="Adding app secrets in Reflex Build",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

## Choose the scope

- **Project secrets** are managed from **Secrets** in the project sidebar and are available to the project's apps.
- **App secrets** are managed from **Secrets** in an app's more menu and apply only to that app.

If an app secret and project secret use the same name, the app value overrides the project value for that app. Use project scope for shared development credentials and app scope for values that must differ between apps.

Integration credentials belong in the integration form rather than either general secret scope.

## Add a secret

Select **Add new variable**, then enter an uppercase, descriptive name and its value. For example, use `STRIPE_SECRET_KEY` rather than `KEY`.

Tell the agent to read the variable by name without including its value:

```text
Use the STRIPE_SECRET_KEY environment variable for server-side Stripe calls.
Do not expose it in client-side code or logs.
```

Backend Python code can read it with `os.environ`:

```python
import os

stripe_secret_key = os.environ["STRIPE_SECRET_KEY"]
```

Do not read a secret in browser-executed code or send it to the frontend.

## Add or update several secrets

Use **Raw editor** to manage one `NAME=VALUE` pair per line:

```text
DATABASE_URL=postgresql://user:pass@host:5432/db
STRIPE_SECRET_KEY=sk_test_xxxxx
OPENAI_API_KEY=sk-xxxxxx
```

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/project_secrets_raw_editor.webp",
    alt="Managing several secrets with the raw editor",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

The raw editor replaces the complete secret set for the selected scope. Review every line before saving; removing a line deletes that variable from the scope.

## Edit, rotate, or delete a secret

Open a secret's action menu:

- Select **Edit** to replace its value. Replacing a value is the normal way to rotate a credential.
- Select **Delete** to remove it from the current scope. Check which apps use it first because deletion can break authentication or external-service calls.

Project Secrets records rotation information. When the configured secret store supports versioning, **Version history** can restore an earlier project-secret set. Do not treat version history as a substitute for keeping the current credential in an approved secret manager.

After rotating or deleting a value, revoke the old credential at its provider when applicable and test every affected workflow.

## Permissions

Project permissions independently control who can see secret names, reveal values, and edit secrets. Use the lowest access needed and review [Roles & permissions](/docs/ai/organization/roles-and-permissions/) before sharing a project.

## Related

- [Call an External API](/docs/ai/apis/) — use a credential in a server-side API request.
- [Custom Integration](/docs/ai/features/integration-shortcut/#custom-integration) — store credentials with reusable service instructions.
- [Secrets and Environment Variables](/docs/hosting/secrets-environment-vars/) — configure values for a deployed app.
