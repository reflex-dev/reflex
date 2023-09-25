from reflex.vars import Var

from ...component import Component


class RadixThemeComponent(Component):
    library = "@radix-ui/themes"

    color: Var[str]

    variant: Var[str]

