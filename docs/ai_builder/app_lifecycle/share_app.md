# Share App

The **Share** feature makes it easy to show your app to others without deploying it.
When you share, Reflex Build generates a unique link that points to the current version of your project in the builder.

```python exec
import reflex as rx


def render_image():
    return rx.el.div(
        rx.image(
            src="https://web.reflex-assets.dev/ai_builder/app_lifecycle/share_light.avif",
            class_name="rounded-md h-auto",
            border=f"0.81px solid {rx.color('slate', 5)}",
        ),
        class_name="w-full flex flex-col rounded-md",
    )
```

```python eval
rx.el.div(render_image())
```

## How to Share

1. In the AI Builder workspace, click on the arrow down icon next to the deploy button and click on the **Share** button.
2. A popup will appear with a **shareable link**.
3. Copy the link and send it to teammates, collaborators, or stakeholders.


## What Others See

- The link opens a **read-only view** of your app generation.
- Recipients can see the app preview but cannot make edits.
- This makes it safe to share work-in-progress versions for quick feedback.


## Common Use Cases

- **Get Feedback Quickly**
  Share a work-in-progress version with your team before deploying.

- **Demo Features**
  Send a link to showcase a new component, layout, or integration.

- **Collaboration**
  Share context with another developer before handing off to GitHub or download.
