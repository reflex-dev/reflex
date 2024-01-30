"""A component to indicate progress through a multi-step process."""

from typing import List, Literal, Optional, Tuple

from reflex.components.chakra import ChakraComponent, LiteralColorScheme
from reflex.components.component import Component
from reflex.vars import Var


class Stepper(ChakraComponent):
    """The parent container for a stepper."""

    tag = "Stepper"

    orientation: Var[Literal["vertical", "horizontal"]]

    # The color scheme to use for the stepper; default is blue.
    colorScheme: Var[LiteralColorScheme]

    # Chakra provides a useSteps hook to control the stepper.
    # Instead, use an integer state value to set progress in the stepper.

    # The index of the current step.
    index: Var[int]

    # The size of the steps in the stepper.
    size: Var[str]

    @classmethod
    def create(
        cls, *children, items: Optional[List[Tuple]] = None, **props
    ) -> Component:
        """Create a Stepper component.

        If the kw-args `items` is provided and is a list, they will be added as children.

        Args:
            *children: The children of the component.
            items (list): The child components for each step.
            **props: The properties of the component.

        Returns:
            The stepper component.
        """
        if len(children) == 0:
            children = []
            for indicator, layout, separator in items or []:
                children.append(
                    Step.create(
                        StepIndicator.create(indicator),
                        layout,
                        StepSeparator.create(separator),
                    )
                )
        return super().create(*children, **props)


class Step(ChakraComponent):
    """A component for an individual step in the stepper."""

    tag = "Step"


class StepDescription(ChakraComponent):
    """The description text for a step component."""

    tag = "StepDescription"


class StepIcon(ChakraComponent):
    """The icon displayed in a step indicator component."""

    tag = "StepIcon"


class StepIndicator(ChakraComponent):
    """The component displaying the status of a step."""

    tag = "StepIndicator"


class StepNumber(ChakraComponent):
    """The number of a step displayed in a step indicator component."""

    tag = "StepNumber"


class StepSeparator(ChakraComponent):
    """The component separting steps."""

    tag = "StepSeparator"


class StepStatus(ChakraComponent):
    """A component that displays a number or icon based on the status of a step."""

    # [not working yet]
    # active, complete, and incomplete should also be able to accept StepIcon or StepNumber components
    # currently, these props only support strings

    active: Var[str]

    complete: Var[str]

    incomplete: Var[str]

    tag = "StepStatus"


class StepTitle(ChakraComponent):
    """The title text for a step component."""

    tag = "StepTitle"
