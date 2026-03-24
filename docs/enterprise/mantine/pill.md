---
title: Pill
---

```python exec
import reflex as rx
import reflex_enterprise as rxe
from pcweb.pages.docs import enterprise
```

# Pill

`rxe.mantine.pill` is a wrapping of the mantine component [Pill](https://mantine.dev/core/pill/). It is a simple component that can be used to display a small piece of information, such as a tag or a label. It can be used in various contexts, such as in a list of tags or labels, or as a standalone component.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

def pill_page():
    """Pill demo."""
    return rxe.mantine.pill(
        "Pill",
        color="blue",
        size="md",
        variant="outline",
        radius="xl",
        with_remove_button=True,
        on_remove=lambda: rx.toast("Pill on_remove triggered"),
    )
```

## Pill Group
`rxe.mantine.pill.group` allows grouping multiple `rxe.mantine.pill` components together, with a predefined layout.

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

def pill_group_page():
    """Pill demo."""
    return rxe.mantine.pill.group(
        rxe.mantine.pill("Pill 1"),
        rxe.mantine.pill("Pill 2"),
    )
```


# PillsInput

`rxe.mantine.pills_input` is a wrapping of the mantine component [PillsInput](https://mantine.dev/core/pills-input/). It is an utility component that can be used to display a list of tags or labels. It can be used in various contexts, such as in a form or as a standalone component.
By itself it does not include any logic, it only renders given children.

```md alert info
# For a fully functional out-of-the-box component, consider using [`rxe.mantine.tags_input`](/docs/enterprise/mantine/tags-input/) instead.
```

## Example

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

class PillInputState(rx.State):
    """State for the PillsInput demo."""

    tags: set[str] = {"Foo", "Bar"}

    @rx.event
    def add_tag(self, tag: str):
        """Add a tag to the list of tags."""
        self.tags.add(tag)

    @rx.event
    def remove_tag(self, tag: str):
        """Remove a tag from the list of tags."""
        self.tags.remove(tag)

def pills_input_page():
    """PillsInput demo."""
    return rxe.mantine.pills_input(
        rxe.mantine.pill.group(
            rx.foreach(
                PillInputState.tags, lambda tag: rxe.mantine.pill(tag, with_remove_button=True, on_remove=PillInputState.remove_tag(tag))
            ),
            rxe.mantine.pills_input.field(
                placeholder="Enter tags",
                # on_blur=PillInputState.add_tag,
            ),
        ),
        label="PillsInput",
        id="pills-input",
        value=["tag1", "tag2"],
    )
```
