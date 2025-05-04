"""""Image component from next/image."""

from __future__ import annotations

import reflex as rx
from reflex.components.component import Component
from reflex.components.core.cond import cond
from reflex.event import EventHandler, call_script, no_args_event_spec
from reflex.utils import console, types
from reflex.vars.base import Var, ComponentVar
from .base import NextComponent

DEFAULT_W_H = "100%"


class Image(NextComponent):
    """Display an image."""

    tag = "Image"
    library = "next/image"
    is_default = True

    # This can be either an absolute external URL, or an internal path
    src: Var[str]

    # Represents the rendered width in pixels, so it will affect how large the image appears.
    width: Var[Any]

    # Represents the rendered height in pixels, so it will affect how large the image appears.
    height: Var[Any]

    # Used to describe the image for screen readers and search engines.
    alt: Var[str]

    # A component to render if the image fails to load.
    fallback: ComponentVar | None = None

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
    # style: Var[Any] #noqa: ERA001

    # The loading behavior of the image. Defaults to lazy. Can hurt performance, recommended to use `priority` instead.
    loading: Var[Literal["lazy", "eager"]]

    # A Data URL to be used as a placeholder image before the src image successfully loads. Only takes effect when combined with placeholder="blur".
    blur_data_url: Var[str]

    # Fires when the image has loaded.
    on_load: EventHandler[no_args_event_spec]

    # Fires when the image has an error.
    on_error: EventHandler[no_args_event_spec]

    @classmethod
    def create(
        cls,
        *children,
        width: int | str | None = None,
        height: int | str | None = None,
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
        if "blurDataURL" in props:
            console.deprecate(
                feature_name="blurDataURL",
                reason="Use blur_data_url instead",
                deprecation_version="0.7.0",
                removal_version="0.8.0",
            )
            props["blur_data_url"] = props.pop("blurDataURL")

        style = props.get("style", {})

        def check_prop_type(prop_name: str, prop_value: int | str | None):
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

        return super().create(*children, **props)

    def _get_all_imports(self) -> dict[str, set[str]]:
        """Get all the imports for the component.

        Returns:
            The imports for the component.
        """
        imports = super()._get_all_imports()
        if self.fallback:
            imports.setdefault("react", set()).add("useState")
            fallback_imports = self.fallback.get_imports()
            for lib, fields in fallback_imports.items():
                imports.setdefault(lib, set()).update(fields) # type: ignore
        return imports

    def _get_all_hooks(self) -> str | None:
        """Get all the hooks for the component.

        Returns:
            The hooks for the component.
        """
        hooks = super()._get_all_hooks() or ""
        if self.fallback:
            hooks += "\nconst [image_error, setImageError] = useState(false);" # UseState needs to be added to imports
            fallback_hooks = self.fallback._get_all_hooks()
            if fallback_hooks:
                hooks += f"\n{fallback_hooks}"
        return hooks if hooks else None

    def _get_all_custom_code(self) -> str | None:
        """Get all the custom code for the component.

        Returns:
            The custom code for the component.
        """
        custom_code = super()._get_all_custom_code() or ""
        if self.fallback:
          fallback_custom_code = self.fallback._get_all_custom_code()
          if fallback_custom_code:
            custom_code += f"\n{fallback_custom_code}"
        return custom_code if custom_code else None


    def _get_all_refs(self) -> str | None:
        """Get all the refs for the component.

        Returns:
            The refs for the component.
        """
        refs = super()._get_all_refs() or ""
        if self.fallback:
          fallback_refs = self.fallback._get_all_refs()
          if fallback_refs:
            refs += f"\n{fallback_refs}"
        return refs if refs else None

    def _render(self):
        if self.fallback:
            # Define the onError event handler
            on_error_handler = call_script("setImageError(true)")

            # Prepare the props for the original image tag
            tag = super()._render()

            # Add our onError handler, overwriting any user-provided one for fallback logic
            tag.props["onError"] = on_error_handler

            # Render the fallback component
            rendered_fallback = self.fallback.render()

            # Return the conditional rendering structure
            return cond(Var.create("image_error", _var_is_string=False), rendered_fallback, tag)
        else:
            # Original behavior if no fallback is provided
            return super()._render()


