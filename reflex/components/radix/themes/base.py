from typing import Dict
from reflex.components.tags import Tag

from reflex.vars import Var

from ...component import Component


class RadixThemeComponent(Component):
    library = "@radix-ui/themes"

    color: Var[str]

    variant: Var[str]

    def _render(self) -> Tag:
        # change sx prop to "style"
        return super()._render().remove_props(
            "sx",
        ).add_props(style=self.style)