"""Badge component."""

from typing import Literal

from reflex_components_core.el.elements.inline import Span

from reflex.vars.base import Var
from reflex_ui.components.component import CoreComponent

BaseColorType = Literal[
    "primary",
    "secondary",
    "info",
    "success",
    "warning",
    "destructive",
    "gray",
    "mauve",
    "slate",
    "sage",
    "olive",
    "sand",
    "tomato",
    "red",
    "ruby",
    "crimson",
    "pink",
    "plum",
    "purple",
    "violet",
    "iris",
    "indigo",
    "blue",
    "cyan",
    "teal",
    "jade",
    "green",
    "grass",
    "brown",
    "orange",
    "sky",
    "mint",
    "lime",
    "yellow",
    "amber",
    "gold",
    "bronze",
]
LiteralBadgeVariant = Literal["solid", "soft"]
LiteralBadgeSize = Literal["xs", "sm", "md"]

DEFAULT_BASE_CLASSES = "inline-flex items-center font-medium [&_svg]:pointer-events-none [&_svg]:shrink-0 gap-1.5"

# Light colors that need dark text on solid backgrounds for better contrast
LIGHT_COLORS = {"sky", "mint", "lime", "yellow", "amber", "secondary"}

BADGE_VARIANTS = {
    "size": {
        "xs": "px-1.5 py-0.5 h-4 rounded-ui-xss text-[11px] [&_svg]:size-3",
        "sm": "px-1.5 py-0.5 h-5 rounded-ui-xs text-xs [&_svg]:size-3.5",
        "md": "px-2 py-0.5 h-6 rounded-ui-sm text-sm [&_svg]:size-4",
    }
}


def get_color_classes(color: str, variant: LiteralBadgeVariant) -> str:
    """Get the color-specific classes based on color and variant.

    Returns:
        The component.
    """
    if variant == "solid":
        text_color = "text-black/90" if color in LIGHT_COLORS else "text-white"
        return f"border-transparent bg-{color}-9 {text_color}"
    # Soft variant
    return f"border-transparent bg-{color}-3 text-{color}-11"


def get_badge_classes(
    color: str, variant: LiteralBadgeVariant, size: LiteralBadgeSize
) -> str:
    """Get the complete badge class string.

    Returns:
        The component.
    """
    color_classes = get_color_classes(color, variant)
    size_classes = BADGE_VARIANTS["size"][size]

    return f"{DEFAULT_BASE_CLASSES} {size_classes} {color_classes}"


class Badge(Span, CoreComponent):
    """A badge component that displays a label."""

    # Badge color
    color: BaseColorType | Var[str]

    # Badge variant
    variant: Var[LiteralBadgeVariant]

    # Badge size
    size: Var[LiteralBadgeSize]

    @classmethod
    def create(cls, *children, **props) -> Span:
        """Create the badge component.

        Returns:
            The component.
        """
        variant = props.pop("variant", "solid")
        color = props.pop("color", "primary")
        size = props.pop("size", "sm")

        cls.set_class_name(get_badge_classes(color, variant, size), props)

        return super().create(*children, **props)

    def _exclude_props(self) -> list[str]:
        return [*super()._exclude_props(), "color", "variant", "size"]


badge = Badge.create
