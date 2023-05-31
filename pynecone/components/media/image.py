"""An image component."""
from __future__ import annotations

from typing import Any, Optional, Set

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.components.tags import Tag
from pynecone.utils import format, types
from pynecone.vars import Var


class Image(ChakraComponent):
    """Display an image."""

    tag = "Image"

    # How to align the image within its bounds. It maps to css `object-position` property.
    align: Var[str]

    # Fallback Pynecone component to show if image is loading or image fails.
    fallback: Optional[Component] = None

    # Fallback image src to show if image is loading or image fails.
    fallback_src: Var[str]

    # How the image to fit within its bounds. It maps to css `object-fit` property.
    fit: Var[str]

    # The native HTML height attribute to the passed to the img.
    html_height: Var[str]

    # The native HTML width attribute to the passed to the img.
    html_width: Var[str]

    # If true, opt out of the fallbackSrc logic and use as img.
    ignore_fallback: Var[bool]

    # "eager" | "lazy"
    loading: Var[str]

    # The image src attribute.
    src: Var[Any]

    # The image srcset attribute.
    src_set: Var[str]

    def get_triggers(self) -> Set[str]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return super().get_triggers() | {"on_error", "on_load"}

    def _render(self) -> Tag:
        # If the src is an image, convert it to a base64 string.
        if types.is_image(type(self.src)):
            self.src = Var.create(format.format_image_data(self.src))  # type: ignore

        # Render the table.
        return super()._render()
