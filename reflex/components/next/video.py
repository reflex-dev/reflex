"""Wrapping of the next-video component."""

from reflex.components.component import Component
from reflex.utils import console
from reflex.vars.base import Var

from .base import NextComponent


class Video(NextComponent):
    """A video component from NextJS."""

    tag = "Video"
    library = "next-video@2.2.0"
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
        console.deprecate(
            "next-video",
            "The next-video component is deprecated. Use `rx.video` instead.",
            deprecation_version="0.7.11",
            removal_version="0.8.0",
        )
        return super().create(*children, **props)
