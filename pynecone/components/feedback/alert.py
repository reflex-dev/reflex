"""Alert components."""

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Alert(ChakraComponent):
    """An alert feedback box."""

    tag = "Alert"

    # The status of the alert ("success" | "info" | "warning" | "error")
    status: Var[str]

    # "subtle" | "left-accent" | "top-accent" | "solid"
    variant: Var[str]

    @classmethod
    def create(
        cls, *children, icon=True, title="Alert title", desc=None, **props
    ) -> Component:
        """Create an alert component.

        Args:
            children: The children of the component.
            icon (bool): The icon of the alert.
            title (str): The title of the alert.
            desc (str): The description of the alert
            props: The properties of the component.

        Returns:
            The alert component.
        """
        if len(children) == 0:
            children = []

            if icon:
                children.append(AlertIcon.create())

            children.append(AlertTitle.create(title))

            if desc:
                children.append(AlertDescription.create(desc))

        return super().create(*children, **props)


class AlertIcon(ChakraComponent):
    """An icon displayed in the alert."""

    tag = "AlertIcon"


class AlertTitle(ChakraComponent):
    """The title of the alert."""

    tag = "AlertTitle"


class AlertDescription(ChakraComponent):
    """AlertDescription composes the Box component."""

    tag = "AlertDescription"
