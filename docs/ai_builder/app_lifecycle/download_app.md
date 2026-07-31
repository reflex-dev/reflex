# Download App

```python exec
import reflex as rx
```

Download creates a one-time source export for local development or self-hosting.

## Download the Source

1. Open the menu next to **Deploy**.
2. Select **Download**. The action is also available from app **Settings**.
3. Save and extract the generated archive.

```python eval
rx.image(
    src="https://web.reflex-assets.dev/docs-preview/ai-builder/platform/app_download_action.webp",
    alt="The Download action in the menu next to Deploy",
    class_name="rounded-md h-auto mb-4",
    border=f"0.81px solid {rx.color('slate', 5)}",
)
```

The archive contains the app source, assets, dependency manifests, and Reflex configuration needed to continue development.

Secrets, integration credentials, and other protected project values are not a portable part of the source export. Configure them separately in the destination environment and never commit them to source control.

For an ongoing source-control workflow, connect a [Project Repository](/docs/ai/features/connect-to-git-providers/) instead of repeatedly downloading archives.
