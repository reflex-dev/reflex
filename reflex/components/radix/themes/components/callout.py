"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

import reflex as rx
from reflex.components.component import Component, ComponentNamespace, field
from reflex.components.core.breakpoints import Responsive
from reflex.components.el import elements
from reflex.components.lucide.icon import Icon
from reflex.components.radix.themes.base import LiteralAccentColor, RadixThemesComponent
from reflex.vars.base import Var

CalloutVariant = Literal["soft", "surface", "outline"]


class CalloutRoot(elements.Div, RadixThemesComponent):
    """Groups Icon and Text parts of a Callout."""

    tag = "Callout.Root"

    as_child: Var[bool] = field(
        doc="Change the default rendered element for the one passed as a child, merging their props and behavior."
    )

    size: Var[Responsive[Literal["1", "2", "3"]]] = field(doc='Size "1" - "3"')

    variant: Var[CalloutVariant] = field(
        doc='Variant of button: "soft" | "surface" | "outline"'
    )

    color_scheme: Var[LiteralAccentColor] = field(doc="Override theme color for button")

    high_contrast: Var[bool] = field(
        doc="Whether to render the button with higher contrast color against background"
    )


class CalloutIcon(elements.Div, RadixThemesComponent):
    """Provides width and height for the icon associated with the callout."""

    tag = "Callout.Icon"


class CalloutText(elements.P, RadixThemesComponent):
    """Renders the callout text. This component is based on the p element."""

    tag = "Callout.Text"


class Callout(CalloutRoot):
    """A short message to attract user's attention."""

    text: Var[str] = field(doc="The text of the callout.")

    icon: Var[str] = field(doc="The icon of the callout.")

    @classmethod
    def create(cls, text: str | Var[str], **props) -> Component:
        """Create a callout component.

        Args:
            text: The text of the callout.
            **props: The properties of the component.

        Returns:
            The callout component.
        """
        return CalloutRoot.create(
            (
                CalloutIcon.create(Icon.create(tag=props["icon"]))
                if "icon" in props
                else rx.fragment()
            ),
            CalloutText.create(text),
            **props,
        )


class CalloutNamespace(ComponentNamespace):
    """Callout components namespace."""

    root = staticmethod(CalloutRoot.create)
    icon = staticmethod(CalloutIcon.create)
    text = staticmethod(CalloutText.create)
    __call__ = staticmethod(Callout.create)


callout = CalloutNamespace()
