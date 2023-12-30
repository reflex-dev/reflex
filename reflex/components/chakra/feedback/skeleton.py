"""Container to stack elements with spacing."""

from reflex.components.chakra import ChakraComponent
from reflex.vars import Var


class Skeleton(ChakraComponent):
    """Skeleton is used to display the loading state of some components. You can use it as a standalone component. Or to wrap another component to take the same height and width."""

    tag = "Skeleton"

    # The color at the animation end
    end_color: Var[str]

    # The fadeIn duration in seconds
    fade_duration: Var[float]

    # If true, it'll render its children with a nice fade transition
    is_loaded: Var[bool]

    # The animation speed in seconds
    speed: Var[float]

    # The color at the animation start
    start_color: Var[str]


class SkeletonCircle(ChakraComponent):
    """SkeletonCircle is used to display the loading state of some components."""

    tag = "SkeletonCircle"

    # The color at the animation end
    end_color: Var[str]

    # The fadeIn duration in seconds
    fade_duration: Var[float]

    # If true, it'll render its children with a nice fade transition
    is_loaded: Var[bool]

    # The animation speed in seconds
    speed: Var[float]

    # The color at the animation start
    start_color: Var[str]


class SkeletonText(ChakraComponent):
    """SkeletonText is used to display the loading state of some components."""

    tag = "SkeletonText"

    # The color at the animation end
    end_color: Var[str]

    # The fadeIn duration in seconds
    fade_duration: Var[float]

    # If true, it'll render its children with a nice fade transition
    is_loaded: Var[bool]

    # The animation speed in seconds
    speed: Var[float]

    # The color at the animation start
    start_color: Var[str]

    # Number is lines of text.
    no_of_lines: Var[int]
