"""Alert components."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Alert(ChakraComponent):
    """Container to stack elements with spacing."""

    tag = "Alert"

    # The status of the alert ("success" | "info" | "warning" | "error")
    status: Var[str]

    # "subtle" | "left-accent" | "top-accent" | "solid"
    variant: Var[str]


class AlertIcon(ChakraComponent):
    """AlertIcon composes Icon and changes the icon based on the status prop."""

    tag = "AlertIcon"


class AlertTitle(ChakraComponent):
    """AlertTitle composes the Box component."""

    tag = "AlertTitle"


class AlertDescription(ChakraComponent):
    """AlertDescription composes the Box component."""

    tag = "AlertDescription"
