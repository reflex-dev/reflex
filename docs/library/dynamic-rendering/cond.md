```python exec
import reflex as rx
```

# Cond

This component is used to conditionally render components.

The cond component takes a condition and two components.
If the condition is `True`, the first component is rendered, otherwise the second component is rendered.

```python demo exec
class CondState(rx.State):
    show: bool = True

    @rx.event
    def change(self):
        self.show = not (self.show)


def cond_example():
    return rx.vstack(
        rx.button("Toggle", on_click=CondState.change),
        rx.cond(CondState.show, rx.text("Text 1", color="blue"), rx.text("Text 2", color="red")),
    )
```

The second component is optional and can be omitted.
If it is omitted, nothing is rendered if the condition is `False`.

```python demo exec
class CondOptionalState(rx.State):
    show_optional: bool = True

    @rx.event
    def toggle_optional(self):
        self.show_optional = not (self.show_optional)


def cond_optional_example():
    return rx.vstack(
        rx.button("Toggle", on_click=CondOptionalState.toggle_optional),
        rx.cond(CondOptionalState.show_optional, rx.text("This text appears when condition is True", color="green")),
        rx.text("This text is always visible", color="gray"),
    )
```

```md video https://youtube.com/embed/ITOZkzjtjUA?start=6040&end=6463
# Video: Conditional Rendering
```

## Negation

You can use the logical operator `~` to negate a condition.

```python
rx.vstack(
    rx.button("Toggle", on_click=CondState.change),
    rx.cond(CondState.show, rx.text("Text 1", color="blue"), rx.text("Text 2", color="red")),
    rx.cond(~CondState.show, rx.text("Text 1", color="blue"), rx.text("Text 2", color="red")),
)
```

## Multiple Conditions

It is also possible to make up complex conditions using the `logical or` (|) and `logical and` (&) operators.

Here we have an example using the var operators `>=`, `<=`, `&`. We define a condition that if a person has an age between 18 and 65, including those ages, they are able to work, otherwise they cannot.

We could equally use the operator `|` to represent a `logical or` in one of our conditions.

```python demo exec
import random

class CondComplexState(rx.State):
    age: int = 19

    @rx.event
    def change(self):
        self.age = random.randint(0, 100)


def cond_complex_example():
    return rx.vstack(
        rx.button("Toggle", on_click=CondComplexState.change),
        rx.text(f"Age: {CondComplexState.age}"),
        rx.cond(
            (CondComplexState.age >= 18) & (CondComplexState.age <=65),
            rx.text("You can work!", color="green"),
            rx.text("You cannot work!", color="red"),
        ),
    )

```

## Nested Conditional

We can also nest `cond` components within each other to create more complex logic. In python we can have an `if` statement that then has several `elif` statements before finishing with an `else`. This is also possible in reflex using nested `cond` components. In this example we check whether a number is positive, negative or zero.

Here is the python logic using `if` statements:

```python
number = 0

if number > 0:
    print("Positive number")

elif number == 0:
    print('Zero')
else:
    print('Negative number')
```

This reflex code that is logically identical:

```python demo exec
import random


class NestedState(rx.State):

    num: int = 0

    def change(self):
        self.num = random.randint(-10, 10)


def cond_nested_example():
    return rx.vstack(
        rx.button("Toggle", on_click=NestedState.change),
        rx.cond(
            NestedState.num > 0,
            rx.text(f"{NestedState.num} is Positive!", color="orange"),
            rx.cond(
                NestedState.num == 0,
                rx.text(f"{NestedState.num} is Zero!", color="blue"),
                rx.text(f"{NestedState.num} is Negative!", color="red"),
            )
        ),
    )

```

Here is a more advanced example where we have three numbers and we are checking which of the three is the largest. If any two of them are equal then we return that `Some of the numbers are equal!`.

The reflex code that follows is logically identical to doing the following in python:

```python
a = 8
b = 10
c = 2

if((a>b and a>c) and (a != b and a != c)):
 print(a, " is the largest!")
elif((b>a and b>c) and (b != a and b != c)):
 print(b, " is the largest!")
elif((c>a and c>b) and (c != a and c != b)):
 print(c, " is the largest!")
else:
 print("Some of the numbers are equal!")
```
