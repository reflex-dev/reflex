---
tags: AI Builder
description: Add supported Python libraries to a Reflex Build app and give the agent focused guidance for specialized packages.
---

# Python Libraries

Reflex Build can add supported Python packages to an app. Ask for the behavior you need and name a package when you have already chosen one:

```text
Use pandas to build a CSV upload and validation workflow. Show rows with missing
email addresses or invalid dates before the user confirms the import.
```

The prompt attachment gives the agent context; it does not become a runtime upload automatically. Ask the agent to build an upload workflow when app users need to provide CSV files.

The agent can use web search to check current package documentation when needed. Review the selected package, version, and license before shipping the app.

See [Install External Packages](/docs/ai/features/installing-external-packages/) for chat and `requirements.txt` workflows.

## Add library guidance to Knowledge

For a specialized package, add short usage instructions to the app's **Knowledge**:

- The package name and purpose.
- The version or API surface the app should use.
- A small example of the expected usage.
- Any constraints the agent must preserve.

See [Knowledge](/docs/ai/features/knowledge/) for project-wide and app-specific instructions.

## Package limitations

Some packages are too large or depend on operating-system libraries that are unavailable in the Builder environment. If a package cannot be installed, use a hosted API or another supported service for that capability.

## Related

- [Install External Packages](/docs/ai/features/installing-external-packages/) — add or pin a dependency.
- [Call an External API](/docs/ai/apis/) — use an HTTP API when a local package is unsuitable.
