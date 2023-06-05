"""A component to indicate progress through a multi-step process."""

from typing import Union

from pynecone.components.component import Component
from pynecone.components.libs.chakra import ChakraComponent
from pynecone.vars import Var

class Step(ChakraComponent):
    """A component for an individual step in the stepper."""

    tag = "Step"

    @classmethod
    def create(cls, *children, items=None, **props) -> Component:
        # if len(children) == 0:
        #     children = []
        #     for indicator, layout in items or []:
        #         children.append(
        #             Step.create(StepIndicator.create(), layout)
        #         )
        return super().create(*children, **props)


class StepDescription(ChakraComponent):
    """The description text for a step component."""

    tag = "StepDescription"


class StepIcon(ChakraComponent):
    """The icon displayed in a step indicator component."""

    tag="StepIcon"


class StepIndicator(ChakraComponent):
    """The component displaying the status of a step."""

    tag="StepIndicator"

    @classmethod
    def create(cls, *children, items=None, icon_pos="right", **props) -> Component:
        return super().create(*children, **props)


class StepNumber(ChakraComponent):
    """The number of a step displayed in a step indicator component."""

    tag="StepNumber"


class StepSeparator(ChakraComponent):
    """The component separting steps."""

    tag="StepSeparator"


class StepStatus(ChakraComponent):
    """A component that displays a number or icon based on the status of a step."""

    active: Var[Union[StepNumber, StepIcon]]

    complete: Var[Union[StepNumber, StepIcon]]

    incomplete: Var[Union[StepNumber, StepIcon]]

    tag="StepStatus"


class StepTitle(ChakraComponent):
    """The title text for a step component."""

    tag="StepTitle"


class Stepper(ChakraComponent):
    """The parent container for a stepper."""

    tag = "Stepper"

    # The color scheme to use for the stepper; default is blue
    colorScheme: Var[str]

    # The index of the current step
    index: Var[int]

    # The size of the steps in the stepper
    size: Var[str]

    @classmethod
    def create(cls, *children, items=None, icon_pos="right", **props) -> Component:
        return super().create(*children, **props)
