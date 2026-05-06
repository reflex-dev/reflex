```python exec
import reflex as rx
```

# Data Dashboard

**~20 min hands-on** · Build a small data dashboard where users can input data that renders in a table and a graph.

This tutorial does not assume any existing Reflex knowledge, but we do recommend checking out the quick [Basics Guide](/docs/getting-started/basics) first. The techniques you'll learn are fundamental to any Reflex app.

This tutorial is divided into several sections:

- **Setup**: Get your machine ready.
- **Overview**: Components and props.
- **Dynamic data with State**: Render data that changes.
- **Add data with a form**: Forms + event handlers.
- **Plot a graph**: Reflex's graphing components.
- **Customize** + **[Full app](#full-app-styled)**: Customize and see the finished code.

## What are you building?

An interactive data dashboard: a table of users, a form to add more, and a bar chart that updates as data changes. Want to skip ahead? Jump to the [Full app](#full-app-styled) at the bottom.

```python exec
import dataclasses
from collections import Counter


@dataclasses.dataclass
class User:
    """The user model."""

    name: str
    email: str
    gender: str


class State5(rx.State):
    users: list[User] = [
        User(name="Danilo Sousa", email="danilo@example.com", gender="Male"),
        User(name="Zahra Ambessa", email="zahra@example.com", gender="Female"),
    ]
    users_for_graph: list[dict] = []

    def add_user(self, form_data: dict):
        self.users.append(User(**form_data))
        self.transform_data()

        return rx.toast.info(
            f"User {form_data['name']} has been added.",
            position="bottom-right",
        )

    def transform_data(self):
        """Transform user gender group data into a format suitable for visualization in graphs."""
        # Count users of each gender group
        gender_counts = Counter(user.gender for user in self.users)

        # Transform into list of dict so it can be used in the graph
        self.users_for_graph = [
            {"name": gender_group, "value": count}
            for gender_group, count in gender_counts.items()
        ]


def show_user5(user: User):
    """Show a user in a table row."""
    return rx.table.row(
        rx.table.cell(user.name),
        rx.table.cell(user.email),
        rx.table.cell(user.gender),
        style={"_hover": {"bg": rx.color("gray", 3)}},
        align="center",
    )


def add_customer_button5() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("plus", size=26),
                rx.text("Add User", size="4"),
            ),
        ),
        rx.dialog.content(
            rx.dialog.title(
                "Add New User",
            ),
            rx.dialog.description(
                "Fill the form with the user's info",
            ),
            rx.form(
                rx.flex(
                    rx.input(placeholder="User Name", name="name", required=True),
                    rx.input(
                        placeholder="user@reflex.dev",
                        name="email",
                    ),
                    rx.select(
                        ["Male", "Female"],
                        placeholder="male",
                        name="gender",
                    ),
                    rx.flex(
                        rx.dialog.close(
                            rx.button(
                                "Cancel",
                                variant="soft",
                                color_scheme="gray",
                            ),
                        ),
                        rx.dialog.close(
                            rx.button("Submit", type="submit"),
                        ),
                        spacing="3",
                        justify="end",
                    ),
                    direction="column",
                    spacing="4",
                ),
                on_submit=State5.add_user,
                reset_on_submit=False,
            ),
            max_width="450px",
        ),
    )


def graph5():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="value",
            fill=rx.color("accent", 9),
            radius=6,
            bar_size=48,
        ),
        rx.recharts.x_axis(
            data_key="name",
            tick_line=False,
            axis_line=False,
            padding={"left": 24, "right": 24},
        ),
        rx.recharts.y_axis(
            tick_line=False,
            axis_line=False,
            allow_decimals=False,
        ),
        rx.recharts.cartesian_grid(
            stroke_dasharray="3 3",
            vertical=False,
            stroke=rx.color("slate", 4),
        ),
        data=State5.users_for_graph,
        width="100%",
        height=200,
        margin={"top": 8, "right": 8, "bottom": 0, "left": 0},
    )
```

```python eval
rx.box(
    rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.text(
                    "Users",
                    size="4",
                    weight="bold",
                    color=rx.color("slate", 12),
                    text_align="left",
                    width="100%",
                ),
                rx.text(
                    "Add customers and watch the chart update.",
                    size="2",
                    color=rx.color("slate", 10),
                    text_align="left",
                    width="100%",
                ),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            add_customer_button5(),
            align="center",
            width="100%",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Name"),
                    rx.table.column_header_cell("Email"),
                    rx.table.column_header_cell("Gender"),
                ),
            ),
            rx.table.body(
                rx.foreach(State5.users, show_user5),
            ),
            variant="surface",
            size="2",
            width="100%",
        ),
        graph5(),
        align="stretch",
        width="100%",
        on_mouse_enter=State5.transform_data,
        spacing="4",
        padding="1.75em 2em",
    ),
    border=f"1px solid {rx.color('slate', 5)}",
    border_radius="12px",
    margin_y="1em",
    background=rx.color("slate", 1),
)
```

## Setup

1. [Install Reflex](/docs/getting-started/installation) if you haven't already.
2. Create a folder called `dashboard_tutorial` and `cd` into it.
3. Run `uv init` and `uv add reflex`.
4. Run `uv run reflex init` and choose template `0` (the blank template).
5. Run `uv run reflex run` to start the app and confirm everything works.

## Overview

### Starter code

The `reflex init` command scaffolds an `rxconfig.py` (app [config](/docs/advanced-onboarding/configuration)), an `assets/` folder for static files, and a `dashboard_tutorial/dashboard_tutorial.py` module containing your app. Open that module and replace its contents — we'll build the app up from scratch.

A minimal Reflex page is just a component function plus an app that registers it:

```python
import reflex as rx


def index() -> rx.Component:
    return rx.text("Hello World!")


app = rx.App()
app.add_page(index)
```

```md alert info
For the rest of the tutorial the `app = rx.App()` and `app.add_page` lines are implied and not shown — we'll come back to them in [Customize](#customize).
```

### Create a table

The `rx.table` component has a `root` that wraps a `header` and a `body`. The header takes `row` → `column_header_cell` components; the body takes `row` → `cell` components holding the actual data. Props like `variant` and `size` customize the look:

```python eval
rx.box(
    rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Name"),
                rx.table.column_header_cell("Email"),
                rx.table.column_header_cell("Gender"),
            ),
        ),
        rx.table.body(
            rx.table.row(
                rx.table.cell("Danilo Sousa"),
                rx.table.cell("danilo@example.com"),
                rx.table.cell("Male"),
            ),
            rx.table.row(
                rx.table.cell("Zahra Ambessa"),
                rx.table.cell("zahra@example.com"),
                rx.table.cell("Female"),
            ),
        ),
        variant="surface",
        size="3",
    ),
    border=f"1px solid {rx.color('slate', 5)}",
    border_radius="12px",
    padding="2em",
)
```

```python
def index() -> rx.Component:
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Name"),
                rx.table.column_header_cell("Email"),
                rx.table.column_header_cell("Gender"),
            ),
        ),
        rx.table.body(
            rx.table.row(
                rx.table.cell("Danilo Sousa"),
                rx.table.cell("danilo@example.com"),
                rx.table.cell("Male"),
            ),
            rx.table.row(
                rx.table.cell("Zahra Ambessa"),
                rx.table.cell("zahra@example.com"),
                rx.table.cell("Female"),
            ),
        ),
        variant="surface",
        size="3",
    )
```

## Dynamic data with State

The table above is static — the rows are hardcoded. To make it dynamic, we move the data onto **state**: a Python class whose fields ([state vars](/docs/state/overview)) hold the app's data and whose methods ([event handlers](/docs/events/events-overview)) mutate them.

We'll model each row as a `User` dataclass so we can access fields by name (`user.name`) instead of by index:

```python
import dataclasses


@dataclasses.dataclass
class User:
    name: str
    email: str
    gender: str


class State(rx.State):
    users: list[User] = [
        User(name="Danilo Sousa", email="danilo@example.com", gender="Male"),
        User(name="Zahra Ambessa", email="zahra@example.com", gender="Female"),
    ]
```

To iterate a list state var, use [`rx.foreach`](/docs/components/rendering-iterables) — it takes an iterable and a function that renders each item. Here `show_user` receives a `User` and returns a `table.row`:

```python
def show_user(user: User) -> rx.Component:
    return rx.table.row(
        rx.table.cell(user.name),
        rx.table.cell(user.email),
        rx.table.cell(user.gender),
    )


def index() -> rx.Component:
    return rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Name"),
                rx.table.column_header_cell("Email"),
                rx.table.column_header_cell("Gender"),
            ),
        ),
        rx.table.body(
            rx.foreach(State.users, show_user),
        ),
        variant="surface",
        size="3",
    )
```

```md alert info
# Why not a `for` loop?

A regular `for` loop runs at compile time, but state vars change at runtime — so the rendered rows wouldn't update. `rx.foreach` tells the compiler to re-render when the state var changes. See [compile-time vs runtime](/docs/getting-started/basics#compile-time-vs.-runtime).
```

```python exec
import dataclasses


@dataclasses.dataclass
class User:
    """The user model."""

    name: str
    email: str
    gender: str


class State2(rx.State):
    users: list[User] = [
        User(name="Danilo Sousa", email="danilo@example.com", gender="Male"),
        User(name="Zahra Ambessa", email="zahra@example.com", gender="Female"),
    ]


def show_user2(user: User):
    """Show a person in a table row."""
    return rx.table.row(
        rx.table.cell(user.name),
        rx.table.cell(user.email),
        rx.table.cell(user.gender),
    )
```

```python eval
rx.box(
    rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Name"),
                rx.table.column_header_cell("Email"),
                rx.table.column_header_cell("Gender"),
            ),
        ),
        rx.table.body(
            rx.foreach(State2.users, show_user2),
        ),
        variant="surface",
        size="3",
    ),
    border=f"1px solid {rx.color('slate', 5)}",
    border_radius="12px",
    padding="2em",
)
```

The table looks the same, but the rows now come from state — next we'll add a form that appends to `State.users` so new rows appear automatically.

## Add data with a form

We build a form using `rx.form`, which takes several components such as `rx.input` and `rx.select`, which represent the form fields that allow you to add information to submit with the form. Check out the [form](/docs/library/forms/form) docs for more information on form components.

The `rx.input` component takes in several props. The `placeholder` prop is the text that is displayed in the input field when it is empty. The `name` prop is the name of the input field, which gets passed through in the dictionary when the form is submitted. The `required` prop is a boolean that determines if the input field is required.

The `rx.select` component takes in a list of options that are displayed in the dropdown. The other props used here are identical to the `rx.input` component.

```python demo
rx.form(
    rx.input(placeholder="User Name", name="name", required=True),
    rx.input(
        placeholder="user@reflex.dev",
        name="email",
    ),
    rx.select(
        ["Male", "Female"],
        placeholder="Male",
        name="gender",
    ),
)
```

This form is all very compact as you can see from the example, so we need to add some styling to make it look better. We can do this by adding a `vstack` component around the form fields. The `vstack` component stacks the form fields vertically. Check out the [layout](/docs/styling/layout) docs for more information on how to layout your app.

```python demo
rx.form(
    rx.vstack(
        rx.input(placeholder="User Name", name="name", required=True),
        rx.input(
            placeholder="user@reflex.dev",
            name="email",
        ),
        rx.select(
            ["Male", "Female"],
            placeholder="Male",
            name="gender",
        ),
    ),
)
```

Now you have probably realised that we have all the form fields, but we have no way to submit the form. We can add a submit button to the form by adding a `rx.button` component to the `vstack` component. The `rx.button` component takes in the text that is displayed on the button and the `type` prop which is the type of button. The `type` prop is set to `submit` so that the form is submitted when the button is clicked.

In addition to this we need a way to update the `users` state variable when the form is submitted. All state changes are handled through functions in the state class, called [event handlers](/docs/events/events-overview).

Components have special props called event triggers, such as `on_submit`, that can be used to make components interactive. Event triggers connect components to event handlers, which update the state. Different event triggers expect the event handler that you hook them up to, to take in different arguments (and some do not take in any arguments).

The `on_submit` event trigger of `rx.form` is hooked up to the `add_user` event handler that is defined in the `State` class. This event trigger expects to pass a `dict`, containing the form data, to the event handler that it is hooked up to. The `add_user` event handler takes in the form data as a dictionary and appends it to the `users` state variable.

```python
class State(rx.State):
    ...

    def add_user(self, form_data: dict):
        self.users.append(User(**form_data))


def form():
    return rx.form(
        rx.vstack(
            rx.input(placeholder="User Name", name="name", required=True),
            rx.input(
                placeholder="user@reflex.dev",
                name="email",
            ),
            rx.select(
                ["Male", "Female"],
                placeholder="Male",
                name="gender",
            ),
            rx.button("Submit", type="submit"),
        ),
        on_submit=State.add_user,
        reset_on_submit=True,
    )
```

Finally we must add the new `form()` component we have defined to the `index()` function so that the form is rendered on the page.

Below is the full code for the app so far. If you try this form out you will see that you can add new users to the table by filling out the form and clicking the submit button. The form data will also appear as a toast (a small window in the corner of the page) on the screen when submitted.

```python exec
class State3(rx.State):
    users: list[User] = [
        User(name="Danilo Sousa", email="danilo@example.com", gender="Male"),
        User(name="Zahra Ambessa", email="zahra@example.com", gender="Female"),
    ]

    def add_user(self, form_data: dict):
        self.users.append(User(**form_data))

        return rx.toast.info(
            f"User has been added: {form_data}.",
            position="bottom-right",
        )


def show_user(user: User):
    """Show a person in a table row."""
    return rx.table.row(
        rx.table.cell(user.name),
        rx.table.cell(user.email),
        rx.table.cell(user.gender),
    )


def form():
    return rx.form(
        rx.vstack(
            rx.input(placeholder="User Name", name="name", required=True),
            rx.input(
                placeholder="user@reflex.dev",
                name="email",
            ),
            rx.select(
                ["Male", "Female"],
                placeholder="Male",
                name="gender",
            ),
            rx.button("Submit", type="submit"),
        ),
        on_submit=State3.add_user,
        reset_on_submit=True,
    )
```

```python eval
rx.vstack(
    form(),
    rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Name"),
                rx.table.column_header_cell("Email"),
                rx.table.column_header_cell("Gender"),
            ),
        ),
        rx.table.body(
            rx.foreach(State3.users, show_user),
        ),
        variant="surface",
        size="3",
    ),
    spacing="4",
    border=f"1px solid {rx.color('slate', 5)}",
    border_radius="12px",
    padding="2em",
)
```

```python
class State(rx.State):
    users: list[User] = [
        User(name="Danilo Sousa", email="danilo@example.com", gender="Male"),
        User(name="Zahra Ambessa", email="zahra@example.com", gender="Female"),
    ]

    def add_user(self, form_data: dict):
        self.users.append(User(**form_data))


def show_user(user: User):
    """Show a person in a table row."""
    return rx.table.row(
        rx.table.cell(user.name),
        rx.table.cell(user.email),
        rx.table.cell(user.gender),
    )


def form():
    return rx.form(
        rx.vstack(
            rx.input(placeholder="User Name", name="name", required=True),
            rx.input(
                placeholder="user@reflex.dev",
                name="email",
            ),
            rx.select(
                ["Male", "Female"],
                placeholder="Male",
                name="gender",
            ),
            rx.button("Submit", type="submit"),
        ),
        on_submit=State.add_user,
        reset_on_submit=True,
    )


def index() -> rx.Component:
    return rx.vstack(
        form(),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Name"),
                    rx.table.column_header_cell("Email"),
                    rx.table.column_header_cell("Gender"),
                ),
            ),
            rx.table.body(
                rx.foreach(State.users, show_user),
            ),
            variant="surface",
            size="3",
        ),
    )
```

### Put the form in a dialog

In Reflex, we like to make the user interaction as intuitive as possible. Placing the form we just constructed in an overlay creates a focused interaction by dimming the background, and ensures a cleaner layout when you have multiple action points such as editing and deleting as well.

We will place the form inside of a `rx.dialog` component (also called a modal). The `rx.dialog.root` contains all the parts of a dialog, and the `rx.dialog.trigger` wraps the control that will open the dialog. In our case the trigger will be an `rx.button` that says "Add User" as shown below.

```python
rx.dialog.trigger(
    rx.button(
        rx.icon("plus", size=26),
        rx.text("Add User", size="4"),
    ),
)
```

After the trigger we have the `rx.dialog.content` which contains everything within our dialog, including a title, a description and our form. The first way to close the dialog is without submitting the form and the second way is to close the dialog by submitting the form as shown below. This requires two `rx.dialog.close` components within the dialog.

```python
(
    rx.dialog.close(
        rx.button(
            "Cancel",
            variant="soft",
            color_scheme="gray",
        ),
    ),
)
rx.dialog.close(
    rx.button("Submit", type="submit"),
)
```

The total code for the dialog with the form in it is below.

```python demo
rx.dialog.root(
    rx.dialog.trigger(
        rx.button(
            rx.icon("plus", size=26),
            rx.text("Add User", size="4"),
        ),
    ),
    rx.dialog.content(
        rx.dialog.title(
            "Add New User",
        ),
        rx.dialog.description(
            "Fill the form with the user's info",
        ),
        rx.form(
            # flex is similar to vstack and used to layout the form fields
            rx.flex(
                rx.input(placeholder="User Name", name="name", required=True),
                rx.input(
                    placeholder="user@reflex.dev",
                    name="email",
                ),
                rx.select(
                    ["Male", "Female"],
                    placeholder="Male",
                    name="gender",
                ),
                rx.flex(
                    rx.dialog.close(
                        rx.button(
                            "Cancel",
                            variant="soft",
                            color_scheme="gray",
                        ),
                    ),
                    rx.dialog.close(
                        rx.button("Submit", type="submit"),
                    ),
                    spacing="3",
                    justify="end",
                ),
                direction="column",
                spacing="4",
            ),
            on_submit=State3.add_user,
            reset_on_submit=False,
        ),
        # max_width is used to limit the width of the dialog
        max_width="450px",
    ),
)
```

At this point we have an app that allows you to add users to a table by filling out a form. The form is placed in a dialog that can be opened by clicking the "Add User" button. We change the name of the component from `form` to `add_customer_button` and update this in our `index` component. The full app so far and code are below.

```python exec
def add_customer_button() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("plus", size=26),
                rx.text("Add User", size="4"),
            ),
        ),
        rx.dialog.content(
            rx.dialog.title(
                "Add New User",
            ),
            rx.dialog.description(
                "Fill the form with the user's info",
            ),
            rx.form(
                rx.flex(
                    rx.input(placeholder="User Name", name="name", required=True),
                    rx.input(
                        placeholder="user@reflex.dev",
                        name="email",
                    ),
                    rx.select(
                        ["Male", "Female"],
                        placeholder="Male",
                        name="gender",
                    ),
                    rx.flex(
                        rx.dialog.close(
                            rx.button(
                                "Cancel",
                                variant="soft",
                                color_scheme="gray",
                            ),
                        ),
                        rx.dialog.close(
                            rx.button("Submit", type="submit"),
                        ),
                        spacing="3",
                        justify="end",
                    ),
                    direction="column",
                    spacing="4",
                ),
                on_submit=State3.add_user,
                reset_on_submit=False,
            ),
            max_width="450px",
        ),
    )
```

```python eval
rx.vstack(
    add_customer_button(),
    rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Name"),
                rx.table.column_header_cell("Email"),
                rx.table.column_header_cell("Gender"),
            ),
        ),
        rx.table.body(
            rx.foreach(State3.users, show_user),
        ),
        variant="surface",
        size="3",
    ),
    spacing="4",
    border=f"1px solid {rx.color('slate', 5)}",
    border_radius="12px",
    padding="2em",
)
```

```python
@dataclasses.dataclass
class User:
    """The user model."""

    name: str
    email: str
    gender: str


class State(rx.State):
    users: list[User] = [
        User(name="Danilo Sousa", email="danilo@example.com", gender="Male"),
        User(name="Zahra Ambessa", email="zahra@example.com", gender="Female"),
    ]

    def add_user(self, form_data: dict):
        self.users.append(User(**form_data))


def show_user(user: User):
    """Show a person in a table row."""
    return rx.table.row(
        rx.table.cell(user.name),
        rx.table.cell(user.email),
        rx.table.cell(user.gender),
    )


def add_customer_button() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("plus", size=26),
                rx.text("Add User", size="4"),
            ),
        ),
        rx.dialog.content(
            rx.dialog.title(
                "Add New User",
            ),
            rx.dialog.description(
                "Fill the form with the user's info",
            ),
            rx.form(
                rx.flex(
                    rx.input(placeholder="User Name", name="name", required=True),
                    rx.input(
                        placeholder="user@reflex.dev",
                        name="email",
                    ),
                    rx.select(
                        ["Male", "Female"],
                        placeholder="Male",
                        name="gender",
                    ),
                    rx.flex(
                        rx.dialog.close(
                            rx.button(
                                "Cancel",
                                variant="soft",
                                color_scheme="gray",
                            ),
                        ),
                        rx.dialog.close(
                            rx.button("Submit", type="submit"),
                        ),
                        spacing="3",
                        justify="end",
                    ),
                    direction="column",
                    spacing="4",
                ),
                on_submit=State.add_user,
                reset_on_submit=False,
            ),
            max_width="450px",
        ),
    )


def index() -> rx.Component:
    return rx.vstack(
        add_customer_button(),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Name"),
                    rx.table.column_header_cell("Email"),
                    rx.table.column_header_cell("Gender"),
                ),
            ),
            rx.table.body(
                rx.foreach(State.users, show_user),
            ),
            variant="surface",
            size="3",
        ),
    )
```

## Plot a graph

Next we'll plot the user data in a graph using Reflex's built-in recharts library, counting users by gender.

### Transform the data

The graphing components in Reflex expect to take in a list of dictionaries. Each dictionary represents a data point on the graph and contains the x and y values. We will create a new event handler in the state called `transform_data` to transform the user data into the format that the graphing components expect. We must also create a new state variable called `users_for_graph` to store the transformed data, which will be used to render the graph.

```python
from collections import Counter


class State(rx.State):
    users: list[User] = []
    users_for_graph: list[dict] = []

    def add_user(self, form_data: dict):
        self.users.append(User(**form_data))
        self.transform_data()

    def transform_data(self):
        """Transform user gender group data into a format suitable for visualization in graphs."""
        # Count users of each gender group
        gender_counts = Counter(user.gender for user in self.users)

        # Transform into list of dict so it can be used in the graph
        self.users_for_graph = [
            {"name": gender_group, "value": count}
            for gender_group, count in gender_counts.items()
        ]
```

As we can see above the `transform_data` event handler uses the `Counter` class from the `collections` module to count the number of users of each gender. We then create a list of dictionaries from this which we set to the state var `users_for_graph`.

Finally we can see that whenever we add a new user through submitting the form and running the `add_user` event handler, we call the `transform_data` event handler to update the `users_for_graph` state variable.

### Render the graph

We use the `rx.recharts.bar_chart` component to render the graph. We pass through the state variable for our graphing data as `data=State.users_for_graph`. We also pass in a `rx.recharts.bar` component which represents the bars on the graph. The `rx.recharts.bar` component takes in the `data_key` prop which is the key in the data dictionary that represents the y value of the bar. The `stroke` and `fill` props are used to set the color of the bars.

The `rx.recharts.bar_chart` component also takes in `rx.recharts.x_axis` and `rx.recharts.y_axis` components which represent the x and y axes of the graph. The `data_key` prop of the `rx.recharts.x_axis` component is set to the key in the data dictionary that represents the x value of the bar. Finally we add `width` and `height` props to set the size of the graph.

```python
def graph():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="value",
            stroke=rx.color("accent", 9),
            fill=rx.color("accent", 8),
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        data=State.users_for_graph,
        width="100%",
        height=250,
    )
```

Finally we add this `graph()` component to our `index()` component so that the graph is rendered on the page. The code for the full app with the graph included is below. If you try this out you will see that the graph updates whenever you add a new user to the table.

```python exec
from collections import Counter


class State4(rx.State):
    users: list[User] = [
        User(name="Danilo Sousa", email="danilo@example.com", gender="Male"),
        User(name="Zahra Ambessa", email="zahra@example.com", gender="Female"),
    ]
    users_for_graph: list[dict] = []

    def add_user(self, form_data: dict):
        self.users.append(User(**form_data))
        self.transform_data()

        return rx.toast.info(
            f"User {form_data['name']} has been added.",
            position="bottom-right",
        )

    def transform_data(self):
        """Transform user gender group data into a format suitable for visualization in graphs."""
        # Count users of each gender group
        gender_counts = Counter(user.gender for user in self.users)

        # Transform into list of dict so it can be used in the graph
        self.users_for_graph = [
            {"name": gender_group, "value": count}
            for gender_group, count in gender_counts.items()
        ]


def add_customer_button() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("plus", size=26),
                rx.text("Add User", size="4"),
            ),
        ),
        rx.dialog.content(
            rx.dialog.title(
                "Add New User",
            ),
            rx.dialog.description(
                "Fill the form with the user's info",
            ),
            rx.form(
                rx.flex(
                    rx.input(placeholder="User Name", name="name", required=True),
                    rx.input(
                        placeholder="user@reflex.dev",
                        name="email",
                    ),
                    rx.select(
                        ["Male", "Female"],
                        placeholder="Male",
                        name="gender",
                    ),
                    rx.flex(
                        rx.dialog.close(
                            rx.button(
                                "Cancel",
                                variant="soft",
                                color_scheme="gray",
                            ),
                        ),
                        rx.dialog.close(
                            rx.button("Submit", type="submit"),
                        ),
                        spacing="3",
                        justify="end",
                    ),
                    direction="column",
                    spacing="4",
                ),
                on_submit=State4.add_user,
                reset_on_submit=False,
            ),
            max_width="450px",
        ),
    )


def graph():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="value",
            stroke=rx.color("accent", 9),
            fill=rx.color("accent", 8),
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        data=State4.users_for_graph,
        width="100%",
        height=250,
    )
```

```python eval
rx.vstack(
    add_customer_button(),
    rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Name"),
                rx.table.column_header_cell("Email"),
                rx.table.column_header_cell("Gender"),
            ),
        ),
        rx.table.body(
            rx.foreach(State4.users, show_user),
        ),
        variant="surface",
        size="3",
    ),
    graph(),
    spacing="4",
    border=f"1px solid {rx.color('slate', 5)}",
    border_radius="12px",
    padding="2em",
)
```

```python
from collections import Counter


class State(rx.State):
    users: list[User] = [
        User(name="Danilo Sousa", email="danilo@example.com", gender="Male"),
        User(name="Zahra Ambessa", email="zahra@example.com", gender="Female"),
    ]
    users_for_graph: list[dict] = []

    def add_user(self, form_data: dict):
        self.users.append(User(**form_data))
        self.transform_data()

    def transform_data(self):
        """Transform user gender group data into a format suitable for visualization in graphs."""
        # Count users of each gender group
        gender_counts = Counter(user.gender for user in self.users)

        # Transform into list of dict so it can be used in the graph
        self.users_for_graph = [
            {"name": gender_group, "value": count}
            for gender_group, count in gender_counts.items()
        ]


def show_user(user: User):
    """Show a person in a table row."""
    return rx.table.row(
        rx.table.cell(user.name),
        rx.table.cell(user.email),
        rx.table.cell(user.gender),
    )


def add_customer_button() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("plus", size=26),
                rx.text("Add User", size="4"),
            ),
        ),
        rx.dialog.content(
            rx.dialog.title(
                "Add New User",
            ),
            rx.dialog.description(
                "Fill the form with the user's info",
            ),
            rx.form(
                rx.flex(
                    rx.input(placeholder="User Name", name="name", required=True),
                    rx.input(
                        placeholder="user@reflex.dev",
                        name="email",
                    ),
                    rx.select(
                        ["Male", "Female"],
                        placeholder="male",
                        name="gender",
                    ),
                    rx.flex(
                        rx.dialog.close(
                            rx.button(
                                "Cancel",
                                variant="soft",
                                color_scheme="gray",
                            ),
                        ),
                        rx.dialog.close(
                            rx.button("Submit", type="submit"),
                        ),
                        spacing="3",
                        justify="end",
                    ),
                    direction="column",
                    spacing="4",
                ),
                on_submit=State.add_user,
                reset_on_submit=False,
            ),
            max_width="450px",
        ),
    )


def graph():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="value",
            stroke=rx.color("accent", 9),
            fill=rx.color("accent", 8),
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        data=State.users_for_graph,
        width="100%",
        height=250,
    )


def index() -> rx.Component:
    return rx.vstack(
        add_customer_button(),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Name"),
                    rx.table.column_header_cell("Email"),
                    rx.table.column_header_cell("Gender"),
                ),
            ),
            rx.table.body(
                rx.foreach(State.users, show_user),
            ),
            variant="surface",
            size="3",
        ),
        graph(),
    )
```

If you run the app locally with no seed users, the graph is empty until you add one — `transform_data` only runs when a user is added. The next section fixes that by calling it on page load.

## Customize

### Revisit `app.add_page`

At the beginning of this tutorial we mentioned that the `app.add_page` function is required for every Reflex app. This function is used to add a component to a page.

The `app.add_page` currently looks like this `app.add_page(index)`. We could change the route that the page renders on by setting the `route` prop such as `route="/custom-route"`, this would change the route to `http://localhost:3000/custom-route` for this page.

We can also set a `title` to be shown in the browser tab and a `description` as shown in search results.

To solve the problem we had above about our graph not loading when the page loads, we can use `on_load` inside of `app.add_page` to call the `transform_data` event handler when the page loads. This would look like `on_load=State.transform_data`. Below see what our `app.add_page` would look like with some of the changes above added.

```python eval
rx.vstack(
    add_customer_button(),
    rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Name"),
                rx.table.column_header_cell("Email"),
                rx.table.column_header_cell("Gender"),
            ),
        ),
        rx.table.body(
            rx.foreach(State4.users, show_user),
        ),
        variant="surface",
        size="3",
    ),
    graph(),
    on_mouse_enter=State4.transform_data,
    spacing="4",
    border=f"1px solid {rx.color('slate', 5)}",
    border_radius="12px",
    padding="2em",
)
```

```python
app.add_page(
    index,
    title="Customer Data App",
    description="A simple app to manage customer data.",
    on_load=State.transform_data,
)
```

### Revisit `rx.App()`

At the beginning of the tutorial we also mentioned that we defined our app using `app=rx.App()`. We can also pass in some props to the `rx.App` component to customize the app.

The most important one is `theme` which allows you to customize the look and feel of the app. The `theme` prop takes in an `rx.theme` component which has several props that can be set.

The `radius` prop sets the global radius value for the app that is inherited by all components that have a `radius` prop. It can be overwritten locally for a specific component by manually setting the `radius` prop.

The `accent_color` prop sets the accent color of the app. See the [theme docs](/docs/library/other/theme) for the full list of options.

To see other props that can be set at the app level check out this [documentation](/docs/styling/theming)

```python
app = rx.App(
    theme=rx.theme(radius="full", accent_color="grass"),
)
```

The theme applies at the app level, so you'll need to run locally to see it in action.

## Full app styled

Finally let's make some styling updates. We will add hover styling to the table rows and center the table inside `show_user` with `style={"_hover": {"bg": rx.color("gray", 3)}}, align="center"`.

In addition, we will add some `width="100%"` and `align="center"` to the `index()` component to center the items on the page and ensure they stretch the full width of the page.

Check out the full code and interactive app below:

```python eval
rx.box(
    rx.vstack(
        rx.hstack(
            rx.vstack(
                rx.text(
                    "Users",
                    size="4",
                    weight="bold",
                    color=rx.color("slate", 12),
                    text_align="left",
                    width="100%",
                ),
                rx.text(
                    "Add customers and watch the chart update.",
                    size="2",
                    color=rx.color("slate", 10),
                    text_align="left",
                    width="100%",
                ),
                spacing="1",
                align="start",
            ),
            rx.spacer(),
            add_customer_button5(),
            align="center",
            width="100%",
        ),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Name"),
                    rx.table.column_header_cell("Email"),
                    rx.table.column_header_cell("Gender"),
                ),
            ),
            rx.table.body(
                rx.foreach(State5.users, show_user5),
            ),
            variant="surface",
            size="2",
            width="100%",
        ),
        graph5(),
        align="stretch",
        width="100%",
        on_mouse_enter=State5.transform_data,
        spacing="4",
        padding="1.75em 2em",
    ),
    border=f"1px solid {rx.color('slate', 5)}",
    border_radius="12px",
    margin_y="1em",
    background=rx.color("slate", 1),
)
```

```python
import reflex as rx
from collections import Counter


@dataclasses.dataclass
class User:
    """The user model."""

    name: str
    email: str
    gender: str


class State(rx.State):
    users: list[User] = [
        User(name="Danilo Sousa", email="danilo@example.com", gender="Male"),
        User(name="Zahra Ambessa", email="zahra@example.com", gender="Female"),
    ]
    users_for_graph: list[dict] = []

    def add_user(self, form_data: dict):
        self.users.append(User(**form_data))
        self.transform_data()

    def transform_data(self):
        """Transform user gender group data into a format suitable for visualization in graphs."""
        # Count users of each gender group
        gender_counts = Counter(user.gender for user in self.users)

        # Transform into list of dict so it can be used in the graph
        self.users_for_graph = [
            {"name": gender_group, "value": count}
            for gender_group, count in gender_counts.items()
        ]


def show_user(user: User):
    """Show a user in a table row."""
    return rx.table.row(
        rx.table.cell(user.name),
        rx.table.cell(user.email),
        rx.table.cell(user.gender),
        style={"_hover": {"bg": rx.color("gray", 3)}},
        align="center",
    )


def add_customer_button() -> rx.Component:
    return rx.dialog.root(
        rx.dialog.trigger(
            rx.button(
                rx.icon("plus", size=26),
                rx.text("Add User", size="4"),
            ),
        ),
        rx.dialog.content(
            rx.dialog.title(
                "Add New User",
            ),
            rx.dialog.description(
                "Fill the form with the user's info",
            ),
            rx.form(
                rx.flex(
                    rx.input(placeholder="User Name", name="name", required=True),
                    rx.input(
                        placeholder="user@reflex.dev",
                        name="email",
                    ),
                    rx.select(
                        ["Male", "Female"],
                        placeholder="male",
                        name="gender",
                    ),
                    rx.flex(
                        rx.dialog.close(
                            rx.button(
                                "Cancel",
                                variant="soft",
                                color_scheme="gray",
                            ),
                        ),
                        rx.dialog.close(
                            rx.button("Submit", type="submit"),
                        ),
                        spacing="3",
                        justify="end",
                    ),
                    direction="column",
                    spacing="4",
                ),
                on_submit=State.add_user,
                reset_on_submit=False,
            ),
            max_width="450px",
        ),
    )


def graph():
    return rx.recharts.bar_chart(
        rx.recharts.bar(
            data_key="value",
            fill=rx.color("accent", 9),
            radius=6,
            bar_size=48,
        ),
        rx.recharts.x_axis(
            data_key="name",
            tick_line=False,
            axis_line=False,
            padding={"left": 24, "right": 24},
        ),
        rx.recharts.y_axis(
            tick_line=False,
            axis_line=False,
            allow_decimals=False,
        ),
        rx.recharts.cartesian_grid(
            stroke_dasharray="3 3",
            vertical=False,
            stroke=rx.color("slate", 4),
        ),
        data=State.users_for_graph,
        width="100%",
        height=200,
        margin={"top": 8, "right": 8, "bottom": 0, "left": 0},
    )


def index() -> rx.Component:
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.vstack(
                    rx.text(
                        "Users",
                        size="4",
                        weight="bold",
                        color=rx.color("slate", 12),
                        text_align="left",
                        width="100%",
                    ),
                    rx.text(
                        "Add customers and watch the chart update.",
                        size="2",
                        color=rx.color("slate", 10),
                        text_align="left",
                        width="100%",
                    ),
                    spacing="1",
                    align="start",
                ),
                rx.spacer(),
                add_customer_button(),
                align="center",
                width="100%",
            ),
            rx.table.root(
                rx.table.header(
                    rx.table.row(
                        rx.table.column_header_cell("Name"),
                        rx.table.column_header_cell("Email"),
                        rx.table.column_header_cell("Gender"),
                    ),
                ),
                rx.table.body(
                    rx.foreach(State.users, show_user),
                ),
                variant="surface",
                size="2",
                width="100%",
            ),
            graph(),
            align="stretch",
            width="100%",
            spacing="4",
            padding="1.75em 2em",
        ),
        border=f"1px solid {rx.color('slate', 5)}",
        border_radius="12px",
        margin_y="1em",
        background=rx.color("slate", 1),
    )


app = rx.App(
    theme=rx.theme(radius="full", accent_color="grass"),
)

app.add_page(
    index,
    title="Customer Data App",
    description="A simple app to manage customer data.",
    on_load=State.transform_data,
)
```

## Recap

You built:

- A table that displays user data.
- A form (inside a dialog) to add new users.
- A bar chart that visualizes the distribution.

Along the way you learned:

- **State** — how to store data that changes over time.
- **Events** — how to respond to user actions and update the UI.
- **Styling** — tweaking theme, layout, and hover states.
