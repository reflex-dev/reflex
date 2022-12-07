"""Alert components."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Alert(ChakraComponent):
    """An alert feedback box."""

    tag = "Alert"

    # The status of the alert ("success" | "info" | "warning" | "error")
    status: Var[str]

    # "subtle" | "left-accent" | "top-accent" | "solid"
    variant: Var[str]


class AlertIcon(ChakraComponent):
    """An icon displayed in the alert."""

    tag = "AlertIcon"


class AlertTitle(ChakraComponent):
    """The title of the alert."""

    tag = "AlertTitle"


class AlertDescription(ChakraComponent):
    """AlertDescription composes the Box component."""

    tag = "AlertDescription"
