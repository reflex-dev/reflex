"""Hugeicons Icon component."""

from reflex.components.component import Component
from reflex.utils.imports import ImportVar
from reflex.vars.base import Var, VarData
from reflex_components_internal.components.component import CoreComponent

REACT_LIBRARY = "@hugeicons/react@1.1.6"
CORE_ICONS_LIBRARY = "@hugeicons/core-free-icons@4.1.1"


class HugeIcon(CoreComponent):
    """A HugeIcon component using HugeiconsIcon from @hugeicons/react."""

    library = REACT_LIBRARY

    tag = "HugeiconsIcon"

    # The main icon to display
    icon: Var[str]

    # Alternative icon for states/interactions
    alt_icon: Var[str | None]

    # Whether to show the alternative icon
    show_alt: Var[bool]

    # The size of the icon in pixels
    size: Var[int | str] = Var.create(16)

    # Icon color (CSS color value)
    color: Var[str]

    # The stroke width of the icon
    stroke_width: Var[float] = Var.create(1.5)

    # When true, stroke width scales relative to icon size
    absolute_stroke_width: Var[bool]

    # Primary color for multicolor icons (Bulk, Duotone, Twotone styles)
    primary_color: Var[str]

    # Secondary color for multicolor icons (Bulk, Duotone, Twotone styles)
    secondary_color: Var[str]

    # Disables the default opacity applied to the secondary color
    disable_secondary_opacity: Var[bool]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Initialize the Icon component.

        Args:
            *children: The positional arguments
            **props: The keyword arguments

        Returns:
            The created component.

        """
        if children and isinstance(children[0], str) and "icon" not in props:
            props["icon"] = children[0]
            children = children[1:]
        for prop in ["icon", "alt_icon"]:
            if prop in props and isinstance(props[prop], str):
                icon_name = props[prop]
                props[prop] = Var(
                    icon_name,
                    _var_data=VarData(
                        imports={
                            CORE_ICONS_LIBRARY: ImportVar(
                                tag=icon_name,
                                is_default=True,
                                package_path=f"/{icon_name}",
                            )
                        }
                    ),
                )
        stroke_width = props.pop("stroke_width", 2)
        cls.set_class_name(f"[&_path]:stroke-[{stroke_width}]", props)

        return super().create(*children, **props)


hi = icon = HugeIcon.create
