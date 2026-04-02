# Copy App

The **Copy** feature lets you duplicate an existing app inside Reflex Build.
This is useful when you want to experiment with changes without affecting the original project, or when you want to use an app as a starting point for a new idea.


```python exec
import reflex as rx


def render_image():
    return rx.el.div(
        rx.image(
            src="https://web.reflex-assets.dev/ai_builder/app_lifecycle/copy_light.avif",
            class_name="rounded-md h-auto",
            border=f"0.81px solid {rx.color('slate', 5)}",
        ),
        class_name="w-full flex flex-col rounded-md",
    )
```

```python eval
rx.el.div(render_image())
```

## How to Copy an App

1. In the Reflex Build workspace, click on the arrow down icon next to the deploy button and click on the **Copy** button. You can also do this in the Settings tab.
2. Reflex Build will create a new app in your workspace with the same:
   - Code files and components
   - State and configuration
   - Dependencies

The copied app will appear as a separate project, independent from the original.


## Common Use Cases

- **Experiment Safely**
  Try out new components, layouts, or integrations without risking your working app.

- **Create Variations**
  Use the original app as a base to quickly spin up a different version (e.g., a light and dark theme version).

- **Template Reuse**
  Turn an app into a personal template and copy it each time you start a new project.

## Best Practices

- Rename your copied app immediately so it’s easy to distinguish from the original.
