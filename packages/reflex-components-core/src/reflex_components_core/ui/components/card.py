"""A card container with header, content, and footer sections."""

from __future__ import annotations

from typing import ClassVar

from reflex_base.components.component import ComponentNamespace

from reflex_components_core.el.elements.typography import Div
from reflex_components_core.ui.base import UIComponent


class CardComponent(Div, UIComponent):
    """Base class for card parts."""

    # The default Tailwind classes for this card part.
    _default_class_name: ClassVar[str] = ""

    @classmethod
    def create(cls, *children, **props):
        """Create a card part.

        Args:
            *children: The children of the component.
            **props: The props of the component.

        Returns:
            The card part component.
        """
        cls._apply_class_name(cls._default_class_name, props)
        return super().create(*children, **props)


class Card(CardComponent):
    """A bordered container grouping related content."""

    _slot: ClassVar[str | None] = "card"
    _default_class_name: ClassVar[str] = (
        "bg-card text-card-foreground flex flex-col gap-6 rounded-xl "
        "border border-border py-6 shadow-sm"
    )


class CardHeader(CardComponent):
    """The header section of a card."""

    _slot: ClassVar[str | None] = "card-header"
    _default_class_name: ClassVar[str] = "flex flex-col gap-1.5 px-6"


class CardTitle(CardComponent):
    """The title of a card."""

    _slot: ClassVar[str | None] = "card-title"
    _default_class_name: ClassVar[str] = "leading-none font-semibold"


class CardDescription(CardComponent):
    """The description of a card."""

    _slot: ClassVar[str | None] = "card-description"
    _default_class_name: ClassVar[str] = "text-muted-foreground text-sm"


class CardContent(CardComponent):
    """The main content section of a card."""

    _slot: ClassVar[str | None] = "card-content"
    _default_class_name: ClassVar[str] = "px-6"


class CardFooter(CardComponent):
    """The footer section of a card."""

    _slot: ClassVar[str | None] = "card-footer"
    _default_class_name: ClassVar[str] = "flex items-center px-6"


class CardNamespace(ComponentNamespace):
    """Namespace for card components."""

    root = staticmethod(Card.create)
    header = staticmethod(CardHeader.create)
    title = staticmethod(CardTitle.create)
    description = staticmethod(CardDescription.create)
    content = staticmethod(CardContent.create)
    footer = staticmethod(CardFooter.create)
    __call__ = staticmethod(Card.create)


card = CardNamespace()
