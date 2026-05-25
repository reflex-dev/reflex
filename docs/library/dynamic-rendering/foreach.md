---
components:
  - rx.foreach
---

```python exec
import reflex as rx
```

# Foreach

The `rx.foreach` component takes an iterable (list, tuple, or dict) and a function that renders each item in the list.
This is useful for dynamically rendering a list of items defined in a state.

```md alert warning
# Use `rx.foreach` for state vars; use Python list or dict comprehensions for constants.
```

```python demo exec
from typing import List


class ForeachState(rx.State):
    colors: List[str] = [
        "#E5484D",
        "#12A594",
        "#3E63DD",
        "#AD5700",
        "#F76B15",
        "#8E4EC6",
    ]


def color_swatch(label, color: rx.Var[str]):
    return rx.box(
        rx.text(label, color="white", weight="medium"),
        bg=color,
        padding_y="0.5em",
        padding_x="0.75em",
        min_width="5.5em",
        text_align="center",
        border_radius="0.375rem",
        border="1px solid rgba(0, 0, 0, 0.12)",
        box_shadow="0 1px 2px rgba(0, 0, 0, 0.10)",
    )


def colored_box(color: rx.Var[str]):
    return color_swatch(color, color)


def foreach_example():
    return rx.grid(
        rx.foreach(ForeachState.colors, colored_box),
        columns="2",
    )
```

The function can also take an index as a second argument.

```python demo exec
def colored_box_index(color: rx.Var[str], index: int):
    return color_swatch(index, color)


def foreach_example_index():
    return rx.grid(
        rx.foreach(
            ForeachState.colors, lambda color, index: colored_box_index(color, index)
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


def display_row(row: rx.Var[list[str]]):
    return rx.hstack(
        rx.foreach(
            row,
            lambda item: rx.box(
                item,
                border="1px solid black",
                padding="0.5em",
            ),
        ),
    )


def nested_foreach_example():
    return rx.vstack(rx.foreach(NestedForeachState.numbers, display_row))
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

    @rx.event
    def finish_item(self, item: str):
        self.items = [i for i in self.items if i != item]


def get_item(item: rx.Var[str]):
    return rx.list.item(
        rx.hstack(
            rx.button(
                "Done",
                on_click=lambda: ListState.finish_item(item),
                size="1",
                variant="soft",
            ),
            rx.text(item, font_size="1.25em"),
        ),
    )


def todo_example():
    return rx.vstack(
        rx.heading("Todos"),
        rx.input(
            on_blur=ListState.set_new_item, placeholder="Add a todo...", bg="white"
        ),
        rx.button("Add", on_click=ListState.add_item),
        rx.divider(),
        rx.list.ordered(
            rx.foreach(
                ListState.items,
                get_item,
            ),
        ),
        bg="#ededed",
        padding="1em",
        border_radius="0.5em",
        shadow="lg",
    )
```

## Dictionaries

Items in a dictionary are passed to the render function as key-value pairs.
Using the color example, we can slightly modify the code to use dicts as shown below.

```python demo exec
class SimpleDictForeachState(rx.State):
    color_chart: dict[int, str] = {1: "#3E63DD", 2: "#E5484D", 3: "#12A594"}


def display_color(color: rx.Var[tuple[int, str]]):
    # color is presented as a key-value pair such as (1, "#3E63DD").
    return color_swatch(color[0], color[1])


def foreach_dict_example():
    return rx.grid(
        rx.foreach(SimpleDictForeachState.color_chart, display_color), columns="2"
    )
```

Now let's show a more complex example with dicts using the color example.
This example groups related hex colors in a dictionary and renders both the keys and values as swatches:

```python demo exec
from typing import List, Dict


class ComplexDictForeachState(rx.State):
    color_chart: Dict[str, List[str]] = {
        "#8E4EC6": ["#E5484D", "#3E63DD"],
        "#F76B15": ["#AD5700", "#E5484D"],
        "#12A594": ["#3E63DD", "#AD5700"],
    }


def display_colors(color: rx.Var[tuple[str, list[str]]]):
    return rx.vstack(
        color_swatch(color[0], color[0]),
        rx.hstack(
            rx.foreach(
                color[1],
                lambda x: color_swatch(x, x),
            )
        ),
        align="center",
        spacing="2",
    )


def foreach_complex_dict_example():
    return rx.grid(
        rx.foreach(ComplexDictForeachState.color_chart, display_colors),
        columns="3",
        spacing="4",
    )
```
