---
tags: AI Builder
description: Install a supported Python dependency through the Reflex Build agent or by editing the app's requirements file.
---

# Install External Packages

```python exec
import reflex as rx
```

Add a Python package when the app needs a library that is not already in its environment.

You can install one in either of these ways:

1. Ask the agent to add the package while implementing a feature.
2. Add the package to `requirements.txt` in **Code**, then save the file.

## Ask the agent

Describe the outcome and name the package when you already know which one to use:

```text
Use the requests package to call this REST endpoint. Add it to the app's
dependencies and handle timeouts and non-success responses.
```

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/agent_package_install.webp",
        alt="Installing external packages via the chat interface",
        class_name="rounded-md h-auto mb-4",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

## Edit `requirements.txt`

Open `requirements.txt` in **Code**, add the package on its own line, and save. Reflex installs the dependency and recompiles the app.

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/requirements_package_added.webp",
        alt="Installing external packages via requirements.txt",
        class_name="rounded-md h-auto mb-4",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

Pin or constrain dependencies used by a deployed app so future builds remain repeatable. Update those versions deliberately after reviewing compatibility. After installation, check **Preview** and the build output for import or compatibility errors.

Some packages are too large or require system dependencies that are unavailable in the Builder environment. When that happens, use a hosted API or another supported service instead.

## Related

- [Python Libraries](/docs/ai/python-libraries/) — give the agent reusable guidance for a specialized package.
- [Call an External API](/docs/ai/apis/) — connect to a hosted service instead of installing a package.
