from typing import Dict

from reflex.vars import Var

from ...component import Component


class RadixThemeComponent(Component):
    library = "@radix-ui/themes"

    color: Var[str]

    variant: Var[str]

    def render(self) -> Dict:
        """Render the component.

        Returns:
            The dictionary for template of component.
        """
        rd = super().render()
        # XXX: yucky hacks
        for ix, prop in enumerate(rd.get("props", [])):
            if prop.startswith("sx="):
                rd["props"][ix] = rd["props"][ix].replace("sx=", "style=")
                breakpoint()
                break
        return rd