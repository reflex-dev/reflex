```python exec
import reflex as rx
```

# Machine Types

Machine types define the CPU and RAM allocated to each app instance.

## Change the machine type in Reflex Build

1. Open **Deployments** and select the app.
2. Open **Settings > Scale**.
3. Review the current CPU, RAM, and machine type.
4. Select **Change VM**, choose a machine type, and review the change before confirming.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/hosting/settings_scale.webp",
    alt="Scale settings with the current and available VM types",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

**Persistent Machine** is visible on this page but is currently marked **Coming soon**.

## Use machine types from the CLI

List the machine types available to your organization:

```bash
reflex cloud vmtypes
```

Pass the selected ID with `--vmtype` when you deploy:

```bash
reflex deploy --project <PROJECT_ID> --vmtype c2m4
```

CLI arguments override the corresponding value in `cloud.yml` or `pyproject.toml`. See [Cloud Configuration File](/docs/hosting/config-file/).
