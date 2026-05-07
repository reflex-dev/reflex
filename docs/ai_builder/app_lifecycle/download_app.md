# Download App

You can download your Reflex Build project if you want to work on it locally or self-host it outside the AI Builder.

**Tip:** The recommended workflow is to use the GitHub integration, which keeps your code version-controlled and in sync. Downloading is useful if GitHub integration isn’t available or you just want a one-time export.


```python exec
import reflex as rx


def render_image():
    return rx.el.div(
        rx.image(
            src="https://web.reflex-assets.dev/ai_builder/app_lifecycle/download_light.avif",
            class_name="rounded-md h-auto",
            border=f"0.81px solid {rx.color('slate', 5)}",
        ),
        class_name="w-full flex flex-col rounded-md",
    )
```

```python eval
rx.el.div(render_image())
```

## How to Download

1. In the AI Builder workspace, click on the arrow down icon next to the deploy button and click on the **Download** button. You can also do this in the Settings tab.
2. A `.zip` file will be generated containing your entire Reflex app, including:
   - Source code (`.py` files, components, state, etc.)
   - `requirements.txt` with dependencies
   - Config files (`rxconfig.py`, `.env`, etc.)
