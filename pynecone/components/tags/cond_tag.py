"""Tag to conditionally render components."""

from pynecone import utils
from pynecone.components.tags.tag import Tag
from pynecone.var import Var


class CondTag(Tag):
    """A conditional tag."""

    # The condition to determine which component to render.
    cond: Var[bool]

    # The code to render if the condition is true.
    true_value: str

    # The code to render if the condition is false.
    false_value: str

    # Whether the cond tag is nested.
    is_nested: bool = False

    def __str__(self) -> str:
        """Render the tag as a React string.

        Returns:
            The React code to render the tag.
        """
        assert self.cond is not None, "The condition must be set."
        return utils.format_cond(
            cond=self.cond.full_name,
            true_value=self.true_value,
            false_value=self.false_value,
            is_nested=self.is_nested,
        )
