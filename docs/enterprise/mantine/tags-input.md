---
title: TagsInput
---

# TagsInput

`rxe.mantine.tags_input` is a wrapping of the mantine component [TagsInput](https://mantine.dev/core/tags-input/). It is an utility component that can be used to display a list of tags or labels. It can be used in various contexts, such as in a form or as a standalone component.

```md alert info
# You can use the props mentioned in the Mantine documentation, but they need to be passed in snake_case.
```

## Basic Example

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

def tags_input_simple_page():
    """TagsInput demo."""
    return rxe.mantine.tags_input(
        placeholder="Enter tags",
        label="Press Enter to ad a tag",
    )
```

## State Example

```python demo exec
import reflex as rx
import reflex_enterprise as rxe

class TagsInputState(rx.State):
    """State for the TagsInput component."""

    tags: list[str] = ["Tag1", "Tag2"]

    @rx.event
    def update_tags(self, tags: list[str]):
        """Add a tag to the list of tags."""
        self.tags = tags

def tags_input_page():
    """TagsInput demo."""
    return rxe.mantine.tags_input(
        value=TagsInputState.tags,
        on_change=TagsInputState.update_tags,
        placeholder="Enter tags",
        label="TagsInput",
        description="This is a TagsInput component",
        error="",
        size="md",
        radius="xl",
    )
```
