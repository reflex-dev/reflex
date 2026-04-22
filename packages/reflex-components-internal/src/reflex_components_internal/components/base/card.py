"""Custom card component."""

from reflex_components_core.el.elements.typography import Div

from reflex.components.component import Component, ComponentNamespace
from reflex.vars.base import Var
from reflex_ui.components.component import CoreComponent


class ClassNames:
    """Class names for the card component."""

    ROOT = "rounded-ui-xl border border-secondary-a4 bg-secondary-1 shadow-small"
    HEADER = "flex flex-col px-6 pt-6 pb-4"
    TITLE = "text-2xl font-semibold text-secondary-12"
    DESCRIPTION = "text-sm text-secondary-11 font-[450] mt-4"
    CONTENT = "flex flex-col gap-4 px-6 pb-6"
    FOOTER = "flex flex-row justify-between items-center px-6 pb-6"


class CardComponent(Div, CoreComponent):
    """Base component for the card component."""


class CardRoot(CardComponent):
    """A card component that displays content in a card format."""

    @classmethod
    def create(cls, *children, **props):
        """Create the card component.

        Returns:
            The component.
        """
        props["data-slot"] = "card"
        cls.set_class_name(ClassNames.ROOT, props)
        return super().create(*children, **props)


class CardHeader(CardComponent):
    """A header component for the card."""

    @classmethod
    def create(cls, *children, **props):
        """Create the card header component.

        Returns:
            The component.
        """
        props["data-slot"] = "card-header"
        cls.set_class_name(ClassNames.HEADER, props)
        return super().create(*children, **props)


class CardTitle(CardComponent):
    """A title component for the card."""

    @classmethod
    def create(cls, *children, **props):
        """Create the card title component.

        Returns:
            The component.
        """
        props["data-slot"] = "card-title"
        cls.set_class_name(ClassNames.TITLE, props)
        return super().create(*children, **props)


class CardDescription(CardComponent):
    """A description component for the card."""

    @classmethod
    def create(cls, *children, **props):
        """Create the card description component.

        Returns:
            The component.
        """
        props["data-slot"] = "card-description"
        cls.set_class_name(ClassNames.DESCRIPTION, props)
        return super().create(*children, **props)


class CardContent(CardComponent):
    """A content component for the card."""

    @classmethod
    def create(cls, *children, **props):
        """Create the card content component.

        Returns:
            The component.
        """
        props["data-slot"] = "card-content"
        cls.set_class_name(ClassNames.CONTENT, props)
        return super().create(*children, **props)


class CardFooter(CardComponent):
    """A footer component for the card."""

    @classmethod
    def create(cls, *children, **props):
        """Create the card footer component.

        Returns:
            The component.
        """
        props["data-slot"] = "card-footer"
        cls.set_class_name(ClassNames.FOOTER, props)
        return super().create(*children, **props)


class HighLevelCard(CardComponent):
    """A high level card component that displays content in a card format."""

    # Card props
    title: Var[str | Component | None]
    description: Var[str | Component | None]
    content: Var[str | Component | None]
    footer: Var[str | Component | None]

    @classmethod
    def create(cls, *children, **props):
        """Create the card component.

        Returns:
            The component.
        """
        title = props.pop("title", None)
        description = props.pop("description", None)
        content = props.pop("content", None)
        footer = props.pop("footer", None)

        return CardRoot.create(
            (
                CardHeader.create(
                    CardTitle.create(title) if title is not None else None,
                    (
                        CardDescription.create(description)
                        if description is not None
                        else None
                    ),
                )
                if title or description
                else None
            ),
            CardContent.create(content) if content is not None else None,
            CardFooter.create(footer) if footer is not None else None,
            *children,
            **props,
        )

    def _exclude_props(self) -> list[str]:
        return [
            *super()._exclude_props(),
            "title",
            "description",
            "content",
            "footer",
        ]


class Card(ComponentNamespace):
    """A card component that displays content in a card format."""

    root = staticmethod(CardRoot.create)
    header = staticmethod(CardHeader.create)
    title = staticmethod(CardTitle.create)
    description = staticmethod(CardDescription.create)
    content = staticmethod(CardContent.create)
    footer = staticmethod(CardFooter.create)
    class_names = ClassNames
    __call__ = staticmethod(HighLevelCard.create)


card = Card()
