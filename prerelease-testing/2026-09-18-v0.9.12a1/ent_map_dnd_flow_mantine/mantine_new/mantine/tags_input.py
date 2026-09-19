import reflex as rx

import reflex_enterprise as rxe

from .common import demo


class TagsInputState(rx.State):
    """State for the TagsInput component."""

    tags: list[str] = ["Tag1", "Tag2"]

    @rx.event
    def update_tags(self, tags: list[str]):
        """Add a tag to the list of tags."""
        self.tags = tags


@demo(
    route="/tags-input",
    title="Tags Input",
    description="A simple Tags Input example using Mantine.",
)
def tags_input_page():
    return rxe.mantine.tags_input(
        value=TagsInputState.tags,
        on_change=TagsInputState.update_tags,
        placeholder="Enter tags",
        label="TagsInput",
        description="This is a TagsInput component",
        size="md",
        radius="xl",
    )
