"""An image component."""
from __future__ import annotations

import base64
import io
from typing import Any, Optional

from reflex.components.component import Component
from reflex.components.libs.chakra import ChakraComponent
from reflex.components.tags import Tag
from reflex.utils.serializers import serializer
from reflex.vars import Var


class Image(ChakraComponent):
    """Display an image."""

    tag = "Image"

    # How to align the image within its bounds. It maps to css `object-position` property.
    align: Var[str]

    # Fallback Reflex component to show if image is loading or image fails.
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

    # The path/url to the image or PIL image object.
    src: Var[Any]

    # The alt text of the image.
    alt: Var[str]

    # Provide multiple sources for an image, allowing the browser
    # to select the most appropriate source based on factors like
    # screen resolution and device capabilities.
    # Learn more _[here](https://developer.mozilla.org/en-US/docs/Learn/HTML/Multimedia_and_embedding/Responsive_images)_
    src_set: Var[str]

    def get_triggers(self) -> set[str]:
        """Get the event triggers for the component.

        Returns:
            The event triggers.
        """
        return super().get_triggers() | {"on_error", "on_load"}

    def _render(self) -> Tag:
        self.src.is_string = True

        # Render the table.
        return super()._render()


try:
    from PIL.Image import Image as Img

    @serializer
    def serialize_image(image: Img) -> str:
        """Serialize a plotly figure.

        Args:
            image: The image to serialize.

        Returns:
            The serialized image.
        """
        buff = io.BytesIO()
        image.save(buff, format="PNG")
        image_bytes = buff.getvalue()
        base64_image = base64.b64encode(image_bytes).decode("utf-8")
        return f"data:image/png;base64,{base64_image}"

except ImportError:
    pass
