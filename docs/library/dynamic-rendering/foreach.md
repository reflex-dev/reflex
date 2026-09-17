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
class ForeachState(rx.State):
    colors: list[str] = [
        "#E5484D",
        "#12A594",
        "#3E63DD",
        "#AD5700",
        "#F76B15",
        "#8E4EC6",
    ]


def color_swatch(label: rx.Var[str | int], color: rx.Var[str]):
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
def colored_box_index(color: rx.Var[str], index: rx.Var[int]):
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
class NestedForeachState(rx.State):
    numbers: list[list[str]] = [["1", "2", "3"], ["4", "5", "6"], ["7", "8", "9"]]


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
from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass
class TodoItem:
    text: str
    id: UUID = field(default_factory=uuid4)


class ListState(rx.State):
    items: list[TodoItem] = [
        TodoItem(text="Write Code"),
        TodoItem(text="Sleep"),
        TodoItem(text="Have Fun"),
    ]
    new_item: str = ""

    @rx.event
    def set_new_item(self, new_item: str):
        self.new_item = new_item

    @rx.event
    def add_item(self):
        self.items += [TodoItem(text=self.new_item)]

    @rx.event
    def finish_item(self, item_id: UUID):
        self.items = [item for item in self.items if item.id != item_id]


def get_item(item: rx.Var[TodoItem]):
    return rx.list.item(
        rx.hstack(
            rx.button(
                "Done",
                on_click=lambda: ListState.finish_item(item.id),
                size="1",
                variant="soft",
            ),
            rx.text(item.text, font_size="1.25em"),
        ),
        key=item.id,
    )


def todo_example():
    return rx.vstack(
        rx.heading("Todos", as_="h2"),
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
When iterating over a dict, keys are coerced to strings in the `foreach` callback, even when the Python dictionary uses another key type.
Using the color example, we can slightly modify the code to use dicts as shown below.

```python demo exec
class SimpleDictForeachState(rx.State):
    color_chart: dict[int, str] = {1: "#3E63DD", 2: "#E5484D", 3: "#12A594"}


def display_color(color: rx.Var[tuple[str, str]]):
    # color is presented as a key-value pair such as ("1", "#3E63DD").
    return color_swatch(color[0], color[1])


def foreach_dict_example():
    return rx.grid(
        rx.foreach(SimpleDictForeachState.color_chart, display_color), columns="2"
    )
```

Now let's show a more complex example with dicts using the color example.
This example groups related hex colors in a dictionary and renders both the keys and values as swatches:

```python demo exec
class ComplexDictForeachState(rx.State):
    color_chart: dict[str, list[str]] = {
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

## Per-Item State And Event Handlers

Each rendered item gets its own scope, so the item and index are available
anywhere in that item's subtree -- including in event handlers and in
components the compiler splits out on its own:

```python
class TodoState(rx.State):
    items: list[str] = ["write docs", "ship it"]

    @rx.event
    def done(self, item: str, index: int): ...


def todo_row(item: rx.Var[str], index: rx.Var[int]) -> rx.Component:
    return rx.hstack(
        rx.text(item),
        rx.button("done", on_click=TodoState.done(item, index)),
    )


def todo_list():
    return rx.vstack(rx.foreach(TodoState.items, todo_row))
```

Client state works the same way: an unnamed `rx.client_state` var in a
`foreach` body is per item, the way `useState` would be in a React list.

```python
def expandable_row(item: rx.Var[str]) -> rx.Component:
    expanded = rx.client_state(False)  # one per rendered row
    return rx.vstack(
        rx.button(item, on_click=expanded.set(lambda prev: ~prev)),
        rx.cond(expanded.value, rx.text(f"details for {item}")),
    )
```

The default can be the loop item or index, which seeds each row from its own
value:

```python
def counter_row(item: rx.Var[str], index: rx.Var[int]) -> rx.Component:
    count = rx.client_state(index)  # row N starts at N
    return rx.hstack(
        rx.text(item),
        rx.heading(count.value),
        rx.button("+", on_click=count.set(lambda prev: prev + 1)),
    )
```

A default is a *seed*, read once when the row first claims the slot. It is not a
binding: a later change to the var does not reset a row, which is what keeps a
row from losing what the user typed into it every time the list re-renders.

That has a consequence worth knowing before you reach for it, and it is the same
one `useState(props.value)` has in React. Rows are keyed by position by default
(see below), so replacing the list's contents re-renders the existing rows
instead of mounting new ones -- and a state seeded from the item keeps the *old*
item's seed:

```python
rx.foreach(State.items, lambda item: rx.text(rx.client_state(item).value))
# State.items: ["a", "b", "c"] -> ["d", "e", "f"]
#   rx.text(item)                  renders d, e, f   <- follows the data
#   rx.client_state(item).value    renders a, b, c   <- seeded once, per position
```

The item itself always follows the data; only the seeded state lags. Pass `key=`
on the item when you want the state to belong to the item, so replacing the list
unmounts the old rows and the new ones seed themselves:

```python
rx.foreach(State.items, lambda item: row(item, key=item))
```

If you want a row's state to track a var while staying editable in between, seed
it and then push updates explicitly with `on_mount=count.set(index)`, or on a
`rx.fragment(key=..., on_mount=...)` to tie the reset to something of your own
choosing.

Loops nest, and each level gets its own scope. A nested body can read an
*enclosing* loop's item and index, as long as it does not reuse their names --
the same rule Python already imposes, since an inner argument of the same name
shadows the outer one:

```python
rx.foreach(
    State.rows,
    lambda row: rx.foreach(row, lambda cell: rx.text(f"{row[0]}/{cell}")),
)
```

By default each item is keyed by its position in the list. Pass `key=` on the
item to key by identity instead:

```python
rx.foreach(TodoState.items, lambda item: todo_row(item, key=item))
```

The key decides what a row's state belongs to. Under the default positional
keys, changing the list re-renders the existing rows in place rather than
mounting new ones, so anything a row is holding -- a typed-in value, focus, an
in-flight animation, a `rx.client_state` var -- stays with the *position*. Row 3
of the old list keeps its expanded/selected state as row 3 of the new one. Key
by identity and the old rows unmount instead, releasing their state, and a row
that reappears starts fresh.

Neither is the right default for every list, which is why the choice is yours.
Positional keys suit a list whose rows are interchangeable slots, where you want
"row 3 is expanded" to persist as the data flows through. Identity keys suit a
list of distinct things each carrying its own state, where a row's state should
travel with its item across reorders and disappear with it. Identity keys need
the key expression to be unique within the list -- duplicate keys make React
reconcile the wrong rows together.

## API Reference


### `rx.foreach`

```python
rx.foreach(iterable, render_fn)
```

- `iterable`: A state var or iterable to render. Lists, tuples, sets, strings, and dicts are supported; dicts are passed to `render_fn` as key-value tuples with string keys.
- `render_fn`: A function that returns a component for each item. It receives the item as the first `rx.Var[...]` argument and, optionally, the index as a second `rx.Var[int]` argument.
