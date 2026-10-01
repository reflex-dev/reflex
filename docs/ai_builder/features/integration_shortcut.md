---
tags: AI Builder
description: Add built-in or custom integrations to a Reflex project and make them available to Builder apps.
---

# Integrations

```python exec
import reflex as rx
```

Integrations give Reflex Build the context and credentials it needs to work with databases, AI models, authentication providers, APIs, and other services.

Manage the project's integrations from **Integrations** in the project settings. Inside an app, open **Integrations** to review what is available to that app.

## Adding an integration

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/integrations_gallery.webp",
    alt="The searchable integrations gallery in Reflex Build",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

1. Open the project's **Integrations** page.
2. Select **Add Integration**.
3. Browse or search the gallery, then open the integration you need.
4. Complete its configuration and secret fields.
5. Return to the app and enable the integration when it is not already available there.

Builder can then use the integration's instructions while generating or updating the app.

```md alert warning
# Keep credentials out of prompts
Enter secrets only in the integration's secret fields. Do not paste API keys, tokens, passwords, or private connection strings into chat, knowledge, source code, or screenshots.
```

## Custom integration

Use **Custom Integration** when the service or internal tool you need is not represented by a built-in integration.

From **Add Integration**, find **Custom Integration** and select **Create Custom Integration**. The form asks for:

- **Name**: the service or tool name.
- **Description**: what it is for and when Builder should use it.
- **Knowledge / Context**: instructions Builder needs in order to use the service.
- [**Secrets**](/docs/ai/features/secrets/) (optional): key-value credentials or other sensitive configuration.

Useful knowledge/context includes:

- The service's purpose and base URL.
- The authentication scheme, referring to secret keys by name rather than including their values.
- Required packages and imports.
- Common operations, request shapes, and response formats.
- Error handling, rate limits, and usage constraints.
- A short safe example when the API is unusual.

Write the context as focused Markdown with clear headings. Include enough information to call the service correctly, but avoid copying an entire API reference when only a few operations are relevant.

For each optional secret, add a descriptive key and its value in the **Secrets** section. Never repeat the value in the knowledge/context field.

After creation, the integration appears in the project's integration list with the **Custom** type. Use **Auto-enable** to turn it on by default for new app generations. Existing app threads are not changed. Use **Edit** when its guidance or credentials need to change.

## Managing a configured integration

Open the integration's action menu to see the actions available for that integration.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/integration_actions.webp",
    alt="Action menu for a configured project integration",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

### Rename or edit

Use **Rename** to change the display name of a configured gallery integration. Use **Edit** to update its configuration or secrets.

For a custom integration, **Edit** also updates its name, description, knowledge/context, and optional secrets.

### Duplicate

For a configured gallery integration that shows this action, use **Duplicate** to copy it into the current project or another project in the same organization. Enter a name and choose the destination project.

The copy includes the integration's secrets. It is not automatically attached to an app, and the original integration is unchanged. You need permission to view the source secrets and manage integrations in the destination project.

```md alert warning
# Duplicating copies credentials
Confirm that the destination project should receive the same credentials. Repository connections cannot be duplicated; connect the repository separately in the destination project.
```

### Manage access

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/integration_access.webp",
    alt="Member access controls for a configured integration",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

For a configured gallery integration that shows this action, use **Manage access** to choose what each project member can do:

- **No access**: cannot use the integration.
- **Can use**: can use it while building.
- **Can manage**: can configure or delete it and view its secret values.

Project and organization admins always have full access. Project Viewers cannot use integrations.

### Delete

Deleting an integration disconnects it from the project and removes its stored configuration and credentials. Apps that depend on it may stop working.

Before deleting it, check which apps use it and create any replacement integration they need. Deletion is permanent.

## Choosing what to enable

Enable only the integrations an app needs. This keeps Builder's context focused and limits unnecessary access.

Before using a custom integration with a sensitive system:

- Give its credential the least privilege required.
- Use separate development and production credentials.
- Confirm the project's members and [effective permissions](/docs/ai/organization/project-access/#viewing-effective-permissions).
- Review generated calls and run them against safe data before production.
