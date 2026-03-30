```python exec
import reflex as rx
```

# Foreach

The `rx.foreach` component takes an iterable(list, tuple or dict) and a function that renders each item in the list.
This is useful for dynamically rendering a list of items defined in a state.

```md alert warning
# `rx.foreach` is specialized for usecases where the iterable is defined in a state var.

For an iterable where the content doesn't change at runtime, i.e a constant, using a list/dict comprehension instead of `rx.foreach` is preferred.
```

```python demo exec
from typing import List
class ForeachState(rx.State):
    color: List[str] = ["red", "green", "blue", "yellow", "orange", "purple"]

def colored_box(color: str):
    return rx.box(
        rx.text(color),
        bg=color
    )

def foreach_example():
    return rx.grid(
        rx.foreach(
            ForeachState.color,
            colored_box
        ),
        columns="2",
    )
```

The function can also take an index as a second argument.

```python demo exec
def colored_box_index(color: str, index: int):
    return rx.box(
        rx.text(index),
        bg=color
    )

def foreach_example_index():
    return rx.grid(
        rx.foreach(
            ForeachState.color,
            lambda color, index: colored_box_index(color, index)
        ),
        columns="2",
    )
```

Nested foreach components can be used to render nested lists.

When indexing into a nested list, it's important to declare the list's type as Reflex requires it for type checking.
This ensures that any potential frontend JS errors are caught before the user can encounter them.

```python demo exec
from typing import List

class NestedForeachState(rx.State):
    numbers: List[List[str]] = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]]

def display_row(row):
    return rx.hstack(
        rx.foreach(
            row,
            lambda item: rx.box(
                item,
                border="1px solid black",
                padding="0.5em",
            )
        ),
    )

def nested_foreach_example():
    return rx.vstack(
        rx.foreach(
             NestedForeachState.numbers,
            display_row
        )
    )
```

Below is a more complex example of foreach within a todo list.

```python demo exec
from typing import List
class ListState(rx.State):
    items: List[str] = ["Write Code", "Sleep", "Have Fun"]
    new_item: str

    @rx.event
    def set_new_item(self, new_item: str):
        self.new_item = new_item

    @rx.event
    def add_item(self):
        self.items += [self.new_item]

    def finish_item(self, item: str):
        self.items = [i for i in self.items if i != item]

def get_item(item):
    return rx.list.item(
        rx.hstack(
            rx.button(
                on_click=lambda: ListState.finish_item(item),
                height="1.5em",
                background_color="white",
                border="1px solid blue",
            ),
            rx.text(item, font_size="1.25em"),
        ),
    )

def todo_example():
    return rx.vstack(
        rx.heading("Todos"),
        rx.input(on_blur=ListState.set_new_item, placeholder="Add a todo...", bg  = "white"),
        rx.button("Add", on_click=ListState.add_item, bg = "white"),
        rx.divider(),
        rx.list.ordered(
            rx.foreach(
                ListState.items,
                get_item,
            ),
        ),
        bg = "#ededed",
        padding = "1em",
        border_radius = "0.5em",
        shadow = "lg"
    )
```

## Dictionaries

Items in a dictionary can be accessed as list of key-value pairs.
Using the color example, we can slightly modify the code to use dicts as shown below.

```python demo exec
from typing import List
class SimpleDictForeachState(rx.State):
    color_chart: dict[int, str] = {
         1 : "blue",
         2: "red",
         3: "green"
    }

def display_color(color: List):
    # color is presented as a list key-value pair([1, "blue"],[2, "red"], [3, "green"])
    return rx.box(rx.text(color[0]), bg=color[1])


def foreach_dict_example():
    return rx.grid(
        rx.foreach(
            SimpleDictForeachState.color_chart,
            display_color
        ),
        columns = "2"
    )
```

Now let's show a more complex example with dicts using the color example.
Assuming we want to display a dictionary of secondary colors as keys and their constituent primary colors as values, we can modify the code as below:

```python demo exec
from typing import List, Dict
class ComplexDictForeachState(rx.State):
    color_chart: Dict[str, List[str]] = {
        "purple": ["red", "blue"],
        "orange": ["yellow", "red"],
        "green": ["blue", "yellow"]
    }

def display_colors(color: List):
    return rx.vstack(
            rx.text(color[0], color=color[0]),
            rx.hstack(
                rx.foreach(
                    color[1], lambda x: rx.box(rx.text(x, color="black"), bg=x)
                )

            )
        )

def foreach_complex_dict_example():
    return rx.grid(
        rx.foreach(
            ComplexDictForeachState.color_chart,
            display_colors
        ),
        columns="2"
    )
```
