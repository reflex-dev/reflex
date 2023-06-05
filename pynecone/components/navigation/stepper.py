"""A component to indicate progress through a multi-step process."""

from typing import Union

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.vars import Var

class Step(ChakraComponent):
    """A component for an individual step in the stepper."""

    tag = "Step"


class StepDescription(ChakraComponent):
    """The description text for a step component."""

    tag = "StepDescription"


class StepIcon(ChakraComponent):
    """The icon displayed in a step indicator component."""

    tag="StepIcon"


class StepIndicator(ChakraComponent):
    """The component displaying the status of a step."""

    tag="StepIndicator"


class StepNumber(ChakraComponent):
    """The number of a step displayed in a step indicator component."""

    tag="StepNumber"


class StepSeparator(ChakraComponent):
    """The component separting steps."""

    tag="StepSeparator"


class StepStatus(ChakraComponent):
    """A component that displays a number or icon based on the status of a step."""

    # [not working yet]
    # active, complete, and incomplete should also be able to accept StepIcon or StepNumber components 
    # currently, these props only support strings 

    active: Var[str]

    complete: Var[str]

    incomplete: Var[str]

    tag="StepStatus"


class StepTitle(ChakraComponent):
    """The title text for a step component."""

    tag="StepTitle"


class Stepper(ChakraComponent):
    """The parent container for a stepper."""

    tag = "Stepper"

    # The color scheme to use for the stepper; default is blue
    colorScheme: Var[str]

    # chakra provides a useSteps hook to control the stepper
    # instead, use an integer state value to set progress in the stepper

    # The index of the current step
    index: Var[int]

    # The size of the steps in the stepper
    size: Var[str]

    @classmethod
    def create(cls, *children, items=None, icon_pos="right", **props) -> Component:
        # implement items shorthand for steps
        if len(children) == 0:
            children = []
            for indicator, layout, separator in items:
                 children.append(
                    Step.create(
                        StepIndicator.create(indicator),
                        layout,
                        StepSeparator.create(separator)
                    )
                 )
        return super().create(*children, **props)
