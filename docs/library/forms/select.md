---
components:
  - rx.select

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
              rx.select.item("grape", value="grape", **props),
              rx.select.item("pear", value="pear", **props),
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

A select component displays a dropdown list of options for the user to pick one from. It's one of the most common form controls in web applications, use it whenever you need a user to choose a single value from a predefined list and screen space is limited.

Reflex's `rx.select` is a fully-featured, accessible dropdown built on Radix UI primitives. It works with simple option lists or full state-bound bindings, supports form integration, keyboard navigation, and works out-of-the-box on desktop and mobile.

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

The user can click the trigger button to open the dropdown and choose a different option.

## Tracking the Selected Value

In most real apps, you need to react when the user selects a value, to filter data, update a chart, save to a database, or trigger another event. Bind the select to a [State](/docs/state/overview) var using the `value` prop and an `on_change` event handler.

```python demo exec
class SelectState(rx.State):
    selected_fruit: str = "apple"

    @rx.event
    def update_fruit(self, value: str):
        self.selected_fruit = value


def select_with_state():
    return rx.hstack(
        rx.select(
            ["apple", "grape", "pear"],
            value=SelectState.selected_fruit,
            on_change=SelectState.update_fruit,
        ),
        rx.text("You selected:"),
        rx.badge(SelectState.selected_fruit),
        align="center",
        spacing="3",
    )
```

This is the most common pattern. Because the select is bound to a state var, the value always reflects what's stored there, you can update it from anywhere in your app, and the select will re-render automatically.

## Setting a Default Value

If you just need the select to start with a specific option chosen, without tracking the user's choice in state, use `default_value`. This is the simplest pattern when you only care about the value at form submission time, or when you don't need the selected value to affect anything else in your app.

```python demo
rx.select(
    ["apple", "grape", "pear"],
    default_value="grape",
)
```

## Placeholder Text

When you want the select to start empty, prompting the user to make a choice, omit `default_value` and provide a `placeholder`.

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
            rx.hstack(
                rx.heading("Results:"),
                rx.badge(SelectFormState.form_data.to_string()),
            ),
            spacing="3",
            width="100%",
            align_items="left",
        ),
        width="400px",
    )
```

For full details on building forms, validation, and submission handling, see the [Form documentation](/docs/library/forms/form).

## Mapping Display Labels to Underlying Values

When your options have separate display labels and underlying values (e.g., a user ID for the value, a name for the label), use a [computed var](/docs/vars/computed-vars) to map between them.

```python demo exec
class SelectDictState(rx.State):
    users: dict[str, str] = {
        "user_001": "Alice Johnson",
        "user_002": "Bob Smith",
        "user_003": "Carol Davis",
    }
    selected_name: str = "Alice Johnson"

    @rx.var
    def user_names(self) -> list[str]:
        return list(self.users.values())

    @rx.var
    def selected_id(self) -> str:
        for uid, name in self.users.items():
            if name == self.selected_name:
                return uid
        return ""

    @rx.event
    def set_user(self, name: str):
        self.selected_name = name


def select_dict_example():
    return rx.vstack(
        rx.select(
            SelectDictState.user_names,
            value=SelectDictState.selected_name,
            on_change=SelectDictState.set_user,
        ),
        rx.text("Selected user ID:"),
        rx.badge(SelectDictState.selected_id),
        spacing="3",
    )
```

For native label/value separation in the dropdown itself, use the [low-level Select API](/docs/library/forms/select/low) and pass `value=` and a display label child to each `rx.select.item`.

## Using Select Inside a Dialog

When placing a select inside a [Dialog](/docs/library/overlay/dialog) or other portal-based container, set `position="popper"` on the select so the dropdown menu positions itself correctly above the overlay content.

```python demo
rx.dialog.root(
    rx.dialog.trigger(rx.button("Open Dialog")),
    rx.dialog.content(
        rx.dialog.title("Pick a fruit"),
        rx.vstack(
            rx.select(
                ["apple", "grape", "pear"],
                position="popper",
                default_value="apple",
            ),
            rx.dialog.close(rx.button("Close")),
            spacing="3",
        ),
    ),
)
```

## React to Open and Close Events

Beyond `on_change`, the `on_open_change` event fires when the dropdown opens or closes. Use this to trigger analytics, prefetch data, or animate related UI.

The example below uses [rx.cond](/docs/library/dynamic-rendering/cond) to swap between two badges based on whether the dropdown is open.

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
        rx.text("Open count: ", SelectOpenState.open_count),
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

A classic use case, the select controls what data is displayed elsewhere on the page.

```python demo exec
class FilterState(rx.State):
    all_items: list[dict[str, str]] = [
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
    def filtered_items(self) -> list[dict[str, str]]:
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

When one select's options depend on another's value, a common pattern for country/state, category/subcategory, etc.

```python demo exec
class CascadeState(rx.State):
    regions: dict[str, list[str]] = {
        "North America": ["USA", "Canada", "Mexico"],
        "Europe": ["UK", "France", "Germany"],
        "Asia": ["Japan", "Korea", "Singapore"],
    }
    region: str = "North America"
    country: str = "USA"

    @rx.event
    def set_region(self, value: str):
        self.region = value
        self.country = self.regions[value][0]

    @rx.event
    def set_country(self, value: str):
        self.country = value

    @rx.var
    def region_names(self) -> list[str]:
        return list(self.regions.keys())

    @rx.var
    def countries(self) -> list[str]:
        return self.regions.get(self.region, [])


def select_cascade():
    return rx.hstack(
        rx.select(
            CascadeState.region_names,
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


<!-- faqs-start -->

## Frequently Asked Questions

### What is the best alternative to st.selectbox?

For prototypes and quick data scripts, `st.selectbox` is fine. But for production apps, you need a dropdown component that doesn't trigger a full-page rerun on every interaction. `rx.select` is the most direct replacement, same API simplicity, but built on Radix UI as a real React component bound to Python state. It supports proper form integration, keyboard navigation, and accessibility out of the box, and works in apps with authentication, routing, and complex state.

### How do you make a dropdown menu in Python without writing JavaScript?

Use `rx.select(["option_1", "option_2", "option_3"])`. That's the full code for a working dropdown, Reflex compiles your Python to a React app, so the menu renders as a styled, accessible web component without you writing any JavaScript, HTML, or CSS. For interactive dropdowns bound to your app state, add `value=` and `on_change=` props pointing to a state var and event handler.

### How do you replace dcc.Dropdown with a simpler API?

Plotly Dash's `dcc.Dropdown` works but requires the callback decorator pattern, every interaction needs a `@app.callback` with explicit inputs and outputs. `rx.select` does the same job with standard Python event handlers: define a method on your state class, pass it to `on_change=`, and Reflex handles the wiring. Migration is usually mechanical: replace `dcc.Dropdown(options=..., value=..., id=...)` with `rx.select(options, value=State.value, on_change=State.set_value)` and delete the `@app.callback` decorators.

### Why does my Streamlit selectbox cause the whole page to rerun?

Because that's how Streamlit works by default, every widget interaction reruns your entire script from the top. This is fine for small scripts but becomes a performance problem as your app grows. The alternatives are: use `st.cache_data` and `st.session_state` aggressively to limit recomputation, switch to fragments (`@st.fragment`) for isolated reruns, or move to a framework like Reflex where state updates trigger granular re-renders instead of full reruns. Reflex's `rx.select` only updates the UI elements that actually depend on the selected value.

### What dropdown component works best for production Python web apps?

For prototypes, `st.selectbox` (Streamlit), `gr.Dropdown` (Gradio), and `dcc.Dropdown` (Plotly Dash) all work fine. For production apps with auth, routing, and complex state, `rx.select` (Reflex) is purpose-built, it's a real React component under the hood, supports proper form integration, and doesn't suffer from the full-page rerun problem that limits Streamlit at scale. The choice often comes down to whether you're building a quick demo or a real product.

### How do you build a dropdown that filters a table of data?

Bind the dropdown to a state variable, then derive the filtered data using a computed property. In Reflex: `rx.select(categories, value=State.selected, on_change=State.set_selected)` paired with a `@rx.var filtered_rows(self) -> list: return [r for r in self.all_rows if r.category == self.selected]`. The pattern is essentially the same in Streamlit, Dash, and Gradio, but Reflex's version only re-renders the table, not the entire page.

### What's a good Retool alternative for building admin panels with dropdowns?

Reflex is the most popular open-source alternative to Retool for building internal tools and admin panels. Unlike Retool, which is a hosted low-code platform with seat-based pricing, Reflex is open source, self-hostable, and lets you build everything in Python, including dropdowns (`rx.select`), tables, forms, and complete CRUD workflows. You get the same component-based UX as Retool, but with full code ownership and no per-user fees.

### How do you populate a dropdown from a database in Python?

Load the values into a state variable when the page loads, then pass the variable as the options list. In a Reflex app: define `options: list[str] = []` on a State class, populate it in an `on_mount` handler that queries your database, and pass `State.options` to `rx.select`. The dropdown updates automatically whenever the underlying data changes. The same pattern works with any database, SQLAlchemy, raw SQL, an ORM, or an API call.

### How do you build a dropdown with searchable or filterable options?

Native `<select>` elements don't support search. For a searchable dropdown, sometimes called a combobox or typeahead, you need a custom implementation. In Reflex, this is done via the low-level Select API combined with an input field that filters the options list. Streamlit's `st.selectbox` added basic search behavior, and Dash has `dcc.Dropdown(searchable=True)`, but both are limited in customization compared to building it yourself with composable primitives.

### What's the difference between a dropdown and a multiselect?

A dropdown (or single-select) lets the user pick one option. A multiselect lets them pick several. In native HTML these are different elements (`<select>` vs `<select multiple>`). In Python frameworks: Streamlit uses `st.selectbox` and `st.multiselect`, Dash uses `dcc.Dropdown(multi=True)`, and Reflex uses `rx.select` for single and `rxe.mantine.multi_select` (Reflex Enterprise) for multi. Choose based on whether your data model allows one or many values per field.

<!-- faqs-end -->

## Related Components

- [Radio Group](/docs/library/forms/radio-group) - inline single-selection for fewer than 5 options
- [Checkbox](/docs/library/forms/checkbox) - single or multi-selection with visible state
- [Form](/docs/library/forms/form) - grouping selects with other inputs for submission
- [Dialog](/docs/library/overlay/dialog) - modal dialogs that can contain selects
- [Low-level Select API](/docs/library/forms/select/low) - fine-grained control over trigger, content, and items

## Related Concepts

- [State Management](/docs/state/overview) - how Reflex components track and update values
- [Event Handlers](/docs/events/events-overview) - understanding `on_change`, `on_open_change`, and related triggers
- [Forms and Validation](/docs/library/forms/form) - building complete forms with typed, validated inputs
- [Computed Vars](/docs/vars/computed-vars) - deriving values from state for dynamic options and lookups
