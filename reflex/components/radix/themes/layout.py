from reflex.vars import Var
from .base import RadixThemeComponent


class Box(RadixThemeComponent):
    tag = "Box"

    background_color: Var[str]


class Flex(RadixThemeComponent):
    tag = "Flex"
