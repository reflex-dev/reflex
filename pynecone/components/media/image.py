"""An image component."""
from __future__ import annotations

from typing import Optional, Set

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Image(ChakraComponent):
    """The Image component is used to display images. Image composes Box so you can use all the style props and add responsive styles as well."""

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
    src: Var[str]

    # The image srcset attribute.
    src_set: Var[str]

    @classmethod
    def get_triggers(cls) -> Set[str]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return super().get_triggers() | {"on_error", "on_load"}
