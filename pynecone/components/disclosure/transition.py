"""A transition Component."""
from typing import Union

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.utils import imports
from pynecone.vars import ImportVar, Var


class Transition(ChakraComponent):
    """Base componemt of all transitions."""

    in_: Var[bool]

    unmount_on_exit: Var[bool] = False  # type: ignore

    def _get_imports(self) -> imports.ImportDict:
        return imports.merge_imports(
            super()._get_imports(),
            {"@chakra-ui/react": {ImportVar(tag="useDisclosure")}},
        )


class Fade(Transition):
    """Fade component cab be used show and hide content of your app."""

    tag = "Fade"


class ScaleFade(Transition):
    """Fade component can be scaled and reverse your app."""

    tag = "ScaleFade"

    unmount_on_exit: Var[bool] = False  # type: ignore

    initial_scale: Var[float] = 0.95  # type: ignore

    reverse: Var[bool] = True  # type: ignore


class Slide(Transition):
    """Side can be used show content below your app."""

    tag = "Slide"

    direction: Var[str] = "right"  # type: ignore


class SlideFade(Transition):
    """SlideFade component."""

    tag = "SlideFade"

    offsetX: Var[Union[str, int]] = 0  # type: ignore

    offsetY: Var[Union[str, int]] = 8  # type: ignore

    reverse: Var[bool] = True  # type: ignore


class Collapse(Transition):
    """Collapse component can collapse some content."""

    tag = "Collapse"

    animateOpacity: Var[bool] = True  # type: ignore

    endingHeight: Var[str] = "auto"  # type: ignore

    startingHeight: Var[Union[str, int]] = 0  # type: ignore
