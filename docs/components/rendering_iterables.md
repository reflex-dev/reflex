```python exec
import reflex as rx

from pcweb.pages import docs
```

# Rendering Iterables

Recall again from the [basics]({docs.getting_started.basics.path}) that we cannot use Python `for` loops when referencing state vars in Reflex. Instead, use the `rx.foreach` component to render components from a collection of data.

For dynamic content that should automatically scroll to show the newest items, consider using the [auto scroll]({docs.library.dynamic_rendering.auto_scroll.path}) component together with `rx.foreach`.

```python demo exec
class IterState(rx.State):
    color: list[str] = [
        "red",
        "green",
        "blue",
    ]


def colored_box(color: str):
    return rx.button(color, background_color=color)


def dynamic_buttons():
    return rx.vstack(
        rx.foreach(IterState.color, colored_box),
    )

```

Here's the same example using a lambda function.

```python
def dynamic_buttons():
    return rx.vstack(
        rx.foreach(IterState.color, lambda color: colored_box(color)),
    )
```

You can also use lambda functions directly with components without defining a separate function.

```python
def dynamic_buttons():
    return rx.vstack(
        rx.foreach(IterState.color, lambda color: rx.button(color, background_color=color)),
    )
```

In this first simple example we iterate through a `list` of colors and render a dynamic number of buttons.

The first argument of the `rx.foreach` function is the state var that you want to iterate through. The second argument is a function that takes in an item from the data and returns a component. In this case, the `colored_box` function takes in a color and returns a button with that color.

## For vs Foreach

```md definition
# Regular For Loop
* Use when iterating over constants.

# Foreach
* Use when iterating over state vars.
```

The above example could have been written using a regular Python `for` loop, since the data is constant.

```python demo exec
colors = ["red", "green", "blue"]
def dynamic_buttons_for():
    return rx.vstack(
        [colored_box(color) for color in colors],
    )
```

However, as soon as you need the data to be dynamic, you must use `rx.foreach`.

```python demo exec
class DynamicIterState(rx.State):
    color: list[str] = [
        "red",
        "green",
        "blue",
    ]

    def add_color(self, form_data):
        self.color.append(form_data["color"])

def dynamic_buttons_foreach():
    return rx.vstack(
        rx.foreach(DynamicIterState.color, colored_box),
        rx.form(
            rx.input(name="color", placeholder="Add a color"),
            rx.button("Add"),
            on_submit=DynamicIterState.add_color,
        )
    )
```

## Render Function

The function to render each item can be defined either as a separate function or as a lambda function. In the example below, we define the function `colored_box` separately and pass it to the `rx.foreach` function. 

```python demo exec
class IterState2(rx.State):
    color: list[str] = [
        "red",
        "green",
        "blue",
    ]

def colored_box(color: rx.Var[str]):
    return rx.button(color, background_color=color)

def dynamic_buttons2():
    return rx.vstack(
        rx.foreach(IterState2.color, colored_box),
    )

```

Notice that the type annotation for the `color` parameter in the `colored_box` function is `rx.Var[str]` (rather than just `str`). This is because the `rx.foreach` function passes the item as a `Var` object, which is a wrapper around the actual value. This is what allows us to compile the frontend without knowing the actual value of the state var (which is only known at runtime).

## Enumerating Iterables

The function can also take an index as a second argument, meaning that we can enumerate through data as shown in the example below.

```python demo exec
class IterIndexState(rx.State):
    color: list[str] = [
        "red",
        "green",
        "blue",
    ]


def create_button(color: rx.Var[str], index: int):
    return rx.box(
        rx.button(f"{index + 1}. {color}"),
        padding_y="0.5em",
    )

def enumerate_foreach():
    return rx.vstack(
        rx.foreach(
            IterIndexState.color,
            create_button
        ),
    )
```

Here's the same example using a lambda function.

```python
def enumerate_foreach():
    return rx.vstack(
        rx.foreach(
            IterIndexState.color,
            lambda color, index: create_button(color, index)
        ),
    )
```

## Iterating Dictionaries

We can iterate through a `dict` using a `foreach`. When the dict is passed through to the function that renders each item, it is presented as a list of key-value pairs `[("sky", "blue"), ("balloon", "red"), ("grass", "green")]`.

```python demo exec
class SimpleDictIterState(rx.State):
    color_chart: dict[str, str] = {
        "sky": "blue",
        "balloon": "red",
        "grass": "green",
    }


def display_color(color: list):
    # color is presented as a list key-value pairs [("sky", "blue"), ("balloon", "red"), ("grass", "green")]
    return rx.box(rx.text(color[0]), bg=color[1], padding_x="1.5em")


def dict_foreach():
    return rx.grid(
        rx.foreach(
            SimpleDictIterState.color_chart,
            display_color,
        ),
        columns="3",
    )

```

```md alert warning
# Dict Type Annotation.
It is essential to provide the correct full type annotation for the dictionary in the state definition (e.g., `dict[str, str]` instead of `dict`) to ensure `rx.foreach` works as expected. Proper typing allows Reflex to infer and validate the structure of the data during rendering.
```

## Nested examples

`rx.foreach` can be used with nested state vars. Here we use nested `foreach` components to render the nested state vars. The `rx.foreach(project["technologies"], get_badge)` inside of the `project_item` function, renders the `dict` values which are of type `list`. The `rx.box(rx.foreach(NestedStateFE.projects, project_item))` inside of the `projects_example` function renders each `dict` inside of the overall state var `projects`.

```python demo exec
class NestedStateFE(rx.State):
    projects: list[dict[str, list]] = [
        {
            "technologies": ["Next.js", "Prisma", "Tailwind", "Google Cloud", "Docker", "MySQL"]
        },
        {
            "technologies": ["Python", "Flask", "Google Cloud", "Docker"]
        }
    ]

def get_badge(technology: rx.Var[str]) -> rx.Component:
    return rx.badge(technology, variant="soft", color_scheme="green")

def project_item(project: rx.Var[dict[str, list]]) -> rx.Component:
    return rx.box(
        rx.hstack(            
            rx.foreach(project["technologies"], get_badge)
        ),
    )

def projects_example() -> rx.Component:
    return rx.box(rx.foreach(NestedStateFE.projects, project_item))
```

If you want an example where not all of the values in the dict are the same type then check out the example on [var operations using foreach]({docs.vars.var_operations.path}).

Here is a further example of how to use `foreach` with a nested data structure.

```python demo exec
class NestedDictIterState(rx.State):
    color_chart: dict[str, list[str]] = {
        "purple": ["red", "blue"],
        "orange": ["yellow", "red"],
        "green": ["blue", "yellow"],
    }


def display_colors(color: rx.Var[tuple[str, list[str]]]):
    return rx.vstack(
        rx.text(color[0], color=color[0]),
        rx.hstack(
            rx.foreach(
                color[1],
                lambda x: rx.box(
                    rx.text(x, color="black"), bg=x
                ),
            )
        ),
    )


def nested_dict_foreach():
    return rx.grid(
        rx.foreach(
            NestedDictIterState.color_chart,
            display_colors,
        ),
        columns="3",
    )

```

## Foreach with Cond

We can also use `foreach` with the `cond` component.

In this example we define the function `render_item`. This function takes in an `item`, uses the `cond` to check if the item `is_packed`. If it is packed it returns the `item_name` with a `✔` next to it, and if not then it just returns the `item_name`. We use the `foreach` to iterate over all of the items in the `to_do_list` using the `render_item` function.

```python demo exec
import dataclasses

@dataclasses.dataclass
class ToDoListItem:
    item_name: str
    is_packed: bool

class ForeachCondState(rx.State):
    to_do_list: list[ToDoListItem] = [
        ToDoListItem(item_name="Space suit", is_packed=True), 
        ToDoListItem(item_name="Helmet", is_packed=True),
        ToDoListItem(item_name="Back Pack", is_packed=False),
        ]


def render_item(item: rx.Var[ToDoListItem]):
    return rx.cond(
        item.is_packed, 
        rx.list.item(item.item_name + ' ✔'),
        rx.list.item(item.item_name),
    )

def packing_list():
    return rx.vstack(
        rx.text("Sammy's Packing List"),
        rx.list(rx.foreach(ForeachCondState.to_do_list, render_item)),
    )

```
