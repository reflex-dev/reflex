# Deploy App

```python exec
import reflex as rx
```

It is easy to deploy your app into production from Reflex Build to Reflex Cloud.

Simply click the `Deploy` button in the top right corner of Reflex Build, as shown below:



```python exec
import reflex as rx


def render_image():
    return rx.el.div(
        rx.image(
            src="https://web.reflex-assets.dev/ai_builder/app_lifecycle/deploy_light.avif",
            class_name="rounded-md h-auto",
            border=f"0.81px solid {rx.color('slate', 5)}",
        ),
        class_name="w-full flex flex-col rounded-md",
    )
```

```python eval
rx.el.div(render_image())
```

When deploying you can set the following options:
- **App Name**: The name of your app
- **Hostname**: Set your url by setting your hostname, i.e. if you set `myapp` as your hostname, your app will be available at `myapp.reflex.run`
- **Region**: The regions where your app will be deployed
- **VM Size**: The size of the VM where your app will be deployed
- **Secrets**: The environment variables that will be set for your app, you can load the variables currently being used by your app by clicking the `Load from settings` button

Note: Hostname customization, region selection, and VM sizing are only available on paid plans.
