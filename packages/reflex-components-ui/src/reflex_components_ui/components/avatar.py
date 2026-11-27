"""An avatar: an image of a user, and what stands in for it."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import Component, field
from reflex_base.utils.imports import ImportVar
from reflex_base.vars.base import LiteralVar, Var, VarData
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_ui.base import Part, UIComponent
from reflex_components_ui.constants import WEB_DIR
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.avatar import AVATAR
from reflex_components_ui.themes import LiteralAccentColor, LiteralRadius

LiteralSize = Literal["1", "2", "3", "4", "5", "6", "7", "8", "9"]

# The ref of the image: it tells the image and the fallback how the load
# ended, which is all the JavaScript of an avatar.
_WATCH_IMAGE = Var(
    "watchImage",
    _var_data=VarData(
        imports={
            f"$/{WEB_DIR}/behaviors/image-status.js": [ImportVar(tag="watchImage")]
        }
    ),
)

# The part that holds the fallback, by the number of its letters.
_FALLBACK_PARTS = {1: "fallback_one", 2: "fallback_two"}


class AvatarImage(Part, elements.Img):
    """The image of an avatar."""

    tag = "img"


class Avatar(UIComponent):
    """An image element with a fallback for representing the user."""

    tag = "span"

    styles: ClassVar[ComponentStyles] = AVATAR

    variant: Var[Literal["solid", "soft"]] = field(doc="The variant of the avatar")

    size: Var[Responsive[LiteralSize]] = field(doc='The size of the avatar: "1" - "9"')

    color_scheme: Var[LiteralAccentColor] = field(doc="Color theme of the avatar")

    high_contrast: Var[bool] = field(
        doc="Whether to render the avatar with higher contrast color against background"
    )

    radius: Var[LiteralRadius] = field(
        doc='Override theme radius for avatar: "none" | "small" | "medium" | "large" | "full"'
    )

    src: Var[str] = field(doc="The src of the avatar image")

    alt: Var[str] = field(
        doc='Alternative text for the avatar image. Use "" for a decorative image whose name is already shown next to it.'
    )

    fallback: Var[str] = field(doc="The rendered fallback text")

    def _exclude_props(self) -> list[str]:
        """Keep the props that are not attributes of the element off it.

        Returns:
            The props read as styles, and the ones of the image and of the
            fallback inside.
        """
        return [*super()._exclude_props(), "src", "alt", "fallback"]

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create an avatar: the fallback, and the image over it when it has one.

        The fallback shows until the image has loaded, and when it fails. An
        avatar without a ``src`` is its fallback alone, and has no JavaScript.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The avatar.
        """
        fallback = props.get("fallback")
        letters = fallback
        if isinstance(fallback, LiteralVar):
            letters = fallback._var_value
        # The size of the letters follows their number, which only a literal
        # says while compiling: any other fallback has the size around it.
        part = _FALLBACK_PARTS.get(len(letters) if isinstance(letters, str) else 0)
        parts = [
            Part.create(
                *([] if fallback is None else [fallback]),
                part=part or "fallback",
                tag="span",
            )
        ]
        src = props.get("src")
        if src is not None:
            image_props = {"src": src, "custom_attrs": {"ref": _WATCH_IMAGE}}
            if "alt" in props:
                image_props["alt"] = props["alt"]
            parts.append(AvatarImage.create(part="image", **image_props))
        return super().create(*parts, *children, **props)


avatar = Avatar.create
