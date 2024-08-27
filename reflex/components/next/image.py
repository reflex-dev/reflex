"""Image component from next/image."""

from typing import Any, Literal, Optional, Union

from reflex.event import EventHandler
from reflex.utils import types
from reflex.vars import Var

from pathlib import Path
from constants.base import Dirs

import requests
import os

from .base import NextComponent

# implementing image call back technique here
class Image(NextComponent):
    """Display an image."""

    tag = "Image"
    library = "next/image"
    is_default = True

    # This can be either an absolute external URL, or an internal path
    src: Var[Any]

    # Represents the rendered width in pixels, so it will affect how large the image appears.
    width: Var[Any]

    # Represents the rendered height in pixels, so it will affect how large the image appears.
    height: Var[Any]

    # Used to describe the image for screen readers and search engines.
    alt: Var[str]

    # A custom function used to resolve image URLs.
    loader: Var[Any]

    # A boolean that causes the image to fill the parent element, which is useful when the width and height are unknown. Default to True
    fill: Var[bool]

    # A string, similar to a media query, that provides information about how wide the image will be at different breakpoints.
    sizes: Var[str]

    # The quality of the optimized image, an integer between 1 and 100, where 100 is the best quality and therefore largest file size. Defaults to 75.
    quality: Var[int]

    # When true, the image will be considered high priority and preload. Lazy loading is automatically disabled for images using priority.
    priority: Var[bool]

    # A placeholder to use while the image is loading. Possible values are blur, empty, or data:image/.... Defaults to empty.
    placeholder: Var[str]

    # Allows passing CSS styles to the underlying image element.
    # style: Var[Any]

    # The loading behavior of the image. Defaults to lazy. Can hurt performance, recommended to use `priority` instead.
    loading: Var[Literal["lazy", "eager"]]

    # A Data URL to be used as a placeholder image before the src image successfully loads. Only takes effect when combined with placeholder="blur".
    blurDataURL: Var[str]

    # Fires when the image has loaded.
    on_load: EventHandler[lambda: []]

    # Fires when the image has an error.
    on_error: EventHandler[lambda: []]

    # Fires when the src image is not provided.
    fallback: Var[str]

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

        def validate_src_image(src):
            """
            Validates the 'src' parameter for the Image component.
            Args:
                src: The source parameter (local file path, web URL, or Pillow Image).
            Returns:
                Valid source (src) or raises an error.
            """
            try:
                if isinstance(src, str):
                    if src.startswith("/"):
                        full_path = Path.cwd() / Dirs.APP_ASSETS / src.strip("/")
                        if os.path.exists(full_path):
                            return True
                        else:
                            raise FileNotFoundError(f"Local image not found: {full_path}")
                    elif src.startswith("http"):
                        try:
                            response = requests.head(src)
                            if response.status_code == 200:
                                return True
                            else:
                                raise ValueError(f"Invalid web URL: {src}")
                        except requests.RequestException:
                            raise ValueError(f"Failed to validate web URL: {src}")
                    else:
                        raise ValueError(f"Unsupported src format: {src}")
                elif isinstance(src, Image.Image):
                    return True
                else:
                    raise ValueError(f"Invalid src type: {type(src)}")
            except Exception as e:
                print(f"Error: {e}")
                return False
                                

        def check_prop_type(prop_name, prop_value):
            if types.check_prop_in_allowed_types(prop_value, allowed_types=[int]):
                props[prop_name] = prop_value

            elif types.check_prop_in_allowed_types(prop_value, allowed_types=[str]):
                props[prop_name] = 0
                style[prop_name] = prop_value
            else:
                props[prop_name] = 0
                style[prop_name] = DEFAULT_W_H


        src = props.get("src", "")
        if not validate_src_image(src):
            if props.get("fallback"):
                if validate_src_image(props.get("fallback")):
                    props["src"] = props.get("fallback")
                else:
                    raise ValueError(f"Invalid fallback image: {props.get('fallback')}")
            else:
                raise ValueError(f"Invalid src image: {src}")

        check_prop_type("width", width)
        check_prop_type("height", height)

        props["style"] = style

        # mysteriously, following `sizes` prop is needed to avoid blury images.
        props["sizes"] = "100vw"

        return super().create(*children, **props)
