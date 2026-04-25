# General App Settings

The **General App Settings** section lets you manage key aspects of your app, including its name, ID, and deletion. This is your central place to view and update your app’s core information.


```python exec
import reflex as rx


def render_image():
    return rx.el.div(
        rx.image(
            src="https://web.reflex-assets.dev/ai_builder/app_lifecycle/general_light.avif",
            class_name="rounded-md h-auto",
            border=f"0.81px solid {rx.color('slate', 5)}",
        ),
        class_name="w-full flex flex-col rounded-md",
    )
```

```python eval
rx.el.div(render_image())
```


## How to Access Settings

1. In the AI Builder workspace, on the top bar click the more 3 dots icon and then click the **Settings** tab.
2. This will open the **Settings** tab to see your app’s main settings.

## What You Can Do

- **Change App Name**
  Update the name of your app to reflect its purpose or version.

- **Change App Visibility**
  Update the visibility of your app to public or private.

- **View App ID**
  Find the unique identifier for your app, which can be used for integrations or support.

- **Fork App**
  Fork your app to create a copy of it.

-- **Download App**
  Download your app to your local machine.

- **Delete App**
  Permanently remove an app you no longer need. **Warning:** This action cannot be undone.
