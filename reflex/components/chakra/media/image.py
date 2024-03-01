"""An image component."""
from __future__ import annotations

from typing import Any, Optional, Union

from reflex.components.chakra import ChakraComponent, LiteralImageLoading
from reflex.components.component import Component
from reflex.vars import Var


class Image(ChakraComponent):
    """Display an image."""

    tag: str = "Image"
    alias = "ChakraImage"
    # How to align the image within its bounds. It maps to css `object-position` property.
    align: Optional[Var[str]] = None

    # Fallback Reflex component to show if image is loading or image fails.
    fallback: Optional[Component] = None

    # Fallback image src to show if image is loading or image fails.
    fallback_src: Optional[Var[str]] = None

    # How the image to fit within its bounds. It maps to css `object-fit` property.
    fit: Optional[Var[str]] = None

    # The native HTML height attribute to the passed to the img.
    html_height: Optional[Var[str]] = None

    # The native HTML width attribute to the passed to the img.
    html_width: Optional[Var[str]] = None

    # If true, opt out of the fallbackSrc logic and use as img.
    ignore_fallback: Optional[Var[bool]] = None

    # "eager" | "lazy"
    loading: Optional[Var[LiteralImageLoading]] = None

    # The path/url to the image or PIL image object.
    src: Optional[Var[Any]] = None

    # The alt text of the image.
    alt: Optional[Var[str]] = None

    # Provide multiple sources for an image, allowing the browser
    # to select the most appropriate source based on factors like
    # screen resolution and device capabilities.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Learn/HTML/Multimedia_and_embedding/Responsive_images)_
    src_set: Optional[Var[str]] = None

    def get_event_triggers(self) -> dict[str, Union[Var, Any]]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_error": lambda: [],
            "on_load": lambda: [],
        }

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an Image component.

        Args:
            *children: The children of the image.
            **props: The props of the image.

        Returns:
            The Image component.
        """
        src = props.get("src", None)
        if src is not None and not isinstance(src, (Var)):
            props["src"] = Var.create(value=src, _var_is_string=True)
        return super().create(*children, **props)
