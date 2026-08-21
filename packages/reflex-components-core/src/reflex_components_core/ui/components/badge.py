"""A badge styled with Tailwind classes on a span element."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from reflex_components_core.el.elements.inline import Span
from reflex_components_core.ui.base import UIComponent
from reflex_components_core.ui.styling import variant_class

LiteralBadgeVariant = Literal["primary", "secondary", "destructive", "outline"]

BADGE_CLASS_NAME = (
    "inline-flex items-center justify-center gap-1 rounded-md border px-2 py-0.5 "
    "text-xs font-medium w-fit whitespace-nowrap shrink-0 overflow-hidden "
    "[&>svg]:size-3 [&>svg]:pointer-events-none "
    "focus-visible:border-ring focus-visible:ring-ring/50 focus-visible:ring-[3px]"
)

BADGE_VARIANTS: dict[str, str] = {
    "primary": "border-transparent bg-primary text-primary-foreground",
    "secondary": "border-transparent bg-secondary text-secondary-foreground",
    "destructive": "border-transparent bg-destructive text-destructive-foreground",
    "outline": "border-border text-foreground",
}


class Badge(Span, UIComponent):
    """A small label for statuses and counts."""

    _slot: ClassVar[str | None] = "badge"

    variant: Var[LiteralBadgeVariant] = field(
        doc='Visual style of the badge. Defaults to "primary".'
    )

    @classmethod
    def create(cls, *children, **props):
        """Create a badge.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The badge component.
        """
        variant = variant_class(
            props.pop("variant", None),
            BADGE_VARIANTS,
            default="primary",
            prop="variant",
            component="rx.ui.badge",
        )
        default_class_name: str | list = (
            f"{BADGE_CLASS_NAME} {variant}"
            if isinstance(variant, str)
            else [BADGE_CLASS_NAME, variant]
        )
        cls._apply_class_name(default_class_name, props)
        return super().create(*children, **props)

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "variant",
        ]


badge = Badge.create
