```python exec
import reflex as rx
```

# Match

The `rx.match` feature in Reflex serves as a powerful alternative to `rx.cond` for handling conditional statements.
While `rx.cond` excels at conditionally rendering two components based on a single condition,
`rx.match` extends this functionality by allowing developers to handle multiple conditions and their associated components.
This feature is especially valuable when dealing with intricate conditional logic or nested scenarios,
where the limitations of `rx.cond` might lead to less readable and more complex code.

With `rx.match`, developers can not only handle multiple conditions but also perform structural pattern matching,
making it a versatile tool for managing various scenarios in Reflex applications.

## Basic Usage

The `rx.match` function provides a clear and expressive syntax for handling multiple
conditions and their corresponding components:

```python
rx.match(
    condition,
    (case_1, component_1),
    (case_2, component_2),
    ...
    default_component,
)

```

- `condition`: The value to match against.
- `(case_i, component_i)`: A Tuple of matching cases and their corresponding return components.
- `default_component`: A special case for the default component when the condition isn't matched by any of the match cases.

Example

```python demo exec
from typing import List

import reflex as rx


class MatchState(rx.State):
    cat_breed: str = ""
    animal_options: List[str] = ["persian", "siamese", "maine coon", "ragdoll", "pug", "corgi"]

    @rx.event
    def set_cat_breed(self, breed: str):
        self.cat_breed = breed

def match_demo():
    return rx.flex(
        rx.match(
            MatchState.cat_breed,
            ("persian", rx.text("Persian cat selected.")),
            ("siamese", rx.text("Siamese cat selected.")),
            ("maine coon", rx.text("Maine Coon cat selected.")),
            ("ragdoll", rx.text("Ragdoll cat selected.")),
            rx.text("Unknown cat breed selected.")
        ),
        rx.select.root(
            rx.select.trigger(),
            rx.select.content(
                rx.select.group(
                    rx.foreach(MatchState.animal_options, lambda x: rx.select.item(x, value=x))
                ),
            ),
            value=MatchState.cat_breed,
            on_change=MatchState.set_cat_breed,

        ),
        direction= "column",
        gap= "2"
    )
```

## Default Case

The default case in `rx.match` serves as a universal handler for scenarios where none of
the specified match cases aligns with the given match condition. Here are key considerations
when working with the default case:

- **Placement in the Match Function**: The default case must be the last non-tuple argument in the `rx.match` component.
  All match cases should be enclosed in tuples; any non-tuple value is automatically treated as the default case. For example:

```python
rx.match(
           MatchState.cat_breed,
           ("persian", rx.text("persian cat selected")),
           rx.text("Unknown cat breed selected."),
           ("siamese", rx.text("siamese cat selected")),
       )
```

The above code snippet will result in an error due to the misplaced default case.

- **Single Default Case**: Only one default case is allowed in the `rx.match` component.
  Attempting to specify multiple default cases will lead to an error. For instance:

```python
rx.match(
           MatchState.cat_breed,
           ("persian", rx.text("persian cat selected")),
           ("siamese", rx.text("siamese cat selected")),
           rx.text("Unknown cat breed selected."),
           rx.text("Another unknown cat breed selected.")
       )
```

- **Optional Default Case for Component Return Values**: If the match cases in a `rx.match` component
  return components, the default case can be optional. In this scenario, if a default case is
  not provided, `rx.fragment` will be implicitly assigned as the default. For example:

```python
rx.match(
           MatchState.cat_breed,
           ("persian", rx.text("persian cat selected")),
           ("siamese", rx.text("siamese cat selected")),
       )
```

In this case, `rx.fragment` is the default case. However, not providing a default case for non-component
return values will result in an error:

```python
rx.match(
           MatchState.cat_breed,
           ("persian", "persian cat selected"),
           ("siamese", "siamese cat selected"),
       )
```

The above code snippet will result in an error as a default case must be explicitly
provided in this scenario.

## Handling Multiple Conditions

`rx.match` excels in efficiently managing multiple conditions and their corresponding components,
providing a cleaner and more readable alternative compared to nested `rx.cond` structures.

Consider the following example:

```python demo exec
from typing import List

import reflex as rx


class MultiMatchState(rx.State):
    animal_breed: str = ""
    animal_options: List[str] = ["persian", "siamese", "maine coon", "pug", "corgi", "mustang", "rahvan", "football", "golf"]

    @rx.event
    def set_animal_breed(self, breed: str):
        self.animal_breed = breed

def multi_match_demo():
    return rx.flex(
        rx.match(
            MultiMatchState.animal_breed,
            ("persian", "siamese", "maine coon", rx.text("Breeds of cats.")),
            ("pug", "corgi", rx.text("Breeds of dogs.")),
            ("mustang", "rahvan", rx.text("Breeds of horses.")),
            rx.text("Unknown animal breed")
        ),
        rx.select.root(
            rx.select.trigger(),
            rx.select.content(
                rx.select.group(
                    rx.foreach(MultiMatchState.animal_options, lambda x: rx.select.item(x, value=x))
                ),
            ),
            value=MultiMatchState.animal_breed,
            on_change=MultiMatchState.set_animal_breed,

        ),
        direction= "column",
        gap= "2"
    )
```

In a match case tuple, you can specify multiple conditions. The last value of the match case
tuple is automatically considered as the return value. It's important to note that a match case
tuple should contain a minimum of two elements: a match case and a return value.
The following code snippet will result in an error:

```python
rx.match(
            MatchState.cat_breed,
            ("persian",),
            ("maine coon", rx.text("Maine Coon cat selected")),
        )
```

## Usage as Props

Similar to `rx.cond`, `rx.match` can be used as prop values, allowing dynamic behavior for UI components:

```python demo exec
import reflex as rx


class MatchPropState(rx.State):
    value: int = 0

    @rx.event
    def incr(self):
        self.value += 1

    @rx.event
    def decr(self):
        self.value -= 1


def match_prop_demo_():
    return rx.flex(
        rx.button("decrement", on_click=MatchPropState.decr, background_color="red"),
        rx.badge(
            MatchPropState.value,
            color_scheme= rx.match(
                    MatchPropState.value,
                    (1, "red"),
                    (2, "blue"),
                    (6, "purple"),
                    (10, "orange"),
                    "green"
                ),
                size="2",
        ),
        rx.button("increment", on_click=MatchPropState.incr),
        align_items="center",
        direction= "row",
        gap= "3"
    )
```

In the example above, the background color property of the box component containing `State.value` changes to red when
`state.value` is 1, blue when its 5, green when its 5, orange when its 15 and black for any other value.

The example below also shows handling multiple conditions with the match component as props.

```python demo exec
import reflex as rx


class MatchMultiPropState(rx.State):
    value: int = 0

    @rx.event
    def incr(self):
        self.value += 1

    @rx.event
    def decr(self):
        self.value -= 1


def match_multi_prop_demo_():
    return rx.flex(
        rx.button("decrement", on_click=MatchMultiPropState.decr, background_color="red"),
        rx.badge(
            MatchMultiPropState.value,
            color_scheme= rx.match(
                    MatchMultiPropState.value,
                    (1, 3, 9, "red"),
                    (2, 4, 5, "blue"),
                    (6, 8, 12, "purple"),
                    (10, 15, 20, 25, "orange"),
                    "green"
                ),
                size="2",
        ),
        rx.button("increment", on_click=MatchMultiPropState.incr),
        align_items="center",
        direction= "row",
        gap= "3"
    )
```

```md alert warning
# Usage with Structural Pattern Matching

The `rx.match` component is designed for structural pattern matching. If the value of your match condition evaluates to a boolean (True or False), it is recommended to use `rx.cond` instead.

Consider the following example, which is more suitable for `rx.cond`:\*
```

```python
rx.cond(
    MatchPropState.value == 10,
    "true value",
    "false value"
)
```
