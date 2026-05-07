"""Reflex custom component ImageZoom."""

import reflex as rx


class ImageZoom(rx.NoSSRComponent):
    """ImageZoom component."""

    # The React library to wrap.
    library = "react-medium-image-zoom@5.4.2"

    # The React component tag.
    tag = "Zoom"

    # If the tag is the default export from the module, you must set is_default = True.
    is_default = True

    # To add custom code to your component
    def _get_custom_code(self) -> str:
        return "import 'react-medium-image-zoom/dist/styles.css'"


image_zoom = ImageZoom.create
