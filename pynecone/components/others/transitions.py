"""Chakra Transitions Component."""
from typing import Optional

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.vars import Var


class TransitionsFade(ChakraComponent):
    """Wrapper component for Fade transition."""

    tag = "TransitionsFade"


class TransitionsScaleFade(ChakraComponent):
    """Wrapper component for ScaleFade transition."""

    tag = "TransitionsScaleFade"


class TransitionsSlide(ChakraComponent):
    """Wrapper component for Slide transition."""

    tag = "TransitionsSlide"


class TransitionsSlideFade(ChakraComponent):
    """Wrapper component for SlideFade transition."""

    tag = "TransitionsSlideFade"


class TransitionsCollapse(ChakraComponent):
    """Wrapper component for Collapse transition."""

    tag = "TransitionsCollapse"


class Transitions(ChakraComponent):
    """The parent wrapper that provides context for its children with transitions."""

    tag = "Transitions"

    # The visual color appearance of the component.
    # options: "whiteAlpha" | "blackAlpha" | "gray" | "red" | "orange" | "yellow" |
    #  "green" | "teal" | "blue" | "cyan" | "purple" | "pink" | "linkedin" |
    #  "facebook" | "messenger" | "whatsapp" | "twitter" | "telegram"
    # default: "gray"
    color_scheme: Var[str]

    # The size of the Transitions component
    # options: "sm" | "md" | "lg"
    # default: "md"
    size: Var[str]

    @classmethod
    def create(
        cls,
        content: Component,
        *,
        fade: Optional[Component] = None,
        scale_fade: Optional[Component] = None,
        slide: Optional[Component] = None,
        slide_fade: Optional[Component] = None,
        collapse: Optional[Component] = None,
        **props
    ) -> Component:
        """Creates a Chakra Transitions component with content and optional transitions, and returns it.

        Args:
            content (Component): The main content of the Transitions component that will be created.
            fade (Optional[Component]): Should be a Fade instance.
            scale_fade (Optional[Component]): Should be a ScaleFade instance.
            slide (Optional[Component]): Should be a Slide instance.
            slide_fade (Optional[Component]): Should be a SlideFade instance.
            collapse (Optional[Component]): Should be a Collapse instance.
            props: The properties to be passed to the component.

        Returns:
            The `create()` method returns a Transitions object.
        """
        children = [x for x in (content, fade, scale_fade, slide, slide_fade, collapse) if x is not None]
        return super().create(*children, **props)
