"""Container to stack elements with spacing."""
from typing import Optional

from reflex.components.chakra import ChakraComponent
from reflex.vars import Var


class Skeleton(ChakraComponent):
    """Skeleton is used to display the loading state of some components. You can use it as a standalone component. Or to wrap another component to take the same height and width."""

    tag: str = "Skeleton"

    # The color at the animation end
    end_color: Optional[Var[str]] = None

    # The fadeIn duration in seconds
    fade_duration: Optional[Var[float]] = None

    # If true, it'll render its children with a nice fade transition
    is_loaded: Optional[Var[bool]] = None

    # The animation speed in seconds
    speed: Optional[Var[float]] = None

    # The color at the animation start
    start_color: Optional[Var[str]] = None


class SkeletonCircle(ChakraComponent):
    """SkeletonCircle is used to display the loading state of some components."""

    tag: str = "SkeletonCircle"

    # The color at the animation end
    end_color: Optional[Var[str]] = None

    # The fadeIn duration in seconds
    fade_duration: Optional[Var[float]] = None

    # If true, it'll render its children with a nice fade transition
    is_loaded: Optional[Var[bool]] = None

    # The animation speed in seconds
    speed: Optional[Var[float]] = None

    # The color at the animation start
    start_color: Optional[Var[str]] = None


class SkeletonText(ChakraComponent):
    """SkeletonText is used to display the loading state of some components."""

    tag: str = "SkeletonText"

    # The color at the animation end
    end_color: Optional[Var[str]] = None

    # The fadeIn duration in seconds
    fade_duration: Optional[Var[float]] = None

    # If true, it'll render its children with a nice fade transition
    is_loaded: Optional[Var[bool]] = None

    # The animation speed in seconds
    speed: Optional[Var[float]] = None

    # The color at the animation start
    start_color: Optional[Var[str]] = None

    # Number is lines of text.
    no_of_lines: Optional[Var[int]] = None
