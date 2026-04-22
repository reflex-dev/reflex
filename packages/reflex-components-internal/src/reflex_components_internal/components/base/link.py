"""Custom link component."""

from typing import Literal

from reflex_components_core.react_router.dom import ReactRouterLink, To

from reflex.vars.base import Var
from reflex_components_internal.components.icons.hugeicon import hi
from reflex_components_internal.utils.twmerge import cn

LiteralLinkVariant = Literal["primary", "secondary"]
LiteralLinkSize = Literal["xs", "sm", "md", "lg", "xl"]


class ClassNames:
    """Class names for the link component."""

    ROOT = "font-medium underline-offset-2 hover:underline w-fit group/link relative"
    ICON = "absolute top-1/2 -translate-y-1/2 right-[-1.25rem] group-hover/link:opacity-100 text-secondary-9 opacity-0"


LINK_VARIANTS: dict[str, dict[str, str]] = {
    "size": {
        "xs": "text-xs",
        "sm": "text-sm",
        "md": "text-md",
        "lg": "text-lg",
        "xl": "text-xl",
    },
    "variant": {
        "primary": "text-primary-11",
        "secondary": "text-secondary-11",
    },
}


class Link(ReactRouterLink):
    """Link component."""

    # The size of the link. Defaults to "sm".
    size: Var[LiteralLinkSize]

    # The variant of the link. Defaults to "secondary".
    variant: Var[LiteralLinkVariant]

    # Whether to show the icon. Defaults to False.
    show_icon: Var[bool]

    # The page to link to.
    to: Var[str | To]

    @classmethod
    def create(cls, *children, **props) -> ReactRouterLink:
        """Create the link component.

        Returns:
            The component.
        """
        size = props.pop("size", "sm")
        cls.validate_size(size)
        variant = props.pop("variant", "secondary")
        cls.validate_variant(variant)
        render_component = props.pop("render_", None)
        show_icon = props.pop("show_icon", False)
        link_class_name = props.get("class_name", "")

        # Get the class name and children from the render component
        if render_component:
            children = list(getattr(render_component, "children", []))
            class_name = cn(
                getattr(render_component, "class_name", ""), link_class_name
            )
        else:
            children = list(children)
            size_class = LINK_VARIANTS["size"][size]
            variant_class = LINK_VARIANTS["variant"][variant]
            class_name = cn(
                f"{ClassNames.ROOT} {size_class} {variant_class}", link_class_name
            )

        if show_icon:
            children.append(hi("LinkSquare02Icon", class_name=ClassNames.ICON))

        props["class_name"] = class_name
        return super().create(*children, **props)

    @staticmethod
    def validate_variant(variant: LiteralLinkVariant):
        """Validate the link variant."""
        if variant not in LINK_VARIANTS["variant"]:
            available_variants = ", ".join(LINK_VARIANTS["variant"].keys())
            message = (
                f"Invalid variant: {variant}. Available variants: {available_variants}"
            )
            raise ValueError(message)

    @staticmethod
    def validate_size(size: LiteralLinkSize):
        """Validate the link size."""
        if size not in LINK_VARIANTS["size"]:
            available_sizes = ", ".join(LINK_VARIANTS["size"].keys())
            message = f"Invalid size: {size}. Available sizes: {available_sizes}"
            raise ValueError(message)

    def _exclude_props(self) -> list[str]:
        return [*super()._exclude_props(), "size", "variant", "show_icon", "render_"]


link = Link.create
