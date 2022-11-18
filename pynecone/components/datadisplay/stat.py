"""Statistics components."""

from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Stat(ChakraComponent):
    """The Stat component is used to display some statistics. It can take in a label, a number and a help text."""

    tag = "Stat"


class StatLabel(ChakraComponent):
    """A stat label component."""

    tag = "StatLabel"


class StatNumber(ChakraComponent):
    """The stat to display."""

    tag = "StatNumber"


class StatHelpText(ChakraComponent):
    """A helper text to display under the stat."""

    tag = "StatHelpText"


class StatArrow(ChakraComponent):
    """A stat arrow component indicating the direction of change."""

    tag = "StatArrow"

    # The type of arrow, either increase or decrease.
    type_: Var[str]


class StatGroup(ChakraComponent):
    """A stat group component to evenly space out the stats."""

    tag = "StatGroup"
