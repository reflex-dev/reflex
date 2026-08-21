"""A separator line between content sections."""

from __future__ import annotations

from typing import ClassVar, Literal

from reflex_base.components.component import field
from reflex_base.vars.base import Var

from reflex_components_core.el.elements.typography import Div
from reflex_components_core.ui.base import UIComponent
from reflex_components_core.ui.styling import variant_class

LiteralSeparatorOrientation = Literal["horizontal", "vertical"]

SEPARATOR_CLASS_NAME = "bg-border shrink-0"

SEPARATOR_ORIENTATIONS: dict[str, str] = {
    "horizontal": "h-px w-full",
    "vertical": "w-px self-stretch",
}


class Separator(Div, UIComponent):
    """A visual divider between content."""

    _slot: ClassVar[str | None] = "separator"

    orientation: Var[LiteralSeparatorOrientation] = field(
        doc='Orientation of the separator. Defaults to "horizontal".'
    )

    @classmethod
    def create(cls, *children, **props):
        """Create a separator.

        Args:
            *children: Unused; separators render no children.
            **props: The props of the component.

        Returns:
            The separator component.
        """
        orientation = props.pop("orientation", None)
        orientation_class = variant_class(
            orientation,
            SEPARATOR_ORIENTATIONS,
            default="horizontal",
            prop="orientation",
            component="rx.ui.separator",
        )
        props.setdefault("role", "none")
        props.setdefault(
            "data_orientation", "horizontal" if orientation is None else orientation
        )
        default_class_name: str | list = (
            f"{SEPARATOR_CLASS_NAME} {orientation_class}"
            if isinstance(orientation_class, str)
            else [SEPARATOR_CLASS_NAME, orientation_class]
        )
        cls._apply_class_name(default_class_name, props)
        return super().create(*children, **props)

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "orientation",
        ]


separator = Separator.create
