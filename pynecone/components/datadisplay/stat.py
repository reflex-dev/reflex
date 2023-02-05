"""Statistics components."""

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.var import Var


class Stat(ChakraComponent):
    """The Stat component is used to display some statistics. It can take in a label, a number and a help text."""

    tag = "Stat"

    @classmethod
    def create(cls, *children, **props) -> Component:
        """Create a stat component

        Args:
            children: The children of the component.
            props: The properties of the component.

        Returns:
            The stat component.
        """
        if not children:
            children = []
            prop_label = props.pop("label", None)
            prop_number = props.pop("number", 0)
            prop_helptext = props.pop("help_text", None)
            prop_arrow_type = props.pop("arrow_type", None)

            if prop_label:
                children.append(StatLabel.create(prop_label))

            children.append(StatNumber.create(prop_number))

            if prop_helptext:
                if prop_arrow_type:
                    children.append(
                        StatHelpText.create(
                            prop_helptext, StatArrow.create(type_=prop_arrow_type)
                        )
                    )
                else:
                    children.append(StatHelpText.create(prop_helptext))

        return super().create(*children, **props)


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
