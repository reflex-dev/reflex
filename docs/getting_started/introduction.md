```python exec
import reflex as rx
from pcweb import constants, styles
from pcweb.pages.docs import getting_started
from pcweb.pages.docs import wrapping_react
from pcweb.pages.docs.library import library
from pcweb.pages.docs import pages
from pcweb.pages.docs import vars
from pcweb.styles.colors import c_color
from pcweb.pages.docs import styling
from pcweb.styles.fonts import base
from pcweb.pages.docs import hosting
from pcweb.flexdown import markdown_with_shiki
from pcweb.pages.docs import advanced_onboarding
```

<!-- TODO how do we consistently rename page title? -->

# Introduction

**Reflex** is an open-source framework for quickly building beautiful, interactive web applications in **pure Python**.

## Goals

```md section
### Pure Python

Use Python for everything. Don't worry about learning a new language.

### Easy to Learn

Build and share your first app in minutes. No web development experience required.

### Full Flexibility

Remain as flexible as traditional web frameworks. Reflex is easy to use, yet allows for advanced use cases.

Build anything from small data science apps to large, multi-page websites. **This entire site was built and deployed with Reflex!**

### Batteries Included

No need to reach for a bunch of different tools. Reflex handles the user interface, server-side logic, and deployment of your app.
```

## An example: Make it count

Here, we go over a simple counter app that lets the user count up or down.

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
            rx.tabs.trigger(
                "Frontend", value="tab1",
                class_name="tab-style"
            ),
            rx.tabs.trigger(
                "Backend", value="tab2",
                class_name="tab-style"
            ),
            rx.tabs.trigger(
                "Page", value="tab3",
                class_name="tab-style"
            ),
        ),
        rx.tabs.content(
            markdown_with_shiki(
                """The frontend is built declaratively using Reflex components. Components are compiled down to JS and served to the users browser, therefore:

- Only use Reflex components, vars, and var operations when building your UI. Any other logic should be put in your `State` (backend).

- Use `rx.cond` and `rx.foreach` (replaces if statements and for loops), for creating dynamic UIs.
                """,
            ),
            value="tab1",
            class_name="pt-4"
        ),
        rx.tabs.content(
            markdown_with_shiki(
                """Write your backend in the `State` class. Here you can define functions and variables that can be referenced in the frontend. This code runs directly on the server and is not compiled, so there are no special caveats. Here you can use any Python external library and call any method/function.
                """,
            ),
            value="tab2",
            class_name="pt-4"
        ),
        rx.tabs.content(
            markdown_with_shiki(
                f"""Each page is a Python function that returns a Reflex component. You can define multiple pages and navigate between them, see the [Routing]({pages.overview.path}) section for more information.

- Start with a single page and scale to 100s of pages.
                """,
            ),
            value="tab3",
            class_name="pt-4"
        ),
        class_name="text-slate-12 font-normal",
        default_value="tab1",
        value=IntroTabsState.value,
        on_change=lambda x: IntroTabsState.change_value(
            x
        ),
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
            "var(--c-violet-3) !important",
            "transparent",
        ),
        border=rx.cond(
            IntroTabsState.value == "tab2",
            "1px solid var(--c-violet-5)",
            "none !important"
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
            "1px solid var(--c-violet-5)",
            "none !important",
        ),
        background=rx.cond(
            IntroTabsState.value == "tab1",
            "var(--c-violet-3) !important",
            "transparent",
        ),
        class_name="code-block",
    ),
    rx._x.code_block(
        """app = rx.App()
app.add_page(index)""",
        background=rx.cond(
            IntroTabsState.value == "tab3",
            "var(--c-violet-3) !important",
            "transparent",
        ),
        border=rx.cond(
            IntroTabsState.value == "tab3",
            "1px solid var(--c-violet-5)",
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

We begin by importing the `reflex` package (aliased to `rx`). We reference Reflex objects as `rx.*` by convention.

### State

```python
class State(rx.State):
    count: int = 0
```

The state defines all the variables (called **[vars]({vars.base_vars.path})**) in an app that can change, as well as the functions (called **[event_handlers](#event-handlers)**) that change them.

Here our state has a single var, `count`, which holds the current value of the counter. We initialize it to `0`.

### Event Handlers

```python
@rx.event
def increment(self):
    self.count += 1

@rx.event
def decrement(self):
    self.count -= 1
```

Within the state, we define functions, called **event handlers**, that change the state vars.

Event handlers are the only way that we can modify the state in Reflex.
They can be called in response to user actions, such as clicking a button or typing in a text box.
These actions are called **events**.

Our counter app has two event handlers, `increment` and `decrement`.

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

This function defines the app's user interface.

We use different components such as `rx.hstack`, `rx.button`, and `rx.heading` to build the frontend. Components can be nested to create complex layouts, and can be styled using the full power of CSS or [Tailwind CSS]({styling.tailwind.path}).

Reflex comes with [50+ built-in components]({library.path}) to help you get started.
We are actively adding more components. Also, it's easy to [wrap your own React components]({wrapping_react.overview.path}).

```python
rx.heading(State.count, font_size="2em"),
```

Components can reference the app's state vars.
The `rx.heading` component displays the current value of the counter by referencing `State.count`.
All components that reference state will reactively update whenever the state changes.

```python
rx.button(
    "Decrement",
    color_scheme="ruby",
    on_click=State.decrement,
),
```

Components interact with the state by binding events triggers to event handlers.
For example, `on_click` is an event that is triggered when a user clicks a component.

The first button in our app binds its `on_click` event to the `State.decrement` event handler. Similarly the second button binds `on_click` to `State.increment`.

In other words, the sequence goes like this:

- User clicks "increment" on the UI.
- `on_click` event is triggered.
- Event handler `State.increment` is called.
- `State.count` is incremented.
- UI updates to reflect the new value of `State.count`.

### Add pages

Next we define our app and add the counter component to the base route.

```python
app = rx.App()
app.add_page(index)
```

## Next Steps

🎉 And that's it!

We've created a simple, yet fully interactive web app in pure Python.

By continuing with our documentation, you will learn how to build awesome apps with Reflex. Use the sidebar to navigate through the sections, or search (`Ctrl+K` or `Cmd+K`) to quickly find a page.

For a glimpse of the possibilities, check out these resources:

* For a more real-world example, check out either the [dashboard tutorial]({getting_started.dashboard_tutorial.path}) or the [chatapp tutorial]({getting_started.chatapp_tutorial.path}).
* Check out our open-source [templates]({getting_started.open_source_templates.path})!
* We have an AI Builder that can generate full Reflex apps or help with your existing app! Check it out at [Reflex Build]({constants.REFLEX_BUILD_URL})!
* Deploy your app with a single command using [Reflex Cloud]({hosting.deploy_quick_start.path})!

If you want to learn more about how Reflex works, check out the [How Reflex Works]({advanced_onboarding.how_reflex_works.path}) section.

## Join our Community

If you have questions about anything related to Reflex, you're always welcome to ask our community on [GitHub Discussions]({constants.GITHUB_DISCUSSIONS_URL}), [Discord]({constants.DISCORD_URL}), [Forum]({constants.FORUM_URL}), and [X]({constants.TWITTER_URL}).
