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

seo:
  title: Select Component - Python Dropdown for Web Apps | Reflex
  description: "Build accessible dropdown select components in pure Python with Reflex. Full-featured alternative to Streamlit's selectbox with controlled state, form integration, and custom styling."
  schema:
    type: TechArticle
    headline: Select Component - Reflex Python Web Framework
    description: "Documentation for the Reflex Select component: a dropdown list control for building Python web applications."
    author_name: Reflex
    date_published: "2024-01-01"
    date_modified: "2026-04-24"
    proficiency_level: Beginner

related:
  components:
    - text: Radio Group
      href: /docs/library/forms/radio-group
      description: inline single-selection for fewer than 5 options
    - text: Checkbox
      href: /docs/library/forms/checkbox
      description: single or multi-selection with visible state
    - text: Form
      href: /docs/library/forms/form
      description: grouping selects with other inputs for submission
    - text: Drawer
      href: /docs/library/overlay/drawer
      description: slide-out panels that can contain selects
    - text: Dialog
      href: /docs/library/overlay/dialog
      description: modal dialogs that can contain selects
    - text: Low-level Select API
      href: /docs/library/forms/select/low
      description: fine-grained control over trigger, content, and items
  concepts:
    - text: State Management
      href: /docs/state/overview
      description: how Reflex components track and update values
    - text: Event Handlers
      href: /docs/events/overview
      description: understanding on_change, on_open_change, and related triggers
    - text: Forms and Validation
      href: /docs/library/forms/form
      description: building complete forms with typed, validated inputs
    - text: Components Overview
      href: /docs/components/overview
      description: how all Reflex components fit together

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
```

# Select

A select component displays a dropdown list of options for the user to pick one from. It's one of the most common form controls in web applications — use it whenever you need a user to choose a single value from a predefined list and screen space is limited.

Reflex's `rx.select` is a fully-featured, accessible dropdown built on Radix UI primitives. It supports controlled and uncontrolled usage, custom styling, form integration, keyboard navigation, and works out-of-the-box on desktop and mobile. Unlike Streamlit's `st.selectbox` or Dash's dropdown, `rx.select` gives you full control over state, styling, and behavior in pure Python — no JavaScript or CSS required.

## When to Use Select

Use `rx.select` when:

- You have more than five options and need to save vertical space
- The user should choose exactly one option from a predefined list
- You want a consistent dropdown that matches your app's theme

Consider alternatives when:

- You have fewer than five options → use [Radio Group](/docs/library/forms/radio-group) for better visibility
- Users need to select multiple values → use [Checkbox](/docs/library/forms/checkbox) groups or a multi-select pattern
- Users should type a value rather than choose one → use [Input](/docs/library/forms/input)
- You need hierarchical or searchable options → use the [low-level Select API](/docs/library/forms/select/low) with custom content

## Basic Usage

At its simplest, pass a list of string options. The component renders a dropdown button that opens a menu of choices.

```python demo
rx.select(["apple", "grape", "pear"])
```

By default, the first option is selected. The user can click the trigger button to open the dropdown and choose a different option.

## Controlled Select with State

In most real apps, you need to react when the user selects a value — to filter data, update a chart, save to a database, or trigger another event. Bind the select to a [State](/docs/state/overview) var using the `value` prop and an `on_change` event handler.

```python demo exec
class SelectStateControlled(rx.State):
    selected_fruit: str = "apple"

    @rx.event
    def update_fruit(self, value: str):
        self.selected_fruit = value


def select_controlled():
    return rx.hstack(
        rx.select(
            ["apple", "grape", "pear"],
            value=SelectStateControlled.selected_fruit,
            on_change=SelectStateControlled.update_fruit,
        ),
        rx.text("You selected:"),
        rx.badge(SelectStateControlled.selected_fruit),
        align="center",
        spacing="3",
    )
```

This is the most common pattern. Because the select is controlled, the value always reflects the state var — you can update it from anywhere in your app, and the select will re-render automatically.

## Setting a Default Value

For uncontrolled selects where you just need an initial choice without tracking changes, use `default_value`. This is simpler than a controlled select when you don't need the selected value elsewhere in your app.

```python demo
rx.select(
    ["apple", "grape", "pear"],
    default_value="grape",
)
```

## Placeholder Text

When you want the select to start empty — prompting the user to make a choice — omit `default_value` and provide a `placeholder`.

```python demo
rx.select(
    ["apple", "grape", "pear"],
    placeholder="Choose a fruit…",
)
```

## Dynamic Options from State

Real applications rarely have hardcoded options. More often, options come from a database, API, or calculated from other state. Pass a state var as the options list, and the dropdown updates whenever the list changes.

```python demo exec
class SelectStateDynamic(rx.State):
    options: list[str] = ["apple", "grape", "pear"]
    selected: str = "apple"

    @rx.event
    def set_selected(self, value: str):
        self.selected = value

    @rx.event
    def randomize(self):
        self.selected = random.choice(self.options)

    @rx.event
    def add_option(self):
        new_options = ["banana", "orange", "mango", "kiwi", "cherry"]
        available = [o for o in new_options if o not in self.options]
        if available:
            self.options = self.options + [available[0]]


def select_dynamic():
    return rx.vstack(
        rx.select(
            SelectStateDynamic.options,
            value=SelectStateDynamic.selected,
            on_change=SelectStateDynamic.set_selected,
        ),
        rx.hstack(
            rx.button("Pick Random", on_click=SelectStateDynamic.randomize),
            rx.button("Add Option", on_click=SelectStateDynamic.add_option),
            spacing="2",
        ),
        spacing="3",
    )
```

## Disabled State

To prevent user interaction, set `disabled=True`. The select renders with a muted appearance and cannot be opened.

```python demo
rx.select(
    ["apple", "grape", "pear"],
    default_value="apple",
    disabled=True,
)
```

To disable individual items rather than the whole select, use the [low-level API](/docs/library/forms/select/low) and set `disabled=True` on specific `rx.select.item` components.

## Using Select in a Form

Select components integrate cleanly with Reflex forms. The `name` prop sets the key used when the form is submitted, and `required=True` prevents submission until the user makes a choice.

```python demo exec
class SelectFormState(rx.State):
    form_data: dict = {}

    @rx.event
    def handle_submit(self, form_data: dict):
        self.form_data = form_data


def select_form():
    return rx.card(
        rx.vstack(
            rx.heading("Order Form", size="4"),
            rx.form.root(
                rx.vstack(
                    rx.text("Favorite fruit"),
                    rx.select(
                        ["apple", "grape", "pear"],
                        name="fruit",
                        placeholder="Pick one",
                        required=True,
                    ),
                    rx.text("Quantity"),
                    rx.select(
                        ["1", "2", "3", "4", "5"],
                        name="quantity",
                        default_value="1",
                    ),
                    rx.button("Submit Order", type="submit"),
                    spacing="2",
                    align="stretch",
                ),
                on_submit=SelectFormState.handle_submit,
                reset_on_submit=True,
            ),
            rx.divider(),
            rx.text("Submitted data:"),
            rx.code(SelectFormState.form_data.to_string()),
            spacing="3",
            width="100%",
        ),
        width="400px",
    )
```

For full details on building forms, validation, and submission handling, see the [Form documentation](/docs/library/forms/form).

## Sizes

Select supports three sizes to match the density of your interface. Use smaller sizes in data-heavy tables or toolbars, and larger sizes for primary actions.

```python demo
rx.hstack(
    rx.select(["apple", "grape", "pear"], default_value="apple", size="1"),
    rx.select(["apple", "grape", "pear"], default_value="apple", size="2"),
    rx.select(["apple", "grape", "pear"], default_value="apple", size="3"),
    spacing="3",
    align="center",
)
```

## Variants

The `variant` prop controls the visual style. Use `classic` for bordered selects, `surface` for filled backgrounds, `soft` for subtle elevation, and `ghost` for minimal chrome.

```python demo
rx.hstack(
    rx.select(["apple", "grape", "pear"], default_value="apple", variant="classic"),
    rx.select(["apple", "grape", "pear"], default_value="apple", variant="surface"),
    rx.select(["apple", "grape", "pear"], default_value="apple", variant="soft"),
    rx.select(["apple", "grape", "pear"], default_value="apple", variant="ghost"),
    spacing="3",
)
```

## Custom Color

Override the default accent color with the `color_scheme` prop. Any of Reflex's built-in color tokens work.

```python demo
rx.hstack(
    rx.select(["apple", "grape", "pear"], default_value="apple", color_scheme="blue"),
    rx.select(["apple", "grape", "pear"], default_value="apple", color_scheme="green"),
    rx.select(["apple", "grape", "pear"], default_value="apple", color_scheme="red"),
    rx.select(["apple", "grape", "pear"], default_value="apple", color_scheme="purple"),
    spacing="3",
)
```

## Populating Options from a Dictionary

When your options have separate display labels and underlying values (e.g., a user ID for the value, a name for the label), keep the lookup table as a module-level constant and store only the selection in state. Pass the names list as the options argument:

```python demo exec
USERS: dict[str, str] = {
    "user_001": "Alice Johnson",
    "user_002": "Bob Smith",
    "user_003": "Carol Davis",
}
USER_NAMES: list[str] = list(USERS.values())


class SelectDictState(rx.State):
    selected_name: str = USER_NAMES[0]

    @rx.event
    def set_name(self, value: str):
        self.selected_name = value


def select_dict_example():
    return rx.vstack(
        rx.select(
            USER_NAMES,
            value=SelectDictState.selected_name,
            on_change=SelectDictState.set_name,
        ),
        rx.text("Selected: ", SelectDictState.selected_name),
        rx.link(
            "For full label/value control, use the low-level Select API →",
            href="/docs/library/forms/select/low",
        ),
        spacing="3",
    )
```

For true label/value separation — where the form submits a stable ID but the user sees a friendly name — the [low-level Select API](/docs/library/forms/select/low) gives you `rx.select.item(value="user_001")` with custom children for the display label.

## Using Select Inside a Drawer or Dialog

When placing a select inside a [Drawer](/docs/library/overlay/drawer), [Dialog](/docs/library/overlay/dialog), or other portal-based container, set the `position` prop to `"popper"`. This ensures the dropdown menu renders correctly above the overlay content.

```python demo
rx.drawer.root(
    rx.drawer.trigger(rx.button("Open Drawer")),
    rx.drawer.overlay(z_index="5"),
    rx.drawer.portal(
        rx.drawer.content(
            rx.vstack(
                rx.drawer.close(rx.button("Close", variant="soft")),
                rx.text("Pick a fruit:"),
                rx.select(
                    ["apple", "grape", "pear"],
                    position="popper",
                    default_value="apple",
                ),
                spacing="3",
            ),
            width="20em",
            padding="2em",
            background_color=rx.color("gray", 1),
        ),
    ),
    direction="left",
)
```

## Reacting to Open and Close Events

Beyond `on_change`, the `on_open_change` event fires when the dropdown opens or closes. Use this to trigger analytics, prefetch data, or animate related UI.

```python demo exec
class SelectOpenState(rx.State):
    is_open: bool = False
    open_count: int = 0

    @rx.event
    def on_toggle(self, is_open: bool):
        self.is_open = is_open
        if is_open:
            self.open_count += 1


def select_open_change():
    return rx.vstack(
        rx.select(
            ["apple", "grape", "pear"],
            default_value="apple",
            on_open_change=SelectOpenState.on_toggle,
        ),
        rx.text(f"Opened {SelectOpenState.open_count} times"),
        rx.cond(
            SelectOpenState.is_open,
            rx.badge("Open", color_scheme="green"),
            rx.badge("Closed", color_scheme="gray"),
        ),
        spacing="3",
    )
```

## Common Patterns

### Filtering a List Based on Selection

A classic use case — the select controls what data is displayed elsewhere on the page.

```python demo exec
class FilterState(rx.State):
    all_items: list[dict] = [
        {"name": "MacBook Pro", "category": "laptops"},
        {"name": "Dell XPS", "category": "laptops"},
        {"name": "iPhone 15", "category": "phones"},
        {"name": "Pixel 8", "category": "phones"},
        {"name": "iPad Air", "category": "tablets"},
        {"name": "Galaxy Tab", "category": "tablets"},
    ]
    category: str = "laptops"

    @rx.event
    def set_category(self, value: str):
        self.category = value

    @rx.var
    def filtered_items(self) -> list[dict]:
        return [i for i in self.all_items if i["category"] == self.category]


def select_filter():
    return rx.vstack(
        rx.select(
            ["laptops", "phones", "tablets"],
            value=FilterState.category,
            on_change=FilterState.set_category,
        ),
        rx.foreach(
            FilterState.filtered_items,
            lambda item: rx.card(item["name"]),
        ),
        spacing="3",
        width="300px",
    )
```

### Cascading Selects

When one select's options depend on another's value — a common pattern for country/state, category/subcategory, etc. Keep the static lookup table outside state so the keys can be enumerated at compile time, and use a `@rx.var` for the dependent options:

```python demo exec
REGIONS: dict[str, list[str]] = {
    "North America": ["USA", "Canada", "Mexico"],
    "Europe": ["UK", "France", "Germany"],
    "Asia": ["Japan", "Korea", "Singapore"],
}
REGION_NAMES: list[str] = list(REGIONS.keys())


class CascadeState(rx.State):
    region: str = REGION_NAMES[0]
    country: str = REGIONS[REGION_NAMES[0]][0]

    @rx.event
    def set_region(self, value: str):
        self.region = value
        self.country = REGIONS[value][0]

    @rx.event
    def set_country(self, value: str):
        self.country = value

    @rx.var
    def countries(self) -> list[str]:
        return REGIONS.get(self.region, [])


def select_cascade():
    return rx.hstack(
        rx.select(
            REGION_NAMES,
            value=CascadeState.region,
            on_change=CascadeState.set_region,
        ),
        rx.select(
            CascadeState.countries,
            value=CascadeState.country,
            on_change=CascadeState.set_country,
        ),
        spacing="3",
    )
```

## Accessibility

`rx.select` is fully accessible out of the box:

- **Keyboard navigation**: Tab to focus, Space or Enter to open, arrow keys to navigate options, Enter to select, Escape to close
- **Screen readers**: Properly announces the current selection, available options, and state changes
- **ARIA attributes**: Automatically sets `role`, `aria-expanded`, `aria-controls`, and related attributes
- **Focus management**: Focus returns to the trigger when the dropdown closes

For accessibility compliance, always provide a visible label — either directly above the select or via a form label.

## Frequently Asked Questions

### How do I get the value selected in an rx.select?

Bind the select to a [State](/docs/state/overview) var with the `value` prop and an `on_change` event handler. The selected value is then available as `State.var_name` anywhere in your app. See the [Controlled Select example](#controlled-select-with-state) above.

### How do I set a default value in rx.select?

Use the `default_value` prop for uncontrolled selects, or set the initial value of your state var for controlled selects. The value should match one of the options in the list.

### How do I make an rx.select required in a form?

Set `required=True` on the select. When the select is inside an `rx.form.root`, the form cannot be submitted until the user picks a value. You must also set the `name` prop so the value is included in form data.

### How do I create a dropdown menu in Python with Reflex?

Use `rx.select` with a list of options. Reflex compiles your Python code to a React app, so the dropdown renders as a fully-styled web component without you writing any JavaScript or CSS.

### What's the difference between rx.select and rx.radio_group?

Both let users pick one option from a list. Use `rx.select` when you have more than five options or need to conserve space. Use `rx.radio_group` when all options should be visible at once for easier comparison.

### Can rx.select support multi-selection?

No — `rx.select` is single-selection by default, matching the native HTML behavior. For multi-select scenarios, use a group of [Checkbox](/docs/library/forms/checkbox) components, or build a custom multi-select using the [low-level Select API](/docs/library/forms/select/low).

### How do I populate rx.select options from a database?

Load your data into a [State](/docs/state/overview) var (typically in an `on_mount` event handler), then pass the list as the options argument. Dynamic options update automatically when the state var changes. See the [Dynamic Options example](#dynamic-options-from-state) above.

### Why doesn't my rx.select dropdown appear correctly inside a modal or drawer?

Set `position="popper"` on the select. This switches the dropdown's positioning strategy to work correctly with overlay and portal-based containers. See [Using Select Inside a Drawer or Dialog](#using-select-inside-a-drawer-or-dialog).

### How do I customize the appearance of rx.select?

Use the `variant` (`classic`, `surface`, `soft`, `ghost`), `size` (`1`, `2`, `3`), `color_scheme`, and `radius` props. For deeper customization — custom item rendering, icons, groupings — use the [low-level Select API](/docs/library/forms/select/low).

### Is rx.select a good alternative to Streamlit's st.selectbox?

Yes. Both components serve the same purpose, but `rx.select` gives you full control over styling, state management, and composition with other components. Reflex apps run as full React applications, so your select integrates seamlessly with modern web patterns like routing, authentication, and real-time updates.
