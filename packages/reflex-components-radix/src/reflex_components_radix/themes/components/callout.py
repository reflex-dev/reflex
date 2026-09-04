"""Interactive components provided by @radix-ui/themes."""

from typing import Literal

from reflex_base.components.component import Component, ComponentNamespace, field
from reflex_base.vars.base import Var
from reflex_components_core.base.fragment import fragment
from reflex_components_core.core.breakpoints import Responsive
from reflex_components_core.el import elements

from reflex_components_radix.themes.base import LiteralAccentColor, RadixThemesComponent

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
        from reflex_components_lucide.icon import Icon

        return CalloutRoot.create(
            (
                CalloutIcon.create(Icon.create(tag=props["icon"]))
                if "icon" in props
                else fragment()
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
