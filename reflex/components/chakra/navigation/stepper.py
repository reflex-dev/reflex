"""A component to indicate progress through a multi-step process."""
from typing import List, Literal, Optional, Tuple

from reflex.components.chakra import ChakraComponent, LiteralColorScheme
from reflex.components.component import Component
from reflex.vars import Var


class Stepper(ChakraComponent):
    """The parent container for a stepper."""

    tag: str = "Stepper"

    orientation: Optional[Var[Literal["vertical", "horizontal"]]] = None

    # The color scheme to use for the stepper; default is blue.
    colorScheme: Optional[Var[LiteralColorScheme]] = None

    # Chakra provides a useSteps hook to control the stepper.
    # Instead, use an integer state value to set progress in the stepper.

    # The index of the current step.
    index: Optional[Var[int]] = None

    # The size of the steps in the stepper.
    size: Optional[Var[str]] = None

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

    tag: str = "Step"


class StepDescription(ChakraComponent):
    """The description text for a step component."""

    tag: str = "StepDescription"


class StepIcon(ChakraComponent):
    """The icon displayed in a step indicator component."""

    tag: str = "StepIcon"


class StepIndicator(ChakraComponent):
    """The component displaying the status of a step."""

    tag: str = "StepIndicator"


class StepNumber(ChakraComponent):
    """The number of a step displayed in a step indicator component."""

    tag: str = "StepNumber"


class StepSeparator(ChakraComponent):
    """The component separting steps."""

    tag: str = "StepSeparator"


class StepStatus(ChakraComponent):
    """A component that displays a number or icon based on the status of a step."""

    # [not working yet]
    # active, complete, and incomplete should also be able to accept StepIcon or StepNumber components
    # currently, these props only support strings

    active: Optional[Var[str]] = None

    complete: Optional[Var[str]] = None

    incomplete: Optional[Var[str]] = None

    tag: str = "StepStatus"


class StepTitle(ChakraComponent):
    """The title text for a step component."""

    tag: str = "StepTitle"
