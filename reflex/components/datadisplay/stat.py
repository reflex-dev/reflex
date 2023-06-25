"""Statistics components."""

from reflex.components.component import Component
from reflex.components.libs.chakra import ChakraComponent
from reflex.vars import Var


class Stat(ChakraComponent):
    """The Stat component is used to display some statistics. It can take in a label, a number and a help text."""

    tag = "Stat"

    @classmethod
    def create(
        cls, *children, label=None, number=0, help_text=None, arrow_type=None, **props
    ) -> Component:
        """Create a stat component.

        Args:
            children: The children of the component.
            label: A label for the stat component.
            number: The value of the stat component.
            help_text: A text added to the stat component.
            arrow_type: The type of the arrow ("increase", "decrease", None)
            props: The properties of the component.

        Returns:
            The stat component.
        """
        if len(children) == 0:
            children = []
            if label:
                children.append(StatLabel.create(label))

            children.append(StatNumber.create(number))

            if help_text:
                if arrow_type:
                    children.append(
                        StatHelpText.create(
                            help_text, StatArrow.create(type_=arrow_type)
                        )
                    )
                else:
                    children.append(StatHelpText.create(help_text))

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
