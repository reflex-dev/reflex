"""A box that keeps the ratio of its width to its height."""

from __future__ import annotations

from typing import ClassVar

from reflex_base.components.component import Component, field
from reflex_base.vars.base import LiteralVar, Var

from reflex_components_ui.base import UIComponent
from reflex_components_ui.style import ComponentStyles
from reflex_components_ui.styles.aspect_ratio import ASPECT_RATIO, ASPECT_RATIO_FRAME


class AspectRatioFrame(UIComponent):
    """The element around the content, whose height follows its width."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = ASPECT_RATIO_FRAME

    @classmethod
    def _display_name(cls) -> str:
        """Get the name an app refers to the component by.

        Returns:
            The name of the component the frame belongs to.
        """
        return "rx.ui.aspect_ratio"


class AspectRatio(UIComponent):
    """Displays content with a desired ratio."""

    tag = "div"

    styles: ClassVar[ComponentStyles] = ASPECT_RATIO

    ratio: Var[float | int] = field(
        doc="The ratio of the width to the height of the element"
    )

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create the content of the box, inside the frame that sizes it.

        Args:
            *children: The children of the component.
            **props: The props of the component, which go to the content.

        Returns:
            The frame.
        """
        ratio = LiteralVar.create(props.get("ratio", 1))
        padding = (
            f"{100 / ratio._var_value}%"
            if isinstance(ratio, LiteralVar)
            else (100 / ratio).to(str) + "%"
        )
        return AspectRatioFrame.create(
            super().create(*children, **props),
            style={"padding_bottom": padding},
            custom_attrs={"data-radix-aspect-ratio-wrapper": ""},
        )

    def _exclude_props(self) -> list[str]:
        """Keep the props that are not attributes off the element.

        Returns:
            The props read as styles, and the ratio.
        """
        return [*super()._exclude_props(), "ratio"]


aspect_ratio = AspectRatio.create
