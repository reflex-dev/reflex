```python exec
import reflex as rx
from pcweb.pages import docs
```

# Tutorial: Data Dashboard

During this tutorial you will build a small data dashboard, where you can input data and it will be rendered in table and a graph. This tutorial does not assume any existing Reflex knowledge, but we do recommend checking out the quick [Basics Guide]({docs.getting_started.basics.path}) first. 

The techniques you’ll learn in the tutorial are fundamental to building any Reflex app, and fully understanding it will give you a deep understanding of Reflex.


This tutorial is divided into several sections:

- **Setup for the Tutorial**: A starting point to follow the tutorial
- **Overview**: The fundamentals of Reflex UI (components and props)
- **Showing Dynamic Data**: How to use State to render data that will change in your app.
- **Add Data to your App**: Using a Form to let a user add data to your app and introduce event handlers.
- **Plotting Data in a Graph**: How to use Reflex's graphing components.
- **Final Cleanup and Conclusion**: How to further customize your app and add some extra styling to it.

### What are you building?

In this tutorial, you are building an interactive data dashboard with Reflex.

You can see what the finished app and code will look like here:


```python exec
from collections import Counter

class User(rx.Base):
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
            {
                "name": gender_group,
                "value": count
            }
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
                    rx.input(
                        placeholder="User Name", name="name", required=True
                    ),
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
                            rx.button(
                                "Submit", type="submit"
                            ),
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
            stroke=rx.color("accent", 9),
            fill=rx.color("accent", 8),
        ),
        rx.recharts.x_axis(data_key="name"),
        rx.recharts.y_axis(),
        data=State5.users_for_graph,
        width="100%",
        height=250,
    )
```

```python eval
rx.vstack(
        add_customer_button5(),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Name"),
                    rx.table.column_header_cell("Email"),
                    rx.table.column_header_cell("Gender"),
                ),
            ),
            rx.table.body(
                rx.foreach(
                    State5.users, show_user5
                ),
            ),
            variant="surface",
            size="3",
            width="100%",
        ),
        graph5(),
        align="center",
        width="100%",
        on_mouse_enter=State5.transform_data,
        border_width="2px",
        border_radius="10px",
        padding="1em",
    )
```

```python
import reflex as rx
from collections import Counter

class User(rx.Base):
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
            {
                "name": gender_group,
                "value": count
            }
            for gender_group, count in gender_counts.items()
        ]
        

def show_user(user: User):
    """Show a user in a table row."""
    return rx.table.row(
        rx.table.cell(user.name),
        rx.table.cell(user.email),
        rx.table.cell(user.gender),
        style={
            "_hover": {
                "bg": rx.color("gray", 3)
            }
        },
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
                    rx.input(
                        placeholder="User Name", name="name", required=True
                    ),
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
                            rx.button(
                                "Submit", type="submit"
                            ),
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
                rx.foreach(
                    State.users, show_user
                ),
            ),
            variant="surface",
            size="3",
            width="100%",
        ),
        graph(),
        align="center",
        width="100%",
    )


app = rx.App(
    theme=rx.theme(
        radius="full", accent_color="grass"
    ),
)

app.add_page(
    index,
    title="Customer Data App",
    description="A simple app to manage customer data.",
    on_load=State.transform_data,
)
```

Don't worry if you don't understand the code above, in this tutorial we are going to walk you through the whole thing step by step.


## Setup for the tutorial

Check out the [installation docs]({docs.getting_started.installation.path}) to get Reflex set up on your machine. Follow these to create a folder called `dashboard_tutorial`, which you will `cd` into and `pip install reflex`.

We will choose template `0` when we run `reflex init` to get the blank template. Finally run `reflex run` to start the app and confirm everything is set up correctly.


## Overview

Now that you’re set up, let’s get an overview of Reflex!

### Inspecting the starter code

Within our `dashboard_tutorial` folder we just `cd`'d into, there is a `rxconfig.py` file that contains the configuration for our Reflex app. (Check out the [config docs]({docs.advanced_onboarding.configuration.path}) for more information)

There is also an `assets` folder where static files such as images and stylesheets can be placed to be referenced within your app. ([asset docs]({docs.assets.overview.path}) for more information)

Most importantly there is a folder also called `dashboard_tutorial` which contains all the code for your app. Inside of this folder there is a file named `dashboard_tutorial.py`. To begin this tutorial we will delete all the code in this file so that we can start from scratch and explain every step as we go.

The first thing we need to do is import `reflex`. Once we have done this we can create a component, which is a reusable piece of user interface code. Components are used to render, manage, and update the UI elements in your application. 

Let's look at the example below. Here we have a function called `index` that returns a `text` component (an in-built Reflex UI component) that displays the text "Hello World!".

Next we define our app using `app = rx.App()` and add the component we just defined (`index`) to a page using `app.add_page(index)`. The function name (in this example `index`) which defines the component, must be what we pass into the `add_page`. The definition of the app and adding a component to a page are required for every Reflex app.

```python
import reflex as rx


def index() -> rx.Component:
    return rx.text("Hello World!")

app = rx.App()
app.add_page(index)
```

This code will render a page with the text "Hello World!" when you run your app like below:

```python eval
rx.text("Hello World!", 
    border_width="2px",
    border_radius="10px",
    padding="1em"
)
```

```md alert info
For the rest of the tutorial the `app=rx.App()` and `app.add_page` will be implied and not shown in the code snippets.
```

### Creating a table

Let's create a new component that will render a table. We will use the `table` component to do this. The `table` component has a `root`, which takes in a `header` and a `body`, which in turn take in `row` components. The `row` component takes in `cell` components which are the actual data that will be displayed in the table.

```python eval
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
        border_width="2px",
        border_radius="10px",
        padding="1em",
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
    )
```

Components in Reflex have `props`, which can be used to customize the component and are passed in as keyword arguments to the component function. 

The `rx.table.root` component has for example the `variant` and `size` props, which customize the table as seen below.

```python eval
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
        border_width="2px",
        border_radius="10px",
        padding="1em",
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

## Showing dynamic data (State)

Up until this point all the data we are showing in the app is static. This is not very useful for a data dashboard. We need to be able to show dynamic data that can be added to and updated.

This is where `State` comes in. `State` is a Python class that stores variables that can change when the app is running, as well as the functions that can change those variables.

To define a state class, subclass `rx.State` and define fields that store the state of your app. The state variables (vars) should have a type annotation, and can be initialized with a default value. Check out the [basics]({docs.getting_started.basics.path}) section for a simple example of how state works.


In the example below we define a `State` class called `State` that has a variable called `users` that is a list of lists of strings. Each list in the `users` list represents a user and contains their name, email and gender.

```python
class State(rx.State):
    users: list[list[str]] = [
        ["Danilo Sousa", "danilo@example.com", "Male"],
        ["Zahra Ambessa", "zahra@example.com", "Female"],
    ]
```

To iterate over a state var that is a list, we use the [`rx.foreach`]({docs.components.rendering_iterables.path}) function to render a list of components. The `rx.foreach` component takes an `iterable` (list, tuple or dict) and a `function` that renders each item in the `iterable`.

```md alert info
# Why can we not just splat this in a `for` loop
You might be wondering why a `foreach` is even needed to render this state variable and why we cannot just splat a `for` loop. Check out this [documentation]({docs.getting_started.basics.path}#compile-time-vs.-runtime-(important)) to learn why.
```

Here the render function is `show_user` which takes in a single user and returns a `table.row` component that displays the users name, email and gender.

```python exec
class State1(rx.State):
    users: list[list[str]] = [
        ["Danilo Sousa", "danilo@example.com", "Male"],
        ["Zahra Ambessa", "zahra@example.com", "Female"],
    ]

def show_user1(person: list):
    """Show a person in a table row."""
    return rx.table.row(
        rx.table.cell(person[0]),
        rx.table.cell(person[1]),
        rx.table.cell(person[2]),
    )
```

```python eval
rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Name"),
                rx.table.column_header_cell("Email"),
                rx.table.column_header_cell("Gender"),
            ),
        ),
        rx.table.body(
            rx.foreach(
                State1.users, show_user1
            ),
        ),
        variant="surface",
        size="3",
        border_width="2px",
        border_radius="10px",
        padding="1em",
)
```


```python
class State(rx.State):
    users: list[list[str]] = [
        ["Danilo Sousa", "danilo@example.com", "Male"],
        ["Zahra Ambessa", "zahra@example.com", "Female"],
    ]

def show_user(person: list):
    """Show a person in a table row."""
    return rx.table.row(
        rx.table.cell(person[0]),
        rx.table.cell(person[1]),
        rx.table.cell(person[2]),
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
            rx.foreach(
                State.users, show_user
            ),
        ),
        variant="surface",
        size="3",
)
```

As you can see the output above looks the same as before, except now the data is no longer static and can change with user input to the app.

### Using a proper class structure for our data

So far our data has been defined in a list of lists, where the data is accessed by index i.e. `user[0]`, `user[1]`. This is not very maintainable as our app gets bigger. 

A better way to structure our data in Reflex is to use a class to represent a user. This way we can access the data using attributes i.e. `user.name`, `user.email`.

In Reflex when we create these classes to showcase our data, the class must inherit from `rx.Base`.

`rx.Base` is also necessary if we want to have a state var that is an iterable with different types. For example if we wanted to have `age` as an `int` we would have to use `rx.base` as we could not do this with a state var defined as `list[list[str]]`. 

The `show_user` render function is also updated to access the data by named attributes, instead of indexing.

```python exec
class User(rx.Base):
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
rx.table.root(
        rx.table.header(
            rx.table.row(
                rx.table.column_header_cell("Name"),
                rx.table.column_header_cell("Email"),
                rx.table.column_header_cell("Gender"),
            ),
        ),
        rx.table.body(
            rx.foreach(
                State2.users, show_user2
            ),
        ),
        variant="surface",
        size="3",
        border_width="2px",
        border_radius="10px",
        padding="1em",
)
```


```python
class User(rx.Base):
    """The user model."""

    name: str
    email: str
    gender: str


class State(rx.State):
    users: list[User] = [
        User(name="Danilo Sousa", email="danilo@example.com", gender="Male"),
        User(name="Zahra Ambessa", email="zahra@example.com", gender="Female"),
    ]

def show_user(user: User):
    """Show a person in a table row."""
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
            rx.foreach(
                State.users, show_user
            ),
        ),
        variant="surface",
        size="3",
)
```


Next let's add a form to the app so we can add new users to the table.


## Using a Form to Add Data 

We build a form using `rx.form`, which takes several components such as `rx.input` and `rx.select`, which represent the form fields that allow you to add information to submit with the form. Check out the [form]({docs.library.forms.form.path}) docs for more information on form components.

The `rx.input` component takes in several props. The `placeholder` prop is the text that is displayed in the input field when it is empty. The `name` prop is the name of the input field, which gets passed through in the dictionary when the form is submitted. The `required` prop is a boolean that determines if the input field is required.

The `rx.select` component takes in a list of options that are displayed in the dropdown. The other props used here are identical to the `rx.input` component.

```python demo
rx.form(
    rx.input(
        placeholder="User Name", name="name", required=True
    ),
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

This form is all very compact as you can see from the example, so we need to add some styling to make it look better. We can do this by adding a `vstack` component around the form fields. The `vstack` component stacks the form fields vertically. Check out the [layout]({docs.styling.layout.path}) docs for more information on how to layout your app.


```python demo
rx.form(
    rx.vstack(
        rx.input(
            placeholder="User Name", name="name", required=True
        ),
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

In addition to this we need a way to update the `users` state variable when the form is submitted. All state changes are handled through functions in the state class, called [event handlers]({docs.events.events_overview.path}).

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
            rx.input(
                placeholder="User Name", name="name", required=True
            ),
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
            rx.input(
                placeholder="User Name", name="name", required=True
            ),
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
            rx.foreach(
                State3.users, show_user
            ),
        ),
        variant="surface",
        size="3",
    ),
    border_width="2px",
    border_radius="10px",
    padding="1em",
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
            rx.input(
                placeholder="User Name", name="name", required=True
            ),
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
                rx.foreach(
                    State.users, show_user
                ),
            ),
            variant="surface",
            size="3",
        ),
    )
```


### Putting the Form in an Overlay

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
rx.dialog.close(
    rx.button(
        "Cancel",
        variant="soft",
        color_scheme="gray",
    ),
),
rx.dialog.close(
    rx.button(
        "Submit", type="submit"
    ),
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
                rx.input(
                    placeholder="User Name", name="name", required=True
                ),
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
                        rx.button(
                            "Submit", type="submit"
                        ),
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
                    rx.input(
                        placeholder="User Name", name="name", required=True
                    ),
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
                            rx.button(
                                "Submit", type="submit"
                            ),
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
            rx.foreach(
                State3.users, show_user
            ),
        ),
        variant="surface",
        size="3",
    ),
    border_width="2px",
    border_radius="10px",
    padding="1em",
)
```

```python
class User(rx.Base):
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
                    rx.input(
                        placeholder="User Name", name="name", required=True
                    ),
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
                            rx.button(
                                "Submit", type="submit"
                            ),
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
                rx.foreach(
                    State.users, show_user
                ),
            ),
            variant="surface",
            size="3",
        ),
    )
```


## Plotting Data in a Graph

The last part of this tutorial is to plot the user data in a graph. We will use Reflex's built-in graphing library recharts to plot the number of users of each gender. 

### Transforming the data for the graph

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
            {
                "name": gender_group,
                "value": count
            }
            for gender_group, count in gender_counts.items()
        ]
```

As we can see above the `transform_data` event handler uses the `Counter` class from the `collections` module to count the number of users of each gender. We then create a list of dictionaries from this which we set to the state var `users_for_graph`. 

Finally we can see that whenever we add a new user through submitting the form and running the `add_user` event handler, we call the `transform_data` event handler to update the `users_for_graph` state variable.

### Rendering the graph

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
            {
                "name": gender_group,
                "value": count
            }
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
                    rx.input(
                        placeholder="User Name", name="name", required=True
                    ),
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
                            rx.button(
                                "Submit", type="submit"
                            ),
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
            rx.foreach(
                State4.users, show_user
            ),
        ),
        variant="surface",
        size="3",
    ),
    graph(),
    border_width="2px",
    border_radius="10px",
    padding="1em",
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
            {
                "name": gender_group,
                "value": count
            }
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
                    rx.input(
                        placeholder="User Name", name="name", required=True
                    ),
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
                            rx.button(
                                "Submit", type="submit"
                            ),
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
                rx.foreach(
                    State.users, show_user
                ),
            ),
            variant="surface",
            size="3",
        ),
        graph(),
    )
```

One thing you may have noticed about your app is that the graph does not appear initially when you run the app, and that you must add a user to the table for it to first appear. This occurs because the `transform_data` event handler is only called when a user is added to the table. In the next section we will explore a solution to this.


## Final Cleanup

### Revisiting app.add_page

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
            rx.foreach(
                State4.users, show_user
            ),
        ),
        variant="surface",
        size="3",
    ),
    graph(),
    on_mouse_enter=State4.transform_data,
    border_width="2px",
    border_radius="10px",
    padding="1em",
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

### Revisiting app=rx.App()

At the beginning of the tutorial we also mentioned that we defined our app using `app=rx.App()`. We can also pass in some props to the `rx.App` component to customize the app.

The most important one is `theme` which allows you to customize the look and feel of the app. The `theme` prop takes in an `rx.theme` component which has several props that can be set. 

The `radius` prop sets the global radius value for the app that is inherited by all components that have a `radius` prop. It can be overwritten locally for a specific component by manually setting the `radius` prop.

The `accent_color` prop sets the accent color of the app. Check out other options for the accent color [here]({docs.library.other.theme.path}).

To see other props that can be set at the app level check out this [documentation]({docs.styling.theming.path})

```python
app = rx.App(
    theme=rx.theme(
        radius="full", accent_color="grass"
    ),
)
```

Unfortunately in this tutorial here we cannot actually apply this to the live example on the page, but if you copy and paste the code below into a reflex app locally you can see it in action.



## Conclusion

Finally let's make some final styling updates to our app. We will add some hover styling to the table rows and center the table inside the `show_user` with `style=\{"_hover": \{"bg": rx.color("gray", 3)}}, align="center"`.

In addition, we will add some `width="100%"` and `align="center"` to the `index()` component to center the items on the page and ensure they stretch the full width of the page.

Check out the full code and interactive app below:

```python eval
rx.vstack(
        add_customer_button5(),
        rx.table.root(
            rx.table.header(
                rx.table.row(
                    rx.table.column_header_cell("Name"),
                    rx.table.column_header_cell("Email"),
                    rx.table.column_header_cell("Gender"),
                ),
            ),
            rx.table.body(
                rx.foreach(
                    State5.users, show_user5
                ),
            ),
            variant="surface",
            size="3",
            width="100%",
        ),
        graph5(),
        align="center",
        width="100%",
        on_mouse_enter=State5.transform_data,
        border_width="2px",
        border_radius="10px",
        padding="1em",
    )
```


```python
import reflex as rx
from collections import Counter

class User(rx.Base):
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
            {
                "name": gender_group,
                "value": count
            }
            for gender_group, count in gender_counts.items()
        ]
        

def show_user(user: User):
    """Show a user in a table row."""
    return rx.table.row(
        rx.table.cell(user.name),
        rx.table.cell(user.email),
        rx.table.cell(user.gender),
        style={
            "_hover": {
                "bg": rx.color("gray", 3)
            }
        },
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
                    rx.input(
                        placeholder="User Name", name="name", required=True
                    ),
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
                            rx.button(
                                "Submit", type="submit"
                            ),
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
                rx.foreach(
                    State.users, show_user
                ),
            ),
            variant="surface",
            size="3",
            width="100%",
        ),
        graph(),
        align="center",
        width="100%",
    )


app = rx.App(
    theme=rx.theme(
        radius="full", accent_color="grass"
    ),
)

app.add_page(
    index,
    title="Customer Data App",
    description="A simple app to manage customer data.",
    on_load=State.transform_data,
)
```

And that is it for your first dashboard tutorial. In this tutorial we have created 

- a table to display user data
- a form to add new users to the table
- a dialog to showcase the form
- a graph to visualize the user data

In addition to the above we have we have 

- explored state to allow you to show dynamic data that changes over time
- explored events to allow you to make your app interactive and respond to user actions
- added styling to the app to make it look better



## Advanced Section (Hooking this up to a Database)

Coming Soon!