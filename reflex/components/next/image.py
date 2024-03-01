"""Image component from next/image."""
from typing import Any, Dict, Literal, Optional, Union

from reflex.utils import types
from reflex.vars import Var

from .base import NextComponent


class Image(NextComponent):
    """Display an image."""

    tag: str = "Image"
    library: str = "next/image"
    is_default: bool = True

    # This can be either an absolute external URL, or an internal path
    src: Optional[Var[Any]] = None

    # Represents the rendered width in pixels, so it will affect how large the image appears.
    width: Optional[Var[Any]] = None

    # Represents the rendered height in pixels, so it will affect how large the image appears.
    height: Optional[Var[Any]] = None

    # Used to describe the image for screen readers and search engines.
    alt: Optional[Var[str]] = None

    # A custom function used to resolve image URLs.
    loader: Optional[Var[Any]] = None

    # A boolean that causes the image to fill the parent element, which is useful when the width and height are unknown. Default to True
    fill: Optional[Var[bool]] = None

    # A string, similar to a media query, that provides information about how wide the image will be at different breakpoints.
    sizes: Optional[Var[str]] = None

    # The quality of the optimized image, an integer between 1 and 100, where 100 is the best quality and therefore largest file size. Defaults to 75.
    quality: Optional[Var[int]] = None

    # When true, the image will be considered high priority and preload. Lazy loading is automatically disabled for images using priority.
    priority: Optional[Var[bool]] = None

    # A placeholder to use while the image is loading. Possible values are blur, empty, or data:image/.... Defaults to empty.
    placeholder: Optional[Var[str]] = None

    # Allows passing CSS styles to the underlying image element.
    # style: Optional[Var[Any]] = None

    # The loading behavior of the image. Defaults to lazy. Can hurt performance, recommended to use `priority` instead.
    loading: Optional[Var[Literal["lazy", "eager"]]] = None

    # A Data URL to be used as a placeholder image before the src image successfully loads. Only takes effect when combined with placeholder="blur".
    blurDataURL: Optional[Var[str]] = None

    def get_event_triggers(self) -> Dict[str, Any]:
        """The event triggers of the component.

        Returns:
            The dict describing the event triggers.
        """
        return {
            **super().get_event_triggers(),
            "on_load": lambda: [],
            "on_error": lambda: [],
        }

    @classmethod
    def create(
        cls,
        *children,
        width: Optional[Union[int, str]] = None,
        height: Optional[Union[int, str]] = None,
        **props,
    ):
        """Create an Image component from next/image.

        Args:
            *children: The children of the component.
            width: The width of the image.
            height: The height of the image.
            **props:The props of the component.

        Returns:
            _type_: _description_
        """
        style = props.get("style", {})
        DEFAULT_W_H = "100%"

        def check_prop_type(prop_name, prop_value):
            if types.check_prop_in_allowed_types(prop_value, allowed_types=[int]):
                props[prop_name] = prop_value

            elif types.check_prop_in_allowed_types(prop_value, allowed_types=[str]):
                props[prop_name] = 0
                style[prop_name] = prop_value
            else:
                props[prop_name] = 0
                style[prop_name] = DEFAULT_W_H

        check_prop_type("width", width)
        check_prop_type("height", height)

        props["style"] = style

        # mysteriously, following `sizes` prop is needed to avoid blury images.
        props["sizes"] = "100vw"

        src = props.get("src", None)
        if src is not None and not isinstance(src, (Var)):
            props["src"] = Var.create(value=src, _var_is_string=True)

        return super().create(*children, **props)
