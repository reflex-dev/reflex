---
components:
  - rx.select
  - rx.select.root
  - rx.select.trigger
  - rx.select.content
  - rx.select.group
  - rx.select.item
  - rx.select.label
  - rx.select.separator

HighLevelSelect: |
  lambda **props: rx.select(["apple", "grape", "pear"], default_value="pear", **props)

SelectRoot: |
  lambda **props: rx.select.root(
      rx.select.trigger(),
      rx.select.content(
          rx.select.group(
              rx.select.item("apple", value="apple"),
              rx.select.item("grape", value="grape"),
              rx.select.item("pear", value="pear"),
          ),
      ),
      default_value="pear",
      **props
  )

SelectTrigger: |
  lambda **props: rx.select.root(
      rx.select.trigger(**props),
      rx.select.content(
          rx.select.group(
              rx.select.item("apple", value="apple"),
              rx.select.item("grape", value="grape"),
              rx.select.item("pear", value="pear"),
          ),
      ),
      default_value="pear",
  )

SelectContent: |
  lambda **props: rx.select.root(
      rx.select.trigger(),
      rx.select.content(
          rx.select.group(
              rx.select.item("apple", value="apple"),
              rx.select.item("grape", value="grape"),
              rx.select.item("pear", value="pear"),
          ),
          **props,
      ),
      default_value="pear",
  )

SelectItem: |
  lambda **props: rx.select.root(
      rx.select.trigger(),
      rx.select.content(
          rx.select.group(
              rx.select.item("apple", value="apple", **props),
              rx.select.item("grape", value="grape"),
              rx.select.item("pear", value="pear"),
          ),
      ),
      default_value="pear",
  )
---

```python exec
import random
import reflex as rx
from pcweb.templates.docpage import style_grid
```

# Select

Displays a list of options for the user to pick from—triggered by a button.

```python demo exec
class SelectState(rx.State):
    value: str = "apple"

    @rx.event
    def change_value(self, value: str):
        """Change the select value var."""
        self.value = value


def select_intro():
    return rx.center(
        rx.select(
            ["apple", "grape", "pear"],
            value=SelectState.value,
            on_change=SelectState.change_value,
        ),
        rx.badge(SelectState.value),
    )
```

```python demo exec
class SelectState3(rx.State):

    values: list[str] = ["apple", "grape", "pear"]

    value: str = "apple"

    def set_value(self, value: str):
        self.value = value

    @rx.event
    def change_value(self):
        """Change the select value var."""
        self.value = random.choice(self.values)


def select_example3():
    return rx.vstack(
        rx.select(
            SelectState3.values,
            value=SelectState3.value,
            on_change=SelectState3.set_value,
        ),
        rx.button("Change Value", on_click=SelectState3.change_value),

    )
```

The `on_open_change` event handler acts in a similar way to the `on_change` and is called when the open state of the select changes.

```python demo
rx.select(
    ["apple", "grape", "pear"],
    on_change=rx.window_alert("on_change event handler called"),
)

```

### Submitting a form using select

The `name` prop is needed to submit with its owning form as part of a name/value pair.

When the `required` prop is `True`, it indicates that the user must select a value before the owning form can be submitted.

```python demo exec
class FormSelectState(rx.State):
    form_data: dict = {}

    @rx.event
    def handle_submit(self, form_data: dict):
        """Handle the form submit."""
        self.form_data = form_data


def select_form_example():
    return rx.card(
        rx.vstack(
            rx.heading("Example Form"),
            rx.form.root(
                rx.flex(
                    rx.select(["apple", "grape", "pear"], default_value="apple", name="select", required=True),
                    rx.button("Submit", flex="1", type="submit"),
                    width="100%",
                    spacing="3",
                ),
                on_submit=FormSelectState.handle_submit,
                reset_on_submit=True,
            ),
            rx.divider(),
            rx.hstack(
                rx.heading("Results:"),
                rx.badge(FormSelectState.form_data.to_string()),
            ),
            align_items="left",
            width="100%",
        ),
        width="50%",
    )
```


### Using Select within a Drawer component

If using within a [Drawer](/docs/library/overlay/drawer) component, set the `position` prop to `"popper"` to ensure the select menu is displayed correctly.

```python demo
rx.drawer.root(
    rx.drawer.trigger(rx.button("Open Drawer")),
    rx.drawer.overlay(z_index="5"),
    rx.drawer.portal(
        rx.drawer.content(
            rx.vstack(
                rx.drawer.close(rx.box(rx.button("Close"))),
                rx.select(["apple", "grape", "pear"], position="popper"),
            ),
            width="20em",
            padding="2em",
            background_color=rx.color("gray", 1),
        ),
    ),
    direction="left",
)
```
