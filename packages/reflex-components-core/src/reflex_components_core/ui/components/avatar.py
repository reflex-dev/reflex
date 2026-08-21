"""An avatar built from an image with a text fallback."""

from __future__ import annotations

from typing import ClassVar

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from reflex_components_core.core.cond import cond
from reflex_components_core.el.elements.inline import Span
from reflex_components_core.el.elements.media import Img
from reflex_components_core.ui.base import UIComponent

AVATAR_CLASS_NAME = (
    "relative flex size-8 shrink-0 overflow-hidden rounded-full select-none"
)

AVATAR_IMAGE_CLASS_NAME = "aspect-square size-full object-cover"

AVATAR_FALLBACK_CLASS_NAME = (
    "bg-muted text-muted-foreground flex size-full items-center justify-center "
    "rounded-full text-sm font-medium"
)


class Avatar(Span, UIComponent):
    """A user avatar with an image and a text fallback."""

    _slot: ClassVar[str | None] = "avatar"

    src: Var[str] = field(doc="URL of the avatar image.")

    alt: Var[str] = field(doc="Alternate text for the avatar image.")

    fallback: Var[str] = field(
        doc="Text (typically initials) shown when no image source is set."
    )

    @classmethod
    def create(cls, *children, **props):
        """Create an avatar.

        Args:
            *children: Extra children rendered inside the avatar.
            **props: The props of the component.

        Returns:
            The avatar component.
        """
        src = props.pop("src", None)
        alt = props.pop("alt", None)
        fallback = props.pop("fallback", None)
        cls._apply_class_name(AVATAR_CLASS_NAME, props)

        fallback_child = (
            Span.create(
                fallback,
                data_slot="avatar-fallback",
                class_name=AVATAR_FALLBACK_CLASS_NAME,
            )
            if fallback is not None
            else None
        )
        image_child = (
            Img.create(
                src=src,
                alt=alt,
                data_slot="avatar-image",
                class_name=AVATAR_IMAGE_CLASS_NAME,
            )
            if src is not None
            else None
        )
        if isinstance(src, Var) and fallback_child is not None:
            content = [cond(src, image_child, fallback_child)]
        else:
            content = [
                child
                for child in (image_child if src is not None else fallback_child,)
                if child is not None
            ]
        return super().create(*content, *children, **props)

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "src",
            "alt",
            "fallback",
        ]


avatar = Avatar.create
