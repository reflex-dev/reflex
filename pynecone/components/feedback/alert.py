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
    def create(cls, *children, **props) -> Component:
        """Create an alert component.

        Args:
            children: The children of the component.
            props: The properties of the component.

        Returns:
            The alert component.
        """
        if not children:
            contents = []
            prop_icon = props.pop("icon", True)
            prop_title = props.pop("title", "AlertTitle")
            prop_desc = props.pop("description", None)
            if prop_icon:
                contents.append(AlertIcon.create())
            if prop_title:
                contents.append(AlertTitle.create(prop_title))
            if prop_desc:
                contents.append(AlertDescription.create(prop_desc))

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
