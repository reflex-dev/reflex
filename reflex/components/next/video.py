"""Wrapping of the next-video component."""

from reflex.components.component import Component
from reflex.vars.base import Var

from .base import NextComponent


class Video(NextComponent):
    """A video component from NextJS."""

    tag = "Video"
    library = "next-video"
    is_default = True
    # the URL
    src: Var[str]

    as_: Component | None

    @classmethod
    def create(cls, *children, **props) -> NextComponent:
        """Create a Video component.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The Video component.
        """
        return super().create(*children, **props)
