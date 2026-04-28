```python exec
import reflex as rx
```

# Introduction

**~5 min** · **Reflex** lets you build and deploy full-stack web apps — frontend, backend, and database — in **pure Python**. No JavaScript, no separate API, no context switching.

## Goals

```md section
### Pure Python

Write your entire app — frontend, backend, database — in Python. No need to learn another language.

### Easy to Learn

Ship your first app in minutes. No web development experience required.

### Full Flexibility

Build anything from small data apps to large multi-page websites. **This entire site was built and deployed with Reflex.**

### Batteries Included

One tool covers it all: UI, server-side logic, and deployment.
```

## Build a counter

We'll build a counter app that lets the user count up or down. In ~20 lines of Python you'll touch the three core pieces of every Reflex app: **state**, **event handlers**, and **components**.

```python exec
class CounterExampleState(rx.State):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1

    @rx.event
    def decrement(self):
        self.count -= 1


class IntroTabsState(rx.State):
    """The app state."""

    value: str = "tab1"
    tab_selected: str = ""

    @rx.event
    def change_value(self, val: str):
        self.tab_selected = f"{val} clicked!"
        self.value = val


def tabs():
    return rx.tabs.root(
        rx.tabs.list(
            rx.tabs.trigger("Frontend", value="tab1", class_name="pill-tab"),
            rx.tabs.trigger("Backend", value="tab2", class_name="pill-tab"),
            rx.tabs.trigger("Page", value="tab3", class_name="pill-tab"),
            class_name="pill-tab-list",
        ),
        rx.tabs.content(
            rx.markdown(
                """The frontend is built declaratively with Reflex components, which compile to JS and run in the browser. Use `rx.cond` and `rx.foreach` instead of `if` and `for` for dynamic UIs. Any non-UI logic belongs in `State`.
                """,
            ),
            value="tab1",
            class_name="pt-4",
        ),
        rx.tabs.content(
            rx.markdown(
                """Write your backend in the `State` class. Here you can define functions and variables that can be referenced in the frontend. This code runs directly on the server and is not compiled, so there are no special caveats. Here you can use any Python external library and call any method/function.
                """,
            ),
            value="tab2",
            class_name="pt-4",
        ),
        rx.tabs.content(
            rx.markdown(
                """Each page is a Python function returning a Reflex component. Add as many as you want and link between them — see [Routing](/docs/pages/overview) for details.
                """,
            ),
            value="tab3",
            class_name="pt-4",
        ),
        class_name="text-slate-12 font-normal",
        default_value="tab1",
        value=IntroTabsState.value,
        on_change=lambda x: IntroTabsState.change_value(x),
    )
```

```python demo box id=counter
rx.hstack(
    rx.button(
        "Decrement",
        color_scheme="ruby",
        on_click=CounterExampleState.decrement,
    ),
    rx.heading(CounterExampleState.count, font_size="2em"),
    rx.button(
        "Increment",
        color_scheme="grass",
        on_click=CounterExampleState.increment,
    ),
    spacing="4",
)
```

Here is the full code for this example:

```python eval
tabs()
```

```python demo box
rx.box(
    rx._x.code_block(
        """import reflex as rx """,
        class_name="code-block !bg-transparent !border-none",
    ),
    rx._x.code_block(
        """class State(rx.State):
    count: int = 0

    @rx.event
    def increment(self):
        self.count += 1

    @rx.event
    def decrement(self):
        self.count -= 1""",
        background=rx.cond(
            IntroTabsState.value == "tab2",
            "var(--c-slate-3) !important",
            "transparent",
        ),
        border=rx.cond(
            IntroTabsState.value == "tab2",
            "1px solid var(--c-slate-5)",
            "none !important",
        ),
        class_name="code-block",
    ),
    rx._x.code_block(
        """def index():
    return rx.hstack(
        rx.button(
            "Decrement",
            color_scheme="ruby",
            on_click=State.decrement,
        ),
        rx.heading(State.count, font_size="2em"),
        rx.button(
            "Increment",
            color_scheme="grass",
            on_click=State.increment,
        ),
        spacing="4",
    )""",
        border=rx.cond(
            IntroTabsState.value == "tab1",
            "1px solid var(--c-slate-5)",
            "none !important",
        ),
        background=rx.cond(
            IntroTabsState.value == "tab1",
            "var(--c-slate-3) !important",
            "transparent",
        ),
        class_name="code-block",
    ),
    rx._x.code_block(
        """app = rx.App()
app.add_page(index)""",
        background=rx.cond(
            IntroTabsState.value == "tab3",
            "var(--c-slate-3) !important",
            "transparent",
        ),
        border=rx.cond(
            IntroTabsState.value == "tab3",
            "1px solid var(--c-slate-5)",
            "none !important",
        ),
        class_name="code-block",
    ),
    class_name="w-full flex flex-col",
)
```

## The Structure of a Reflex App

Let's break this example down.

### Import

```python
import reflex as rx
```

Import Reflex as `rx`. All Reflex objects are accessed as `rx.*`.

### State

```python
class State(rx.State):
    count: int = 0
```

State holds the app's mutable data. Variables declared here are called **[vars](/docs/vars/base_vars)**. Our counter has one: `count`, starting at `0`.

### Event Handlers

```python
@rx.event
def increment(self):
    self.count += 1


@rx.event
def decrement(self):
    self.count -= 1
```

**Event handlers** are the only way to modify state. They're triggered by user actions (clicks, typing, etc.) — those actions are called **events**. Our counter has two handlers: `increment` and `decrement`.

### User Interface (UI)

```python
def index():
    return rx.hstack(
        rx.button(
            "Decrement",
            color_scheme="ruby",
            on_click=State.decrement,
        ),
        rx.heading(State.count, font_size="2em"),
        rx.button(
            "Increment",
            color_scheme="grass",
            on_click=State.increment,
        ),
        spacing="4",
    )
```

The UI is built from components (`rx.hstack`, `rx.button`, `rx.heading`) that can be nested and styled with CSS or [Tailwind](/docs/styling/tailwind). Reflex ships with [50+ built-in components](/docs/library), and you can [wrap any React component](/docs/wrapping-react/overview).

Components reference state vars (`rx.heading(State.count, …)`) and reactively re-render when state changes. Event triggers (`on_click=State.decrement`) wire UI to handlers.

The sequence goes like this:

1. User clicks "Increment".
2. `on_click` fires.
3. `State.increment` runs on the server.
4. `State.count` is updated.
5. UI re-renders with the new value.

### Add pages

```python
app = rx.App()
app.add_page(index)
```

Create the app and register the page at the base route.

## Next Steps

🎉 You've built a fully interactive web app in pure Python.

```md alert info
# Keep learning

- [Dashboard tutorial](/docs/getting_started/dashboard_tutorial) — build a real data app.
- [Chatapp tutorial](/docs/getting_started/chatapp_tutorial) — wire up streaming AI responses.
- [How Reflex works](/docs/advanced_onboarding/how-reflex-works) — what happens under the hood.
```

```md alert info
# Ship faster with AI

- [Reflex Build](https://build.reflex.dev/) — generate a full app from a prompt.
- [Reflex Cloud](https://reflex.dev/docs/hosting/deploy-quick-start/) — one-command deploy.
```

Browse our [open-source templates](/docs/getting_started/open_source_templates), or press `Cmd+K` / `Ctrl+K` to search the docs.
