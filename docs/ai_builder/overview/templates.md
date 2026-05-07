# Templates

Reflex has many certified templates, seen on the `Trending` tab of the Reflex Build, that can be used to kickstart your app.

```python exec
import reflex as rx
```

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/overview/templates_light.avif",
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

## Using a Template

To use a template, simply click the template and then in the bottom right corner of the app click the `Fork` button. This will create a copy of the template in your own account. You can then edit the app as you like with further prompting.

```python eval
rx.el.div(
    rx.image(
        src="https://web.reflex-assets.dev/ai_builder/overview/fork_template_light.avif",
        class_name="rounded-md h-auto",
        border=f"0.81px solid {rx.color('slate', 5)}",
    ),
    class_name="w-full flex flex-col rounded-md",
)
```

Templates are great to get started if they have similar UI to what you are looking to build. You can then add your own data to the app.
