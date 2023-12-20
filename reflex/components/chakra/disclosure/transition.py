"""A transition Component."""
from typing import Union

from reflex.components.chakra import ChakraComponent
from reflex.vars import Var


class Transition(ChakraComponent):
    """Base componemt of all transitions."""

    # Show the component; triggers when enter or exit states
    in_: Var[bool]

    # If true, the element will unmount when `in={false}` and animation is done
    unmount_on_exit: Var[bool]


class Fade(Transition):
    """Fade component cab be used show and hide content of your app."""

    tag = "Fade"


class ScaleFade(Transition):
    """Fade component can be scaled and reverse your app."""

    tag = "ScaleFade"

    # The initial scale of the element
    initial_scale: Var[float]

    # If true, the element will transition back to exit state
    reverse: Var[bool]


class Slide(Transition):
    """Side can be used show content below your app."""

    tag = "Slide"

    # The direction to slide from
    direction: Var[str]


class SlideFade(Transition):
    """SlideFade component."""

    tag = "SlideFade"

    # The offset on the horizontal or x axis
    offsetX: Var[Union[str, int]]

    # The offset on the vertical or y axis
    offsetY: Var[Union[str, int]]

    # If true, the element will be transitioned back to the offset when it leaves. Otherwise, it'll only fade out
    reverse: Var[bool]


class Collapse(Transition):
    """Collapse component can collapse some content."""

    tag = "Collapse"

    # If true, the opacity of the content will be animated
    animateOpacity: Var[bool]

    # The height you want the content in its expanded state.
    endingHeight: Var[str]

    # The height you want the content in its collapsed state.
    startingHeight: Var[Union[str, int]]
