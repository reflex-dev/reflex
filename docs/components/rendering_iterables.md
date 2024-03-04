```python exec
import reflex as rx

from pcweb.pages.docs import vars
```

# Rendering Iterables

You will often want to display multiple similar components from a collection of data. The `rx.foreach` component takes an `iterable` (list, tuple or dict) and a `function` that renders each item in the list. This is useful for dynamically rendering a list of items defined in a state.

In this first simple example we iterate through a `list` of colors and render the name of the color and use this color as the background for that `rx.box`. As we can see we have a function `colored_box` that we pass to the `rx.foreach` component. This function renders each item from the `list` that we have defined as a state var `color`.

```python demo exec
class IterState(rx.State):
    color: list[str] = [
        "red",
        "green",
        "blue",
        "yellow",
        "orange",
        "purple",
    ]


def colored_box(color: str):
    return rx.box(rx.text(color), background_color=color)


def simple_foreach():
    return rx.chakra.responsive_grid(
        rx.foreach(IterState.color, colored_box),
        columns=[2, 4, 6],
    )

```

```md alert warning
# The type signature of the functions does not matter to the `foreach` component. It's the type annotation on the `state var` that determines what operations are available (e.g. when nesting).
```

## Enumeration

The function can also take an index as a second argument, meaning that we can enumerate through data as shown in the example below.

```python demo exec
class IterIndexState(rx.State):
    color: list[str] = [
        "red",
        "green",
        "blue",
        "yellow",
        "orange",
        "purple",
    ]


def enumerate_foreach():
    return rx.chakra.responsive_grid(
        rx.foreach(
            IterIndexState.color,
            lambda color, index: rx.box(rx.text(index), bg=color)
        ),
        columns=[2, 4, 6],
    )

```

## Dictionary

We can iterate through a `dict` data structure using a `foreach`. When the dict is passed through to the function that renders each item, it is presented as a list of key-value pairs `[("sky", "blue"), ("balloon", "red"), ("grass", "green")]`.

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
    return rx.chakra.responsive_grid(
        rx.foreach(
            SimpleDictIterState.color_chart,
            display_color,
        ),
        columns=[2, 4, 6],
    )

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

def get_badge(technology: str) -> rx.Component:
    return rx.chakra.badge(technology, variant="subtle", color_scheme="green")

def project_item(project: dict) -> rx.Component:
    return rx.box(
        rx.hstack(            
            rx.foreach(project["technologies"], get_badge)
        ),
    )

def projects_example() -> rx.Component:
    return rx.box(rx.foreach(NestedStateFE.projects, project_item))
```

If you want an example where not all of the values in the dict are the same type then check out the example on [var operations using foreach]({vars.var_operations.path}).

Here is a further example of how to use `foreach` with a nested data structure.

```python demo exec
class NestedDictIterState(rx.State):
    color_chart: dict[str, list[str]] = {
        "purple": ["red", "blue"],
        "orange": ["yellow", "red"],
        "green": ["blue", "yellow"],
    }


def display_colors(color: list[str, list[str]]):
    
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
    return rx.chakra.responsive_grid(
        rx.foreach(
            NestedDictIterState.color_chart,
            display_colors,
        ),
        columns=[2, 4, 6],
    )

```

## Foreach with Cond

We can also use `foreach` with the `cond` component.

In this example we define the function `render_item`. This function takes in an `item`, uses the `cond` to check if the item `is_packed`. If it is packed it returns the `item_name` with a `✔` next to it, and if not then it just returns the `item_name`. We use the `foreach` to iterate over all of the items in the `to_do_list` using the `render_item` function.

```python demo exec
class ToDoListItem(rx.Base):
    item_name: str
    is_packed: bool

class ForeachCondState(rx.State):
    to_do_list: list[ToDoListItem] = [
        ToDoListItem(item_name="Space suit", is_packed=True), 
        ToDoListItem(item_name="Helmet", is_packed=True),
        ToDoListItem(item_name="Back Pack", is_packed=False),
        ]


def render_item(item: [str, bool]):
    return rx.cond(
        item.is_packed, 
        rx.chakra.list_item(item.item_name + ' ✔'),
        rx.chakra.list_item(item.item_name),
        )

def packing_list():
    return rx.vstack(
        rx.text("Sammy's Packing List"),
        rx.chakra.list(rx.foreach(ForeachCondState.to_do_list, render_item)),
    )

```
