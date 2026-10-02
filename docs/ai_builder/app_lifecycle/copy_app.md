# Copy App

```python exec
import reflex as rx
```

Copying creates an independent app from an existing Reflex Build app. Use it to try a significant change without altering the original or to reuse a working starting point.

## Copy an App

1. Open the menu next to **Deploy** and select **Copy**. You can also use the copy action in **Settings**.
2. Wait for the copied app to open in the current project.
3. Rename it so it is easy to distinguish from the original.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/app_copy_action.webp",
    alt="The Copy action in the menu next to Deploy",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

The copy includes the app's code, state, configuration, and dependencies. Changes to the copied app do not change the original app.

Review integrations, secrets, and visibility before sharing or deploying the copy. Credentials and access requirements may need to be confirmed separately.
